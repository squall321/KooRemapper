// *INITIAL_STRESS_SOLID 카드 1 — 매뉴얼 그대로 I10×8 을 한 곳에서 쓴다(덱 내장·.dynain·cclip 공용)
#pragma once

#include <cstdio>
#include <string>

namespace KooRemapper {
namespace initial_stress {

// 왜 한 곳인가 (2026-10-16). 이 카드를 쓰는 자리가 넷(DynainWriter · ModelAssembler 의 덱 내장과 .dynain ·
// cclip)이었고 넷 다 `I10 + I8×5` 로 썼다. 매뉴얼은 카드 1 을 **I10×8** 로 둔다 —
// EID NINT NHISV LARGE IVEFLG IALEGP NTHINT NTHHSV(Vol_I `*INITIAL_STRESS_SOLID` Card 1, 190153 근처).
// 8칸 묶음은 지금 값(NINT=1 · 나머지 0)에서는 10칸 창에 우연히 들어가 맞게 읽혔지만, 다섯째·여섯째 칸
// (머리 주석은 옛 이름 `ics`·`ncomp` 였다)이 0 이 아니게 되는 날 IVEFLG 가 틀리게 읽힌다. 값은 그대로다.
inline const char* card1Comment() {
    return "$#     eid      nint     nhisv     large    iveflg    ialegp    nthint    nthhsv";
}

// 적분점 하나(NINT=1) · 이력변수 0 · 작은 꼴(LARGE=0) — 이 리포가 쓰는 꼴은 이것뿐이다.
inline std::string card1(long long eid) {
    char buf[96];
    std::snprintf(buf, sizeof(buf), "%10lld%10d%10d%10d%10d%10d%10d%10d", eid, 1, 0, 0, 0, 0, 0, 0);
    return buf;
}

}  // namespace initial_stress
}  // namespace KooRemapper
