// StepForge 조각 대응표(JSON)를 계약 그대로 읽고, 조각 `.k` 를 그것과 대조한다 — 모르는 칸은 거절한다
#pragma once

#include <array>
#include <string>
#include <vector>

namespace KooRemapper {
class Mesh;
namespace fragment {

// 정본 — `StepForge/docs/BOUNDARY-DYNAFORGE.md` §3-3(확정본 `540f89f`). 칸은 이것뿐이다(저쪽이 「여러분이 모르는
// 칸을 거절하시므로 빠짐없이 적습니다」라고 적었다 — 우리가 그렇게 약속했다).
//   맨 위 넷   unit(늘 "mm-t-s") · frame(늘 "world") · ranges · parts
//   ranges 넷  node · elem · pid · sid — 값은 실제로 쓴 [lo, hi] 이거나, 하나도 안 썼으면 null
//   parts[] 여덟 path · name · pid · node_start · node_count · elem_start · elem_count · coord_sha
// SECID·MID 는 PID 를 따른다(라이터가 셋을 같은 번호로 쓴다) — `ranges.pid` 가 셋의 대역이다.

struct Range {
    bool used = false;          // false = JSON 의 null(그 번호를 하나도 안 썼다)
    long long lo = 0, hi = 0;
    bool contains(long long v) const { return used && v >= lo && v <= hi; }
};

struct Part {
    std::string path, name, coordSha;
    long long pid = 0, nodeStart = 0, nodeCount = 0, elemStart = 0, elemCount = 0;
};

struct Map {
    std::string unit, frame;
    Range node, elem, pid, sid;
    std::vector<Part> parts;
};

// 대응표 글을 읽는다. 문법·칸 집합·값의 꼴이 계약 밖이면 false 와 까닭 한 문장.
// unit·frame 의 **값**은 여기서 거절하지 않는다 — 받을지는 삽입이 대상 덱과 맞대어 정한다.
bool parseMap(const std::string& jsonText, Map& out, std::string& err);

// 절점 좌표 집합의 해시 — 저쪽 `core/remesh_impact.coord_sha` 와 같은 식(번호·순서 무관).
//   rows = sorted("%16.9e%16.9e%16.9e" % (x, y, z)) · sha256("\n".join(rows)) 의 앞 16자
std::string coordSha(const std::vector<std::array<double, 3>>& xyz);

// 조각 `.k`(경로)를 대응표와 대조한다 — 문제마다 한 문장. 비면 맞는다.
//   · 번호(절점·요소·PID·SECID·MID·SID)가 `ranges` 안이고, `ranges` 의 lo·hi 가 실제로 쓴 최소·최대다
//   · 대응표의 파트와 조각의 `*PART` 가 같은 PID 집합이다
//   · 파트마다 요소 수 · 요소 구간 · 그 요소가 쓰는 절점 = 절점 구간 · `coord_sha`
//   · `ranges.sid` 가 null 이면 `*SET_*` 가 없다
std::vector<std::string> check(const Map& m, const std::string& fragmentPath);

// 파트마다만 본다(요소 수·구간 · 그 요소가 쓰는 절점 = 절점 구간 · `coord_sha`) — 덱 전체의 번호 집합은 보지 않는다.
// `check` 가 쓰고, 삽입이 덱 번호로 옮긴 대응표를 넣은 블록에 대어 본다(넣은 것이 조각 그대로인가).
std::vector<std::string> checkParts(const Map& m, const Mesh& mesh);

// 대응표를 같은 칸 집합·같은 꼴(들여쓰기 2 · UTF-8 그대로 — 저쪽 파일과 같다)의 JSON 으로 쓴다.
std::string toJson(const Map& m);

}  // namespace fragment
}  // namespace KooRemapper
