// K파일 구조화 메타 추출 — 파트별 자유표면적/부피/정사영·재료(모델+DB)·접촉 connectivity JSON
//
// 출력 <output>_modelmeta.json 구조:
//   model: {file, nodes, elements, parts, bbox}
//   parts: [{pid, title, elem_class, n_elems, bbox, area_ext, volume,
//            proj: {x,y,z}, material: {mid, kfile:{...}, db:{...}, match_basis}}]
//   connectivity: {contact_edges: [{a,b,a_title,b_title,contact,type,title,fs}],
//                  single_surface: [...], geometric_edges (detect: true)}
//
// 관례:
//   - 솔리드 파트: 자유면(공유 1회 면) 기준 외부 표면적, 정사영 = sum(area*|n·e|)/2
//     (닫힌 표면 왕복 상쇄). 부피 = 면-중심 피라미드 분해(와인딩 무관 |dot| 합).
//   - 쉘 파트: 요소면 단면 기준(단측), 정사영 /2 없음, 부피 0.
#include "parser/IncludeClosure.h"   // 인클루드 닫힘 — 정본
#include "modelmeta.h"
#include "contact_helpers.h"
#include "cli/ConsoleOutput.h"
#include "parser/KFileReader.h"
#include "core/Mesh.h"
#include "core/Element.h"
#include "util/FigureSvg.h"      // secondOrderSolidPids — 세 그림 op 과 **같은 판정**
#include "util/YamlComment.h"

#include <algorithm>
#include <array>
#include <cctype>
#include <cmath>
#include <cstdio>
#include <fstream>
#include <map>
#include <set>
#include <sstream>
#include <string>
#include <vector>

#ifdef __linux__
#include <unistd.h>
#include <limits.h>
#endif

using KooRemapper::ConsoleOutput;

namespace {

// ── 소도구 ───────────────────────────────────────────────────────────────────

std::string mm_trim(const std::string& s) {
    size_t a = s.find_first_not_of(" \t\r\n");
    if (a == std::string::npos) return "";
    size_t b = s.find_last_not_of(" \t\r\n");
    return s.substr(a, b - a + 1);
}

std::string mm_lower(std::string s) {
    for (char& c : s) c = static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
    return s;
}

std::string mm_unquote(const std::string& s) {
    if (s.size() >= 2 && ((s.front() == '"' && s.back() == '"') ||
                          (s.front() == '\'' && s.back() == '\'')))
        return s.substr(1, s.size() - 2);
    return s;
}

bool mm_toBool(const std::string& v) {
    std::string s = mm_lower(v);
    return s == "true" || s == "yes" || s == "on" || s == "1";
}

std::string mm_jsonEsc(const std::string& s) {
    std::string out;
    out.reserve(s.size() + 8);
    for (char c : s) {
        switch (c) {
            case '"':  out += "\\\""; break;
            case '\\': out += "\\\\"; break;
            case '\n': out += "\\n"; break;
            case '\r': break;
            case '\t': out += "\\t"; break;
            default:
                if (static_cast<unsigned char>(c) < 0x20) { /* skip control */ }
                else out += c;
        }
    }
    return out;
}

std::string mm_dirOf(const std::string& path) {
    size_t p = path.find_last_of("/\\");
    return (p == std::string::npos) ? std::string(".") : path.substr(0, p);
}

// ── 설정 ─────────────────────────────────────────────────────────────────────

struct MmConfig {
    std::string model;
    std::string output;        // 접두 (기본: model 확장자 제거)
    bool detect = false;       // 기하학적 접촉쌍 탐지 병기
    double gapTol = 0.1;
    double normalAngleDeg = 45.0;
    std::string materialDb;    // 비우면 exe 옆 materials/material_db.json 시도
    bool dbMidFallback = false; // MID 일치 폴백 — 로컬 MID가 DB 번호와 우연 충돌하므로 opt-in
    int maxEdges = 2000;       // connectivity 폭주 상한
};

bool mm_parseConfig(const std::string& path, MmConfig& cfg, ConsoleOutput& console) {
    std::ifstream f(path);
    if (!f.is_open()) {
        console.error("[modelmeta] Cannot open config: " + path);
        return false;
    }
    KooRemapper::yamlSkipBOM(f);   // 윈도우 편집기가 붙인 BOM 이 첫 키를 망가뜨렸다
    std::string line;
    while (std::getline(f, line)) {
        std::string s = mm_trim(line);
        if (s.empty() || s[0] == '#') continue;
        size_t c = s.find(':');
        if (c == std::string::npos) continue;
        std::string key = mm_trim(s.substr(0, c));
        // 예전엔 값 어디에 있든 따옴표 한 짝에 상태가 뒤집혀("it's_meta   # note" 의 ') 주석이 값에 남았고,
        // 공백 없이 붙은 #('run#2.k')도 잘랐다
        std::string val = mm_unquote(mm_trim(KooRemapper::yamlStripComment(s.substr(c + 1))));
        if (key == "model") cfg.model = val;
        else if (key == "output") cfg.output = val;
        else if (key == "detect") cfg.detect = mm_toBool(val);
        else if (key == "gap_tol") cfg.gapTol = std::atof(val.c_str());
        else if (key == "normal_angle") cfg.normalAngleDeg = std::atof(val.c_str());
        else if (key == "material_db") cfg.materialDb = val;
        else if (key == "db_mid_fallback") cfg.dbMidFallback = mm_toBool(val);
        else if (key == "max_edges") cfg.maxEdges = std::atoi(val.c_str());
    }
    if (cfg.model.empty()) {
        console.error("[modelmeta] 'model' is required");
        return false;
    }
    // 상대경로는 config 기준으로 해석 (matdb 관례)
    std::string base = mm_dirOf(path);
    auto resolve = [&](std::string& p) {
        if (!p.empty() && p[0] != '/' && !(p.size() > 1 && p[1] == ':'))
            p = base + "/" + p;
    };
    resolve(cfg.model);
    if (!cfg.materialDb.empty()) resolve(cfg.materialDb);
    if (cfg.output.empty()) {
        std::string m = cfg.model;
        size_t dot = m.find_last_of('.');
        cfg.output = (dot == std::string::npos) ? m : m.substr(0, dot);
    } else {
        resolve(cfg.output);
    }
    return true;
}

// ── 원시 라인 수집 — 인클루드 닫힘을 LS-DYNA 가 읽는 차례대로 펼친다 ─────────────────
//
// ⚠ 예전 구현은 **한 단계만** 따라가고 `*INCLUDE_*` 를 전부 맨 `*INCLUDE` 처럼 읽었다 —
//   `*INCLUDE_PATH` 의 디렉터리 이름을 파일로 열려 하고(조용히 실패), `*INCLUDE_TRANSFORM` 파일을
//   **ID 오프셋 없이** 읽어 그 안의 PID·MID·SID 를 그럴듯하게 틀린 값으로 셌다(이 산출은 DataHub
//   적재로 나간다). 인클루드 파일의 `*END` 뒤까지 읽었고, 못 연 파일은 말하지 않았다.
//   지금은 정본(`include_closure`)을 쓴다 — 중첩 · 파일별 `*END` · 주 덱 폴더 기준 ·
//   맨 `*INCLUDE` 가 아닌 것은 **따라가지 않고** `blind` 로 돌려준다(호출자가 경고한다).
struct MmLines {
    std::vector<std::string> lines;      // 펼친 줄
    std::vector<std::string> blind;      // 못 본 인클루드 — 사람이 읽을 문장
};

MmLines mm_collectLines(const std::string& modelPath) {
    MmLines out;
    std::vector<std::string> mainLines;
    std::ifstream f(modelPath);
    if (!f.is_open()) return out;
    std::string line;
    while (std::getline(f, line)) mainLines.push_back(line);
    const auto c = KooRemapper::include_closure::read(modelPath, mainLines);
    out.lines = KooRemapper::include_closure::flatten(mainLines, modelPath, c);
    for (const auto& u : c.unresolved)
        out.blind.push_back(u.file + ":" + std::to_string(u.line) + " 의 *INCLUDE '" + u.name + "' — " + u.why);
    for (const auto& n : c.notFollowed)
        out.blind.push_back(n.file + ":" + std::to_string(n.line) + " 의 " + n.keyword +
                            (n.name.empty() ? "" : " '" + n.name + "'") + " — 따라가지 않았다(ID 오프셋 등)");
    if (c.depthCut) out.blind.push_back("인클루드 깊이 상한에 걸려 더 따라가지 않았다");
    return out;
}

// ── 기하 ─────────────────────────────────────────────────────────────────────

struct V3 { double x = 0, y = 0, z = 0; };

V3 mm_sub(const V3& a, const V3& b) { return {a.x - b.x, a.y - b.y, a.z - b.z}; }
V3 mm_cross(const V3& a, const V3& b) {
    return {a.y * b.z - a.z * b.y, a.z * b.x - a.x * b.z, a.x * b.y - a.y * b.x};
}
double mm_dot(const V3& a, const V3& b) { return a.x * b.x + a.y * b.y + a.z * b.z; }

bool mm_nodePos(const KooRemapper::Mesh& mesh, int nid, V3& out) {
    const auto* nd = mesh.getNode(nid);
    if (!nd) return false;
    out = {nd->position.x, nd->position.y, nd->position.z};
    return true;
}

// 면(tri/quad)을 삼각형으로 분해해 (면적벡터 합, 중심) 반환. 면적 = |면적벡터 합| 아님에
// 주의 — 평면 면에서만 일치. 면적 스칼라는 삼각형 면적 합으로 별도 계산한다.
struct MmFaceGeom {
    double area = 0;      // 삼각형 면적 합
    V3 areaVec;           // 면적벡터(방향 포함) 합
    V3 centroid;
    int nVerts = 0;
};

bool mm_faceGeom(const KooRemapper::Mesh& mesh, const std::array<int, 4>& f, MmFaceGeom& out) {
    bool isTri = (f[3] == f[2] || f[3] == 0);
    int n = isTri ? 3 : 4;
    V3 v[4];
    for (int k = 0; k < n; ++k)
        if (!mm_nodePos(mesh, f[k], v[k])) return false;
    // 중복 노드로 실질 삼각형/선분인 quad 처리: 삼각형 분해가 자연 흡수(면적 0)
    out = MmFaceGeom{};
    out.nVerts = n;
    for (int k = 0; k < n; ++k) {
        out.centroid.x += v[k].x; out.centroid.y += v[k].y; out.centroid.z += v[k].z;
    }
    out.centroid.x /= n; out.centroid.y /= n; out.centroid.z /= n;
    int ntri = (n == 3) ? 1 : 2;
    for (int t = 0; t < ntri; ++t) {
        const V3& a = v[0];
        const V3& b = v[t + 1];
        const V3& c = v[t + 2];
        V3 av = mm_cross(mm_sub(b, a), mm_sub(c, a));
        out.areaVec.x += 0.5 * av.x; out.areaVec.y += 0.5 * av.y; out.areaVec.z += 0.5 * av.z;
        out.area += 0.5 * std::sqrt(mm_dot(av, av));
    }
    return true;
}

// 요소 부피 — 셀 중심 피라미드 분해(각 삼각형 피라미드 |부호부피| 합; 와인딩 무관).
// HEX8/PENTA6/TET4/HEX20/TET10(코너 절점) 공통.
//
// ★사변형 면은 **면중심 4분할**로 쪼갠다 — `v0-v2` 대각 2분할이 아니다.
//
// 왜 (실측 2026-10-06). 대각 2분할은 **면 표의 시작 꼭짓점에 값이 매달린다** — 비평면 면에서
// 어느 대각으로 자르느냐로 부피가 달라진다. 그래서 위상 표를 손댈 때마다 이 숫자가 흔들렸다
// (실제로 한 번 흔들려 `examples/bendtwist/bendtwist_bent.k` 가 31200.37 → 31995.26 이 됐다).
// 면중심 4분할은 **시작점과 무관**하고, 게다가 삼선형 육면체의 **정확한** 부피가 된다.
//
//   같은 덱 250 요소 · 8점 가우스 적분을 참값으로 두고 재면
//     대각 2분할   31200.367738   오차 **+0.1338 %**
//     면중심 4분할 31158.686789   오차 **-0.0000 %**   ← 참값과 같다
//     시작점을 돌려도 31158.686789 로 **같다**
double mm_elementVolume(const KooRemapper::Mesh& mesh, const KooRemapper::Element& elem) {
    // 셀 중심
    V3 cc; int nc = 0;
    std::set<int> seen;
    for (int nid : elem.nodeIds) {
        if (nid == 0 || seen.count(nid)) continue;
        seen.insert(nid);
        V3 p;
        if (!mm_nodePos(mesh, nid, p)) return 0;
        cc.x += p.x; cc.y += p.y; cc.z += p.z; ++nc;
    }
    if (nc < 4) return 0;
    cc.x /= nc; cc.y /= nc; cc.z /= nc;

    double vol = 0;
    for (int fi : elem.getValidFaceIndices()) {
        auto f = elem.getFaceNodeIds(fi);
        bool isTri = (f[3] == f[2] || f[3] == 0);
        int n = isTri ? 3 : 4;
        V3 v[4];
        bool ok = true;
        for (int k = 0; k < n; ++k)
            if (!mm_nodePos(mesh, f[k], v[k])) { ok = false; break; }
        if (!ok) continue;
        if (n == 3) {
            V3 a = mm_sub(v[0], cc), b = mm_sub(v[1], cc), c = mm_sub(v[2], cc);
            vol += std::fabs(mm_dot(mm_cross(a, b), c)) / 6.0;
        } else {
            const V3 fc = {(v[0].x + v[1].x + v[2].x + v[3].x) / 4.0,
                           (v[0].y + v[1].y + v[2].y + v[3].y) / 4.0,
                           (v[0].z + v[1].z + v[2].z + v[3].z) / 4.0};
            const V3 h = mm_sub(fc, cc);
            for (int k = 0; k < 4; ++k) {
                V3 a = mm_sub(v[k], cc), b = mm_sub(v[(k + 1) % 4], cc);
                vol += std::fabs(mm_dot(mm_cross(a, b), h)) / 6.0;
            }
        }
    }
    return vol;
}

// ── 재료 메타 ────────────────────────────────────────────────────────────────

struct MmMatKfile {
    std::string keyword;   // *MAT_... 키워드 (raw 스캔)
    std::string title;     // *MAT_..._TITLE 제목
    // KFileReader 구조 파싱 (5종만)
    bool parsed = false;
    double E = 0, nu = 0, rho = 0, sigy = 0;
};

// raw 라인에서 *MAT_ 키워드별 MID→{keyword,title} 수집
std::map<int, MmMatKfile> mm_scanMatCards(const std::vector<std::string>& lines) {
    std::map<int, MmMatKfile> out;
    for (size_t i = 0; i < lines.size(); ++i) {
        std::string s = mm_trim(lines[i]);
        if (s.empty() || s[0] != '*') continue;
        std::string up = mm_lower(s);
        if (up.rfind("*mat_", 0) != 0) continue;
        if (up.rfind("*mat_add", 0) == 0 || up.rfind("*mat_thermal", 0) == 0) continue;
        bool hasTitle = up.size() >= 6 && up.substr(up.size() - 6) == "_title";
        std::string kw = s;
        std::string title;
        size_t j = i + 1;
        // 원시 라인을 반환한다 — trim 하면 고정폭(10칸) 컬럼이 파괴됨.
        auto nextData = [&]() -> std::string {
            while (j < lines.size()) {
                const std::string& raw = lines[j];
                std::string t = mm_trim(raw);
                ++j;
                if (t.empty() || t[0] == '$') continue;
                if (t[0] == '*') return "";
                return raw;
            }
            return "";
        };
        if (hasTitle) title = mm_trim(nextData());
        std::string data = nextData();
        if (data.empty()) continue;
        // MID 파싱 — 자유형식이면 첫 토큰이 순수 정수, 고정폭이면 rho와 붙어
        // "18.36E-09"처럼 보이므로(cclip 하드닝 전례) 토큰이 정수가 아니면 10칸 고정폭.
        long mid = 0;
        {
            std::istringstream iss(data);
            std::string tok;
            iss >> tok;
            bool pureInt = !tok.empty();
            for (char ch : tok)
                if (!std::isdigit(static_cast<unsigned char>(ch))) { pureInt = false; break; }
            if (pureInt) {
                mid = std::atol(tok.c_str());
            } else {
                try { mid = std::stol(data.substr(0, std::min<size_t>(10, data.size()))); }
                catch (...) { continue; }
            }
        }
        if (mid <= 0) continue;
        auto& e = out[static_cast<int>(mid)];
        e.keyword = kw;
        if (!title.empty()) e.title = title;
    }
    return out;
}

struct MmMatDb {
    bool found = false;
    std::string basis;     // "name" | "mid"
    int dbMid = 0;
    std::string name, tag, category, matType;
    double E_GPa = 0, rho_g_cm3 = 0, PR = 0;
};

// material_db.json에서 "N": { ... } 블록 텍스트 스캔 (matdb list 전례 재사용 패턴)
struct MmDbEntry {
    int mid = 0;
    std::string name, tag, category, matType;
    double E_GPa = 0, rho_g_cm3 = 0, PR = 0;
};

std::vector<MmDbEntry> mm_loadDb(const std::string& path) {
    std::vector<MmDbEntry> out;
    std::ifstream f(path);
    if (!f.is_open()) return out;
    std::stringstream ss;
    ss << f.rdbuf();
    std::string content = ss.str();
    size_t pos = content.find("\"materials\"");
    if (pos == std::string::npos) return out;

    auto findStr = [&](size_t from, size_t limit, const std::string& key) -> std::string {
        std::string pat = "\"" + key + "\"";
        size_t p = content.find(pat, from);
        if (p == std::string::npos || p > limit) return "";
        p = content.find(':', p);
        if (p == std::string::npos) return "";
        p = content.find('"', p + 1);
        if (p == std::string::npos || p > limit) return "";
        size_t e = content.find('"', p + 1);
        if (e == std::string::npos) return "";
        return content.substr(p + 1, e - p - 1);
    };
    auto findNum = [&](size_t from, size_t limit, const std::string& key) -> double {
        std::string pat = "\"" + key + "\"";
        size_t p = content.find(pat, from);
        if (p == std::string::npos || p > limit) return 0;
        p = content.find(':', p);
        if (p == std::string::npos) return 0;
        return std::atof(content.c_str() + p + 1);
    };

    size_t search = pos;
    while (true) {
        size_t q1 = content.find('"', search);
        if (q1 == std::string::npos) break;
        size_t q2 = content.find('"', q1 + 1);
        if (q2 == std::string::npos) break;
        std::string midStr = content.substr(q1 + 1, q2 - q1 - 1);
        search = q2 + 1;
        bool isNum = !midStr.empty();
        for (char c : midStr) if (!std::isdigit(static_cast<unsigned char>(c))) { isNum = false; break; }
        if (!isNum) continue;
        size_t col = content.find_first_not_of(" \t\n\r", search);
        if (col == std::string::npos || content[col] != ':') continue;
        size_t brace = content.find('{', col);
        if (brace == std::string::npos) continue;
        size_t limit = brace + 6000;   // 엔트리 스캔 범위 (matdb 전례 5000 유사)

        MmDbEntry e;
        e.mid = std::atoi(midStr.c_str());
        e.name = findStr(brace, limit, "name");
        e.tag = findStr(brace, limit, "tag");
        e.category = findStr(brace, limit, "category");
        e.matType = findStr(brace, limit, "mat_type");
        e.E_GPa = findNum(brace, limit, "E_GPa");
        e.rho_g_cm3 = findNum(brace, limit, "rho_g_cm3");
        e.PR = findNum(brace, limit, "PR");
        if (e.mid > 0 && (!e.name.empty() || !e.tag.empty())) out.push_back(e);
    }
    return out;
}

// 엄격 부분일치 — 짧은 이름("PL")의 우연 매칭 방지: 완전일치는 무제한,
// 부분일치는 포함되는 쪽 길이 ≥ 4 요구.
bool mm_nameHit(const std::string& title, const std::string& dbKey) {
    if (title.empty() || dbKey.empty()) return false;
    if (title == dbKey) return true;
    if (dbKey.size() >= 4 && title.find(dbKey) != std::string::npos) return true;
    if (title.size() >= 4 && dbKey.find(title) != std::string::npos) return true;
    return false;
}

// 매칭 우선순위: 재료 카드 제목(name-mat) > 파트 제목(name-part) > MID 일치(mid).
// basis 를 함께 보고해 신뢰도를 소비측에서 판단할 수 있게 한다.
MmMatDb mm_matchDb(const std::vector<MmDbEntry>& db, int mid,
                   const std::string& matTitle, const std::string& partTitle,
                   bool midFallback) {
    MmMatDb r;
    auto fill = [&](const MmDbEntry& e, const std::string& basis) {
        r.found = true; r.basis = basis;
        r.dbMid = e.mid; r.name = e.name; r.tag = e.tag;
        r.category = e.category; r.matType = e.matType;
        r.E_GPa = e.E_GPa; r.rho_g_cm3 = e.rho_g_cm3; r.PR = e.PR;
    };
    const std::string tm = mm_lower(mm_trim(matTitle));
    const std::string tp = mm_lower(mm_trim(partTitle));
    for (const auto& e : db) {
        if (mm_nameHit(tm, mm_lower(e.name)) || mm_nameHit(tm, mm_lower(e.tag))) {
            fill(e, "name-mat");
            return r;
        }
    }
    for (const auto& e : db) {
        if (mm_nameHit(tp, mm_lower(e.name)) || mm_nameHit(tp, mm_lower(e.tag))) {
            fill(e, "name-part");
            return r;
        }
    }
    if (midFallback) {
        for (const auto& e : db) {
            if (e.mid == mid) { fill(e, "mid"); return r; }
        }
    }
    return r;
}

std::string mm_defaultDbPath() {
#ifdef __linux__
    char buf[PATH_MAX];
    ssize_t n = readlink("/proc/self/exe", buf, sizeof(buf) - 1);
    if (n > 0) {
        buf[n] = '\0';
        std::string exeDir = mm_dirOf(buf);
        std::string cand = exeDir + "/materials/material_db.json";
        if (std::ifstream(cand).good()) return cand;
        cand = exeDir + "/../materials/material_db.json";
        if (std::ifstream(cand).good()) return cand;
    }
#endif
    if (std::ifstream("materials/material_db.json").good())
        return "materials/material_db.json";
    return "";
}

// ── connectivity ─────────────────────────────────────────────────────────────

struct MmEdge {
    int a = 0, b = 0;
    int contactIndex = 0;
    std::string type, title;
    double fs = 0;
};

struct MmSingleSurface {
    int contactIndex = 0;
    std::string type, title;
    std::vector<int> pids;   // 적용 범위 (빈 목록 = 전 파트)
};

// SSID/MSID(+STYP)를 PID 목록으로 해석. SET_NODE/SET_SEGMENT는 노드→소유 파트로 환원.
// 세트는 정본 해석기(`set_members.h`)로 푼다 — `_ADD`·`_INTERSECT`·`_COLLECT` 를 따라가고, 못 풀면
// `resolved=false` 와 까닭(`why`)을 돌려준다. ⚠ 예전엔 `SetDef::ids` 를 직접 읽어 `*SET_PART_ADD` 를
// 가리키는 접촉이 **0쌍 · 미해석 0** 으로 사라졌다(파서가 세트 ID 멤버를 일부러 비워 두기 때문이다).
std::vector<int> mm_resolveSide(int sid, int styp,
                                const std::vector<SetDef>& sets,
                                const std::map<int, std::set<int>>& nodeOwners,
                                const std::vector<int>& allPids,
                                bool& resolved, std::string& why) {
    resolved = true;
    why.clear();
    std::vector<int> pids;
    auto addNodePids = [&](const std::vector<int>& nids) {
        std::set<int> acc;
        for (int nid : nids) {
            auto it = nodeOwners.find(nid);
            if (it != nodeOwners.end()) acc.insert(it->second.begin(), it->second.end());
        }
        pids.assign(acc.begin(), acc.end());
    };
    if (styp == 3) { pids.push_back(sid); return pids; }
    if (styp == 5) return allPids;
    const char* type = (styp == 2) ? "PART" : (styp == 4) ? "NODE" : (styp == 0) ? "SEGMENT" : nullptr;
    if (!type) {
        resolved = false;
        why = "STYP=" + std::to_string(styp) + " 는 파트로 풀지 않는다";
        return pids;
    }
    const SetMembers m = ct_setMembers(sets, sid, type);
    if (!m.resolved) {
        resolved = false;
        why = m.why;
        return pids;
    }
    if (styp == 2) {
        pids = m.ids;
    } else if (styp == 4) {
        addNodePids(m.ids);
    } else {   // SET_SEGMENT
        std::vector<int> nids;
        for (const auto& seg : m.segments)
            for (int nid : seg) if (nid > 0) nids.push_back(nid);
        addNodePids(nids);
    }
    return pids;
}

}  // namespace

// ── 메인 ─────────────────────────────────────────────────────────────────────

int runModelmeta(const std::string& yamlFile, ConsoleOutput& console) {
    {   // 탭으로 들여쓴 YAML 은 블록이 통째로 무너져 조용히 아무 일도 안 했다 — 파싱 전에 거른다
        std::string tabLine;
        if (KooRemapper::yamlScanTabIndent(yamlFile, tabLine)) {
            console.error(KooRemapper::yamlTabIndentMessage("modelmeta", tabLine));
            return 1;
        }
    }
    MmConfig cfg;
    if (!mm_parseConfig(yamlFile, cfg, console)) return 1;

    console.info("[modelmeta] Model: " + cfg.model);

    KooRemapper::KFileReader reader;
    KooRemapper::Mesh mesh;
    // 메시도 인클루드 닫힘까지 읽는다(2026-10-16) — 재질·접촉 원문(mm_collectLines)은 이미 닫힘까지 모았는데 메시만
    // 주 덱이라 마스터 덱의 파트가 비었다. 인클루드가 없으면 예전과 같다.
    std::string closureNote;
    try { mesh = reader.readFileWithIncludes(cfg.model, &closureNote); }
    catch (const std::exception& e) {
        console.error("[modelmeta] read failed: " + std::string(e.what()));
        return 1;
    }
    if (!closureNote.empty()) console.info("[modelmeta] " + closureNote);

    auto collected = mm_collectLines(cfg.model);
    for (const auto& b : collected.blind)
        console.warning("[modelmeta] 못 본 인클루드 — 그 안의 파트·재질·접촉은 이 보고에 없다: " + b);
    auto rawLines = std::move(collected.lines);

    // 파트별 요소 분류
    std::map<int, std::vector<const KooRemapper::Element*>> byPart;
    std::map<int, std::set<int>> nodeOwners;   // nid → {pid}
    for (const auto& [eid, elem] : mesh.getElements()) {
        byPart[elem.partId].push_back(&elem);
        mesh.forEachElementNode(elem, [&](int nid) { nodeOwners[nid].insert(elem.partId); });   // 2차는 중간절점까지
    }
    std::vector<int> allPids;
    for (const auto& [pid, _] : byPart) allPids.push_back(pid);

    // 재료 메타 준비
    auto matCards = mm_scanMatCards(rawLines);
    std::string dbPath = cfg.materialDb.empty() ? mm_defaultDbPath() : cfg.materialDb;
    std::vector<MmDbEntry> db;
    if (!dbPath.empty()) {
        db = mm_loadDb(dbPath);
        console.info("[modelmeta] Material DB: " + dbPath + " (" +
                     std::to_string(db.size()) + " entries)");
    } else {
        console.warning("[modelmeta] material_db.json not found — db lookup skipped");
    }

    // ── 파트별 메트릭 ──
    struct PartOut {
        int pid = 0;
        std::string title;
        std::string elemClass;   // solid | shell | mixed
        int nElems = 0;
        double bbox[6] = {0, 0, 0, 0, 0, 0};
        double areaExt = 0, volume = 0;
        double proj[3] = {0, 0, 0};
        int mid = 0;
        MmMatKfile kf;
        MmMatDb dbm;
        // P1-7 에서 더한 것들. **전부 새 키다** — 기존 10키 값은 한 줄도 건드리지 않았다
        // (plan2 조건: "기존 키 값 불변(하류 파서 보호)").
        int nNode = 0;                      // 이 파트 요소가 참조하는 **고유** 절점 수
        bool hasThickness = false;          // `*SECTION_SHELL` 의 T1 을 찾았나
        double thickness = 0;
        std::string thicknessWhy;           // 못 찾은 이유(찾았으면 빈 문자열)
        bool hasMass = false;
        double mass = 0;
        std::string massBasis;              // "volume*rho" | "area*t*rho"
        std::string massWhy;                // 유도 못 한 이유
        bool hasEdge = false;
        double edgeMin = 0, edgeP50 = 0, edgeMax = 0;
        std::string geomWhy;                // 기하 값을 낼 수 없는 이유(2차 솔리드) — 비었으면 냈다
    };
    std::vector<PartOut> parts;

    for (int pid : allPids) {
        PartOut po;
        po.pid = pid;
        po.nElems = static_cast<int>(byPart[pid].size());
        auto pit = mesh.getParts().find(pid);
        if (pit != mesh.getParts().end()) {
            po.title = pit->second.name;
            po.mid = pit->second.materialId;
        }

        int nSolid = 0, nShell = 0;
        bool first = true;
        for (const auto* e : byPart[pid]) {
            bool shell = (e->type == KooRemapper::ElementType::QUAD4);
            (shell ? nShell : nSolid)++;
            // 요소가 **참조하는** 절점 — 2차 솔리드는 중간절점까지(휜 모서리가 bbox 를 넓힐 수 있다)
            mesh.forEachElementNode(*e, [&](int nid) {
                V3 p;
                if (!mm_nodePos(mesh, nid, p)) return;
                if (first) {
                    po.bbox[0] = po.bbox[3] = p.x;
                    po.bbox[1] = po.bbox[4] = p.y;
                    po.bbox[2] = po.bbox[5] = p.z;
                    first = false;
                } else {
                    po.bbox[0] = std::min(po.bbox[0], p.x); po.bbox[3] = std::max(po.bbox[3], p.x);
                    po.bbox[1] = std::min(po.bbox[1], p.y); po.bbox[4] = std::max(po.bbox[4], p.y);
                    po.bbox[2] = std::min(po.bbox[2], p.z); po.bbox[5] = std::max(po.bbox[5], p.z);
                }
            });
        }
        po.elemClass = (nSolid && nShell) ? "mixed" : (nShell ? "shell" : "solid");

        // 고유 절점 수. `n_elems * 8` 이 아니다 — 요소가 절점을 공유하고 축퇴 요소는 같은 절점을
        // 두 번 쓴다(TET4 를 HEX8 로 적을 때 n4 가 네 번 반복된다). 2차 솔리드는 중간절점까지 센다.
        {
            std::set<int> uniq;
            for (const auto* e : byPart[pid])
                mesh.forEachElementNode(*e, [&](int nid) { uniq.insert(nid); });
            po.nNode = static_cast<int>(uniq.size());
        }

        // 에지 길이 — min·max 는 정확히, p50 은 **고정 버킷 히스토그램**으로.
        // ⚠ 정렬하면 요소가 많은 덱에서 메모리가 터진다. 실측: 가장 큰 실덱이 요소 3,499,605개 ·
        // modelmeta 가 36.5초 / 2.13GB 인데 업로드 timeout 이 120초다(여유 3.3배). 요소당
        // `set<pair>` 를 쓰면 그 여유를 넘긴다. 그래서 두 번 훑고 상수 메모리로 낸다.
        //
        // ★모서리 표는 위상 정본(`topo::edgesOf`)이다(2026-10-17). 예전에는 여기 육면체 12모서리 사본을 모든 솔리드에 썼다 —
        //   사면체(TET4 꼴 `[n1,n2,n3,n4,n4,n4,n4,n4]`)에서 n1–n3 모서리가 **빠지고** 둘이 겹쳤다(실측: 가장 긴 모서리가
        //   n1–n3 = 10.0 인 사면체의 max 가 9.055). 2차 사면체를 코너로 재게 되면서 그대로 둘 수 없었다.
        {
            auto forEachEdge = [&](const auto& fn) {
                for (const auto* e : byPart[pid]) {
                    for (const auto& ed : KooRemapper::topo::edgesOf(e->topoType())) {
                        const int na = e->nodeIds[ed.first], nb = e->nodeIds[ed.second];
                        // 축퇴 에지 이른 탈출. ⚠ 아래 `L > 0` 필터와 **중복**이다(같은 절점이면
                        // 길이가 0 이다) — 돌연변이로 확인했다. 값이 아니라 비용만 줄인다.
                        if (na <= 0 || nb <= 0 || na == nb) continue;
                        V3 pa, pb;
                        if (!mm_nodePos(mesh, na, pa) || !mm_nodePos(mesh, nb, pb)) continue;
                        const double dx = pa.x - pb.x, dy = pa.y - pb.y, dz = pa.z - pb.z;
                        const double L = std::sqrt(dx * dx + dy * dy + dz * dz);
                        if (L > 0) fn(L);
                    }
                }
            };
            double lo = 0, hi = 0; long long cnt = 0;
            forEachEdge([&](double L) {
                if (!cnt || L < lo) lo = L;
                if (!cnt || L > hi) hi = L;
                ++cnt;
            });
            if (cnt) {
                po.hasEdge = true;
                po.edgeMin = lo;
                po.edgeMax = hi;
                if (hi <= lo) {
                    po.edgeP50 = lo;
                } else {
                    // 버킷 2048개. 상수 메모리이고 폭이 (hi-lo)/2048 이라 p50 오차가 그 이하다.
                    const int kB = 2048;
                    std::vector<long long> h(kB, 0);
                    const double w = (hi - lo) / kB;
                    forEachEdge([&](double L) {
                        int b = static_cast<int>((L - lo) / w);
                        if (b < 0) b = 0;
                        if (b >= kB) b = kB - 1;
                        ++h[b];
                    });
                    long long acc = 0;
                    const long long half = (cnt + 1) / 2;
                    for (int b = 0; b < kB; ++b) {
                        acc += h[b];
                        if (acc >= half) { po.edgeP50 = lo + (b + 0.5) * w; break; }
                    }
                }
            }
        }

        // 솔리드: 자유면 기준 (닫힌 표면 → 정사영 /2)
        if (nSolid) {
            auto faces = ct_extractSurface(mesh, pid);
            double pj[3] = {0, 0, 0};
            for (const auto& f : faces) {
                MmFaceGeom fg;
                if (!mm_faceGeom(mesh, f, fg)) continue;
                po.areaExt += fg.area;
                pj[0] += std::fabs(fg.areaVec.x);
                pj[1] += std::fabs(fg.areaVec.y);
                pj[2] += std::fabs(fg.areaVec.z);
            }
            po.proj[0] += pj[0] * 0.5;
            po.proj[1] += pj[1] * 0.5;
            po.proj[2] += pj[2] * 0.5;
            for (const auto* e : byPart[pid])
                if (e->type != KooRemapper::ElementType::QUAD4)
                    po.volume += mm_elementVolume(mesh, *e);
        }
        // 쉘: 요소면 단측 기준 (정사영 /2 없음, 부피 0)
        if (nShell) {
            for (const auto* e : byPart[pid]) {
                if (e->type != KooRemapper::ElementType::QUAD4) continue;
                std::array<int, 4> f = {e->nodeIds[0], e->nodeIds[1], e->nodeIds[2], e->nodeIds[3]};
                MmFaceGeom fg;
                if (!mm_faceGeom(mesh, f, fg)) continue;
                po.areaExt += fg.area;
                po.proj[0] += std::fabs(fg.areaVec.x);
                po.proj[1] += std::fabs(fg.areaVec.y);
                po.proj[2] += std::fabs(fg.areaVec.z);
            }
        }

        // 재료
        auto mc = matCards.find(po.mid);
        if (mc != matCards.end()) po.kf = mc->second;
        auto pm = mesh.getMaterials().find(po.mid);
        if (pm != mesh.getMaterials().end()) {
            po.kf.parsed = true;
            po.kf.E = pm->second.E;
            po.kf.nu = pm->second.nu;
            po.kf.rho = pm->second.density;
            po.kf.sigy = pm->second.sigy;
        }
        if (!db.empty())
            po.dbm = mm_matchDb(db, po.mid, po.kf.title, po.title, cfg.dbMidFallback);

        // 두께 — 셸 파트의 `*SECTION_SHELL` Card 2 T1.
        //
        // ⚠ **TSHELL 은 두께를 내지 않는다.** `*SECTION_TSHELL` 에는 두께 칸이 **없다**(Card 1 은
        // SECID ELFORM SHRF NIP PROPT QR/IRID ICOMP TSHEAR). 그 자리를 따라가면 이 리포가 만든
        // 골든 3장에서 다음 섹션 세트의 Card 1 을 두께로 읽는다. 그래서 `null` + 이유다.
        //
        // ⚠ 파트가 `solid` 로 분류돼도 TSHELL 일 수 있다 — `elem_class` 는 **기하 기준**이고
        // TSHELL 요소는 육면체다(`conventions.elem_class` 에 적었다).
        if (po.elemClass == "shell" || po.elemClass == "mixed") {
            if (pit != mesh.getParts().end()) {
                auto sit = mesh.shellSections.find(pit->second.sectionId);
                if (sit != mesh.shellSections.end() && sit->second.thickness > 0) {
                    po.hasThickness = true;
                    po.thickness = sit->second.thickness;
                } else {
                    po.thicknessWhy = "*SECTION_SHELL " + std::to_string(pit->second.sectionId) +
                                      " 의 T1 을 찾지 못했다";
                }
            } else {
                po.thicknessWhy = "이 PID 의 *PART 카드가 없어 SECID 를 모른다";
            }
        } else {
            po.thicknessWhy = "이 파트는 " + po.elemClass + " 다 — 두께 칸이 없다";
        }

        // 질량. **0 으로 채우지 않는다** — 유도할 수 없으면 `null` 과 **이유**를 낸다.
        // (plan2 가 그것을 명시로 금지했다. 지금 셸의 `volume: 0` 이 그 실수의 전례다.)
        if (po.kf.rho <= 0) {
            po.massWhy = "재질 밀도를 모른다(MID " + std::to_string(po.mid) + ")";
        } else if (po.elemClass == "solid" && po.volume > 0) {
            po.hasMass = true;
            po.mass = po.volume * po.kf.rho;
            po.massBasis = "volume*rho";
        } else if (po.elemClass == "shell" && po.hasThickness && po.areaExt > 0) {
            po.hasMass = true;
            po.mass = po.areaExt * po.thickness * po.kf.rho;
            po.massBasis = "area*t*rho";
        } else if (po.elemClass == "mixed") {
            po.massWhy = "솔리드와 셸이 섞인 파트다 — 한 기준으로 낼 수 없다";
        } else if (po.elemClass == "shell") {
            po.massWhy = "셸인데 두께를 모른다(" + po.thicknessWhy + ")";
        } else {
            po.massWhy = "부피가 0 이다(제로두께 코히시브 등)";
        }

        parts.push_back(po);
    }

    // ── connectivity ──
    auto contacts = ct_parseContacts(rawLines);
    auto sets = ct_parseSets(rawLines);
    ct_resolveSetRanges(sets, mesh);   // `_GENERATE` 범위를 덱에 정의된 ID 로 좁힌다
    std::vector<MmEdge> edges;
    std::vector<MmSingleSurface> singles;
    int unresolvedSides = 0;
    // 못 푼 접촉 면 — 개수만 내면 화면이 「무엇이 왜」 를 말할 수 없다. 까닭을 같이 든다.
    struct MmUnresolved { int contact; std::string type, title, side; int sid, styp; std::string why; };
    std::vector<MmUnresolved> unresolved;
    bool edgesTruncated = false;

    auto partTitle = [&](int pid) -> std::string {
        auto it = mesh.getParts().find(pid);
        return (it != mesh.getParts().end()) ? it->second.name : "";
    };

    for (const auto& c : contacts) {
        bool okS = true, okM = true;
        std::string whyS, whyM;
        auto sPids = mm_resolveSide(c.ssid, c.sstyp, sets, nodeOwners, allPids, okS, whyS);
        bool singleSurface = (c.msid == 0 && c.mstyp == 0) ||
                             c.type.find("SINGLE_SURFACE") != std::string::npos;
        if (!okS) {
            ++unresolvedSides;
            unresolved.push_back({c.index, c.type, c.title, "slave", c.ssid, c.sstyp, whyS});
        }

        if (singleSurface) {
            MmSingleSurface ss;
            ss.contactIndex = c.index;
            ss.type = c.type;
            ss.title = c.title;
            if (c.sstyp != 5) ss.pids = sPids;
            singles.push_back(ss);
            continue;
        }
        auto mPids = mm_resolveSide(c.msid, c.mstyp, sets, nodeOwners, allPids, okM, whyM);
        if (!okM) {
            ++unresolvedSides;
            unresolved.push_back({c.index, c.type, c.title, "master", c.msid, c.mstyp, whyM});
        }

        std::set<std::pair<int, int>> seen;
        for (int a : sPids) {
            for (int b : mPids) {
                if (a == b) continue;
                auto key = std::minmax(a, b);
                if (!seen.insert(key).second) continue;
                if (static_cast<int>(edges.size()) >= cfg.maxEdges) { edgesTruncated = true; break; }
                MmEdge e;
                e.a = key.first; e.b = key.second;
                e.contactIndex = c.index;
                e.type = c.type; e.title = c.title; e.fs = c.fs;
                edges.push_back(e);
            }
            if (edgesTruncated) break;
        }
    }

    // 기하학적 접촉쌍 탐지 (옵션)
    std::vector<ct_PairResult> geoPairs;
    if (cfg.detect) {
        console.info("[modelmeta] Geometric contact detection (gap_tol=" +
                     std::to_string(cfg.gapTol) + ") ...");
        auto surfaces = ct_extractAllSurfaces(mesh, allPids);
        geoPairs = ct_detectAllPairs(surfaces, allPids, allPids, mesh,
                                     cfg.gapTol, cfg.normalAngleDeg);
    }

    // ── 모델 bbox ──
    //
    // ★기준을 **두 가지 다** 낸다. 한 JSON 안에서 `model.bbox_*`(전체 절점)과
    //   `parts[].bbox_*`(요소 기준)이 **같은 이름으로 다른 기준**이었다 — 읽는 쪽이 구분할
    //   방법이 없었다. 현장에서 그 혼동이 낙하판을 기기 밖 53mm 에 놓았다(요소 기준 14.55mm
    //   vs 전체 절점 67.50mm). 그래서 `bbox_basis` 를 적고 요소 기준 값을 함께 싣는다.
    //
    // 전체-절점 루프를 여기 따로 두지 않는다 — `Mesh::bboxReport()` 가 정본이고
    // 한 번 순회로 둘 다 낸다(실사용 덱이 절점 13,366,933개다).
    // ★2차 솔리드(2026-10-17) — 리더가 절점 칸을 다 읽고 코너를 제자리에 놓는다. 그래서 값은 **코너로 잰 값**이다
    //   (`geometry_basis: corners` — 모서리가 곧으면 정확하고, 중간절점이 휜 모서리는 곧게 본다). n_node·bbox·고아는
    //   중간절점까지 세어 정확하다. 기하를 믿을 수 없는 파트(코너 차례를 모르는 ELFORM 25-28 · 칸이 모자란 카드)만
    //   null + 까닭이다 — 판정은 세 그림 op 과 **같은 함수**다(갈리면 못 믿는다).
    //   (2026-10-16 까지는 앞 8칸만 담아 TET10 이 육면체로 읽혔고 — 부피 -48.4% — 2차 파트 전부를 null 로 냈다.
    //    처음에는 값을 내고 `second_order` 만 표시했는데, 플래그를 **안 읽는** 소비자(`kr2datahub` · 리스크 앱 어댑터)가
    //    그 부피를 그대로 실었다. 그래서 틀린 줄 아는 값은 지금도 숫자로 내지 않는다.)
    const auto mmBox = mesh.bboxReport();
    const auto mmBad2nd = KooRemapper::figure::secondOrderSolidPids(mesh);
    std::set<int> mmBad2ndPids;
    for (const auto& pe : mmBad2nd) mmBad2ndPids.insert(pe.first);
    std::map<int, int> mm2ndElform;                     // 2차 파트 → ELFORM(요소가 있는 파트만)
    for (const auto& pe : mesh.getPartSolidElform())
        if (KooRemapper::figure::isSecondOrderElform(pe.second) && byPart.count(pe.first)) mm2ndElform[pe.first] = pe.second;
    if (!mmBad2nd.empty()) {
        console.warning("[modelmeta] " + KooRemapper::figure::secondOrderSolidWhy(mmBad2nd, mesh));
        console.warning("[modelmeta] 그 파트의 volume·area_ext·proj·edge_len·mass 는 JSON 에 null 과 까닭(geometry_reason·"
                        "mass_reason)으로 낸다.");
    }
    {
        const auto mmCorner = KooRemapper::figure::secondOrderCornerPids(mesh);
        if (!mmCorner.empty())
            console.info("[modelmeta] " + KooRemapper::figure::secondOrderCornerNote(mmCorner) +
                         " — 기하 값은 코너로 잰다(part.geometry_basis = corners)");
    }
    for (auto& p : parts) {
        for (const auto& pe : mmBad2nd) {
            if (pe.first != p.pid) continue;
            p.geomWhy = "2차 솔리드(ELFORM " + std::to_string(pe.second) + ") — " +
                        KooRemapper::figure::secondOrderSolidReason(mesh, pe.first, pe.second) +
                        "(그 기하로 잰 값은 믿을 수 없다)";
            p.hasMass = false;
            p.massBasis.clear();
            p.massWhy = "부피를 믿을 수 없어 질량도 낼 수 없다. " + p.geomWhy;
        }
    }
    // 고아 수는 칸이 모자란 2차 카드가 있을 때만 **상한**이다 — 못 읽은 칸의 절점이 고아로 잡힌다.
    // 센 값이 0 이면 그것은 참이다(참조가 줄어도 참 고아가 사라지지는 않는다).
    const bool mmOrphanUnsure = !mesh.getPartIncompleteSolids().empty() && mmBox.orphanNodes > 0;

    const double mb[6] = {mmBox.allMin.x, mmBox.allMin.y, mmBox.allMin.z,
                          mmBox.allMax.x, mmBox.allMax.y, mmBox.allMax.z};

    // ── JSON 출력 ──
    std::string outPath = cfg.output + "_modelmeta.json";
    std::ofstream rf(outPath);
    if (!rf.is_open()) {
        console.error("[modelmeta] Cannot write: " + outPath);
        return 1;
    }
    char nb[64];
    auto num = [&](double v) -> std::string {
        snprintf(nb, sizeof(nb), "%.6g", v);
        return std::string(nb);
    };

    rf << "{\n";
    rf << "  \"model\": {\n"
       << "    \"file\": \"" << mm_jsonEsc(cfg.model) << "\",\n"
       << "    \"nodes\": " << mesh.getNodes().size() << ",\n"
       << "    \"elements\": " << mesh.getElements().size() << ",\n"
       << "    \"parts\": " << parts.size() << ",\n"
       << "    \"bbox_min\": [" << num(mb[0]) << ", " << num(mb[1]) << ", " << num(mb[2]) << "],\n"
       << "    \"bbox_max\": [" << num(mb[3]) << ", " << num(mb[4]) << ", " << num(mb[5]) << "],\n"
       << "    \"bbox_basis\": \"all_nodes\",\n"
       << "    \"bbox_used_min\": [" << num(mmBox.usedMin.x) << ", " << num(mmBox.usedMin.y)
       << ", " << num(mmBox.usedMin.z) << "],\n"
       << "    \"bbox_used_max\": [" << num(mmBox.usedMax.x) << ", " << num(mmBox.usedMax.y)
       << ", " << num(mmBox.usedMax.z) << "],\n"
       << "    \"bbox_used_basis\": \"nodes_referenced_by_elements\",\n"
       << "    \"orphan_nodes\": "
       << (mmOrphanUnsure ? std::string("null") : std::to_string(mmBox.orphanNodes)) << ",\n"
       << "    \"orphan_nodes_reason\": "
       << (mmOrphanUnsure ? "\"절점 칸이 모자란 2차 카드가 있어 못 읽은 칸의 절점을 고아로 센다 — 센 값은 "
                            "상한일 뿐이다(" + std::to_string(mmBox.orphanNodes) + "개)\""
                          : std::string("null")) << ",\n"
       << "    \"second_order_solid_pids\": [";
    {
        size_t i = 0;
        for (const auto& [pid, ef] : mm2ndElform)
            rf << (i++ ? ", " : "") << "{\"pid\": " << pid << ", \"elform\": " << ef
               << ", \"geometry_basis\": " << (mmBad2ndPids.count(pid) ? "null" : "\"corners\"") << "}";
    }
    rf << "]\n"
       << "  },\n";
    rf << "  \"conventions\": {\n"
       << "    \"area_ext\": \"solid: free-face sum; shell: one-sided element area\",\n"
       << "    \"proj\": \"solid: sum(area*|n.axis|)/2 (closed); shell: no /2 (open)\",\n"
       << "    \"volume\": \"solid cell face-pyramid decomposition; shell: 0\",\n"
       // 아래는 P1-7 에서 더한 관례들. 값이 아니라 **무슨 기준으로 낸 값인가**를 적는다 —
       // 같은 파일을 두고 `info` 와 여기가 다른 숫자를 말하던 것이 그 기준 차이였다.
       << "    \"parts_basis\": \"요소가 참조한 PID 기준. *PART 카드만 있고 요소가 없는 PID 는 "
          "세지 않는다 — `info` 의 파트 수와 다를 수 있고, 그것이 기준 차이다\",\n"
       << "    \"bbox\": \"parts[].bbox_* 와 model.bbox_used_*: 요소가 참조한 절점만. "
          "⚠ model.bbox_* 는 **`*NODE` 전체**다(고아 포함) — 전에 여기 '고립 절점은 들어오지 "
          "않는다' 고 적혀 있었는데 **사실이 아니었다**(실측: 고아를 x=-40 에 둔 덱에서 "
          "model.bbox_min.x = -40, bbox_used_min.x = 0). 낙하판·접촉면은 **used 기준**으로 "
          "놓아라 — 현장 덱에서 두 기준이 14.55mm vs 67.50mm 로 갈려 낙하판이 기기 밖 53mm 에 "
          "생겼다. 기준은 bbox_basis/bbox_used_basis 가 말한다\",\n"
       << "    \"second_order\": \"part.second_order=true 면 2차(고차) 솔리드 파트다(ELFORM 16·17·23-29). "
          "리더가 절점 칸을 다 읽고 코너를 제자리에 놓으므로 volume·area_ext·proj·edge_len·mass 는 **코너로 잰 값**이다 — "
          "part.geometry_basis = corners. 모서리가 곧으면 정확하고, 중간절점이 휜 모서리는 곧게 본다. n_node·bbox·"
          "model.orphan_nodes 는 중간절점까지 세어 정확하다. 코너 차례를 매뉴얼 본문이 적지 않은 ELFORM(25·26·27·28)과 "
          "절점 칸이 모자란 카드(노드를 8+2 로 쪼갠 덱 등)가 든 파트만 기하가 null(geometry_basis = null)이고 까닭을 "
          "geometry_reason·mass_reason 에 적는다 — `section`·`surfview`·`stackdiagram` 은 같은 판정으로 그 파트를 "
          "**거절**한다. 칸이 모자란 카드가 있으면 model.orphan_nodes 는 상한이라 0 이 아닐 때 null + "
          "orphan_nodes_reason 이다. (2026-10-16 까지는 리더가 앞 8칸만 담아 2차 파트 전부가 null 이었다)\",\n"
       << "    \"geometry_basis\": \"그 파트의 기하 값을 무엇으로 쟀나 — nodes(1차 요소 · 절점 전부가 코너다) · "
          "corners(2차 솔리드 · 코너만 — 휜 모서리는 곧게 본다) · null(기하를 믿을 수 없어 내지 않았다)\",\n"
       << "    \"elem_class\": \"**기하 기준**이다. TSHELL 요소는 육면체라 solid 로 센다 — "
          "카드 키워드 기준이 아니다\",\n"
       << "    \"n_node\": \"그 파트 요소가 참조한 **고유** 절점 수. 축퇴 요소는 같은 절점을 "
          "여러 번 쓰므로 n_elems*8 이 아니다 2차 솔리드는 중간절점까지 센다(절점 칸이 모자란 카드가 든 파트는 null)\",\n"
       << "    \"thickness\": \"셸만. *SECTION_SHELL Card 2 의 T1. *SECTION_TSHELL 에는 두께 칸이 "
          "**없어** TSHELL 은 null 이다\",\n"
       << "    \"mass\": \"유도할 수 없으면 **0 이 아니라 null + reason** 이다. "
          "solid: volume*rho, shell: area*t*rho\",\n"
       << "    \"edge_len\": \"min/max 는 정확값, p50 은 버킷 2048개 히스토그램(오차 (max-min)/2048 "
          "이하). 축퇴 에지는 빼고 센다\",\n"
       << "    \"element_kinds\": \"BEAM/DISCRETE/SEATBELT 는 세지 않는다 — 추적 489장·실사용 "
          "1,303장 전수에서 **0장**이라 확정할 근거가 없었다(2026-09-27 실측)\"\n"
       << "  },\n";

    rf << "  \"parts\": [\n";
    for (size_t i = 0; i < parts.size(); ++i) {
        const auto& p = parts[i];
        const bool geomOk = p.geomWhy.empty();
        rf << "    {\n"
           << "      \"pid\": " << p.pid << ",\n"
           << "      \"title\": \"" << mm_jsonEsc(p.title) << "\",\n"
           << "      \"elem_class\": \"" << p.elemClass << "\",\n"
           // ★이 파트의 기하 값을 믿을 수 있나. 플래그만 위(model)에 두면 파트 하나를
           //   읽는 소비자가 못 본다 — ④ 에서 신호가 플랫폼까지 끊겨 있던 것과 같은 자리다.
           << "      \"second_order\": "
           << (mm2ndElform.count(p.pid) ? "true" : "false") << ",\n"
           << "      \"geometry_basis\": "
           << (!geomOk ? std::string("null") : mm2ndElform.count(p.pid) ? std::string("\"corners\"") : std::string("\"nodes\""))
           << ",\n"
           << "      \"geometry_reason\": "
           << (geomOk ? std::string("null") : "\"" + mm_jsonEsc(p.geomWhy) + "\"") << ",\n"
           << "      \"n_elems\": " << p.nElems << ",\n"
           << "      \"bbox_min\": [" << num(p.bbox[0]) << ", " << num(p.bbox[1]) << ", " << num(p.bbox[2]) << "],\n"
           << "      \"bbox_max\": [" << num(p.bbox[3]) << ", " << num(p.bbox[4]) << ", " << num(p.bbox[5]) << "],\n"
           << "      \"area_ext\": " << (geomOk ? num(p.areaExt) : std::string("null")) << ",\n"
           << "      \"volume\": " << (geomOk ? num(p.volume) : std::string("null")) << ",\n"
           << "      \"proj\": "
           << (geomOk ? "{\"x\": " + num(p.proj[0]) + ", \"y\": " + num(p.proj[1]) +
                        ", \"z\": " + num(p.proj[2]) + "}"
                      : std::string("null")) << ",\n"
           // 2차 솔리드도 중간절점까지 세어 정확하다 — 칸이 모자란 카드가 든 파트만 셀 수 없다(못 읽은 칸이 있다)
           << "      \"n_node\": "
           << (mesh.getPartIncompleteSolids().count(p.pid) ? std::string("null") : std::to_string(p.nNode)) << ",\n"
           << "      \"thickness\": " << (p.hasThickness ? num(p.thickness) : std::string("null"))
           << ",\n"
           << "      \"thickness_reason\": "
           << (p.hasThickness ? std::string("null") : "\"" + mm_jsonEsc(p.thicknessWhy) + "\"")
           << ",\n"
           << "      \"mass\": " << (p.hasMass ? num(p.mass) : std::string("null")) << ",\n"
           << "      \"mass_basis\": "
           << (p.hasMass ? "\"" + p.massBasis + "\"" : std::string("null")) << ",\n"
           << "      \"mass_reason\": "
           << (p.hasMass ? std::string("null") : "\"" + mm_jsonEsc(p.massWhy) + "\"") << ",\n"
           << "      \"edge_len\": "
           << (p.hasEdge && geomOk ? "{\"min\": " + num(p.edgeMin) + ", \"p50\": " + num(p.edgeP50) +
                           ", \"max\": " + num(p.edgeMax) + "}"
                         : std::string("null")) << ",\n";
        rf << "      \"material\": {\n"
           << "        \"mid\": " << p.mid << ",\n"
           << "        \"kfile\": {";
        {
            bool firstKv = true;
            auto kv = [&](const std::string& k, const std::string& v, bool quote) {
                if (!firstKv) rf << ", ";
                firstKv = false;
                rf << "\"" << k << "\": " << (quote ? "\"" + mm_jsonEsc(v) + "\"" : v);
            };
            if (!p.kf.keyword.empty()) kv("keyword", p.kf.keyword, true);
            if (!p.kf.title.empty()) kv("name", p.kf.title, true);
            if (p.kf.parsed) {
                kv("E", num(p.kf.E), false);
                kv("nu", num(p.kf.nu), false);
                kv("rho", num(p.kf.rho), false);
                if (p.kf.sigy > 0) kv("sigy", num(p.kf.sigy), false);
            }
        }
        rf << "},\n";
        if (p.dbm.found) {
            rf << "        \"db\": {\"match_basis\": \"" << p.dbm.basis << "\", "
               << "\"db_mid\": " << p.dbm.dbMid << ", "
               << "\"name\": \"" << mm_jsonEsc(p.dbm.name) << "\", "
               << "\"tag\": \"" << mm_jsonEsc(p.dbm.tag) << "\", "
               << "\"category\": \"" << mm_jsonEsc(p.dbm.category) << "\", "
               << "\"mat_type\": \"" << mm_jsonEsc(p.dbm.matType) << "\", "
               << "\"E_GPa\": " << num(p.dbm.E_GPa) << ", "
               << "\"rho_g_cm3\": " << num(p.dbm.rho_g_cm3) << ", "
               << "\"PR\": " << num(p.dbm.PR) << "}\n";
        } else {
            rf << "        \"db\": null\n";
        }
        rf << "      }\n";
        rf << "    }" << (i + 1 < parts.size() ? "," : "") << "\n";
    }
    rf << "  ],\n";

    rf << "  \"connectivity\": {\n";
    rf << "    \"contact_edges\": [\n";
    for (size_t i = 0; i < edges.size(); ++i) {
        const auto& e = edges[i];
        rf << "      {\"a\": " << e.a << ", \"b\": " << e.b
           << ", \"a_title\": \"" << mm_jsonEsc(partTitle(e.a)) << "\""
           << ", \"b_title\": \"" << mm_jsonEsc(partTitle(e.b)) << "\""
           << ", \"contact\": " << e.contactIndex
           << ", \"type\": \"" << mm_jsonEsc(e.type) << "\""
           << ", \"title\": \"" << mm_jsonEsc(e.title) << "\""
           << ", \"fs\": " << num(e.fs) << "}"
           << (i + 1 < edges.size() ? "," : "") << "\n";
    }
    rf << "    ],\n";
    rf << "    \"single_surface\": [\n";
    for (size_t i = 0; i < singles.size(); ++i) {
        const auto& s = singles[i];
        rf << "      {\"contact\": " << s.contactIndex
           << ", \"type\": \"" << mm_jsonEsc(s.type) << "\""
           << ", \"title\": \"" << mm_jsonEsc(s.title) << "\""
           << ", \"pids\": [";
        for (size_t k = 0; k < s.pids.size(); ++k)
            rf << (k ? ", " : "") << s.pids[k];
        rf << "]}" << (i + 1 < singles.size() ? "," : "") << "\n";
    }
    rf << "    ],\n";
    if (cfg.detect) {
        rf << "    \"geometric_edges\": [\n";
        for (size_t i = 0; i < geoPairs.size(); ++i) {
            const auto& g = geoPairs[i];
            rf << "      {\"a\": " << g.pidA << ", \"b\": " << g.pidB
               << ", \"a_title\": \"" << mm_jsonEsc(partTitle(g.pidA)) << "\""
               << ", \"b_title\": \"" << mm_jsonEsc(partTitle(g.pidB)) << "\""
               << ", \"gap_min\": " << num(g.gapMin)
               << ", \"gap_avg\": " << num(g.gapAvg)
               << ", \"pairs\": " << g.pairCount << "}"
               << (i + 1 < geoPairs.size() ? "," : "") << "\n";
        }
        rf << "    ],\n";
    }
    rf << "    \"contacts_total\": " << contacts.size() << ",\n"
       << "    \"unresolved_sides\": " << unresolvedSides << ",\n";
    rf << "    \"unresolved_detail\": [\n";
    for (size_t i = 0; i < unresolved.size(); ++i) {
        const auto& u = unresolved[i];
        rf << "      {\"contact\": " << u.contact
           << ", \"type\": \"" << mm_jsonEsc(u.type) << "\""
           << ", \"title\": \"" << mm_jsonEsc(u.title) << "\""
           << ", \"side\": \"" << u.side << "\""
           << ", \"sid\": " << u.sid << ", \"styp\": " << u.styp
           << ", \"why\": \"" << mm_jsonEsc(u.why) << "\"}"
           << (i + 1 < unresolved.size() ? "," : "") << "\n";
    }
    rf << "    ],\n";
    rf << "    \"edges_truncated\": " << (edgesTruncated ? "true" : "false") << "\n";
    rf << "  }\n";
    rf << "}\n";
    rf.close();

    // ── 콘솔 요약 ──
    console.info("[modelmeta] Parts: " + std::to_string(parts.size()) +
                 ", contacts: " + std::to_string(contacts.size()) +
                 " (edges: " + std::to_string(edges.size()) +
                 ", single_surface: " + std::to_string(singles.size()) +
                 (cfg.detect ? ", geometric: " + std::to_string(geoPairs.size()) : "") + ")");
    int dbHit = 0;
    for (const auto& p : parts) if (p.dbm.found) ++dbHit;
    if (!db.empty())
        console.info("[modelmeta] Material DB match: " + std::to_string(dbHit) + "/" +
                     std::to_string(parts.size()) + " parts");
    if (unresolvedSides) {
        console.warning("[modelmeta] " + std::to_string(unresolvedSides) +
                        " contact side(s) unresolved — 그 면의 파트쌍은 연결도에 없다(까닭: connectivity.unresolved_detail)");
        for (size_t i = 0; i < unresolved.size() && i < 5; ++i)
            console.warning("[modelmeta]   contact " + std::to_string(unresolved[i].contact) + " " +
                            unresolved[i].side + " SID " + std::to_string(unresolved[i].sid) +
                            " (STYP=" + std::to_string(unresolved[i].styp) + "): " + unresolved[i].why);
    }
    console.success("[modelmeta] Report -> " + outPath);
    return 0;
}
