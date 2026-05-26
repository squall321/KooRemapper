# database — DATABASE output control (§37)

Source: [database.cpp](../../src/commands/database.cpp)
Manual: [`KooRemapper_Manual.md`#37-database--database-출력-제어](../../docs/KooRemapper_Manual.md#37-database--database-출력-제어)


## Synopsis

```
KooRemapper database <args>
```

## What it does

8 presets + per-keyword spec. Emits `*DATABASE_*` cards.

## Key references

- [[lsdyna/keywords#LS-DYNA Keyword Cross-Reference]]

## From the manual

_Excerpted from [`KooRemapper_Manual.md`](../../docs/KooRemapper_Manual.md) §37. database — DATABASE 출력 제어._

<!-- BEGIN MANUAL EXCERPT -->



### 용도

LS-DYNA K-파일에 `*DATABASE_*` 출력 제어 키워드를 자동 삽입합니다.
프리셋 또는 개별 키워드 토글 방식을 지원하며, 기존 키워드는 자동으로 건너뜁니다.

### 사용법

```bash
KooRemapper.exe database <config.yaml>
```

### YAML 형식 (프리셋)

```yaml
model:  model.k
output: model_db.k
preset: drop           # all/drop/crash/static/thermal/forming/modal/minimal
dt:     0.001          # ASCII 출력 간격 (기본 0.001)
dt_plot: 0.01          # D3PLOT 간격 (기본 dt×10)
```

### YAML 형식 (개별 지정)

```yaml
model:  model.k
output: model_db.k
ascii:
  glstat: true
  matsum: true
  nodout: true
  rcforc: true
binary:
  d3plot: true
  d3thdt: true
extent:
  neiph: 6             # 추가 적분점 히스토리 변수
  strflg: 1            # 변형률 텐서 출력
  sigflg: 1            # 응력 텐서 출력
  epsflg: 1            # 유효 소성 변형률 출력
```

### 프리셋 (8종)


**표 37. (표 설명 — 해당 명령어/기능의 파라미터 또는 옵션 목록)**

| 프리셋 | ASCII 키워드 | Binary | EXTENT |
|--------|-------------|--------|--------|
| `all` | 20종 전체 (glstat~massout) | d3plot, d3thdt, d3dump, runrsf | O |
| `drop` | glstat, matsum, nodout, elout, rcforc, sleout, spcforc, rwforc, nodfor, secforc, bndout, ncforc | d3plot, d3thdt, d3dump | O |
| `crash` | glstat, matsum, nodout, elout, rcforc, sleout, spcforc, rwforc, nodfor, secforc, swforc, ncforc, abstat | d3plot, d3thdt, d3dump | O |
| `static` | glstat, matsum, nodout, elout, spcforc, nodfor, bndout, secforc | d3plot, d3thdt | O |
| `thermal` | glstat, matsum, nodout, elout, spcforc, tprint, bndout | d3plot, d3thdt | O |
| `forming` | glstat, matsum, nodout, elout, rcforc, sleout, spcforc, nodfor, secforc, ncforc, swforc | d3plot, d3thdt, d3dump | O |
| `modal` | glstat, matsum, nodout, elout, spcforc | d3plot | X |
| `minimal` | glstat, matsum | d3plot | X |

### 지원 키워드

**ASCII (20종):** glstat, matsum, nodout, elout, rcforc, sleout, spcforc, nodfor, rwforc, secforc, jntforc, bndout, abstat, swforc, ssstat, deforc, disbout, ncforc, tprint, massout

**Binary (6종):** d3plot, d3thdt, d3dump, runrsf, intfor, d3drlf

### 동작
- 기존 `*DATABASE_*` 키워드를 스캔하여 중복 건너뛰기 (`[SKIP]` 표시)
- `*END` 직전에 출력 블록 삽입
- 프리셋 미지정 + 개별 미지정 시 `all` 프리셋 자동 적용

---

<!-- END MANUAL EXCERPT -->
