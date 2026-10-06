# SmartTwinPreprocessor.sif bake 가 KooRemapper 를 **자동으로** 집게 하는 훅

`BuildSmartTwinPreprocessor.sh` 는 **이 리포 밖**(`/home/koopark/serviceApptainers/`)에 있고
어떤 git 저장소에도 들어 있지 않다. 그래서 그 스크립트가 교체되면 아래 두 삽입이 사라진다 —
이 문서가 복원 방법이다.

## 왜 필요한가 (실측, 두 번 당했다)

그 스크립트의 5/5 단계는 `appt313/opt/kooremapper/bin` 을 **그대로 복사**할 뿐이고, 그 스테이징
사본을 갱신하는 장치가 없었다. 그래서 **SIF 를 다시 구워도 구 바이너리가 그대로 나갔다.**

| 날짜 | 무슨 일 |
|---|---|
| 2026-10-02 | 13:15 재bake 가 **09-28 바이너리**(`25ca6b52`)를 구웠다. SIF 날짜만 새로워서 안 보였다 |
| 2026-10-06 | 또 같은 상태였다 — 스테이징이 10-02 본(`0dd2d26c`)이고 배포 SIF 가 세 그림 op 을 **0개** 알았다 |

사람이 기억해야 하는 단계는 두 번 잊혔다. 그래서 **빌드가 하게** 만들었다.

## 삽입 ① — 5/5 단계 **앞**에 스테이징 갱신

`echo "5/5 KooRemapper 복사 중..."` 줄 **바로 위**에 넣는다.

```bash
KOOREMAPPER_REPO="${KOOREMAPPER_REPO:-/home/koopark/claude/KooRemapper}"
STAGE_SH="${KOOREMAPPER_REPO}/scripts/stage-to-appt313.sh"
if [ "${SKIP_KOOREMAPPER_REFRESH:-0}" = "1" ]; then
    echo "(skip) KooRemapper 스테이징 갱신: SKIP_KOOREMAPPER_REFRESH=1"
elif [ -x "${STAGE_SH}" ]; then
    echo "5/5-0 KooRemapper 스테이징 갱신 중..."
    KOOREMAPPER_APPT313="$(readlink -f "${APPT_OPT}/kooremapper")" bash "${STAGE_SH}"
else
    echo "⚠ 스테이징 갱신 스크립트가 없다: ${STAGE_SH} — 구 바이너리가 나갈 수 있다" >&2
    echo "⚠   구워질 것: $(sha256sum "${APPT_OPT}/kooremapper/bin/KooRemapper" | cut -d' ' -f1)" >&2
fi
KOORM_EXPECT_SHA="$(sha256sum "${APPT_OPT}/kooremapper/bin/KooRemapper" | cut -d' ' -f1)"
```

## 삽입 ② — `apptainer build` **뒤**에 sha 검증

`ls -lh "${SIF}"` 뒤에 넣는다. ★**이것이 핵심이다** — 10-02 의 실패는 "SIF 날짜만 새로워서
안 보인" 것이었으므로 날짜가 아니라 **sha** 를 봐야 한다.

```bash
KOORM_BAKED_SHA="$(apptainer exec "${SIF}" sha256sum /opt/kooremapper/bin/KooRemapper 2>/dev/null | cut -d' ' -f1 || true)"
if [ "${KOORM_BAKED_SHA}" != "${KOORM_EXPECT_SHA}" ]; then
    echo "✗ 구워진 KooRemapper 가 스테이징과 다르다 — 이 SIF 를 배포하지 말 것." >&2
    exit 1
fi
```

검증이 동작하는지 확인하는 법 — **구 바이너리가 구워진 SIF** 에 대고 돌려 보면 불일치로
잡힌다(2026-10-06 에 그렇게 확인했다: 기대 `43084d35…`, 실제 `0dd2d26c…`).

## 정본 로직은 리포 안에 있다

`scripts/stage-to-appt313.sh` 가 실제 갱신을 한다. 혼자서도 돌릴 수 있다.

```
bash scripts/stage-to-appt313.sh            # 갱신
bash scripts/stage-to-appt313.sh --check    # 바꾸지 않고 필요 여부만 (필요하면 rc=2)
bash scripts/stage-to-appt313.sh --with-cli-sif   # cli.sif 도 함께
```

지키는 규율 셋.

- **백업은 `bin/` 밖**(`bin-backups/`)에 둔다 — `bin/` 은 통째로 구워져 SIF 에 두 번째
  바이너리가 들어간다(실측으로 그 실수를 했다).
- **glibc 를 검사한다.** 실사용 소비자 중 최솟값이 SmartTwinPreprocessor.sif 의 **2.35** 다.
  실측 — 호스트 빌드(`build/dev`)는 **GLIBC_2.38** 을 요구해 거부된다. 반드시
  `scripts/build_linux_compat.sh`(debian:12 빌더) 산출을 쓴다.
- **소스를 못 찾으면 조용히 넘기지 않는다** — 지금 구워질 사본의 sha·날짜를 크게 적는다.
  그 경고가 없어서 구 바이너리가 두 번 나갔다.

## bake 실행

```
sudo HOME=/home/koopark bash /home/koopark/serviceApptainers/BuildSmartTwinPreprocessor.sh
```

- `set -euo pipefail` 이라 **root** 여야 한다 — koopark 으로는 2/5 단계 `cp` 에서
  uid 100999 소유 파일 때문에 거부되고 죽는다(kooremapper 복사에 닿지도 못한다).
- `HOME` 을 넘겨야 마지막 Drive·메일 알림이 건너뛰어지지 않는다(`~/.config/smartTwinMailer.env`
  를 찾는다 — sudo 기본은 `HOME=/root`).
