# KooRemapper ↔ pyKooCAE 통합 (Generator 모듈)

pyKooCAE/SmartTwinPreprocessor의 Runner·체인에 KooRemapper를 **하나의 모듈 스텝**으로
붙이는 스캐폴드다. pyKooCAE가 다른 도구(예: `/opt/KooMeshModifier/run.sh`)를 subprocess로
부르는 관례를 그대로 따른다 — 서비스(api/postgres/mcp) 없이 **상태 없는 CLI SIF**로 실행.

## 구성
- `run.sh` — 표준 진입점. `run.sh <workdir> <op> [args...]` → `apptainer run cli.sif …`.
- `kooremapper_module.py` — Runner/체인에서 import해 쓰는 `KooRemapperModule` 클래스.

## 설치 (pyKooCAE 쪽)
1. CLI SIF 빌드: `infra/scripts/build-cli.sh` → `infra/apptainer/cli.sif`.
2. 배치: SIF와 `run.sh`를 표준 위치로 (예: `/opt/kooremapper/`).
   ```bash
   install -Dm755 run.sh /opt/kooremapper/run.sh
   cp infra/apptainer/cli.sif /opt/kooremapper/cli.sif
   ```
3. Runner에서 KooMeshModifier처럼 호출.
   ```python
   subprocess.run(["/opt/kooremapper/run.sh", case_dir, "matdb", "job.yaml"], check=True)
   ```

## Python 모듈로 (체인 스텝)
```python
from kooremapper_module import KooRemapperModule

kr = KooRemapperModule(sif="/opt/kooremapper/cli.sif")   # 또는 binary="/path/KooRemapper"

# yaml op — dict를 config.yaml로 써서 실행
outputs = kr.run("matdb", workdir=case_dir, config={
    "model": "model.k", "output": "mapped.k",
    "database": "/opt/kooremapper/materials/material_db.json",  # 번들 525종 DB
    "materials": [
        {"match": "AL7003H", "mat_type": "MAT_PIECEWISE_LINEAR_PLASTICITY"},
        {"match": "OCA Rigid Standard", "mat_type": "MAT_VISCOELASTIC"},
        {"match": "*"},
    ],
})
# → ["mapped.k"]  (case_dir에 생성된 파일들의 상대경로)

# positional op
kr.run("generate", workdir=case_dir, argv=["torus", "t", "--dim-i", "10", "--dim-j", "5", "--dim-k", "5"])
```

## 주의 / 설계
- **워크디렉토리 격리** — 각 스텝을 케이스 디렉토리에서 실행하고, 생성 파일만 반환한다(스냅샷 diff).
- **번들 DB** — matdb `database:` 에 `/opt/kooremapper/materials/material_db.json` 을 주면 업로드 없이 525종 사용.
- **YAML 들여쓰기** — matdb의 미니 파서가 리스트 항목을 키보다 더 들여써야 인식한다. 모듈이
  `_IndentDumper`로 이를 보장한다(직접 config.yaml을 쓸 땐 `  - match:` 처럼 들여쓸 것).
- **임의 op의 dict 인자 전체 지원** — 전체 op를 dict로 완전 검증·생성하려면 `kooremapper-core`
  (argbuild+catalog) 를 설치해 argv/yaml을 생성하면 된다. 이 모듈은 무의존 subprocess 경로를 유지한다.

## 세 모드
- **CLI/job** — 이 모듈 + cli.sif. 상태 없음, 스케줄러·체인 친화.
- **MCP/웹/REST** — `infra/scripts/start.sh` 서비스.
- **Python(REST)** — `clients/python`.
