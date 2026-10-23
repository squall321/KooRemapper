#include "TestFramework.h"

// Include all test files
#include "test_Vector3D.cpp"
#include "test_Mesh.cpp"
#include "test_Interpolation.cpp"
#include "test_Mapping.cpp"
// 덱 계약의 기본 조각 — 2026-10-15 에 더했다. 그 전에는 단언 52개가 전부 기하였다.
#include "test_DeckContract.cpp"
#include "test_IncludeClosure.cpp"
#include "test_IdAllocator.cpp"
// StepForge 조각 계약 — 2026-10-16
#include "test_FragmentMap.cpp"
// 세트 멤버 해석 정본 — 2026-10-23(`_ADD`·`_INTERSECT`·`_COLLECT`)
#include "test_SetMembers.cpp"
#include "test_ContactCards.cpp"

int main(int argc, char* argv[]) {
    (void)argc;
    (void)argv;

    return KooRemapper::Test::TestFramework::instance().runAll();
}
