# Viscoelastic (MATVISCOELASTIC)

Stub mirroring `docs/KooRemapper_Theory_Document.md` §5.2.

Source code: (see See-also)

## Summary

Prony-series relaxation. Used by prestress on rubbery components.

## See also

- [[lsdyna/mat#LS-DYNA MAT cards in KooRemapper]]

## Theory text

_From [`KooRemapper_Theory_Document.md`](../../docs/KooRemapper_Theory_Document.md) §5.2 — 점탄성 재료 (MAT_VISCOELASTIC)._

<!-- BEGIN EXCERPT -->



### 5.2.1 입력 물성

| 물성 | 기호 | 의미 |
|------|------|------|
| 체적 탄성 계수 | K (BULK) | 부피 변형 저항 |
| 단시간 전단 계수 | G₀ | 즉시 전단 응답 |
| 장시간 전단 계수 | Gᵢ | 평형 전단 응답 |
| 감쇠 계수 | β | 이완 속도 |

### 5.2.2 프리스트레스 계산

장시간 거동(평형 상태)을 사용:

$$G = G_i$$

등가 탄성 계수 계산:

$$E = \frac{9KG}{3K + G}$$

$$\nu = \frac{3K - 2G}{2(3K + G)}$$

---

# 6. 참고 문헌

<!-- END EXCERPT -->
