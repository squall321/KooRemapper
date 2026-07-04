# kooremapper-core

KooRemapper의 **op 지식(45개 스키마·예제·호출규칙)과 인자 빌더**를 담은 의존성 최소
설치형 패키지. CLI·MCP·pyKooCAE 모듈이 이 **한 소스**를 공유해 op 인자 생성/검증을 중복
없이 한다(순수 Python → Win/Mac/Linux).

## 설치
```bash
pip install -e platform/core        # 또는 빌드해서 배포
```
의존성: `PyYAML`, `jsonschema` 뿐.

## 사용
```python
from pathlib import Path
from kooremapper_core import catalog, build_command

# 카탈로그 조회
for name in catalog.operation_names():           # 45개
    op = catalog.get_operation(name)
    schema = catalog.args_json_schema(name)       # JSON Schema (폼/검증용)

# 인자 → 실제 호출(argv + config.yaml) 생성
b = build_command(
    "matdb",
    {"model": "model.k", "output": "mapped.k",
     "materials": [{"match": "AL7003H", "mat_type": "MAT_PIECEWISE_LINEAR_PLASTICITY"},
                   {"match": "*"}]},
    Path("workdir"),
    material_db_default="/opt/kooremapper/materials/material_db.json",  # matdb에서 database 생략 시 주입
)
if b.error:
    raise ValueError(b.error)
# b.argv           → ["matdb", "config.yaml"]   (KooRemapper 바이너리에 그대로 전달)
# b.written_files  → {"config.yaml": "<yaml text>"}  (workdir에 이미 기록됨)
```

## 왜 별도 패키지인가
- **CLI/job** — argv/config를 만들어 `KooRemapper`(또는 cli.sif)에 전달.
- **MCP/REST 백엔드** — 같은 build_command로 Job 실행.
- **pyKooCAE 모듈** — dict 인자를 검증·config화해 체인 스텝 실행.

세 모드가 각자 argbuild를 다시 짜지 않게 하는 게 목적이다. 플랫폼 백엔드의
`app/runner/{catalog,argbuild}.py` 와 동일 로직이며, `catalog_data.json` 은 백엔드 복사본과
일치해야 한다(테스트 `test_core_catalog_matches_backend` 가 강제).

> 참고: `build_command` 는 순수 함수다. matdb 번들 DB 기본값은 플랫폼 정책이라, 여기선
> `material_db_default` 파라미터로 주입한다(백엔드는 `settings.kooremapper_bin` 옆 경로를 넘긴다).
