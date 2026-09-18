// CNRB 체결점 하나를 Side A/B 두 강체로 쪼개고 그 사이를 제로길이 discrete beam(ELFORM=6) 하나로 잇는 op
#include "cnrb2spring.h"
#include "cli/ConsoleOutput.h"
#include "util/YamlComment.h"
#include "assembly/ModelAssembler.h"  // 죽은 PID 참조 처리를 restack/merge 와 같은 코드로 한다

#include <algorithm>
#include <cmath>
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <map>
#include <set>
#include <sstream>
#include <string>
#include <vector>

// Knowledge graph (lat.md):
//   @lat: [[modules/commands]]
//   @lat: [[commands/cnrb2spring]]

using KooRemapper::ConsoleOutput;

// ============================================================
// 소도구 — 저장소 관례대로 이 파일 안에 cg_ 접두어로 둔다(cnrb2solid 의 cs_, merge 의 mg_ 와 같다).
// 칸 폭이 카드마다 다르므로 8칸(cg_field8)·10칸(cg_field10) 헬퍼를 반드시 나눠 쓴다.
//   8칸  : *ELEMENT_*  (*ELEMENT_BEAM 포함)
//   10칸 : *PART *SECTION_* *MAT_* *SET_* *CONSTRAINED_* *DEFINE_CURVE *DEFINE_COORDINATE_* ...
// ============================================================

static std::string cg_trim(const std::string& s) {
    size_t a = s.find_first_not_of(" \t\r\n");
    if (a == std::string::npos) return "";
    size_t b = s.find_last_not_of(" \t\r\n");
    return s.substr(a, b - a + 1);
}

static std::string cg_upper(const std::string& s) {
    std::string r = s;
    for (auto& c : r) c = (char)toupper((unsigned char)c);
    return r;
}

static std::vector<std::string> cg_splitWS(const std::string& s) {
    std::vector<std::string> t;
    std::istringstream ss(s);
    std::string w;
    while (ss >> w) t.push_back(w);
    return t;
}

// 키워드 줄의 첫 토큰(대문자) — '*ELEMENT_SHELL   $ 주석' 같은 줄에서 키워드만 뽑는다
static std::string cg_keyword(const std::string& line) {
    auto t = cg_splitWS(line);
    return t.empty() ? std::string() : cg_upper(t[0]);
}

static std::string cg_fieldN(const std::string& line, int idx, int w) {
    int pos = idx * w;
    if (pos >= (int)line.size()) return "";
    int len = std::min(w, (int)line.size() - pos);
    return cg_trim(line.substr(pos, len));
}
static std::string cg_field10(const std::string& line, int idx) { return cg_fieldN(line, idx, 10); }
static std::string cg_field8(const std::string& line, int idx)  { return cg_fieldN(line, idx, 8); }

static int cg_toInt(const std::string& s) {
    try { return std::stoi(cg_trim(s)); } catch (...) { return 0; }
}
static double cg_toDouble(const std::string& s) {
    try { return std::stod(cg_trim(s)); } catch (...) { return 0.0; }
}

// 문자열이 '수 하나' 인가 — YAML 값 검증에서 조용히 기본값으로 떨어지지 않게 한다
static bool cg_parseDoubleStrict(const std::string& s, double& out) {
    std::string t = cg_trim(s);
    if (t.empty()) return false;
    const char* p = t.c_str();
    char* endp = nullptr;
    double v = std::strtod(p, &endp);
    if (endp == p || *endp != '\0') return false;
    out = v;
    return true;
}
static bool cg_parseIntStrict(const std::string& s, int& out) {
    std::string t = cg_trim(s);
    if (t.empty()) return false;
    const char* p = t.c_str();
    char* endp = nullptr;
    long v = std::strtol(p, &endp, 10);
    if (endp == p || *endp != '\0') return false;
    out = (int)v;
    return true;
}

// 줄이 '데이터 줄 모양' 인가 — src/assembly/ModelAssembler.cpp 의 matLineLooksLikeData 소형 사본.
// (그 함수는 어셈블러 내부라 여기서 링크해 쓸 수 없다. 판정 규칙은 정본과 같아야 한다.)
// 빈 칸을 뺀 모든 칸이 수이고 칸이 둘 이상이면 데이터 줄이다. '_TITLE' 카드에서 제목 줄이 빠진 덱을
// 가려내는 자리 — cnrb2solid 처럼 '첫 비-$ 줄을 무조건 제목' 으로 먹으면 PID/NSID 를 한 줄 밀려 읽는다.
static bool cg_looksLikeDataLine(const std::string& raw) {
    std::string line = raw;
    if (!line.empty() && line.back() == '\r') line.pop_back();
    if (line.find_first_not_of(" \t") == std::string::npos) return false;
    std::vector<std::string> fields;
    if (line.find(',') != std::string::npos) {
        size_t pos = 0;
        while (pos <= line.size()) {
            size_t c = line.find(',', pos);
            if (c == std::string::npos) { fields.push_back(line.substr(pos)); break; }
            fields.push_back(line.substr(pos, c - pos));
            pos = c + 1;
        }
    } else {
        for (size_t c = 0; c < line.size(); c += 10) fields.push_back(line.substr(c, 10));
    }
    int numeric = 0;
    for (const auto& f : fields) {
        size_t b = f.find_first_not_of(" \t");
        if (b == std::string::npos) continue;
        size_t e = f.find_last_not_of(" \t");
        std::string tok = f.substr(b, e - b + 1);
        const char* p = tok.c_str();
        char* endp = nullptr;
        std::strtod(p, &endp);
        if (endp == p || *endp != '\0') return false;
        ++numeric;
    }
    return numeric >= 2;
}

// 요소 줄 토큰 — 공백으로 나누되, 8자리 ID 가 칸을 꽉 채워 공백 없이 붙은 줄이면 8칸 고정폭으로 다시 읽는다
static std::vector<std::string> cg_elemTokens(const std::string& line) {
    auto t = cg_splitWS(line);
    bool wide = false;
    for (const auto& s : t) if (s.size() >= 9) { wide = true; break; }
    if (!wide) return t;
    std::vector<std::string> f;
    for (int i = 0; i * 8 < (int)line.size(); ++i) {
        std::string v = cg_field8(line, i);
        if (!v.empty()) f.push_back(v);
    }
    return f;
}

struct CgVec3 { double x = 0, y = 0, z = 0; };

struct CgSetDef {
    std::vector<int> nids;
    size_t lineStart = 0, lineEnd = 0;
    bool   unsupported = false;   // _GENERATE·_COLUMN·콤마 자유형식 — 조용히 틀리게 읽지 않는다
};

struct CgCnrbDef {
    int pid = 0, cid = 0, nsid = 0, pnode = 0, iprt = 0, drflag = 0, rrflag = 0;
    size_t lineStart = 0, lineEnd = 0;
    int dataLines = 0;            // 블록 안 데이터 줄 수 — _SPC·_INERTIA 의 추가 카드를 가린다
    std::string keyword;
};

// ============================================================
// 덱 파싱 — 원문 줄 버퍼에서 직접 읽는다.
// KFileReader/Mesh 를 쓰지 않는 이유: parseElementSolidSection 이 ten-nodes 두 줄 형식의
// 둘째 줄에서 앞 8칸만 저장해 TET10 의 9·10번 중간절점을 버린다. CNRB 노드가 중간절점이면
// 소속 파트를 못 찾아 '두 파트 판정' 이 통째로 틀린다.
// ============================================================

// *NODE 블록만 본다(*NODE_SCALAR 등 파생 제외). 이 맵이 '세트 안 가짜 ID' 판정의 기준이다.
static std::map<int, CgVec3> cg_parseNodes(const std::vector<std::string>& lines) {
    std::map<int, CgVec3> nodes;
    bool inNode = false;
    for (const auto& ln : lines) {
        std::string tr = cg_trim(ln);
        if (tr.empty()) continue;
        if (tr[0] == '*') { inNode = (cg_keyword(tr) == "*NODE"); continue; }
        if (!inNode || tr[0] == '$') continue;
        auto t = cg_splitWS(ln);
        int nid = 0; CgVec3 p;
        if (t.size() >= 4 && cg_toInt(t[0]) > 0) {
            nid = cg_toInt(t[0]);
            p = {cg_toDouble(t[1]), cg_toDouble(t[2]), cg_toDouble(t[3])};
        } else {
            // 고정폭 (I8,3F16) — 좌표가 칸을 꽉 채워 공백이 사라진 줄
            nid = cg_toInt(cg_fieldN(ln, 0, 8));
            if (nid <= 0) continue;
            auto f = [&](int i) {
                size_t pos = 8 + (size_t)i * 16;
                if (pos >= ln.size()) return 0.0;
                return cg_toDouble(cg_trim(ln.substr(pos, std::min<size_t>(16, ln.size() - pos))));
            };
            p = {f(0), f(1), f(2)};
        }
        if (nid > 0) nodes[nid] = p;
    }
    return nodes;
}

// *SET_NODE_LIST[_TITLE] / *SET_NODE[_TITLE](같은 카드의 별칭 — rbe op 이 이 이름으로 낸다)만 읽는다.
// _GENERATE·_COLUMN 은 값의 뜻이 달라 unsupported 로만 적어 둔다(조용히 틀리게 읽지 않는다).
static std::map<int, CgSetDef> cg_parseNodeSets(const std::vector<std::string>& lines) {
    std::map<int, CgSetDef> sets;
    for (size_t i = 0; i < lines.size(); ++i) {
        std::string tr = cg_trim(lines[i]);
        if (tr.empty() || tr[0] != '*') continue;
        std::string up = cg_keyword(tr);
        if (up.rfind("*SET_NODE", 0) != 0) continue;
        bool supported = (up == "*SET_NODE_LIST" || up == "*SET_NODE_LIST_TITLE" ||
                          up == "*SET_NODE" || up == "*SET_NODE_TITLE");
        bool hasTitle = (up.find("_TITLE") != std::string::npos);

        CgSetDef def;
        def.lineStart = i;
        def.unsupported = !supported;
        int sid = 0;
        bool headerDone = false, titleSkipped = !hasTitle;
        size_t j = i + 1;
        for (; j < lines.size(); ++j) {
            std::string jt = cg_trim(lines[j]);
            if (!jt.empty() && jt[0] == '*') break;
            if (jt.empty() || jt[0] == '$') continue;
            if (!titleSkipped) {
                titleSkipped = true;
                // 제목 줄이 빠진 덱이면 이 줄이 이미 데이터 줄이다 — 먹지 않는다
                if (!cg_looksLikeDataLine(lines[j])) continue;
            }
            if (!headerDone) { sid = cg_toInt(cg_field10(lines[j], 0)); headerDone = true; continue; }
            if (!supported) continue;
            for (int c = 0; c < 8; ++c) {
                std::string tok = cg_field10(lines[j], c);
                if (tok.empty()) break;
                int nid = cg_toInt(tok);
                if (nid > 0) def.nids.push_back(nid);
            }
        }
        def.lineEnd = j;
        if (sid > 0 && sets.find(sid) == sets.end()) sets[sid] = def;
    }
    return sets;
}

static std::vector<CgCnrbDef> cg_parseCnrbs(const std::vector<std::string>& lines) {
    std::vector<CgCnrbDef> out;
    for (size_t i = 0; i < lines.size(); ++i) {
        std::string tr = cg_trim(lines[i]);
        if (tr.empty() || tr[0] != '*') continue;
        std::string up = cg_keyword(tr);
        if (up.rfind("*CONSTRAINED_NODAL_RIGID_BODY", 0) != 0) continue;

        CgCnrbDef def;
        def.keyword   = up;
        def.lineStart = i;
        bool hasTitle = (up.find("_TITLE") != std::string::npos);
        bool titleSkipped = !hasTitle;
        size_t j = i + 1;
        for (; j < lines.size(); ++j) {
            std::string jt = cg_trim(lines[j]);
            if (!jt.empty() && jt[0] == '*') break;
            if (jt.empty() || jt[0] == '$') continue;
            if (!titleSkipped) {
                titleSkipped = true;
                if (!cg_looksLikeDataLine(lines[j])) continue;   // 진짜 제목 줄만 건너뛴다
            }
            ++def.dataLines;
            if (def.dataLines == 1) {
                def.pid    = cg_toInt(cg_field10(lines[j], 0));
                def.cid    = cg_toInt(cg_field10(lines[j], 1));
                def.nsid   = cg_toInt(cg_field10(lines[j], 2));
                def.pnode  = cg_toInt(cg_field10(lines[j], 3));
                def.iprt   = cg_toInt(cg_field10(lines[j], 4));
                def.drflag = cg_toInt(cg_field10(lines[j], 5));
                def.rrflag = cg_toInt(cg_field10(lines[j], 6));
            }
        }
        def.lineEnd = j;
        // LS-DYNA 규칙: NSID 가 0 이면 NSID = PID (Vol_I *CONSTRAINED_NODAL_RIGID_BODY, 'EQ.0: NSID = PID')
        if (def.nsid == 0) def.nsid = def.pid;
        if (def.pid > 0) out.push_back(def);
    }
    return out;
}

// 노드 → 그 노드를 쓰는 PART PID 집합. 요소 연결성으로만 판정한다(이름 패턴·가정 금지).
// *ELEMENT_SOLID 의 ten nodes format 은 한 요소가 두 줄이다 — 1줄 'eid pid', 2줄 노드 10개.
// 한 줄짜리로 착각해 읽으면 노드 ID 를 PID 로 읽어 완전히 틀린다.
static std::map<int, std::set<int>> cg_parseElementOwners(const std::vector<std::string>& lines,
                                                          const std::set<int>& needed) {
    std::map<int, std::set<int>> owners;
    bool inElem = false;
    int pendingPid = 0;       // 두 줄 형식의 첫 줄에서 읽은 PID (다음 데이터 줄이 노드 목록이다)
    for (const auto& ln : lines) {
        std::string tr = cg_trim(ln);
        if (tr.empty()) continue;
        if (tr[0] == '*') {
            std::string up = cg_keyword(tr);
            inElem = (up.rfind("*ELEMENT_SOLID", 0) == 0 || up.rfind("*ELEMENT_SHELL", 0) == 0 ||
                      up.rfind("*ELEMENT_TSHELL", 0) == 0 || up.rfind("*ELEMENT_BEAM", 0) == 0);
            pendingPid = 0;
            continue;
        }
        if (!inElem || tr[0] == '$') continue;
        auto t = cg_elemTokens(ln);
        if (t.empty()) continue;
        if (pendingPid > 0) {
            for (const auto& s : t) {
                int nid = cg_toInt(s);
                if (nid > 0 && needed.count(nid)) owners[nid].insert(pendingPid);
            }
            pendingPid = 0;
            continue;
        }
        if (t.size() >= 2 && t.size() <= 3) {   // ten nodes format 의 첫 줄
            pendingPid = cg_toInt(t[1]);
            continue;
        }
        if (t.size() >= 4) {
            int pid = cg_toInt(t[1]);
            for (size_t c = 2; c < t.size(); ++c) {
                int nid = cg_toInt(t[c]);
                if (nid > 0 && needed.count(nid)) owners[nid].insert(pid);
            }
        }
    }
    return owners;
}

// ============================================================
// 사용 중 ID 집합 — 고정 번호대(9000만/990만/99만)가 원본과 겹치는지 '실행 시' 확인한다.
// cnrb2solid runner 의 '모든 데이터 줄 칸0' 방식은 재질 상수까지 ID 로 세므로 쓰지 않는다.
// 키워드 블록별로 그 블록에서 ID 가 실제로 있는 칸만 본다(ModelAssembler 의 mw_scanMaxId 와 같은 눈).
// *SET_NODE* 의 SID 는 여기서 보지 않는다 — cg_parseNodeSets 가 읽은 것을 그대로 쓴다(파싱 정본은 하나다).
// ============================================================

struct CgUsedIds {
    std::set<int> node, elem, part, sect, mat, curve, set, coord;
};

static CgUsedIds cg_scanUsedIds(const std::vector<std::string>& lines) {
    CgUsedIds u;
    enum Kind { NONE, NODE, ELEM, PART, SECT, MAT, CURVE, COORD };
    Kind kind = NONE;
    bool firstDataTaken = false;
    bool titlePending = false;   // '_TITLE' 카드의 제목 줄 한 줄
    int pendingElem = 0;   // ten nodes format — 다음 데이터 줄은 노드 목록이라 EID 가 아니다
    for (const auto& ln : lines) {
        std::string tr = cg_trim(ln);
        if (tr.empty()) continue;
        if (tr[0] == '*') {
            std::string up = cg_keyword(tr);
            firstDataTaken = false;
            pendingElem = 0;
            if      (up == "*NODE")                          kind = NODE;
            else if (up.rfind("*ELEMENT_", 0) == 0)           kind = ELEM;
            else if (up.rfind("*PART", 0) == 0)               kind = PART;
            else if (up.rfind("*SECTION_", 0) == 0)           kind = SECT;
            else if (up.rfind("*MAT_", 0) == 0)               kind = MAT;
            else if (up.rfind("*DEFINE_CURVE", 0) == 0)       kind = CURVE;
            else if (up.rfind("*DEFINE_COORDINATE", 0) == 0)  kind = COORD;
            else                                              kind = NONE;
            titlePending = (up.find("_TITLE") != std::string::npos);
            continue;
        }
        if (kind == NONE || tr[0] == '$') continue;
        if (kind == NODE) {
            auto t = cg_splitWS(ln);
            int nid = (t.size() >= 4) ? cg_toInt(t[0]) : cg_toInt(cg_fieldN(ln, 0, 8));
            if (nid > 0) u.node.insert(nid);
            continue;
        }
        if (kind == ELEM) {
            auto t = cg_elemTokens(ln);
            if (t.empty()) continue;
            if (pendingElem > 0) { pendingElem = 0; continue; }   // 노드 목록 줄
            if (t.size() >= 2 && t.size() <= 3) { pendingElem = 1; }
            int eid = cg_toInt(t[0]);
            if (eid > 0) u.elem.insert(eid);
            continue;
        }
        if (kind == PART) {                            // *PART 는 (제목,데이터) 쌍이 되풀이된다
            if (!cg_looksLikeDataLine(ln)) continue;   // 제목 줄
            int pid = cg_toInt(cg_field10(ln, 0));
            if (pid > 0) u.part.insert(pid);
            continue;
        }
        // SECTION·MAT·DEFINE_CURVE·DEFINE_COORDINATE — 제목 줄은 '_TITLE 이면 한 줄' 로만 건넌다(cg_parseNodeSets 와 같은 판정).
        // 여기서 cg_looksLikeDataLine 으로 거르면 칸이 하나뿐인 헤더 줄(예: *DEFINE_CURVE_TITLE 의 LCID)이
        // 통째로 걸러지고 다음 데이터 줄이 ID 로 등록돼 충돌 검사가 죽는다.
        if (titlePending) {
            titlePending = false;
            if (!cg_looksLikeDataLine(ln)) continue;   // 진짜 제목 줄만 건넌다
        }
        if (firstDataTaken) continue;                  // 이 카드들은 첫 데이터 줄에만 ID 가 있다
        int id = cg_toInt(cg_field10(ln, 0));
        if (id <= 0) continue;
        firstDataTaken = true;
        switch (kind) {
            case SECT:  u.sect.insert(id);  break;
            case MAT:   u.mat.insert(id);   break;
            case CURVE: u.curve.insert(id); break;
            case COORD: u.coord.insert(id); break;
            default: break;
        }
    }
    return u;
}

// ============================================================
// 지워진 *SET_NODE_LIST 의 SID 를 가리키는 카드.
// ModelAssembler 의 scanDeadReferences 에는 이 축이 없다(PID·EID·NODE 뿐) — 거기에 축을 더하면
// restack/merge 회귀 전체를 다시 봐야 하므로, 이 op 이 자기 파일 안에서 작게 한 번 훑는다.
// 등급 어휘는 공용 스캐너와 같게 쓴다: manual(직접 고치세요) / maybe(칸 뜻 미확인 — rc 에 넣지 않는다)
// ============================================================

struct CgSidFinding {
    size_t line = 0;
    std::string keyword, grade, text;
};

static void cg_scanDeadSids(const std::vector<std::string>& lines,
                            const std::set<int>& deadSids,
                            std::vector<CgSidFinding>& out) {
    if (deadSids.empty()) return;
    std::string kw;
    bool firstData = true;
    for (size_t i = 0; i < lines.size(); ++i) {
        std::string tr = cg_trim(lines[i]);
        if (tr.empty()) continue;
        if (tr[0] == '*') { kw = cg_keyword(tr); firstData = true; continue; }
        if (kw.empty() || tr[0] == '$') continue;
        if (!cg_looksLikeDataLine(lines[i])) continue;
        bool isFirst = firstData;
        firstData = false;

        auto hit = [&](int col) {
            int v = cg_toInt(cg_field10(lines[i], col));
            return v > 0 && deadSids.count(v) > 0;
        };
        auto add = [&](const std::string& grade) {
            out.push_back({i + 1, kw, grade, cg_trim(lines[i])});
        };

        // 칸 뜻을 확인한 카드 — 등급 manual
        if (kw == "*BOUNDARY_SPC_SET" || kw == "*BOUNDARY_PRESCRIBED_MOTION_SET" ||
            kw == "*LOAD_NODE_SET" || kw == "*INITIAL_VELOCITY") {
            if (hit(0)) { add("manual"); continue; }
        } else if (kw.rfind("*CONSTRAINED_EXTRA_NODES_SET", 0) == 0) {
            if (hit(1)) { add("manual"); continue; }
        } else if (kw.rfind("*CONSTRAINED_NODAL_RIGID_BODY", 0) == 0) {
            if (isFirst && hit(2)) { add("manual"); continue; }
        } else if (kw.rfind("*DATABASE_HISTORY_NODE_SET", 0) == 0) {
            for (int c = 0; c < 8; ++c) if (hit(c)) { add("manual"); break; }
            continue;
        } else if (kw.rfind("*SET_NODE_ADD", 0) == 0) {
            if (!isFirst) { for (int c = 0; c < 8; ++c) if (hit(c)) { add("manual"); break; } }
            continue;
        } else if (kw.rfind("*CONTACT", 0) == 0) {
            if (isFirst) {
                int sstyp = cg_toInt(cg_field10(lines[i], 2));
                int mstyp = cg_toInt(cg_field10(lines[i], 3));
                if ((sstyp == 4 && hit(0)) || (mstyp == 4 && hit(1))) { add("manual"); continue; }
            }
        }
        // 화이트리스트 밖 — 세트를 다루는 계열에서만 '혹시' 로 알린다(오탐 폭발 방지)
        if (kw.rfind("*SET_", 0) == 0 || kw.rfind("*CONTACT", 0) == 0 ||
            kw.rfind("*CONSTRAINED", 0) == 0 || kw.rfind("*DATABASE", 0) == 0 ||
            kw.rfind("*LOAD", 0) == 0 || kw.rfind("*BOUNDARY", 0) == 0 ||
            kw.rfind("*INITIAL", 0) == 0) {
            for (int c = 0; c < 8; ++c) if (hit(c)) { add("maybe"); break; }
        }
    }
}

// ============================================================
// 카드 생성 — 칸 폭이 카드마다 다르다. 아래 주석이 각 카드의 폭을 못 박는다.
// ============================================================

static std::string cg_fmt(const char* f, ...) {
    char buf[512];
    va_list ap;
    va_start(ap, f);
    vsnprintf(buf, sizeof(buf), f, ap);
    va_end(ap);
    return std::string(buf);
}

// *DEFINE_CURVE — 헤더 줄 10칸, 점은 20칸 2필드 (ModelAssembler 의 ld_generateDefineCurve 와 같은 형식)
static void cg_emitDefineCurve(std::vector<std::string>& out, int lcid,
                               const std::vector<std::pair<double,double>>& pts) {
    out.push_back("*DEFINE_CURVE");
    out.push_back("$#    lcid      sidr       sfa       sfo      offa      offo    dattyp     lcint");
    out.push_back(cg_fmt("%10d%10d%10s%10s%10s%10s%10d%10d", lcid, 0, "1.0", "1.0", "0.0", "0.0", 0, 0));
    out.push_back("$#                a1                  o1");
    for (const auto& p : pts) out.push_back(cg_fmt("%20.10E%20.10E", p.first, p.second));
}

// 10칸 필드에 실수 하나 — VOL/INER 처럼 작은 값도 10칸 안에 유효숫자를 남긴다
static std::string cg_f10(double v) { return cg_fmt("%10.3E", v); }

// *DEFINE_COORDINATE_SYSTEM — 10칸 × 8필드. Card 1 + Card 2(XP, YP, ZP).
// 로컬 x 를 체결 축에 놓는다. 제로길이 discrete beam 은 노드 간격이 아니라 이 좌표계가 (r, s, t) 를
// 정하므로(Vol_II *MAT_067 Remark 2: "local coordinate system which determines (r, s, t) is given by
// the coordinate ID") 축 분리가 상대변위 크기와 무관하게 성립한다 — 이것이 스프링 3개 방식과의 차이다.
static void cg_emitCoordSystem(std::vector<std::string>& out, int cid, int ax) {
    double xl[3] = {0.0, 0.0, 0.0}, xp[3] = {0.0, 0.0, 0.0};
    xl[ax] = 1.0;                  // 로컬 x축 위의 점 → r = 체결 축
    xp[(ax + 1) % 3] = 1.0;        // 로컬 xy평면 위의 점 → s, t = 나머지 두 전역축
    out.push_back("*DEFINE_COORDINATE_SYSTEM");
    out.push_back("$#     cid        xo        yo        zo        xl        yl        zl      cidl");
    out.push_back(cg_fmt("%10d%10.1f%10.1f%10.1f%10.1f%10.1f%10.1f%10d",
                         cid, 0.0, 0.0, 0.0, xl[0], xl[1], xl[2], 0));
    out.push_back("$#      xp        yp        zp");
    out.push_back(cg_fmt("%10.1f%10.1f%10.1f", xp[0], xp[1], xp[2]));
}

// *SECTION_BEAM — 10칸 × 8필드. Card 1 + Card 2f(ELFORM=6 전용, 재질 146 이외는 이 카드).
// SCOOR 는 빈칸(=0.0)으로 둔다 — |SCOOR| <= 1 이어야 제로길이 빔으로 다뤄진다(Vol_I Remark 6).
// SHRF/QR/CST/NSM 은 discrete beam 에 쓰이지 않고 CA/OFFSET 은 케이블 전용이라 빈칸이다.
// RRCON/SRCON/TRCON 도 빈칸(=0) — 이 셋은 구조 구속이 아니라 로컬 좌표계 갱신 플래그다(Vol_I Remark 7).
// VOL·INER 는 0 이면 안 된다. type 6 빔의 병진 시간증분은 VOL·밀도·병진강성으로, 회전 시간증분은
// INER·회전강성으로 계산된다(Vol_I Remark 12).
static void cg_emitSectionBeam(std::vector<std::string>& out, int secid,
                               double vol, double iner, int cid) {
    out.push_back("*SECTION_BEAM");
    out.push_back("$#   secid    elform      shrf   qr/irid       cst     scoor       nsm     naupd");
    out.push_back(cg_fmt("%10d%10d", secid, 6));
    out.push_back("$#     vol      iner       cid        ca    offset     rrcon     srcon     trcon");
    out.push_back(cg_f10(vol) + cg_f10(iner) + cg_fmt("%10d", cid));
}

// *MAT_NONLINEAR_ELASTIC_DISCRETE_BEAM (MAT_067) — 10칸 × 8필드. Card 1~3 이 전부 필수다.
// 6자유도 각각이 '힘/모멘트 = f(상대 변위/회전)' 곡선 하나를 쓴다. 곡선 ID 0 은 그 자유도에 힘을
// 만들지 않는다(=자유)는 뜻이므로(Vol_II Remark 1 "For null load curve IDs, no forces are computed")
// 회전을 묶으려면 반드시 곡선을 줘야 한다. RO=1.0 이면 VOL 이 곧 요소 질량이다(Vol_I VOL 설명).
// Card 2(감쇠)·Card 3(프리로드)는 쓰지 않지만 카드 자체는 있어야 한다 — 빈 줄 대신 0 을 적는다.
static void cg_emitMat067(std::vector<std::string>& out, int mid,
                          int lcAxial, int lcShear, int lcRot) {
    out.push_back("*MAT_NONLINEAR_ELASTIC_DISCRETE_BEAM");
    out.push_back("$#     mid        ro    lcidtr    lcidts    lcidtt    lcidrr    lcidrs    lcidrt");
    out.push_back(cg_fmt("%10d%10.1f%10d%10d%10d%10d%10d%10d", mid, 1.0,
                         lcAxial, lcShear, lcShear, lcRot, lcRot, lcRot));
    out.push_back("$# lcidtdr   lcidtds   lcidtdt   lcidrdr   lcidrds   lcidrdt");
    out.push_back(cg_fmt("%10d%10d%10d%10d%10d%10d", 0, 0, 0, 0, 0, 0));
    out.push_back("$#     for       fos       fot       mor       mos       mot");
    out.push_back(cg_fmt("%10.1f%10.1f%10.1f%10.1f%10.1f%10.1f", 0.0, 0.0, 0.0, 0.0, 0.0, 0.0));
}

// *PART — 제목 줄 + 10칸 데이터 줄
static void cg_emitPart(std::vector<std::string>& out, const std::string& title,
                        int pid, int secid, int mid) {
    out.push_back("*PART");
    out.push_back(title);
    out.push_back("$#     pid     secid       mid");
    out.push_back(cg_fmt("%10d%10d%10d", pid, secid, mid));
}

// *NODE — 8칸 + 3×F16 (cnrb2solid 와 같은 형식)
static std::string cg_nodeLine(int nid, const CgVec3& p) {
    return cg_fmt("%8d%16.8e%16.8e%16.8e       0       0", nid, p.x, p.y, p.z);
}

// *SET_NODE_LIST_TITLE — 10칸 (ModelAssembler 의 bc_generateSetNode 와 같은 형식)
static void cg_emitSetNode(std::vector<std::string>& out, int sid,
                           const std::vector<int>& nids, const std::string& title) {
    out.push_back("*SET_NODE_LIST_TITLE");
    out.push_back(title);
    out.push_back("$#     sid");
    out.push_back(cg_fmt("%10d", sid));
    out.push_back("$#    nid1      nid2      nid3      nid4      nid5      nid6      nid7      nid8");
    for (size_t i = 0; i < nids.size(); i += 8) {
        std::string ln;
        for (size_t j = i; j < std::min(i + 8, nids.size()); ++j) ln += cg_fmt("%10d", nids[j]);
        out.push_back(ln);
    }
}

// *CONSTRAINED_NODAL_RIGID_BODY_TITLE — 10칸
static void cg_emitCnrb(std::vector<std::string>& out, const std::string& title,
                        int pid, int cid, int nsid, int pnode) {
    out.push_back("*CONSTRAINED_NODAL_RIGID_BODY_TITLE");
    out.push_back(title);
    out.push_back("$#     pid       cid      nsid     pnode      iprt    drflag    rrflag");
    out.push_back(cg_fmt("%10d%10d%10d%10d%10d%10d%10d", pid, cid, nsid, pnode, 0, 0, 0));
}

// *ELEMENT_BEAM — **8칸**이다. 다른 카드(10칸)와 다르다.
// 10칸으로 쓰면 7자리 EID 가 잘려 엉뚱한 PID 로 읽히고 'beam element ... has an undefined PID' 가 난다.
// EID PID N1 N2 만 쓴다. N3(방향 노드)는 SCOOR=2.0 일 때만 읽히고 그때도 optional 이므로 비운다
// — 방향은 *SECTION_BEAM 의 CID 가 전담한다(Vol_I *ELEMENT_BEAM N3 설명).
// RT1/RR1/RT2/RR2(릴리즈)는 반드시 0(빈칸)이다 — 릴리즈를 건 노드는 nodal rigid body 에 넣을 수
// 없는데(Vol_I *ELEMENT_BEAM Remark 2) 우리 팬텀 노드 둘은 양쪽 CNRB 에 들어간다.
static std::string cg_elementBeamLine(int eid, int pid, int n1, int n2) {
    return cg_fmt("%8d%8d%8d%8d", eid, pid, n1, n2);
}

// ============================================================
// 핵심 변환
// ============================================================

struct CgJoint {
    int origPid = 0, origCid = 0, origPnode = 0, origNsid = 0;
    int pnodeA = 0, pnodeB = 0;              // 원 PNODE 를 소속(요소 연결성)대로 한쪽 강체에만 넘긴다
    int sidePidA = 0, sidePidB = 0;          // 원 모델에서 CNRB 가 잇던 두 파트(작은 PID 가 A)
    std::vector<int> nodesA, nodesB;         // 원 세트의 등장 순서를 지킨 실재 노드
    CgVec3 anchor;
    CgVec3 cenA, cenB;
    int newPidA = 0, newPidB = 0, sidA = 0, sidB = 0;
    int nA = 0, nB = 0;                      // 팬텀 노드 2개 — 앵커에 겹쳐 둔다(제로길이 빔)
    int eid = 0;                             // discrete beam 1개
    size_t cnrbStart = 0, cnrbEnd = 0, setStart = 0, setEnd = 0;
};

static double cg_comp(const CgVec3& v, int i) { return i == 0 ? v.x : (i == 1 ? v.y : v.z); }

static std::string cg_num(double v) { return cg_fmt("%g", v); }

static std::string cg_idList(const std::set<int>& s, size_t maxN) {
    std::string r;
    size_t n = 0;
    for (int v : s) {
        if (n >= maxN) { r += " ..."; break; }
        r += (n ? " " : "") + std::to_string(v);
        ++n;
    }
    return r;
}

int cnrb2spring_apply(std::vector<std::string>& lines,
                      const Cnrb2SpringConfig& cfg,
                      ConsoleOutput& console)
{
    // ── 1. 값 검증 (덱을 건드리기 전에 끝낸다) ──────────────────────────────
    if (cfg.axis != 'x' && cfg.axis != 'y' && cfg.axis != 'z') {
        console.error("[cnrb2spring] axis 를 반드시 지정해야 합니다. 허용값: x, y, z "
                      "(나사 축 — 이 축에 k_axial 이, 나머지 두 축에 유격 곡선이 붙습니다)");
        return -1;
    }
    struct { const char* name; double v; } pos[] = {
        {"gap", cfg.gap}, {"k_engage", cfg.kEngage}, {"k_axial", cfg.kAxial},
        {"curve_range", cfg.curveRange}};
    for (const auto& p : pos) {
        if (!std::isfinite(p.v)) {
            console.error(std::string("[cnrb2spring] ") + p.name + " 값이 유한하지 않습니다 (nan/inf)");
            return -1;
        }
        if (p.v <= 0.0) {
            console.error(std::string("[cnrb2spring] ") + p.name + " 는 0 보다 커야 합니다 (" +
                          cg_num(p.v) + ")");
            return -1;
        }
    }
    // k_rot 만 0 을 허용한다 — 0 은 '회전 3자유도를 풀어 둔다' 는 뜻이다.
    // MAT_067 은 곡선 ID 0 인 자유도에 힘을 만들지 않으므로(Vol_II Remark 1) 곡선을 아예 내지 않는다.
    if (!std::isfinite(cfg.kRot)) {
        console.error("[cnrb2spring] k_rot 값이 유한하지 않습니다 (nan/inf)");
        return -1;
    }
    if (cfg.kRot < 0.0) {
        console.error("[cnrb2spring] k_rot 는 0 이상이어야 합니다 (" + cg_num(cfg.kRot) +
                      ") — 0 은 회전 3자유도를 풀어 둔다는 뜻입니다");
        return -1;
    }
    if (cfg.curveRange <= cfg.gap) {
        console.error("[cnrb2spring] curve_range(" + cg_num(cfg.curveRange) +
                      ") 는 gap(" + cg_num(cfg.gap) + ") 보다 커야 합니다 — 유격 구간이 곡선 가로축을 덮어버립니다");
        return -1;
    }
    double shearF = cfg.kEngage * (cfg.curveRange - cfg.gap);
    double axialF = cfg.kAxial * cfg.curveRange;
    // 회전 곡선 가로축 반범위 [rad]. 선형 곡선이라 이 범위 밖은 MAT_067 이 외삽해 같은 기울기로 이어진다
    // (Vol_II Remark 3: "displacement values fall outside of the defined range ... will be extrapolated").
    const double ROT_RANGE = 1.0;
    double rotM = cfg.kRot * ROT_RANGE;
    if (!std::isfinite(shearF) || !std::isfinite(axialF) || !std::isfinite(rotM)) {
        console.error("[cnrb2spring] 곡선 좌표가 유한하지 않습니다 (k_engage·k_axial·k_rot·curve_range 를 줄이세요)");
        return -1;
    }
    // *SECTION_BEAM 의 VOL·INER. 매뉴얼은 'reasonable non-zero values' 라고만 하고 수치 기준을 주지 않는다
    // (Vol_I Remark 12). 임의의 상수를 박는 대신 기준 시간증분 DT_REF 에서 거꾸로 잡는다 —
    // Δt ≈ 2*sqrt(m/k) 이므로 m = k*(Δt/2)^2 이면 이 빔이 그 Δt 아래로 모델을 끌어내리지 않는다.
    // RO=1.0 이라 VOL 이 곧 요소 질량이고 두 팬텀 노드에 반씩 실린다(Vol_I *SECTION_BEAM VOL 설명).
    const double DT_REF = 5.0e-7;   // [s] — 가정값(labeled assumption)
    const double DT_H = 0.5 * DT_REF;
    double volMass = std::max(cfg.kAxial, cfg.kEngage) * DT_H * DT_H;              // [t]
    double inerVal = std::max(std::max(cfg.kAxial, cfg.kEngage), cfg.kRot) * DT_H * DT_H;  // [t*mm^2]
    if (!std::isfinite(volMass) || !std::isfinite(inerVal) || volMass <= 0.0 || inerVal <= 0.0) {
        console.error("[cnrb2spring] *SECTION_BEAM 의 VOL/INER 를 계산할 수 없습니다 "
                      "(k_axial·k_engage·k_rot 를 줄이세요) — 둘 다 0 이 아니어야 합니다");
        return -1;
    }
    if (cfg.nodeIdStart <= 0 || cfg.elemIdStart <= 0 || cfg.cardIdStart <= 0) {
        console.error("[cnrb2spring] node_id_start·elem_id_start·card_id_start 는 0 보다 커야 합니다");
        return -1;
    }
    if (cfg.pidRefs != "strict" && cfg.pidRefs != "warn") {
        console.error("[cnrb2spring] pid_refs 값 '" + cfg.pidRefs + "' 를 모릅니다. 허용값: strict, warn");
        return -1;
    }
    const int ax = cfg.axis - 'x';   // 0=x 1=y 2=z
    static const char* AXN[3] = {"X", "Y", "Z"};

    // ── 2. 덱 파싱 ──────────────────────────────────────────────────────────
    // 이 op 이 읽는 카드는 전부 고정폭(8칸/10칸)으로 읽는다. 콤마 자유형식이 섞여 있으면 칸 자리가
    // 통째로 어긋나 노드 ID 를 PID 로 읽는 식으로 조용히 틀린다 — 읽지 않고 rc=1 로 알린다.
    {
        std::string kw;
        for (const auto& ln : lines) {
            std::string tr = cg_trim(ln);
            if (tr.empty()) continue;
            if (tr[0] == '*') { kw = cg_keyword(tr); continue; }
            if (tr[0] == '$' || tr.find(',') == std::string::npos) continue;
            if (kw == "*NODE" || kw.rfind("*ELEMENT_", 0) == 0 || kw.rfind("*SET_NODE", 0) == 0 ||
                kw.rfind("*CONSTRAINED_NODAL_RIGID_BODY", 0) == 0) {
                console.error("[cnrb2spring] " + kw + " 에 콤마 자유형식 줄이 있습니다: " + tr +
                              " — 이 op 은 고정폭(8칸/10칸)으로만 읽습니다");
                return -1;
            }
        }
    }
    auto nodes  = cg_parseNodes(lines);
    auto sets   = cg_parseNodeSets(lines);
    auto cnrbs  = cg_parseCnrbs(lines);
    if (cnrbs.empty()) {
        console.error("[cnrb2spring] 덱에 *CONSTRAINED_NODAL_RIGID_BODY 가 없습니다");
        return -1;
    }
    std::set<int> want(cfg.targetPids.begin(), cfg.targetPids.end());
    {
        std::set<int> have;
        for (const auto& c : cnrbs) have.insert(c.pid);
        std::set<int> missing;
        for (int p : want) if (!have.count(p)) missing.insert(p);
        if (!missing.empty()) {
            console.error("[cnrb2spring] target_pids 에 적은 PID 인 CNRB 가 덱에 없습니다: " +
                          cg_idList(missing, 10));
            return -1;
        }
    }
    std::map<int, int> sidUse;
    for (const auto& c : cnrbs) sidUse[c.nsid]++;

    // ── 3. 대상 선별과 노드 목록 ────────────────────────────────────────────
    std::vector<CgJoint> joints;
    std::vector<const CgCnrbDef*> picked;
    std::set<int> neededNodes;
    bool hardFail = false;

    for (const auto& c : cnrbs) {
        bool explicitTarget = !want.empty() && want.count(c.pid) > 0;
        if (!want.empty() && !explicitTarget) continue;
        auto reject = [&](const std::string& msg) {
            if (explicitTarget) { console.error("[cnrb2spring] " + msg); hardFail = true; }
            else console.warning("[cnrb2spring] " + msg + " — 건너뜁니다");
        };
        if (c.dataLines > 1) {
            reject("PID " + std::to_string(c.pid) + ": " + c.keyword +
                   " 블록에 데이터 줄이 " + std::to_string(c.dataLines) +
                   "줄입니다(_SPC·_INERTIA 의 추가 카드) — 두 강체 중 어느 쪽에 줄지 정할 수 없습니다");
            continue;
        }
        if (c.drflag != 0 || c.rrflag != 0) {
            reject("PID " + std::to_string(c.pid) + ": DRFLAG/RRFLAG 가 0 이 아닙니다(" +
                   std::to_string(c.drflag) + "/" + std::to_string(c.rrflag) +
                   ") — DOF 해제를 두 강체에 나눌 물리적 근거가 없습니다");
            continue;
        }
        auto it = sets.find(c.nsid);
        if (it == sets.end()) {
            reject("PID " + std::to_string(c.pid) + ": NSID " + std::to_string(c.nsid) +
                   " 인 *SET_NODE_LIST 를 찾을 수 없습니다");
            continue;
        }
        if (it->second.unsupported) {
            reject("PID " + std::to_string(c.pid) + ": NSID " + std::to_string(c.nsid) +
                   " 세트가 _GENERATE/_COLUMN 형식입니다 — 이 op 은 읽지 않습니다");
            continue;
        }
        if (sidUse[c.nsid] > 1) {
            reject("PID " + std::to_string(c.pid) + ": NSID " + std::to_string(c.nsid) +
                   " 세트를 CNRB " + std::to_string(sidUse[c.nsid]) +
                   "개가 공유합니다 — 세트를 지우면 나머지가 깨집니다");
            continue;
        }
        CgJoint j;
        j.origPid = c.pid; j.origCid = c.cid; j.origPnode = c.pnode; j.origNsid = c.nsid;
        j.cnrbStart = c.lineStart; j.cnrbEnd = c.lineEnd;
        j.setStart = it->second.lineStart; j.setEnd = it->second.lineEnd;
        joints.push_back(j);
        picked.push_back(&c);
        std::set<int> seen;
        for (int nid : it->second.nids) {
            if (!seen.insert(nid).second) continue;
            neededNodes.insert(nid);
        }
    }
    if (hardFail) return -1;
    if (joints.empty()) {
        console.error("[cnrb2spring] 변환할 CNRB 가 없습니다 (경고만 쌓이고 덱이 바뀌지 않았습니다)");
        return -1;
    }

    auto owners = cg_parseElementOwners(lines, neededNodes);

    // ── 4. 두 파트 판정(요소 연결성) · 앵커 · 축 교차검증 ────────────────────
    std::vector<CgJoint> kept;
    for (size_t k = 0; k < joints.size(); ++k) {
        CgJoint j = joints[k];
        const CgCnrbDef& c = *picked[k];
        bool explicitTarget = !want.empty();
        auto reject = [&](const std::string& msg) {
            if (explicitTarget) { console.error("[cnrb2spring] " + msg); hardFail = true; }
            else console.warning("[cnrb2spring] " + msg + " — 건너뜁니다");
        };
        const auto& raw = sets[c.nsid].nids;
        std::vector<int> real;
        std::set<int> seen;
        int ghost = 0, dup = 0;
        for (int nid : raw) {
            if (!seen.insert(nid).second) { ++dup; continue; }
            if (!nodes.count(nid)) { ++ghost; continue; }
            real.push_back(nid);
        }
        if (ghost > 0)
            console.warning("[cnrb2spring] PID " + std::to_string(c.pid) + ": *NODE 에 없는 ID " +
                            std::to_string(ghost) + "개를 세트에서 제외했습니다");
        if (dup > 0)
            console.warning("[cnrb2spring] PID " + std::to_string(c.pid) + ": 세트 안 중복 ID " +
                            std::to_string(dup) + "개를 뗐습니다");
        std::map<int, std::vector<int>> byPart;
        int orphan = 0, shared = 0;
        for (int nid : real) {
            auto oi = owners.find(nid);
            if (oi == owners.end() || oi->second.empty()) { ++orphan; continue; }
            if (oi->second.size() > 1) { ++shared; continue; }
            byPart[*oi->second.begin()].push_back(nid);
        }
        if (orphan > 0)
            console.warning("[cnrb2spring] PID " + std::to_string(c.pid) + ": 어떤 요소에도 붙지 않은 노드 " +
                            std::to_string(orphan) + "개를 제외했습니다");
        if (shared > 0) {
            reject("PID " + std::to_string(c.pid) + ": 노드 " + std::to_string(shared) +
                   "개가 두 파트 요소에 함께 쓰입니다(공유절점) — 두 파트가 이미 붙어 있어 유격이 물리적으로 불가능합니다");
            continue;
        }
        if (byPart.size() != 2) {
            std::set<int> pl;
            for (const auto& kv : byPart) pl.insert(kv.first);
            reject("PID " + std::to_string(c.pid) + ": CNRB 가 잇는 파트가 " +
                   std::to_string(byPart.size()) + "개입니다(2개여야 합니다). 파트: " + cg_idList(pl, 10));
            continue;
        }
        auto pit = byPart.begin();
        j.sidePidA = pit->first;  j.nodesA = pit->second;  ++pit;
        j.sidePidB = pit->first;  j.nodesB = pit->second;   // map 이 오름차순이라 작은 PID 가 Side A
        auto cen = [&](const std::vector<int>& v) {
            CgVec3 s;
            for (int nid : v) { const CgVec3& p = nodes[nid]; s.x += p.x; s.y += p.y; s.z += p.z; }
            double n = (double)v.size();
            return CgVec3{s.x / n, s.y / n, s.z / n};
        };
        // PNODE 는 소속된 쪽 강체에만 넘긴다. 반대쪽 강체에 넘기면 그 노드가 두 강체에 함께 들어가고,
        // LS-DYNA 가 PNODE 좌표를 그 강체 무게중심으로 옮겨 실메시 노드가 끌려간다(Vol_I *CONSTRAINED_NODAL_RIGID_BODY).
        if (j.origPnode > 0) {
            if (std::find(j.nodesA.begin(), j.nodesA.end(), j.origPnode) != j.nodesA.end())
                j.pnodeA = j.origPnode;
            else if (std::find(j.nodesB.begin(), j.nodesB.end(), j.origPnode) != j.nodesB.end())
                j.pnodeB = j.origPnode;
            else
                console.warning("[cnrb2spring] PID " + std::to_string(c.pid) + ": PNODE " +
                                std::to_string(j.origPnode) +
                                " 은 어느 강체에 속하는지 정할 수 없어 버렸습니다(양쪽 다 PNODE=0)");
        }
        j.cenA = cen(j.nodesA);
        j.cenB = cen(j.nodesB);
        j.anchor = {(j.cenA.x + j.cenB.x) / 2.0, (j.cenA.y + j.cenB.y) / 2.0,
                    (j.cenA.z + j.cenB.z) / 2.0};
        CgVec3 d{j.cenB.x - j.cenA.x, j.cenB.y - j.cenA.y, j.cenB.z - j.cenA.z};
        int big = 0;
        for (int i = 1; i < 3; ++i) if (std::fabs(cg_comp(d, i)) > std::fabs(cg_comp(d, big))) big = i;
        if (big != ax)
            console.warning("[cnrb2spring] PID " + std::to_string(c.pid) + ": axis=" +
                            std::string(1, cfg.axis) + " 라고 했지만 두 파트 간격의 최대 성분은 " +
                            std::string(AXN[big]) + " 입니다 (dx,dy,dz=" + cg_num(d.x) + "," +
                            cg_num(d.y) + "," + cg_num(d.z) + ")");
        if (j.nodesA.size() < 3 || j.nodesB.size() < 3)
            console.warning("[cnrb2spring] PID " + std::to_string(c.pid) + ": 한쪽 노드가 " +
                            std::to_string(std::min(j.nodesA.size(), j.nodesB.size())) +
                            "개입니다 — 회전관성이 거의 없는 강체에 k_axial 이 붙어 시간증분이 급감할 수 있습니다");
        kept.push_back(j);
    }
    if (hardFail) return -1;
    if (kept.empty()) {
        console.error("[cnrb2spring] 변환할 CNRB 가 없습니다 (경고만 쌓이고 덱이 바뀌지 않았습니다)");
        return -1;
    }
    joints = kept;
    const int N = (int)joints.size();

    // k_rot=0 이면 회전 3자유도가 자유다 — 한 파트 쌍에 조인트가 하나뿐이면 그 점을 중심으로 돈다
    if (cfg.kRot <= 0.0) {
        std::map<std::pair<int,int>, int> pairCount;
        for (const auto& j : joints) pairCount[{j.sidePidA, j.sidePidB}]++;
        for (const auto& kv : pairCount)
            if (kv.second == 1)
                console.warning("[cnrb2spring] PART " + std::to_string(kv.first.first) + " <-> PART " +
                                std::to_string(kv.first.second) +
                                " 사이 조인트가 1개인데 k_rot=0 입니다 — 회전 3자유도가 자유라 두 파트가 이 점을 "
                                "중심으로 돕니다(원 CNRB 는 회전도 구속했습니다)");
    }
    if (cfg.curveRange > 20.0 * cfg.gap)
        console.warning("[cnrb2spring] curve_range(" + cg_num(cfg.curveRange) + ") 가 gap(" +
                        cg_num(cfg.gap) + ") 의 20배를 넘습니다 — LS-DYNA 가 곡선을 균일 격자로 "
                        "재이산화하면 자유유격 평탄부가 뭉개질 수 있습니다");

    // ── 5. ID 배정과 충돌 검사 (덱을 만들기 전에) ───────────────────────────
    const int B = cfg.cardIdStart;
    const int lcAxial = B + 0, lcShear = B + 1, lcRot = B + 2;
    const int matId = B + 0, secId = B + 0, coordId = B + 0, pidBeam = B + 0;
    const int lcRotUse = (cfg.kRot > 0.0) ? lcRot : 0;   // 0 = 그 자유도는 자유
    std::set<int> newNodeIds, newElemIds, newPartIds, newSetIds;
    for (int k = 0; k < N; ++k) {
        CgJoint& j = joints[k];
        j.nA  = cfg.nodeIdStart + 2 * k;      newNodeIds.insert(j.nA);
        j.nB  = cfg.nodeIdStart + 2 * k + 1;  newNodeIds.insert(j.nB);
        j.eid = cfg.elemIdStart + k;          newElemIds.insert(j.eid);
        j.newPidA = B + 10 + 2 * k;  j.newPidB = B + 11 + 2 * k;
        j.sidA = j.newPidA;          j.sidB = j.newPidB;   // 세트와 파트는 다른 네임스페이스다(NSID=PID 규약)
        newPartIds.insert(j.newPidA); newPartIds.insert(j.newPidB);
        newSetIds.insert(j.sidA);     newSetIds.insert(j.sidB);
    }
    newPartIds.insert(pidBeam);

    CgUsedIds used = cg_scanUsedIds(lines);
    for (const auto& kv : sets) used.set.insert(kv.first);  // SID 는 세트 파싱 정본에서 그대로 받는다
    for (const auto& c : cnrbs) used.part.insert(c.pid);   // CNRB 의 PID 는 파트 네임스페이스다
    for (const auto& j : joints) { used.part.erase(j.origPid); used.set.erase(j.origNsid); }

    struct Ns { const char* name; const std::set<int>* mine; const std::set<int>* used; const char* key; };
    std::set<int> mySect{secId}, myMat{matId}, myCurve{lcAxial, lcShear}, myCoord{coordId};
    if (lcRotUse > 0) myCurve.insert(lcRot);
    Ns nss[] = {
        {"노드",   &newNodeIds, &used.node,  "node_id_start"},
        {"요소",   &newElemIds, &used.elem,  "elem_id_start"},
        {"파트",   &newPartIds, &used.part,  "card_id_start"},
        {"세트",   &newSetIds,  &used.set,   "card_id_start"},
        {"섹션",   &mySect,     &used.sect,  "card_id_start"},
        {"재질",   &myMat,      &used.mat,   "card_id_start"},
        {"곡선",   &myCurve,    &used.curve, "card_id_start"},
        {"좌표계", &myCoord,    &used.coord, "card_id_start"},
    };
    bool clash = false;
    for (const auto& n : nss) {
        std::set<int> hit;
        for (int v : *n.mine) if (n.used->count(v)) hit.insert(v);
        if (!hit.empty()) {
            clash = true;
            console.error(std::string("[cnrb2spring] ") + n.name + " ID 가 원본 덱과 겹칩니다 (" +
                          std::to_string(hit.size()) + "개): " + cg_idList(hit, 5) +
                          " — " + n.key + " 를 바꾸세요");
        }
        int mx = n.mine->empty() ? 0 : *n.mine->rbegin();
        if (mx > 99999999) {
            clash = true;
            console.error(std::string("[cnrb2spring] ") + n.name + " ID 가 I8 상한(99999999)을 넘습니다: " +
                          std::to_string(mx) + " — " + n.key + " 를 낮추세요");
        }
    }
    if (clash) return -1;

    // ── 6. 카드 생성 ────────────────────────────────────────────────────────
    std::vector<std::string> ins;
    ins.push_back("$");
    ins.push_back("$ === cnrb2spring: CNRB 체결점 " + std::to_string(N) +
                  "개를 두 강체 + 제로길이 discrete beam(ELFORM=6) 유격 조인트로 쪼갰습니다 ===");
    ins.push_back(cg_fmt("$ gap=%g mm  k_engage=%g N/mm  k_axial=%g N/mm  k_rot=%g N*mm/rad  "
                         "curve_range=%g mm  axis=%c (로컬 r)",
                         cfg.gap, cfg.kEngage, cfg.kAxial, cfg.kRot, cfg.curveRange, cfg.axis));
    ins.push_back(cg_fmt("$ *SECTION_BEAM VOL=%g (RO=1.0 이라 요소 질량[t]) INER=%g [t*mm^2] "
                         "— 기준 시간증분 %g s 로 잡았습니다", volMass, inerVal, DT_REF));
    ins.push_back("$ 위 값은 실측이 아닌 가정값입니다(labeled assumption).");
    // 축(로컬 r) 곡선 — 유격 없이 기울기 k_axial
    cg_emitDefineCurve(ins, lcAxial, {{-cfg.curveRange, -axialF}, {cfg.curveRange, axialF}});
    // 전단(로컬 s·t) 곡선 — 가장 음수부터. ±gap 구간은 힘 0(자유유격), 그 밖은 기울기 k_engage
    cg_emitDefineCurve(ins, lcShear, {{-cfg.curveRange, -shearF}, {-cfg.gap, 0.0},
                                      {cfg.gap, 0.0}, {cfg.curveRange, shearF}});
    // 회전(로컬 r·s·t) 곡선 — 모멘트 vs 상대회전[rad]. k_rot=0 이면 아예 내지 않는다(=회전 자유)
    if (lcRotUse > 0)
        cg_emitDefineCurve(ins, lcRot, {{-ROT_RANGE, -rotM}, {ROT_RANGE, rotM}});
    cg_emitCoordSystem(ins, coordId, ax);
    cg_emitSectionBeam(ins, secId, volMass, inerVal, coordId);
    cg_emitMat067(ins, matId, lcAxial, lcShear, lcRotUse);
    cg_emitPart(ins, cg_fmt("cnrb2spring joint r=%s (gap=%g)", AXN[ax], cfg.gap), pidBeam, secId, matId);

    // 두 팬텀 노드를 같은 자리에 둔다. MAT_067 은 "The two nodes defining a beam may be coincident to
    // give a zero length beam" 이라 간격이 필요 없고, 방향은 CID 가 전담한다 — eps 개념이 사라진 자리다.
    ins.push_back("*NODE");
    for (auto& j : joints) {
        ins.push_back(cg_nodeLine(j.nA, j.anchor));
        ins.push_back(cg_nodeLine(j.nB, j.anchor));
    }

    for (auto& j : joints) {
        std::vector<int> a = j.nodesA, b = j.nodesB;
        a.push_back(j.nA);
        b.push_back(j.nB);
        cg_emitSetNode(ins, j.sidA, a, "cnrb2spring " + std::to_string(j.origPid) + " side A");
        cg_emitSetNode(ins, j.sidB, b, "cnrb2spring " + std::to_string(j.origPid) + " side B");
    }
    for (auto& j : joints) {
        // PNODE 는 소속된 쪽에만 붙인다(반대쪽은 0). 원 PNODE 노드는 지우지 않는다.
        cg_emitCnrb(ins, "cnrb2spring " + std::to_string(j.origPid) + " side A",
                    j.newPidA, j.origCid, j.sidA, j.pnodeA);
        cg_emitCnrb(ins, "cnrb2spring " + std::to_string(j.origPid) + " side B",
                    j.newPidB, j.origCid, j.sidB, j.pnodeB);
    }
    ins.push_back("*ELEMENT_BEAM");
    ins.push_back("$#    eid     pid      n1      n2      n3     rt1     rr1     rt2     rr2   local");
    for (auto& j : joints)
        ins.push_back(cg_elementBeamLine(j.eid, pidBeam, j.nA, j.nB));

    for (const auto& l : ins) {
        std::string up = cg_upper(l);
        if (up.find("NAN") != std::string::npos || up.find("INF") != std::string::npos) {
            console.error("[cnrb2spring] 만들어 넣을 줄에 nan/inf 가 있습니다: " + l);
            return -1;
        }
        if (cg_trim(l).empty()) {
            console.error("[cnrb2spring] 삽입 블록에 빈 줄이 생겼습니다 — "
                          "*ELEMENT_BEAM 이 빈 줄을 요소로 읽어 'element id 0 is invalid' 가 납니다");
            return -1;
        }
    }

    // ── 7. 원 CNRB·SET 블록 삭제 → 죽은 참조 보고 → 삽입 ────────────────────
    std::vector<bool> rm(lines.size(), false);
    std::set<int> deadPids, deadSids;
    for (const auto& j : joints) {
        for (size_t i = j.cnrbStart; i < j.cnrbEnd && i < lines.size(); ++i) rm[i] = true;
        for (size_t i = j.setStart;  i < j.setEnd  && i < lines.size(); ++i) rm[i] = true;
        deadPids.insert(j.origPid);
        deadSids.insert(j.origNsid);
    }
    // 지운 줄을 '빼지 않고' 표시 줄로 바꾼다 — 죽은 참조 보고의 줄 번호가 입력 덱 기준 그대로 남는다
    // (공용 스캐너의 헤더 블록이 '줄 번호는 이 op 가 읽은 입력 덱 기준' 이라고 적는다).
    // 표시 줄은 '$' 주석이라 어떤 스캐너도 데이터로 읽지 않고, 마지막 조립에서 걷어낸다.
    static const char* REMOVED = "$ cnrb2spring: (지운 CNRB/*SET_NODE_LIST 자리 — 줄 번호 보존용 표시)";
    std::vector<std::string> work;
    work.reserve(lines.size());
    for (size_t i = 0; i < lines.size(); ++i) work.push_back(rm[i] ? REMOVED : lines[i]);

    // PID 축 — restack/merge 와 같은 코드(ModelAssembler::processDeadReferences)로 본다.
    // newPids 를 비워 '보고 전용' 으로 쓴다: 강체 하나가 둘로 쪼개지므로 merge 의
    // '죽은 PID 하나 → 새 PID 하나' 이관 가정이 성립하지 않고, 어느 쪽 강체가 원 경계조건을
    // 이어받아야 하는지는 물리로 정할 수 없다(사람이 정해야 한다).
    KooRemapper::ModelAssembler ma;
    std::vector<std::string> addedBlocks, refLines;
    std::string headerBlock;
    bool pidOk = ma.processDeadReferences(work, deadPids, {}, {}, {}, "cnrb2spring",
                                          cfg.pidRefs, addedBlocks, headerBlock, refLines);
    for (const auto& l : refLines) console.info(l);

    // SID 축 — 공용 스캐너에 없는 축이라 여기서 작게 훑는다
    std::vector<CgSidFinding> sidFindings;
    cg_scanDeadSids(work, deadSids, sidFindings);
    size_t sidHard = 0;
    for (const auto& f : sidFindings) {
        std::string msg = "[cnrb2spring] 지운 *SET_NODE_LIST 를 가리키는 자리 [" + f.grade + "] line " +
                          std::to_string(f.line) + " " + f.keyword + ": " + f.text;
        if (f.grade == "maybe") console.warning(msg);
        else { console.warning(msg); ++sidHard; }
    }
    bool sidOk = !(sidHard > 0 && cfg.pidRefs != "warn");

    std::vector<std::string> head;
    if (!headerBlock.empty()) {
        head.push_back("$ cnrb2spring: 아래 KOOREMAPPER-PIDREF 보고는 공용 죽은-참조 스캐너가 만든 것이라 "
                       "문구에 restack/merge 가 들어갑니다");
        std::istringstream hs(headerBlock);
        std::string hl;
        while (std::getline(hs, hl)) if (!cg_trim(hl).empty()) head.push_back(hl);
    }
    if (!sidFindings.empty()) {
        head.push_back("$ KOOREMAPPER-SETREF: " + std::to_string(sidFindings.size()) +
                       " reference(s) — cnrb2spring 이 지운 *SET_NODE_LIST 의 SID 를 가리키던 자리입니다");
        for (const auto& f : sidFindings)
            head.push_back("$ KOOREMAPPER-SETREF [sid] line " + std::to_string(f.line) + " " +
                           f.keyword + " (" + f.grade + "): " + f.text);
        head.push_back("$ KOOREMAPPER-SETREF-END");
    }

    std::vector<std::string> pre;   // 참조 처리가 만든 새 키워드 블록(newPids 가 비면 보통 없다)
    for (const auto& blk : addedBlocks) {
        std::istringstream bs(blk);
        std::string bl;
        while (std::getline(bs, bl)) if (!cg_trim(bl).empty()) pre.push_back(bl);
    }

    std::vector<std::string> out;
    out.reserve(work.size() + head.size() + pre.size() + ins.size() + 2);
    bool headDone = head.empty(), endDone = false;
    for (const auto& ln : work) {
        if (ln == REMOVED) continue;
        std::string up = cg_upper(cg_trim(ln));
        if (!endDone && up == "*END") {
            for (const auto& l : pre) out.push_back(l);
            for (const auto& l : ins) out.push_back(l);
            endDone = true;
        }
        out.push_back(ln);
        if (!headDone && up == "*KEYWORD") {
            for (const auto& l : head) out.push_back(l);
            headDone = true;
        }
    }
    if (!headDone) out.insert(out.begin(), head.begin(), head.end());   // *KEYWORD 가 없는 덱
    if (!endDone) {
        for (const auto& l : pre) out.push_back(l);
        for (const auto& l : ins) out.push_back(l);
        out.push_back("*END");
    }

    // ── 8. 보고 ─────────────────────────────────────────────────────────────
    for (const auto& j : joints)
        console.println(cg_fmt("[cnrb2spring] PID %d: PART %d(노드 %zu) <-> PART %d(노드 %zu), 축=%s, "
                               "앵커=(%.4g, %.4g, %.4g), 새 PID %d/%d",
                               j.origPid, j.sidePidA, j.nodesA.size(), j.sidePidB, j.nodesB.size(),
                               AXN[ax], j.anchor.x, j.anchor.y, j.anchor.z, j.newPidA, j.newPidB));
    for (const auto& j : joints)
        if (j.pnodeA > 0 || j.pnodeB > 0)
            console.println(cg_fmt("[cnrb2spring] PID %d: PNODE %d 를 side %s 강체로 넘겼습니다(노드는 지우지 않습니다)",
                                   j.origPid, j.pnodeA > 0 ? j.pnodeA : j.pnodeB,
                                   j.pnodeA > 0 ? "A" : "B"));
    std::string curveList = cg_fmt("%d,%d", lcAxial, lcShear);
    if (lcRotUse > 0) curveList += cg_fmt(",%d", lcRot);
    console.println(cg_fmt("[cnrb2spring] 새 ID — 노드 %d..%d, 요소 %d..%d, 파트/세트 %d..%d, "
                           "곡선 %s, 재질 %d, 섹션 %d, 좌표계 %d",
                           cfg.nodeIdStart, cfg.nodeIdStart + 2 * N - 1,
                           cfg.elemIdStart, cfg.elemIdStart + N - 1,
                           B, B + 11 + 2 * (N - 1), curveList.c_str(), matId, secId, coordId));
    console.println(cg_fmt("[cnrb2spring] 로컬계 CID %d — r=%s(k_axial), s·t=전단(±%g mm 유격). "
                           "제로길이 빔이라 축 분리가 상대변위 크기와 무관합니다",
                           coordId, AXN[ax], cfg.gap));
    if (lcRotUse > 0)
        console.println(cg_fmt("[cnrb2spring] 회전 3자유도를 k_rot=%g N*mm/rad 로 구속했습니다 "
                               "(원 CNRB 와 같은 자리)", cfg.kRot));
    else
        console.warning("[cnrb2spring] k_rot=0 — 회전 3자유도를 풀었습니다. 원 CNRB 는 회전도 구속했습니다");
    console.println(cg_fmt("[cnrb2spring] *SECTION_BEAM VOL=%g INER=%g — 조인트마다 질량 %g t 를 "
                           "더합니다(합계 %g t)", volMass, inerVal, volMass, volMass * N));
    console.println(cg_fmt("[cnrb2spring] 삭제: CNRB %d, *SET_NODE_LIST %d", N, (int)deadSids.size()));
    console.println(cg_fmt("[cnrb2spring] 죽은 참조: PID 축 %s, SID 축 %zu건",
                           pidOk ? "0건" : "남음", sidFindings.size()));

    if (!pidOk) {
        console.error("[cnrb2spring] 지운 CNRB 의 PID 를 가리키는 자리가 남았습니다 "
                      "(pid_refs: warn 으로 낮출 수 있습니다)");
        return -1;
    }
    if (!sidOk) {
        console.error("[cnrb2spring] 지운 *SET_NODE_LIST 의 SID 를 가리키는 자리가 " +
                      std::to_string(sidHard) + "건 남았습니다 (pid_refs: warn 으로 낮출 수 있습니다)");
        return -1;
    }
    lines = std::move(out);
    return N;
}

// ============================================================
// 단독 YAML 러너
// ============================================================

// 'eps' 는 쓰지 않지만 목록에 남겨 둔다 — 스프링 3개 시절 설정을 그대로 돌렸을 때
// 'eps 가 아직 뭔가 한다' 는 거짓 안내가 되지 않게 전용 [WARN] 을 내기 위해서다.
static const char* CG_KEYS[] = {
    "model", "output", "axis", "target_pids", "gap", "k_engage", "k_axial", "k_rot", "eps",
    "curve_range", "node_id_start", "elem_id_start", "card_id_start", "pid_refs"};

int runCnrb2Spring(const std::string& yamlFile, ConsoleOutput& console) {
    {   // 탭으로 들여쓴 YAML 은 블록이 통째로 무너져 조용히 아무 일도 안 했다 — 파싱 전에 거른다
        std::string tabLine;
        if (KooRemapper::yamlScanTabIndent(yamlFile, tabLine)) {
            console.error(KooRemapper::yamlTabIndentMessage("cnrb2spring", tabLine));
            return 1;
        }
    }
    std::ifstream f(yamlFile);
    if (!f.is_open()) { console.error("[cnrb2spring] 설정을 열 수 없습니다: " + yamlFile); return 1; }
    KooRemapper::yamlSkipBOM(f);   // 윈도우 편집기가 붙인 BOM 이 첫 키를 망가뜨렸다

    std::string configDir;
    size_t lastSlash = yamlFile.find_last_of("/\\");
    if (lastSlash != std::string::npos) configDir = yamlFile.substr(0, lastSlash);

    std::string modelFile, outputFile;
    Cnrb2SpringConfig cfg;
    std::set<std::string> seen;
    // 줄을 통째로 담아 둔다 — 'target_pids:' 뒤에 오는 블록 목록('- 1201')을 이어 읽어야 한다.
    // 플랫폼(argbuild)은 yaml.dump(default_flow_style=False)로 목록을 이 꼴로 내보내므로,
    // 한 줄짜리 'key: value' 만 보면 웹·MCP 경로의 target_pids 가 조용히 버려진다.
    std::vector<std::string> yl;
    {
        std::string ln;
        while (std::getline(f, ln)) {
            if (!ln.empty() && ln.back() == '\r') ln.pop_back();
            yl.push_back(ln);
        }
    }
    bool bad = false;

    auto numErr = [&](const std::string& key, const std::string& val) {
        console.error("[cnrb2spring] '" + key + "' 값을 수로 읽을 수 없습니다: '" + val + "'");
        bad = true;
    };
    for (size_t li = 0; li < yl.size(); ++li) {
        const std::string& line = yl[li];
        std::string tr = cg_trim(line);
        if (tr.empty() || tr[0] == '#') continue;
        size_t cp = tr.find(':');
        if (cp == std::string::npos) continue;
        std::string key = cg_trim(tr.substr(0, cp));
        std::string val = cg_trim(KooRemapper::yamlStripComment(tr.substr(cp + 1)));
        if (val.size() >= 2 && (val.front() == '"' || val.front() == '\'') && val.back() == val.front())
            val = val.substr(1, val.size() - 2);
        if (key == "operations") {
            console.error("[cnrb2spring] 최상위에 'operations:' 가 있습니다 — cnrb2spring 은 flat 설정 op 입니다"
                          " (assemble 설정을 그대로 쓰면 아무 일도 일어나지 않습니다)");
            return 1;
        }
        bool known = false;
        for (const char* k : CG_KEYS) if (key == k) { known = true; break; }
        if (!known) { console.warning("[cnrb2spring] 알 수 없는 키 '" + key + "' 를 무시합니다"); continue; }
        seen.insert(key);
        double d = 0; int i = 0;
        if (val.empty() && key != "target_pids") continue;
        if      (key == "model")  modelFile  = val;
        else if (key == "output") outputFile = val;
        else if (key == "axis") {
            std::string a = cg_upper(val);
            if (a == "X" || a == "Y" || a == "Z") cfg.axis = (char)(a[0] - 'X' + 'x');
            else {
                console.error("[cnrb2spring] axis 값 '" + val + "' 를 모릅니다. 허용값: x, y, z");
                bad = true;
            }
        } else if (key == "pid_refs") {
            if (val == "strict" || val == "warn") cfg.pidRefs = val;
            else {
                console.error("[cnrb2spring] pid_refs 값 '" + val + "' 를 모릅니다. 허용값: strict, warn");
                bad = true;
            }
        } else if (key == "target_pids") {
            std::vector<std::string> items;
            if (val.empty()) {
                // 블록 목록 — 뒤따르는 '- 1201' 줄을 이어 읽는다
                while (li + 1 < yl.size()) {
                    std::string nt = cg_trim(KooRemapper::yamlStripComment(yl[li + 1]));
                    if (nt.empty() || nt[0] == '#') { ++li; continue; }
                    if (nt[0] != '-') break;
                    items.push_back(cg_trim(nt.substr(1)));
                    ++li;
                }
            } else {
                std::string s = val;
                if (!s.empty() && s.front() == '[') s = s.substr(1);
                if (!s.empty() && s.back() == ']') s.pop_back();
                std::stringstream ss(s);
                std::string tok;
                while (std::getline(ss, tok, ',')) items.push_back(cg_trim(tok));
            }
            for (const auto& t : items) {
                if (t.empty()) continue;
                if (!cg_parseIntStrict(t, i)) {
                    console.error("[cnrb2spring] 'target_pids' 원소가 정수가 아닙니다: '" + t + "'");
                    bad = true;
                } else cfg.targetPids.push_back(i);
            }
        }
        else if (key == "eps") {
            console.warning("[cnrb2spring] 'eps' 는 더 이상 쓰지 않습니다 — 두 팬텀 노드를 같은 자리에 두는 "
                            "제로길이 discrete beam 이라 간격이 필요 없고, 방향은 로컬 좌표계(CID)가 정합니다. "
                            "값을 무시합니다");
        }
        else if (key == "gap")           { if (cg_parseDoubleStrict(val, d)) cfg.gap = d;        else numErr(key, val); }
        else if (key == "k_engage")      { if (cg_parseDoubleStrict(val, d)) cfg.kEngage = d;    else numErr(key, val); }
        else if (key == "k_axial")       { if (cg_parseDoubleStrict(val, d)) cfg.kAxial = d;     else numErr(key, val); }
        else if (key == "k_rot")         { if (cg_parseDoubleStrict(val, d)) cfg.kRot = d;       else numErr(key, val); }
        else if (key == "curve_range")   { if (cg_parseDoubleStrict(val, d)) cfg.curveRange = d; else numErr(key, val); }
        else if (key == "node_id_start") { if (cg_parseIntStrict(val, i)) cfg.nodeIdStart = i;   else numErr(key, val); }
        else if (key == "elem_id_start") { if (cg_parseIntStrict(val, i)) cfg.elemIdStart = i;   else numErr(key, val); }
        else if (key == "card_id_start") { if (cg_parseIntStrict(val, i)) cfg.cardIdStart = i;   else numErr(key, val); }
    }
    if (bad) { console.error("[cnrb2spring] 설정 값을 읽지 못해 멈췄습니다"); return 1; }
    if (modelFile.empty())  { console.error("[cnrb2spring] 'model' 이 없습니다");  return 1; }
    if (outputFile.empty()) { console.error("[cnrb2spring] 'output' 이 없습니다"); return 1; }

    std::string modelPath = KooRemapper::yamlResolvePath(configDir, modelFile);
    std::string outPath   = KooRemapper::yamlResolvePath(configDir, outputFile);

    std::vector<std::string> lines;
    {
        std::ifstream mf(modelPath);
        if (!mf.is_open()) { console.error("[cnrb2spring] 모델을 열 수 없습니다: " + modelPath); return 1; }
        std::string ln;
        while (std::getline(mf, ln)) {
            if (!ln.empty() && ln.back() == '\r') ln.pop_back();
            lines.push_back(ln);
        }
    }
    console.println("[cnrb2spring] Model  : " + modelPath);
    console.println("[cnrb2spring] Output : " + outPath);

    // 기본값은 실측이 아니라 가정값이다 — 그대로 쓰면 그 사실을 알린다
    {
        std::string dflt;
        auto add = [&](const char* k, double v, const char* unit) {
            if (!seen.count(k)) dflt += std::string(dflt.empty() ? "" : " ") + k + "=" + cg_num(v) + unit;
        };
        add("gap", cfg.gap, "mm");
        add("k_engage", cfg.kEngage, "N/mm");
        add("k_axial", cfg.kAxial, "N/mm");
        add("k_rot", cfg.kRot, "N*mm/rad");
        add("curve_range", cfg.curveRange, "mm");
        if (!dflt.empty())
            console.println("[cnrb2spring] 기본값 사용: " + dflt + " (실측 아님 — labeled assumption)");
    }

    int n = cnrb2spring_apply(lines, cfg, console);
    if (n < 0) { console.error("[cnrb2spring] 변환을 멈췄습니다 — 위 [ERROR] 줄을 보세요 (출력 파일을 쓰지 않았습니다)"); return 1; }

    std::ofstream out(outPath);
    if (!out.is_open()) { console.error("[cnrb2spring] 쓸 수 없습니다: " + outPath); return 1; }
    for (const auto& ln : lines) out << ln << "\n";
    console.println(cg_fmt("[cnrb2spring] 변환 %d개 -> %s", n, outPath.c_str()));
    return 0;
}
