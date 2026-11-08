// 재질 번호(MID)를 덱 줄에서 한 규칙으로 센다 — 번호 커서 · 있나 · 두 번 정의 · 정의 지우기 · 정의 베끼기 · 고정 번호대 겹침이 같은 셈을 쓴다
#pragma once

#include <map>
#include <set>
#include <string>
#include <vector>

namespace KooRemapper {
namespace matids {

// 왜 이 단위가 있나 (2026-11-08 · 사용자 결정 「이번 판에 다 고친다」).
//
//   MID 를 세는 · 지우는 · 베끼는 훑기가 op 마다 따로 있었다 — matswap(단독 · assemble) · cclip · ale · cnrb2solid · cnrb2spring ·
//   offset 의 IGA 재질 베끼기 · 공용 커서(ModelAssembler). 저마다 `*MAT` 로 시작하는 블록의 첫 카드 첫 칸을 MID 로 보아
//     · 열 재질(`*MAT_THERMAL_*` · `*MAT_T01`~`T18`)의 TMID 와 `*MAT_ADD_*` 의 첫 칸(MID 또는 PID)을 MID 로 셌고,
//     · 바꾸는 MID 와 첫 칸이 같은 블록을 **다** 지웠다 — 같은 번호 TMID 의 열 카드 · 같은 번호 PID 의 `*MAT_ADD_THERMAL_EXPANSION`,
//     · IGA 는 첫 칸이 그 MID 인 **첫** `*MAT` 블록을 베꼈다(열 카드 · 덧붙임 카드가 앞이면 그것 · `_TITLE` 재질은 못 찾았다),
//     · 한 키워드 아래 쌓인 재질(매뉴얼 Card Sets)은 첫 카드만 보아 둘째 MID 를 새 재질이 다시 냈다.
//   그래서 판정을 여기 한 곳에 둔다. 섹션의 카드 묶음 셈(`ModelAssembler.cpp` `cur_scanSectionSets` · StepForge 591d5b5 `card_sets`)과
//   같은 꼴이다 — 묶음 한 벌의 행 수를 매뉴얼이 정하는 꼴은 다 읽고, 모르는 꼴은 행마다 첫 칸 숫자를 넉넉히 센다.
//
// 묶음 한 벌의 데이터 줄 수(묶음마다 오는 `_TITLE` 제목 줄은 뺀다 · Vol II R16) —
//   `*MAT_ELASTIC`(`*MAT_001`) 1 + Card 1.1(E < 0) + Card 2(`_FLUID`) · `*MAT_PLASTIC_KINEMATIC`(003) 2 · `*MAT_VISCOELASTIC`(006) 1 ·
//   `*MAT_NULL`(009) 1 · `*MAT_RIGID`(020) 3(Card 2 · 3 은 비어 있어도 와야 한다) · `*MAT_PIECEWISE_LINEAR_PLASTICITY`(024 · 옵션 없는 꼴) 4.
//   빈 줄도 카드다(끝의 빈 줄만 여백) · 1열의 `$` 주석은 건너뛴다(들여쓴 `$` 줄은 데이터 — Vol_I 17862 · 리더와 같다) · 자유 형식(쉼표) 줄은
//   칸 자리를 몰라 모르는 꼴로 본다.
// 그 밖의 꼴과 못 가른 자리(행 수를 모름 · 묶음의 MID 칸이 정수가 아님)부터는 행마다 첫 칸 숫자를 넉넉히 센다(`loose`) — 그 블록에
// 쌓인 다른 재질의 MID 일 수 있다. 새 번호는 그 위로 낸다(겹치지 않게).

// 구조 재질 키워드인가 — 대문자 키워드 토큰(칸폭 접미사 뗀 것). `*MAT_` 가운데 열 재질(TMID — `cards::isThermalMaterialKeyword`)과
// `*MAT_ADD_*`(있는 재질 · 파트에 덧붙인다 — 첫 칸이 MID 또는 PID)를 뺀다.
bool isStructuralKeyword(const std::string& kw);

// 재질 블록 안의 카드 묶음 한 벌(재질 하나)
struct Set {
    int mid = 0;
    size_t first = 0;    // 묶음의 첫 줄(`_TITLE` 이면 제목 줄)
    size_t card1 = 0;    // Card 1(MID 칸) 줄
    size_t last = 0;     // 묶음의 마지막 줄(길이를 모르면 블록의 마지막 데이터 줄)
    bool exact = false;  // 묶음 길이를 안다
};

// 구조 재질 키워드 블록 하나
struct Block {
    size_t keyword = 0;  // 키워드 줄
    size_t end = 0;      // 블록 끝(다음 키워드 줄 · 없으면 줄 수)
    int width = 10;      // MID 칸 폭(long 덱 20)
    std::vector<Set> sets;
    bool remainder = false;   // 못 가른 자리가 있다(그 뒤에 묶음이 더 있는지 모른다)
};

struct Scan {
    std::vector<Block> blocks;
    std::map<int, std::vector<std::pair<size_t, size_t>>> defs;   // MID → (블록, 묶음) — 나온 차례
    std::set<int> loose;                                          // 못 가른 자리부터 행마다 첫 칸 정수
};
Scan scan(const std::vector<std::string>& lines);

// 정의된 MID(쌓인 묶음까지) — 「있나」 · 「인클루드에만 있나」
std::set<int> defined(const std::vector<std::string>& lines);
// 쓰이는 MID — 정의 ∪ 넉넉한 행(새 번호 · 고정 번호대가 피할 것)
std::set<int> inUse(const std::vector<std::string>& lines);
// 번호 커서 — 쓰이는 MID 의 최대(없으면 0)
int maxId(const std::vector<std::string>& lines);
// MID → 정의마다 Card 1 줄(두 번 정의 판정 · 자리 말하기)
std::map<int, std::vector<size_t>> definitionLines(const std::vector<std::string>& lines);

// 그 MID 의 구조 재질 정의를 지운다 — 길이를 아는 묶음은 그 묶음 줄만(블록의 묶음이 다 지워지면 키워드 줄째), 길이를 모르는 묶음은
// 블록째(예전 그대로 — 그 뒤에 쌓인 재질이 있는지 모른다). 열 재질 · `*MAT_ADD_*` 는 건드리지 않는다.
// `stillUsed` — 지운 뒤에도 그 번호가 쓰인다(모르는 꼴 블록에 쌓였거나 정의가 남았다) — 그 번호를 새 재질에 다시 주면 안 된다.
struct Removed {
    int sets = 0;
    bool stillUsed = false;
};
Removed removeDefinition(std::vector<std::string>& lines, int mid);
// 같은 규칙으로 지울 줄만 표시한다(줄 차례를 바꾸지 않는 op — matdb 의 지움 표지). 여러 MID 를 한 번에 — 한 블록의 묶음이 다 들면 블록째
std::vector<bool> definitionMask(const std::vector<std::string>& lines, const std::set<int>& mids);

// 그 MID 의 첫 구조 재질 정의를 newMid 로 — 키워드 줄 · 그 묶음 줄(앞의 주석 포함 · 길이를 모르면 블록 끝까지). MID 칸만 바꾼다(칸 폭 그대로).
// 없으면 빈 글자.
std::string copyDefinition(const std::vector<std::string>& lines, int mid, int newMid);

// 첫 칸이 그 재질의 MID 인 덧붙임 카드인가 — Vol II R16 의 카드 정의 그대로(대문자 키워드 · `_TITLE` 무관).
//   MID: `*MAT_ADD_EROSION` · `_DAMAGE_GISSMO` · `_DAMAGE_DIEM` · `_FATIGUE` · `_GENERALIZED_DAMAGE` · `_INELASTICITY` · `_PERMEABILITY` ·
//        `_PORE_AIR` · `_PROPERTY_DEPENDENCE` · `_PZELECTRIC` · `_AIRBAG_POROSITY_LEAKAGE` · `_BASIC_INCREMENTAL_FAILURE`
//   PID(이것은 false): `_THERMAL_EXPANSION` · `_COHESIVE` · `_CHEM_SHRINKAGE` · `_SOC_EXPANSION` · `_EXTVAR_EXPANSION`
bool isMidKeyedAddOn(const std::string& kw);

// 그 MID 에 덧붙인 카드(위 MID 꼴 · 블록의 첫 카드 첫 칸이 그 MID)를 블록째 지운다 — 재질이 덱에서 사라질 때만 부른다(남기면 없는 재질을
// 가리킨다). PID 꼴 덧붙임 · 열 재질은 건드리지 않는다. 지운 블록 수.
int removeMidAddOns(std::vector<std::string>& lines, int mid);

}  // namespace matids
}  // namespace KooRemapper
