# info — mesh statistics (§11)

Source: [main.cpp](../../src/main.cpp)
Manual: [`KooRemapper_Manual.md`#11-info--메시-정보](../../docs/KooRemapper_Manual.md#11-info--메시-정보)


## Synopsis

```
KooRemapper info mesh.k
```

## What it does

Prints node/element counts per type, bounding box, material/section table sizes.

## Key references

- [[modules/parser#Module: src/parser/]]

## From the manual

_Excerpted from [`KooRemapper_Manual.md`](../../docs/KooRemapper_Manual.md) §11. info — 메시 정보._

<!-- BEGIN MANUAL EXCERPT -->



### 용도
LS-DYNA K-파일의 메시 정보를 분석하여 콘솔에 출력합니다.

### 사용법

```bash
KooRemapper.exe info <mesh_file.k>
```

### 출력 정보


**표 13-1. bend YAML 설정 파라미터 — 굽힘 반경, 각도, 중립면 위치, 굽힘 축 방향 등 핵심 파라미터.**

| 항목 | 설명 |
|------|------|
| 파일명 | 입력 K-파일 이름 |
| 노드 수 | 전체 노드 개수 |
| 요소 수 | 전체 요소 개수 |
| 파트 수 | 파트 개수 |
| 바운딩 박스 | X/Y/Z 최소~최대 범위 |
| 크기 | X/Y/Z 방향 길이 |
| 검증 결과 | 메시 유효성 검사 |
| 요소 품질 | Jacobian 최소/최대, 음수 Jacobian 요소 수 |

---

<!-- END MANUAL EXCERPT -->
