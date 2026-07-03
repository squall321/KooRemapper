# KooRemapper 배치/HPC job 실행 (경량 CLI SIF)

서비스(웹/MCP/REST)와 별개로, **상태 없는 원샷 CLI**로 스케줄러(SLURM 등) job에서 쓰는 경로다.
`kooremapper-cli.sif` 하나에 바이너리 + gmsh + 525종 재료 DB가 전부 담겨 있어(자체완결)
Apptainer만 있으면 어디서든 돈다 — 호스트 레포/파이썬/DB 불필요.

## 빌드
```bash
infra/scripts/build-cli.sh            # → infra/apptainer/cli.sif
```

## 실행 패턴 (워크디렉토리 bind)
입력 `.k`/`config.yaml`이 있는 디렉토리를 `/work`로 bind하고 거기서 실행한다.
```bash
apptainer run --bind "$PWD:/work" --pwd /work infra/apptainer/cli.sif \
  generate torus t --dim-i 10 --dim-j 5 --dim-k 5

apptainer run --bind "$PWD:/work" --pwd /work infra/apptainer/cli.sif \
  matdb job.yaml
```
산출물은 `/work`(= 현재 디렉토리)에 쓰인다.

## matdb에서 번들 DB 쓰기
이미지에 재료 DB가 `$KOOREMAPPER_MATERIAL_DB`(=`/opt/kooremapper/materials/material_db.json`)로
구워져 있다. job config의 `database:` 에 이 절대경로를 넣으면 업로드 없이 525종을 쓴다.
```yaml
# job.yaml
model: my_model.k
output: my_model_mapped.k
database: /opt/kooremapper/materials/material_db.json
mat_type: MAT_ELASTIC
thermal: false
materials:
  - match: AL7003H
    mat_type: MAT_PIECEWISE_LINEAR_PLASTICITY
  - match: "*"
```

## SLURM
`slurm-matdb.sh` 참고 — `sbatch slurm-matdb.sh my_model.k job.yaml`.

## 세 소비 모드 요약
- **CLI(job)** — 이 SIF. 상태 없음, 스케줄러 친화.
- **MCP / 웹 / REST** — `infra/scripts/start.sh` 서비스 스택(대화형·에이전트).
- **Python 모듈** — `clients/python`(REST) 또는 CLI subprocess 래퍼(pyKooCAE Generator).
