#include "TestFramework.h"

// Include all test files
#include "test_Vector3D.cpp"
#include "test_Mesh.cpp"
#include "test_Interpolation.cpp"
#include "test_Mapping.cpp"
// 덱 계약의 기본 조각 — 2026-10-15 에 더했다. 그 전에는 단언 52개가 전부 기하였다.
#include "test_DeckContract.cpp"
#include "test_IncludeClosure.cpp"
// 쓸 파일이 읽는 파일을 덮는지 묻는 공용 관문 — 2026-11-07
#include "test_OutputGuard.cpp"
#include "test_IdAllocator.cpp"
// StepForge 조각 계약 — 2026-10-16
#include "test_FragmentMap.cpp"
// 세트 멤버 해석 정본 — 2026-10-23(`_ADD`·`_INTERSECT`·`_COLLECT`)
#include "test_SetMembers.cpp"
#include "test_ContactCards.cpp"
// 주응력 퇴행 고유값 회귀 — 2026-10-27(KR-03)
#include "test_StressTensor.cpp"
// StepForge 이월 계획 리더(계획 · 변위장 · 조각 · 보고) — 2026-11-07
#include "test_CarryoverPlan.cpp"
// 주 덱 폴더 기준 상대 경로 공용 함수 — 2026-11-08(이월 적용 · assemble battery 가 같이 쓴다)
#include "test_RelPath.cpp"
// battery 덱 번호 옮기기(assemble battery) — 2026-11-08
#include "test_BatteryIdShift.cpp"

int main(int argc, char* argv[]) {
    (void)argc;
    (void)argv;

    return KooRemapper::Test::TestFramework::instance().runAll();
}
