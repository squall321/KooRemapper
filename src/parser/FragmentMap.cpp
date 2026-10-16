// StepForge 조각 대응표 리더와 조각 대조 — 계약(BOUNDARY-DYNAFORGE §3-3) 밖은 말하고 거절한다
#include "parser/FragmentMap.h"

#include "core/Mesh.h"
#include "parser/DeckScan.h"
#include "parser/KFileReader.h"
#include "util/Sha256.h"
#include "util/StrictJson.h"

#include <algorithm>
#include <cstdio>
#include <fstream>
#include <map>
#include <set>

namespace KooRemapper {
namespace fragment {
namespace {

using json::Value;

// 객체의 칸이 정확히 `keys` 인가 — 모르는 칸·빠진 칸을 이름으로 말한다
bool exactKeys(const Value& v, const std::vector<std::string>& keys, const std::string& where, std::string& err) {
    if (v.type != Value::Type::Object) { err = where + " 이 객체가 아니다"; return false; }
    for (const auto& kv : v.obj)
        if (std::find(keys.begin(), keys.end(), kv.first) == keys.end()) {
            err = where + " 의 모르는 칸 '" + kv.first + "' — 계약(§3-3)에 없는 칸은 받지 않는다";
            return false;
        }
    for (const auto& k : keys)
        if (!v.get(k)) { err = where + " 에 칸 '" + k + "' 가 없다"; return false; }
    return true;
}

bool readString(const Value& v, const std::string& where, std::string& out, std::string& err) {
    if (v.type != Value::Type::String) { err = where + " 이 문자열이 아니다"; return false; }
    out = v.s;
    return true;
}

bool readInt(const Value& v, const std::string& where, long long minValue, long long& out, std::string& err) {
    if (v.type != Value::Type::Int) { err = where + " 이 정수가 아니다"; return false; }
    if (v.i < minValue) { err = where + " 이 " + std::to_string(minValue) + " 보다 작다(" + std::to_string(v.i) + ")"; return false; }
    out = v.i;
    return true;
}

bool readRange(const Value& v, const std::string& where, Range& out, std::string& err) {
    out = Range{};
    if (v.isNull()) return true;                               // 그 번호를 하나도 안 썼다
    if (v.type != Value::Type::Array || v.arr.size() != 2) { err = where + " 은 null 이거나 [lo, hi] 여야 한다"; return false; }
    if (!readInt(v.arr[0], where + "[0]", 1, out.lo, err) || !readInt(v.arr[1], where + "[1]", 1, out.hi, err)) return false;
    if (out.lo > out.hi) { err = where + " 의 lo 가 hi 보다 크다"; return false; }
    out.used = true;
    return true;
}

bool isHex16(const std::string& s) {
    if (s.size() != 16) return false;
    for (char c : s)
        if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'))) return false;
    return true;
}

// 키워드 블록마다 첫 데이터 카드(`_TITLE` 이면 제목 다음)의 첫 칸 — SECID·MID·SID 를 모은다.
// 칸은 10칸이다(이 셋은 표준에서 I10 — 조각은 표준 폭이다).
void firstCardIds(const std::vector<std::string>& lines, std::vector<long long>& sec, std::vector<long long>& mat,
                  std::vector<long long>& sets) {
    for (size_t i = 0; i < lines.size(); ++i) {
        if (deckscan::isDataLine(lines[i])) continue;
        const std::string kw = deckscan::kwBare(deckscan::keywordToken(lines[i]));
        std::vector<long long>* into = nullptr;
        if (kw.rfind("*SECTION_", 0) == 0) into = &sec;
        else if (kw.rfind("*MAT_", 0) == 0 && kw.rfind("*MAT_ADD_", 0) != 0) into = &mat;
        else if (kw.rfind("*SET_", 0) == 0) into = &sets;
        if (!into) continue;
        bool needTitle = kw.find("_TITLE") != std::string::npos;
        for (size_t j = i + 1; j < lines.size(); ++j) {
            const std::string& d = lines[j];
            const size_t h = d.find_first_not_of(" \t");
            if (h != std::string::npos && d[h] == '*') break;
            if (h != std::string::npos && d[h] == '$') continue;
            if (needTitle) { needTitle = false; continue; }
            const auto f = deckscan::cardFields(d, 10);
            long long id = 0;
            if (!f.empty()) {
                try { id = std::stoll(f[0]); } catch (...) { id = 0; }
            }
            into->push_back(id);
            break;
        }
    }
}

std::string rangeText(const Range& r) {
    return r.used ? "[" + std::to_string(r.lo) + ", " + std::to_string(r.hi) + "]" : std::string("null");
}

}  // namespace

bool parseMap(const std::string& jsonText, Map& out, std::string& err) {
    out = Map{};
    Value v;
    std::string jerr;
    if (!json::parse(jsonText, v, jerr)) { err = "대응표 JSON 문법 — " + jerr; return false; }
    if (!exactKeys(v, {"unit", "frame", "ranges", "parts"}, "대응표", err)) return false;
    if (!readString(*v.get("unit"), "unit", out.unit, err) || !readString(*v.get("frame"), "frame", out.frame, err))
        return false;
    const Value& r = *v.get("ranges");
    if (!exactKeys(r, {"node", "elem", "pid", "sid"}, "ranges", err)) return false;
    if (!readRange(*r.get("node"), "ranges.node", out.node, err) || !readRange(*r.get("elem"), "ranges.elem", out.elem, err) ||
        !readRange(*r.get("pid"), "ranges.pid", out.pid, err) || !readRange(*r.get("sid"), "ranges.sid", out.sid, err))
        return false;
    const Value& ps = *v.get("parts");
    if (ps.type != Value::Type::Array) { err = "parts 가 배열이 아니다"; return false; }
    std::set<long long> pids;
    for (size_t k = 0; k < ps.arr.size(); ++k) {
        const std::string w = "parts[" + std::to_string(k) + "]";
        const Value& p = ps.arr[k];
        if (!exactKeys(p, {"path", "name", "pid", "node_start", "node_count", "elem_start", "elem_count", "coord_sha"}, w, err))
            return false;
        Part part;
        if (!readString(*p.get("path"), w + ".path", part.path, err) || !readString(*p.get("name"), w + ".name", part.name, err) ||
            !readInt(*p.get("pid"), w + ".pid", 1, part.pid, err) ||
            !readInt(*p.get("node_start"), w + ".node_start", 1, part.nodeStart, err) ||
            !readInt(*p.get("node_count"), w + ".node_count", 0, part.nodeCount, err) ||
            !readInt(*p.get("elem_start"), w + ".elem_start", 1, part.elemStart, err) ||
            !readInt(*p.get("elem_count"), w + ".elem_count", 0, part.elemCount, err) ||
            !readString(*p.get("coord_sha"), w + ".coord_sha", part.coordSha, err))
            return false;
        if (!isHex16(part.coordSha)) { err = w + ".coord_sha 가 소문자 16진 16자가 아니다"; return false; }
        if (!pids.insert(part.pid).second) { err = w + ".pid " + std::to_string(part.pid) + " 가 두 번 — pid 가 파트의 유일한 열쇠다"; return false; }
        out.parts.push_back(part);
    }
    return true;
}

std::string coordSha(const std::vector<std::array<double, 3>>& xyz) {
    std::vector<std::string> rows;
    rows.reserve(xyz.size());
    char buf[96];
    for (const auto& p : xyz) {
        std::snprintf(buf, sizeof(buf), "%16.9e%16.9e%16.9e", p[0], p[1], p[2]);
        rows.emplace_back(buf);
    }
    std::sort(rows.begin(), rows.end());
    std::string joined;
    for (size_t k = 0; k < rows.size(); ++k) {
        if (k) joined += '\n';
        joined += rows[k];
    }
    return util::sha256Hex(joined).substr(0, 16);
}

std::vector<std::string> check(const Map& m, const std::string& fragmentPath) {
    std::vector<std::string> bad;
    Mesh mesh;
    try {
        KFileReader reader;
        mesh = reader.readFile(fragmentPath);
    } catch (const std::exception& e) {
        bad.push_back("조각을 읽지 못했다: " + std::string(e.what()));
        return bad;
    }
    std::vector<std::string> lines;
    {
        std::ifstream f(fragmentPath);
        for (std::string l; std::getline(f, l);) {
            if (!l.empty() && l.back() == '\r') l.pop_back();
            lines.push_back(l);
        }
    }

    // ① 번호가 ranges 안이고, ranges 의 lo·hi 가 실제로 쓴 최소·최대다(ranges 가 정본 — Q7)
    auto exact = [&](const std::string& what, const Range& r, const std::vector<long long>& ids) {
        if (ids.empty()) {
            if (r.used) bad.push_back(what + " 번호를 하나도 안 썼는데 ranges 가 " + rangeText(r) + " 다");
            return;
        }
        const auto mm = std::minmax_element(ids.begin(), ids.end());
        if (!r.used || *mm.first != r.lo || *mm.second != r.hi)
            bad.push_back(what + " 실제 [" + std::to_string(*mm.first) + ", " + std::to_string(*mm.second) +
                          "] 가 ranges " + rangeText(r) + " 와 다르다");
    };
    std::vector<long long> nodeIds, elemIds, pidIds, secIds, matIds, setIds;
    for (const auto& kv : mesh.nodes) nodeIds.push_back(kv.first);
    for (const auto& kv : mesh.elements) elemIds.push_back(kv.first);
    for (const auto& kv : mesh.parts) pidIds.push_back(kv.first);
    firstCardIds(lines, secIds, matIds, setIds);
    exact("절점", m.node, nodeIds);
    exact("요소", m.elem, elemIds);
    exact("PID", m.pid, pidIds);
    exact("SID", m.sid, setIds);
    // SECID·MID 는 PID 를 따른다 — 같은 대역 안이어야 한다(조각 모드 검사와 같은 규칙)
    for (const auto* ids : {&secIds, &matIds})
        for (long long id : *ids)
            if (!m.pid.contains(id))
                bad.push_back(std::string(ids == &secIds ? "SECID " : "MID ") + std::to_string(id) +
                              " 가 ranges.pid " + rangeText(m.pid) + " 밖이다");

    // ② 대응표의 파트와 조각의 *PART 가 같은 PID 집합이다
    std::set<long long> mapPids, deckPids(pidIds.begin(), pidIds.end());
    for (const auto& p : m.parts) mapPids.insert(p.pid);
    for (long long pid : deckPids)
        if (!mapPids.count(pid)) bad.push_back("조각의 PID " + std::to_string(pid) + " 가 대응표 parts 에 없다");
    for (long long pid : mapPids)
        if (!deckPids.count(pid)) bad.push_back("대응표의 PID " + std::to_string(pid) + " 가 조각에 없다");

    // ③ 파트마다 — 요소 수·구간, 그 요소가 쓰는 절점 = 절점 구간, coord_sha
    std::map<long long, std::vector<int>> elemsOf;
    std::map<long long, std::set<int>> nodesOf;
    for (const auto& kv : mesh.elements) {
        elemsOf[kv.second.partId].push_back(kv.first);
        for (int nid : kv.second.nodeIds)
            if (nid > 0) nodesOf[kv.second.partId].insert(nid);
    }
    for (const auto& p : m.parts) {
        const std::string w = "파트 PID " + std::to_string(p.pid) + "(" + p.name + ")";
        const auto& es = elemsOf[p.pid];
        if ((long long)es.size() != p.elemCount) {
            bad.push_back(w + " — 요소 " + std::to_string(es.size()) + "개, 대응표는 " + std::to_string(p.elemCount));
        } else if (!es.empty()) {
            const auto mm = std::minmax_element(es.begin(), es.end());
            if (*mm.first != p.elemStart || *mm.second != p.elemStart + p.elemCount - 1)
                bad.push_back(w + " — 요소 구간 [" + std::to_string(*mm.first) + ", " + std::to_string(*mm.second) +
                              "] 가 대응표 [" + std::to_string(p.elemStart) + ", +" + std::to_string(p.elemCount) + ") 와 다르다");
        }
        const auto& ns = nodesOf[p.pid];
        const bool nodeRangeOk = (long long)ns.size() == p.nodeCount &&
                                 (ns.empty() || (*ns.begin() == p.nodeStart && *ns.rbegin() == p.nodeStart + p.nodeCount - 1));
        if (!nodeRangeOk) {
            bad.push_back(w + " — 요소가 쓰는 절점 " + std::to_string(ns.size()) + "개가 대응표 구간 [" +
                          std::to_string(p.nodeStart) + ", +" + std::to_string(p.nodeCount) + ") 와 다르다");
            continue;
        }
        std::vector<std::array<double, 3>> xyz;
        for (int nid : ns) {
            const auto it = mesh.nodes.find(nid);
            if (it == mesh.nodes.end()) { bad.push_back(w + " — 요소가 쓰는 절점 " + std::to_string(nid) + " 가 *NODE 에 없다"); continue; }
            xyz.push_back({it->second.position.x, it->second.position.y, it->second.position.z});
        }
        const std::string got = coordSha(xyz);
        if (got != p.coordSha)
            bad.push_back(w + " — coord_sha " + got + " 가 대응표 " + p.coordSha + " 와 다르다(좌표가 바뀌었다)");
    }
    return bad;
}

}  // namespace fragment
}  // namespace KooRemapper
