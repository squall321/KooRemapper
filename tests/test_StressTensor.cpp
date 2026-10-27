#include "TestFramework.h"
#include "analysis/StressTensor.h"
#include <array>

using namespace KooRemapper;
using namespace KooRemapper::Test;

// ============================================================
// StressTensor 주응력 — 퇴행 고유값 회귀 (KR-03, 2026-10-27)
//   겹친 고유값(+미세 전단)에서 옛 솔버의 '한 실근' 가지가 세 값을 같게 만들어
//   min=max 가 됐다. 변형률 매개화로 고쳤다. 아래가 그 회귀다.
// ============================================================

// 퇴행 · 전단 정확히 0 — {2841.058, 1217.596, 1217.596}
TEST(StressTensor_Principal_Degenerate_ZeroShear) {
    StressTensor s(2841.058, 1217.596, 1217.596, 0.0, 0.0, 0.0);
    auto pr = s.principalStresses();
    ASSERT_NEAR(pr[0], 2841.058, 1e-6);
    ASSERT_NEAR(pr[1], 1217.596, 1e-6);
    ASSERT_NEAR(pr[2], 1217.596, 1e-6);
}

// 퇴행 · 미세 전단 잡음 — 여전히 {2841.058, 1217.596, 1217.596}
// (옛 솔버는 이 요소에서 min=2841.058 을 냈다)
TEST(StressTensor_Principal_Degenerate_ShearNoise) {
    StressTensor s(2841.058, 1217.596, 1217.596, -4.5e-12, 7.5e-28, -1.4e-11);
    auto pr = s.principalStresses();
    ASSERT_NEAR(pr[0], 2841.058, 1e-3);
    ASSERT_NEAR(pr[1], 1217.596, 1e-3);
    ASSERT_NEAR(pr[2], 1217.596, 1e-3);
}

// 서로 다른 세 고유값(대각) — 그대로
TEST(StressTensor_Principal_Distinct_Diagonal) {
    StressTensor s(5.0, 3.0, 1.0, 0.0, 0.0, 0.0);
    auto pr = s.principalStresses();
    ASSERT_NEAR(pr[0], 5.0, 1e-9);
    ASSERT_NEAR(pr[1], 3.0, 1e-9);
    ASSERT_NEAR(pr[2], 1.0, 1e-9);
}

// 정수압(세 값 같음)
TEST(StressTensor_Principal_Hydrostatic) {
    StressTensor s(10.0, 10.0, 10.0, 0.0, 0.0, 0.0);
    auto pr = s.principalStresses();
    ASSERT_NEAR(pr[0], 10.0, 1e-9);
    ASSERT_NEAR(pr[1], 10.0, 1e-9);
    ASSERT_NEAR(pr[2], 10.0, 1e-9);
}

// 전단이 있는 경우 — 고유값의 불변량(합=대각합)과 순서만 확인(회전 상태)
TEST(StressTensor_Principal_WithShear_TraceInvariant) {
    StressTensor s(3000.0, 2000.0, 1000.0, 50.0, -30.0, 20.0);
    auto pr = s.principalStresses();
    ASSERT_TRUE(pr[0] >= pr[1] && pr[1] >= pr[2]);          // 내림차순
    ASSERT_NEAR(pr[0] + pr[1] + pr[2], 6000.0, 1e-6);       // I1 보존
}
