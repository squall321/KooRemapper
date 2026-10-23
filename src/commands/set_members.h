// 세트 멤버 해석 정본 — 접촉 면·대상 파트가 세트를 가리킬 때 모든 소비자가 이것을 쓴다
#pragma once
#include "contact_defs.h"

#include <array>
#include <string>
#include <vector>

// 왜 이 파일이 있나 (2026-10-23).
//
//   세트를 파트·절점·세그먼트로 푸는 조회가 modelmeta · contact · optimize 에 따로 있었고, 셋 다
//   `SetDef::ids` 를 그대로 읽었다. 파서는 `_ADD`·`_INTERSECT` 의 멤버(세트 ID)를 개체 ID 로 오인하지
//   않으려고 `ids` 를 일부러 비워 두는데(닫히는 쪽), 소비자는 그 빈 목록을 "멤버 없음" 으로 읽었다 —
//   `*SET_PART_ADD` 를 가리키는 접촉이 연결도에서 **0쌍 · 미해석 0** 으로 사라졌다(실측).
//   그래서 푸는 일을 여기 한 곳에 모으고, 못 풀면 **못 풀었다고** 돌려준다.
//
// 푸는 것 — 평범한 목록 · `_GENERATE`(`ct_resolveSetRanges` 로 좁힌 뒤) · `_COLLECT`(같은 종류·같은 ID
//   정의를 합친다 — 하나라도 COLLECT 가 아니면 LS-DYNA 가 오류로 끝내므로 못 푼 것으로 본다) ·
//   `_ADD`(멤버 세트의 합집합 · PART 는 음수로 범위 · 없는 세트는 무시하고 적어 둔다 — Vol_I
//   "Ignore any nonexistant part set IDs in *SET_PART_ADD") · `_INTERSECT`(멤버 세트의 교집합).
// 못 푸는 것 — `_GENERAL`(옵션 코드) · `_COLUMN` · `_ADVANCED`((세트 ID, 종류) 쌍) · 좁히지 않은 범위 ·
//   순환 · 없는 세트. 그때 `resolved=false` 와 `why` 를 낸다.

struct SetMembers {
    bool found = false;      // 그 종류 · ID 의 세트가 덱에 있는가
    bool resolved = false;   // 멤버를 확정했는가 — false 면 `ids`·`segments` 를 쓰지 않는다
    std::string why;         // 못 푼 까닭(resolved=false 일 때)
    std::string note;        // 풀었지만 알릴 것(무시한 없는 멤버 세트 등)
    std::vector<int> ids;                       // PART/NODE/SHELL/SOLID… — 오름차순 · 중복 없음
    std::vector<std::array<int,4>> segments;    // SEGMENT — 덱 순서 · 같은 면 중복 없음
};

// 종류(`"PART"`·`"NODE"`·`"SEGMENT"`…)와 ID 로 세트의 멤버를 푼다.
SetMembers ct_setMembers(const std::vector<SetDef>& sets, int sid, const std::string& type);

// 그 ID 가 이 세트에 드는가 — 범위를 좁히지 않은 op(메시를 안 읽는 optimize)용.
// 반환 1 = 든다 · 0 = 안 든다 · -1 = 모른다(못 푸는 방언 · 없는 세트 · 순환).
int ct_setHas(const std::vector<SetDef>& sets, int sid, const std::string& type, int id);

// 세트 하나만 보는 포함 판정(목록 · `_GENERATE` 범위). 방언을 따라가지 않는다 — 그 일은 `ct_setHas`.
bool ct_setContains(const SetDef& s, int id);
