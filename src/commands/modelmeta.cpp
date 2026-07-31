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
#include "modelmeta.h"
#include "contact_helpers.h"
#include "cli/ConsoleOutput.h"
#include "parser/KFileReader.h"
#include "core/Mesh.h"
#include "core/Element.h"

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

std::string mm_stripComment(const std::string& v) {
    bool inS = false, inD = false;
    for (size_t i = 0; i < v.size(); ++i) {
        char c = v[i];
        if (c == '\'' && !inD) inS = !inS;
        else if (c == '"' && !inS) inD = !inD;
        else if (c == '#' && !inS && !inD) return mm_trim(v.substr(0, i));
    }
    return mm_trim(v);
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
    std::string line;
    while (std::getline(f, line)) {
        std::string s = mm_trim(line);
        if (s.empty() || s[0] == '#') continue;
        size_t c = s.find(':');
        if (c == std::string::npos) continue;
        std::string key = mm_trim(s.substr(0, c));
        std::string val = mm_unquote(mm_stripComment(s.substr(c + 1)));
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

// ── 원시 라인 수집 (*INCLUDE 1단계 추적 — cclip 전례) ───────────────────────

std::vector<std::string> mm_collectLines(const std::string& modelPath) {
    std::vector<std::string> lines;
    std::ifstream f(modelPath);
    if (!f.is_open()) return lines;
    std::string dir = mm_dirOf(modelPath);
    std::string line;
    bool inInclude = false;
    while (std::getline(f, line)) {
        std::string s = mm_trim(line);
        std::string up = mm_lower(s);
        if (!s.empty() && s[0] == '*') {
            inInclude = (up == "*include" || up.rfind("*include_", 0) == 0);
            lines.push_back(line);
            continue;
        }
        lines.push_back(line);
        if (inInclude && !s.empty() && s[0] != '$') {
            std::string inc = s;
            if (inc[0] != '/' && !(inc.size() > 1 && inc[1] == ':'))
                inc = dir + "/" + inc;
            std::ifstream g(inc);
            std::string l2;
            while (g.is_open() && std::getline(g, l2)) lines.push_back(l2);
        }
    }
    return lines;
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

// 요소 부피 — 면-중심 피라미드 분해(각 삼각형 피라미드 |부호부피| 합; 와인딩 무관,
// 볼록 셀 정확). HEX8/PENTA6/TET4/HEX20/TET10(코너 절점) 공통.
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
        int ntri = (n == 3) ? 1 : 2;
        for (int t = 0; t < ntri; ++t) {
            V3 a = mm_sub(v[0], cc), b = mm_sub(v[t + 1], cc), c = mm_sub(v[t + 2], cc);
            vol += std::fabs(mm_dot(mm_cross(a, b), c)) / 6.0;
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
std::vector<int> mm_resolveSide(int sid, int styp,
                                const std::vector<SetDef>& sets,
                                const std::map<int, std::set<int>>& nodeOwners,
                                const std::vector<int>& allPids,
                                bool& resolved) {
    resolved = true;
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
    if (styp == 2) {
        for (const auto& s : sets)
            if (s.id == sid && s.type == "PART") { pids = s.ids; return pids; }
        resolved = false;
        return pids;
    }
    if (styp == 4) {
        for (const auto& s : sets)
            if (s.id == sid && s.type == "NODE") { addNodePids(s.ids); return pids; }
        resolved = false;
        return pids;
    }
    if (styp == 0) {   // SET_SEGMENT
        for (const auto& s : sets) {
            if (s.id == sid && s.type == "SEGMENT") {
                std::vector<int> nids;
                for (const auto& seg : s.segments)
                    for (int nid : seg) if (nid > 0) nids.push_back(nid);
                addNodePids(nids);
                return pids;
            }
        }
        resolved = false;
        return pids;
    }
    resolved = false;
    return pids;
}

}  // namespace

// ── 메인 ─────────────────────────────────────────────────────────────────────

int runModelmeta(const std::string& yamlFile, ConsoleOutput& console) {
    MmConfig cfg;
    if (!mm_parseConfig(yamlFile, cfg, console)) return 1;

    console.info("[modelmeta] Model: " + cfg.model);

    KooRemapper::KFileReader reader;
    KooRemapper::Mesh mesh;
    try { mesh = reader.readFile(cfg.model); }
    catch (const std::exception& e) {
        console.error("[modelmeta] read failed: " + std::string(e.what()));
        return 1;
    }

    auto rawLines = mm_collectLines(cfg.model);

    // 파트별 요소 분류
    std::map<int, std::vector<const KooRemapper::Element*>> byPart;
    std::map<int, std::set<int>> nodeOwners;   // nid → {pid}
    for (const auto& [eid, elem] : mesh.getElements()) {
        byPart[elem.partId].push_back(&elem);
        for (int nid : elem.nodeIds)
            if (nid > 0) nodeOwners[nid].insert(elem.partId);
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
            for (int nid : e->nodeIds) {
                if (nid <= 0) continue;
                V3 p;
                if (!mm_nodePos(mesh, nid, p)) continue;
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
            }
        }
        po.elemClass = (nSolid && nShell) ? "mixed" : (nShell ? "shell" : "solid");

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

        parts.push_back(po);
    }

    // ── connectivity ──
    auto contacts = ct_parseContacts(rawLines);
    auto sets = ct_parseSets(rawLines);
    std::vector<MmEdge> edges;
    std::vector<MmSingleSurface> singles;
    int unresolvedSides = 0;
    bool edgesTruncated = false;

    auto partTitle = [&](int pid) -> std::string {
        auto it = mesh.getParts().find(pid);
        return (it != mesh.getParts().end()) ? it->second.name : "";
    };

    for (const auto& c : contacts) {
        bool okS = true, okM = true;
        auto sPids = mm_resolveSide(c.ssid, c.sstyp, sets, nodeOwners, allPids, okS);
        bool singleSurface = (c.msid == 0 && c.mstyp == 0) ||
                             c.type.find("SINGLE_SURFACE") != std::string::npos;
        if (!okS) ++unresolvedSides;

        if (singleSurface) {
            MmSingleSurface ss;
            ss.contactIndex = c.index;
            ss.type = c.type;
            ss.title = c.title;
            if (c.sstyp != 5) ss.pids = sPids;
            singles.push_back(ss);
            continue;
        }
        auto mPids = mm_resolveSide(c.msid, c.mstyp, sets, nodeOwners, allPids, okM);
        if (!okM) ++unresolvedSides;

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
    double mb[6] = {0, 0, 0, 0, 0, 0};
    bool mbFirst = true;
    for (const auto& [nid, nd] : mesh.getNodes()) {
        double p[3] = {nd.position.x, nd.position.y, nd.position.z};
        if (mbFirst) {
            mb[0] = mb[3] = p[0]; mb[1] = mb[4] = p[1]; mb[2] = mb[5] = p[2];
            mbFirst = false;
        } else {
            for (int a = 0; a < 3; ++a) {
                mb[a] = std::min(mb[a], p[a]);
                mb[a + 3] = std::max(mb[a + 3], p[a]);
            }
        }
    }

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
       << "    \"bbox_max\": [" << num(mb[3]) << ", " << num(mb[4]) << ", " << num(mb[5]) << "]\n"
       << "  },\n";
    rf << "  \"conventions\": {\n"
       << "    \"area_ext\": \"solid: free-face sum; shell: one-sided element area\",\n"
       << "    \"proj\": \"solid: sum(area*|n.axis|)/2 (closed); shell: no /2 (open)\",\n"
       << "    \"volume\": \"solid cell face-pyramid decomposition; shell: 0\"\n"
       << "  },\n";

    rf << "  \"parts\": [\n";
    for (size_t i = 0; i < parts.size(); ++i) {
        const auto& p = parts[i];
        rf << "    {\n"
           << "      \"pid\": " << p.pid << ",\n"
           << "      \"title\": \"" << mm_jsonEsc(p.title) << "\",\n"
           << "      \"elem_class\": \"" << p.elemClass << "\",\n"
           << "      \"n_elems\": " << p.nElems << ",\n"
           << "      \"bbox_min\": [" << num(p.bbox[0]) << ", " << num(p.bbox[1]) << ", " << num(p.bbox[2]) << "],\n"
           << "      \"bbox_max\": [" << num(p.bbox[3]) << ", " << num(p.bbox[4]) << ", " << num(p.bbox[5]) << "],\n"
           << "      \"area_ext\": " << num(p.areaExt) << ",\n"
           << "      \"volume\": " << num(p.volume) << ",\n"
           << "      \"proj\": {\"x\": " << num(p.proj[0]) << ", \"y\": " << num(p.proj[1])
           << ", \"z\": " << num(p.proj[2]) << "},\n";
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
       << "    \"unresolved_sides\": " << unresolvedSides << ",\n"
       << "    \"edges_truncated\": " << (edgesTruncated ? "true" : "false") << "\n";
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
    if (unresolvedSides)
        console.warning("[modelmeta] " + std::to_string(unresolvedSides) +
                        " contact side(s) unresolved (missing SET definitions)");
    console.success("[modelmeta] Report -> " + outPath);
    return 0;
}
