// battery 덱 글자의 번호를 족마다 옮긴다 — assemble 이 battery 덱을 기존 모델의 번호 위로 얹으려고 쓴다
#pragma once

#include <array>
#include <string>

// Knowledge graph (lat.md):
//   @lat: [[modules/battery]]

namespace bat {

// 왜 이 단위가 있나 (2026-11-08 · 사용자 결정 「고친다」).
//
//   assemble 의 `- type: battery` 는 battery 덱을 지어 주 덱에 `*INCLUDE` 로 붙인다. battery 덱의 번호는 늘 1(절점 · 요소) ·
//   고정 상수(PID 10~2031 · SECID 1~50 · MID 1~15 · 세트 1~1002 · 곡선 9001~9904 · 접촉 1 · 2 · 10~)라 기존 모델과 겹쳤다
//   (실측: 상자 198 절점이 모두 겹쳐 rc 0 — `info` 는 SECID · MID 1 만 짚었다). 카탈로그가 적은 node_id_offset ·
//   elem_id_offset(0 = 있는 최대값 위)은 읽기만 하고 쓰지 않았다.
//
// 지키는 것 — CadSolidMerge 의 조각 옮기기와 같은 원칙.
//   · battery 쓰개가 내는 키워드만 받는다(목록 밖이면 거절) — 옮기는 규칙을 모르는 카드를 옮기면 번호가 그럴듯하게 틀린다
//   · 번호 칸만 바꾸고 나머지 글자는 그대로 둔다. 칸 폭(절점 · 요소 줄 8 · 나머지 10)을 넘는 번호는 거절한다
//   · 뜻을 모르는 번호 칸(EOSID · 좌표계 · 상자 · 강체 RBID …)은 0 이어야 한다 — 0 이 아니면 거절한다
//   · 접촉의 SSID · MSID 는 SSTYP · MSTYP 로 족을 정한다(3 = 파트 · 5 = 전부 · 그 밖 = 세트)
//   · 세트는 종류를 한 통으로 옮긴다(공용 바닥 `ModelAssembler::idMaxima().set` 과 같은 입도)
//
// 하지 않는 것 — battery 덱의 `*CONTROL_*` · `*DATABASE_*` · 고정구(impactor · ground plate) · 경계조건은 그대로 싣는다.
//   번호 겹침만 다룬다. `*INCLUDE_DYNAIN` 은 표시만 한다(부르는 쪽이 번호를 옮기면 거절한다 — 그 dynain 은 다른 실행의 번호다).

// 옮기는 번호 족 — LS-DYNA 의 번호 이름공간 하나씩(TMID 는 MID 와 따로 · 곡선은 표와 한 이름공간)
enum IdFam { FAM_NODE, FAM_ELEM, FAM_PART, FAM_SECTION, FAM_MAT, FAM_TMAT, FAM_HOURGLASS, FAM_SET, FAM_CONTACT, FAM_CURVE,
             FAM_COUNT };
const char* idFamName(int fam);   // 사람이 읽는 이름(절점 · 요소 · 파트 …)

struct IdRange { long long lo = 0, hi = 0; };   // 정의한 번호의 최소 · 최대 — 하나도 없으면 0, 0
using IdRanges = std::array<IdRange, FAM_COUNT>;
using IdShift = std::array<long long, FAM_COUNT>;

struct ShiftResult {
    IdRanges defined{};            // 옮기기 **전** 족마다 정의한 번호 범위
    bool includesDynain = false;   // `*INCLUDE_DYNAIN` 이 있다
};

// deck 의 정의 · 참조 번호를 족마다 by 만큼 옮겨 out 에 담는다(by 가 모두 0 이면 out == deck — 범위만 잰다).
// 모르는 키워드 · 읽지 못한 번호 칸 · 0 이어야 할 칸 · 칸 폭이나 int 를 넘는 번호면 false 와 err(그 줄 · 키워드 · 까닭).
bool shiftBatteryIds(const std::string& deck, const IdShift& by, std::string& out, ShiftResult& res, std::string& err);

}  // namespace bat
