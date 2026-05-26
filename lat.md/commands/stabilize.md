# stabilize — explicit solver stabilization (§36)

Source: [stabilize.cpp](../../src/commands/stabilize.cpp)
Manual: [`KooRemapper_Manual.md`#36-stabilize--explicit-솔버-안정화](../../docs/KooRemapper_Manual.md#36-stabilize--explicit-솔버-안정화)


## Synopsis

```
KooRemapper stabilize <args>
```

## What it does

12-level cumulative system. 1=energy, 2=accuracy, 3=TSSFAC 0.80, 4=IHQ=4, 5=shell, 6=contact soft stage1, 7=TSSFAC 0.67+bulk viscosity, 8=pinball SOFT=2+Card C IGNORE, 9=IHQ=6 BB, 10=TSSFAC 0.60, 11=ERODE (interactive), 12=max conservative. `stab_resolveLevel()` + `stab_applyExplicit()`. `stab_ensureControlContactCard2()` guarantees Card 2 exists.

## Key references

- [[lsdyna/control#LS-DYNA CONTROL cards in KooRemapper]]
- [[../feedback_no_erode]] (level 11 is the only ERODE path)

## From the manual

_Excerpted from [`KooRemapper_Manual.md`](../../docs/KooRemapper_Manual.md) §36. stabilize — Explicit 솔버 안정화._

<!-- BEGIN MANUAL EXCERPT -->



### 용도
Explicit 솔버의 안정성을 단계적으로 강화하는 **12단계 누적 시스템**입니다.

### 사용법

```bash
KooRemapper.exe stabilize <config.yaml>
```

### YAML 형식

```yaml
model: model.k
output: stabilized.k
stabilize: explicit
level: 6               # 1 ~ 12
```

### 레벨 시스템


**표 36. (표 설명 — 해당 명령어/기능의 파라미터 또는 옵션 목록)**

| Lv | 주요 변경 |
|----|----------|
| 1 | 에너지 추적 활성화 |
| 2 | 정확도 향상 (INN=4) |
| 3 | TSSFAC 0.80 |
| 4 | IHQ=4 (hourglass) |
| 5 | 셸 요소 설정 (자동 감지) |
| 6 | 접촉 soft stage 1 |
| 7 | TSSFAC 0.67 + bulk viscosity 강제 |
| 8 | 핀볼 SOFT=2 + Card C IGNORE |
| 9 | IHQ=6 Belytschko-Bindeman |
| 10 | TSSFAC 0.60 |
| 11 | ERODE (대화형) |
| 12 | 최대 보수적 설정 |

각 레벨은 **이전 레벨을 포함**합니다 (누적 적용).

---

<!-- END MANUAL EXCERPT -->
