# CLI / Job / 모듈 통합 작업 노트 (A → B → C)

세 소비 모드를 위한 작업. 기준 C++ 빌드는 건드리지 않는다(빌드된 바이너리만 사용).

## (A) 경량 CLI SIF — 배치/HPC job용 (상태 없음)
- [x] `infra/apptainer/cli.def` — 바이너리 + gmsh + material_db 만 담은 자체완결 이미지
- [x] `infra/scripts/build-cli.sh` — cli.sif 빌드
- [x] `jobs/` — SLURM 예제 + README (원샷 `apptainer exec/run`)
- 목적: `apptainer exec kooremapper-cli.sif KooRemapper matdb config.yaml` 로 스케줄러 job 실행.
- 서비스(api/postgres/mcp)와 별개. 상태 없음, 워크디렉토리만 bind.

## (B) pyKooCAE Generator 모듈 스캐폴드
- [x] KooRemapper를 pyKooCAE `occProject/Generators` 스타일의 모듈로 감싸는 래퍼
- [x] CLI subprocess 방식(체인 스텝 친화, 상태 의존 없음) + 카탈로그 재사용
- 통합점: Runner/체인의 한 스텝으로 op 실행.

## (C) `kooremapper-core` 설치형 패키지
- [x] `argbuild` + `catalog`(catalog_data.json 포함)를 독립 pip 패키지로 추출
- [x] CLI·MCP·모듈이 한 소스(op 스키마 45개)를 공유
- 백엔드/모듈이 이 패키지를 import → 중복 제거, 드리프트 방지.

## 크로스플랫폼 메모
- 기준 CLI(C++): 소스 크로스플랫폼(MSVC/APPLE/LINUX), Windows `dist/KooRemapper.exe` 존재 → 플랫폼별 빌드.
- MCP 서버·Python 클라이언트·core 패키지: 순수 Python → Win/Mac/Linux.
- Apptainer: 리눅스(HPC/WSL2 포함).
