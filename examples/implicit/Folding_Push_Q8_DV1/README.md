# Folding_Push_Q8_DV1 — implicit 레벨별 YAML 템플릿

이 폴더의 YAML 17개(static_level1~8, dynamic_lv1~8, implicit_full)는 `Folding_Push_Q8_DV1_AdvancedRubber.k` 모델용 설정입니다.
**모델 파일은 저장소에 포함되어 있지 않습니다**(사내 해석 모델). 그대로 실행하면 `Cannot open model` 로 끝납니다.

사용법:

1. 대상 K 파일을 이 폴더에 `Folding_Push_Q8_DV1_AdvancedRubber.k` 로 두거나, YAML 의 `model:` 을 자기 모델 경로로 바꿉니다.
2. `./run_all.sh [KooRemapper 경로]` 로 17개를 한 번에 만들거나, `KooRemapper implicit static_level1.yaml` 처럼 하나씩 실행합니다.
3. `dispatch.sh` 는 만들어진 K 파일마다 폴더를 만들어 LS-DYNA 실행 스크립트(`run.sh`, `config.json`)를 돌립니다.

모델 없이 레벨 설정만 확인하려면 상위 폴더의 `examples/implicit/level*.yaml`(입력 `../ale/explicit.k` 포함)을 쓰세요.
