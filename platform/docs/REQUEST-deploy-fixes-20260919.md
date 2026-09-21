# 요청 — 배포·안내 결함 넷 (2026-09-19)

포털 쪽에서 09-19 요청서(`DYNAFORGE_DEPLOY_REVIEW.md` 후속)를 코드와 dev 실측으로 다시 확인한 결과다.
**확인한 것만** 적었고, 확인 못 한 것은 「미확인」이라고 표시했다. 판정 기준은 원격 최신
`origin/feat/kooremapper-platform`(c10a1d5)이다.

우선순위는 ①이 압도적으로 높다 — **"간헐적 접속 불가"의 직접 원인**이고, 다른 셋은 안내 문제다.

| | 무엇 | 자리 | 급함 |
|---|---|---|---|
| ① | 감독자가 **멀쩡한 API 를 재기동**한다(하루 100회 이상) | `platform/infra/scripts/_common.sh:108` | ★★★ |
| ② | 재기동 실패 종료코드가 **늘 0** 으로 찍힌다 | `platform/infra/scripts/supervisor.sh:38` | ★★ |
| ③ | 감독자를 **지금 띄우지 않는다**(재부팅 전까지 감독 공백) | `platform/infra/scripts/install-autostart.sh` | ★★ |
| ④ | MCP 접속 힌트가 공개 주소를 **지어낸다**(포트 유실·내부 주소) | `platform/backend/app/modules/system/routes.py:67`·`users/routes.py:18-31` | ★ |

---

## ① 감독자가 멀쩡한 API 를 죽이고 다시 띄운다 ★최우선

`_common.sh:108-110`:

```bash
instance_running() {
  "$APPTAINER" instance list --json 2>/dev/null | grep -q "\"instance\": *\"$1\"" || return 1
}
```

같은 파일 3행이 `set -euo pipefail` 이다. `grep -q` 는 **첫 매칭에서 바로 끝나고**, 그러면 아직 쓰고 있던
`apptainer` 가 `SIGPIPE` 로 죽어 종료코드 141 이 된다. `pipefail` 은 파이프라인 전체를 실패로 만들므로
**떠 있는 인스턴스를 "없다" 로 판정**한다. 목록에서 앞에 오는 인스턴스일수록(= 뒤에 남은 출력이 많을수록)
자주 걸린다.

**dev 실측(2026-09-18~19, `platform/infra/data/supervisor.log`)**

| 날짜 | `api down` | `api restart 성공` | `api restart 실패` | `mcp down` |
|---|---|---|---|---|
| 09-18 | **168** | 106 | 62 | 0 |
| 09-19(오전) | 9 | 5 | 4 | 0 |

- `restart 성공` 106회는 `restart-api-only.sh` 가 자기 검사를 통과해 **멀쩡한 API 를 stop→start** 한 것이다.
- `실패` 62회는 그 검사마저 거짓 음성이라 stop 을 건너뛰고 start 로 가서 `instance koorm_api already exists`
  가 난 것이다.
- `mcp down` 이 0회인 것이 방증이다 — `koorm_mcp` 는 목록 뒤쪽이라 SIGPIPE 를 거의 안 맞는다.
- 감독자 프로세스는 하나뿐이다(dev pid 4133) — 두 감독자가 겹친 경합이 아니다.

**영향** — DynaForge 웹과 MCP 도구가 하루 100번 이상 수 초씩 끊긴다. 요청서의 "간헐적 접속 불가" 가 이것이다.
진행 중인 잡이 함께 죽는지는 미확인이다.

**고침** — 출력을 먼저 받아 두거나 `-q` 를 쓰지 않는다.

```bash
instance_running() {
  local out
  out="$("$APPTAINER" instance list --json 2>/dev/null)" || return 1
  case "$out" in *"\"instance\": \"$1\""*) return 0 ;; *) return 1 ;; esac
}
```

⚠ 같은 꼴(`… | grep -q`)이 다른 스크립트에도 있으면 함께 본다 — `pipefail` 아래서는 전부 같은 병을 갖는다.

## ② 재기동 실패 종료코드가 늘 0 이다

`supervisor.sh:38`:

```bash
echo "[$(date '+%F %T')] api restart 실패(rc=$?) — /tmp/koorm-restart-api.log"
```

`$?` 를 읽기 전에 `$(date)` 가 돌아 **date 의 종료코드(0)** 가 찍힌다. dev 로그에 `실패(rc=0)` 가 **431줄**
있다. 실패 원인을 이 줄로는 못 가른다.

**고침** — rc 를 먼저 받아 둔다.

```bash
if "$SCRIPT_DIR/restart-api-only.sh" >/tmp/koorm-restart-api.log 2>&1; then
  echo "[$(date '+%F %T')] api restart 성공"
else
  rc=$?
  echo "[$(date '+%F %T')] api restart 실패(rc=$rc) — /tmp/koorm-restart-api.log"
  …
fi
```

## ③ 감독자를 설치만 하고 띄우지 않는다

`install-autostart.sh` 는 `@reboot` crontab 줄만 쓴다. `start.sh` 도 감독자를 띄우지 않는다. 그래서
**배포 직후~다음 재부팅 전까지는 감독자가 없고**, 감독 루프가 죽어도 되살리는 주체가 없다. 다른 스택
(HEAXHub·AIDataHub 등)은 매분 도는 watchdog 크론을 갖고 있다.

**고침(둘 중 하나)**
- 설치 스크립트가 크론 줄을 쓴 뒤 `pgrep -f "$SCRIPT_DIR/supervisor.sh"` 로 확인하고 없으면 그 자리에서
  `nohup … supervisor.sh &` 로 띄운다.
- 더 단단하게 — `@reboot` 무한 루프 대신 `* * * * * supervisor.sh --once` 로 바꾼다. 부팅과 루프 사망이
  한 번에 해결되고 다른 스택과 모양이 같아진다. (`--once` 는 이미 있다.)

⚠ ①을 먼저 고친다. ①이 남은 채로 크론 주기를 촘촘히 하면 **거짓 재기동만 늘어난다.**

## ④ MCP 접속 힌트가 공개 주소를 지어낸다

- `system/routes.py:67` 은 설정을 보지 않고 `f"http://<host>:{settings.mcp_port}/mcp"` 를 박는다.
- `users/routes.py:18-31` 의 `mcp_public_url` 은 `설정 → X-Forwarded-Host → http://127.0.0.1:8701/mcp` 순인데,
  **세 경로 모두 틀린 값**이 나온다(dev 읽기전용 GET 실측).

| 부른 경로 | 나온 값 | 무엇이 틀렸나 |
|---|---|---|
| 포털(:8088) 경유 | `http://<IP>/apps/kooremapper_mcp/mcp` | **포트(:8088)가 빠졌다** — nginx 가 Host 를 `$host`(포트 없음)로 넘긴다 |
| HEAX Caddy(:4180) 경유 | `http://127.0.0.1:4180/apps/…` | 내부 주소다 — Caddy 에 `trusted_proxies` 가 없어 X-Forwarded-* 를 자기 Host 로 덮는다 |
| 직결 | `http://127.0.0.1:8701/mcp` | 루프백 폴백 |

MCP 경유 호출에는 원리상 공개 주소를 알 방법이 없다 — MCP 서버가 백엔드로 `Authorization` 만 넘긴다
(`mcp_server/server.py:32-39`). **헤더로는 못 얻는다.**

**고침** — 형제 앱 StepForge 가 같은 문제를 겪고 정한 규율을 그대로 권한다(그쪽 D-272):
`X-Forwarded-Host` 로 **지어내지 않는다.** 설정이 없으면 **모른다고 말한다.**

1. `mcp_public_url` 을 `설정(KOORM_MCP_PUBLIC_URL, 또는 KOORM_PUBLIC_BASE + '/apps/kooremapper_mcp/mcp')` 만
   보게 하고, 없으면 `<포털오리진>/apps/kooremapper_mcp/mcp` 자리표시자 + "공개 주소 미설정" 경고를 낸다.
   그쪽 `report_upload_instructions`(`mcp_server/server.py:371`)가 이미 그 모양이다.
2. `system_status`(67)·`system_capabilities`(96-99)·웹 토큰 화면 스니펫(`users/routes.py:34-40`)이 **그 함수 하나**를
   쓰게 한다. 지금은 셋이 각자 다른 답을 낸다.
3. `.env.example` MCP 절에 `KOORM_MCP_PUBLIC_URL`·`KOORM_PUBLIC_BASE` 를 적는다(둘 다 코드에는 있는데 문서에
   없다 — `KOORM_ANALYSIS_PUBLIC_BASE_URL` 은 이미 문서화돼 있다).
4. **운영 조치** — 그 서버 `platform/.env` 에 값을 넣고 api·mcp 를 재기동해야 증상이 실제로 없어진다.
   코드만 고치면 자리표시자로 바뀔 뿐이다.

---

## 표시명 "System Admin" 은 계정 문제다 (요청서 C-2)

dev 에서 확인한 것 — 그 표시명은 **HEAX 시드 관리자 계정 자체로 로그인한 경우**였다
(`whoami.email == SEED_ADMIN_EMAIL`). 개인 계정이 시드 행을 재사용한 것이 아니다.

**그 서버에서 먼저 `whoami` 의 이메일을 보라.**
- 시드 관리자 이메일이면 — 공용 계정이므로 **이름을 바꾸지 말고** 개인 계정으로 로그인해 `kr_` PAT 을 다시 발급한다.
- 개인 이메일이면 — 표시명만 고친다. DynaForge 는 JIT 이후 이름을 다시 읽지 않으므로
  관리자 `PATCH /api/v1/admin/users/{id} {"display_name": …}` 로 함께 고쳐야 한다.

`is_system_admin=false` 는 의도된 동작이다(HEAX 관리자를 DynaForge 관리자로 매핑하지 않는다) — 고치지 말 것.

## 알려 둘 것 — 허브가 보내는 표시명 헤더가 바뀌었다

HEAXHub `authz` 게이트가 표시명을 **latin-1 로 못 싣는 경우 빈 값으로** 보낸다(오늘 고쳤다, HEAXHub 57d1e68).
전에는 한글 표시명에서 `UnicodeEncodeError` → 게이트 500 → 그 사용자는 `/apps/*` 를 **하나도** 못 썼다
(dev 사용자 44명 중 6명이 해당, 로그에 authz 500 셋).

- DynaForge 쪽 영향 — `sso_login` 의 JIT 프로비저닝(`auth/routes.py:92`)이 받는 `x-heax-user-name` 이
  한글 이름인 사용자에게는 **빈 문자열**로 온다. 지금 코드는 `or None` 이라 그대로 안전하다.
- 한글 이름을 그대로 나르려면 허브가 퍼센트 인코딩해 보내고 **받는 쪽이 `unquote`** 해야 한다. 그렇게 하길
  원하면 알려 달라 — 양쪽을 같은 시점에 바꿔야 한다(지금 바꾸면 ASCII 이름의 공백이 `%20` 으로 보인다).

## `/apps/kooremapper_mcp/mcp` 의 406 은 결함이 아니다 (요청서 D-2)

dev 에서 그대로 재현되지만 **인증을 거는 층이 다른 것**이다. 이 앱 매니페스트는 `portal_auth` 를 일부러 빼
두었고(forward_auth 가 `kr_` PAT 를 HEAX 자격으로 잘못 읽어 401 을 낸다), 그래서 Caddy 가 forward_auth 핸들러를
붙이지 않는다. 인증 없는 GET 은 `:8701` FastMCP 까지 가고 FastMCP 가 `Client must accept text/event-stream`
으로 406 을 낸다. 다른 MCP 앱은 앞단 게이트가 401 을 먼저 낸다.

**판정은 상태코드가 아니라 게이트웨이 `/tools-map` 의 도구 수로 하는 게 맞다**(dev 는 `heax-kooremapper_mcp`
50 tools, reachable). 익명 `initialize`·`tools/list` 까지 막고 싶으면 FastMCP 앞에 `Authorization` 없으면 401 을
내는 ASGI 검사를 두면 된다 — 게이트웨이는 `kr_` Bearer 를 싣고 오므로 영향이 없다. 매니페스트에 `portal_auth` 를
켜는 방식은 `kr_` PAT 를 깨뜨리므로 쓰면 안 된다.

---

### 이 요청서가 나온 경위

포털 쪽 절차 기능이 "재현을 시도하면 결손이 드러난다" 는 고리를 돌린다(HWAXPortal `docs/procedures/PLAN.md` §9-2).
이번에는 사용자가 09-19 에 낸 요청서를 **코드·배포와 대조**하다가 위 넷이 나왔다. ①②③은 그쪽 스택 안의 문제라
우리가 손대지 않았다. 소속 헤더 계약은 같은 폴더의 `REQUEST-postprocess-operation.md` §8(개정판)에 있다.

⚠ 한 번 헛짚은 적이 있어 적어 둔다 — 그 §8 의 첫 판("헤더 하나만 읽으면 된다")은 **틀렸다.** 지금 판은 서명을
함께 싣는다. 이번 문서도 틀린 곳이 있으면 알려 달라. 위 표의 수치는 dev 로그·원격 소스에서 직접 센 것이고,
그 서버의 상태는 미확인이다.

---

# 2026-09-20 — 포털 회신: 넷 다 미수정이라 **고쳐서 브랜치로 올렸다** · §8 되물음 답

## 먼저 답 — nginx 에서 두 헤더를 지워도 **우리 경로의 증명은 안 지워진다**

(`REQUEST-postprocess-operation.md` §9 의 "게이트웨이가 앱 nginx 를 거치지 않는 구성이라면 알려 달라")

**거치지 않는다.** 허브가 프록시 모드로 MCP 서버에 직결한다 — HEAXHub
`integrations/kooremapper-mcp/.portal/manifest.yaml` 의 `launch.mode: proxy`,
`upstream: http://127.0.0.1:8701`. dev 에서 포트도 그대로 갈린다: `:8701` 은 `koorm_mcp`(loopback 전용),
`:8443` 은 `koorm_nginx`. 그러니 `location /mcp`·`location /api/` 에서 두 헤더를 비워도 우리 호출이 실어
보낸 정상 증명은 지워지지 않는다.

다만 거절 사유의 나머지는 그대로 유효하다 — **위조 방어는 서명이 이미 한다.** 이건 심층 방어일 뿐이니
넣을지는 그쪽 판단이고, 우리가 요구하지 않는다. 사외 PC 가 `:8443` 으로 **직접** 붙는 경로가 있다면
그 location 에서만 지워도 된다.

## §8 구현 잘 받았다 — 특히 요청 **밖**의 자리를 본 것

`verified_affiliation()` · `_forward_headers()` · 반입 시점 동결 · 요청마다 검증 · 읽기/수정 분리 전부
계약대로다. **검색·facet 확장은 우리가 못 본 자리였다** — 상세만 열면 같은 소속 사람이 리포트를 *찾을 수*
없다는 지적이 맞다. 빈 소속이 어느 쪽에서도 매칭되지 않는 것까지 시험이 걸어 둔 것을 확인했다.

## 배포 결함 넷 — 2026-09-20 기준 **미수정**이었다

`git fetch --all` 뒤 여덟 ref(`main` · `feat/kooremapper-platform` · `integrate/defects-20260918` ·
`wip/*` 넷 · `HEAD`)에서 다섯 파일이 **동일 blob** 이고, `git log --all --since=2026-09-16 -- <다섯 파일>` 이
빈 출력이다. 그래서 "고쳤는데 배포가 안 됐다" 가 아니라 **수정 자체가 없다**고 판정했다. 164 커밋은
restack·파서·요소 카드 줄기였다 — 우선순위 판단이었다면 그 말만 해 주면 된다(우리도 그 판단을 존중한다).

**브랜치 `fix/deploy-defects-20260919`(커밋 `71edaf1`, origin 에 푸시)에 고쳐 두었다.**
머지·배포는 하지 않았다 — 그쪽 작업트리·브랜치·워크트리 어디에도 손대지 않았다.

### ① 먼저 정정 — 우리 진단은 **재현 조건이 빠져 있었다**

요청서 ①은 "SIGPIPE 때문" 이라고 단정했는데, **유휴 상태에서는 재현되지 않는다(400회 중 0회).**
목록 출력이 13KB 라 파이프 버퍼(64KiB) 안에 들어가 apptainer 가 먼저 끝나기 때문이다. 우리 쪽 재검증도
여기서 한 번 "원인이 아니다" 로 기울었다. 그 판정이 틀렸다 — **부하를 걸면 난다.**

| 구현 | 경합 중 600회 | rc |
|---|---|---|
| 옛 `… instance list --json \| grep -q …` | 거짓 음성 **88 (14.7%)** | 전부 141 |
| 고친 구현(출력 먼저·모름 분리) | **0** | — |

감독자는 30초마다 도니 하루 2,880회다 — 1% 만 걸려도 하루 28회이고, 실측이 09-19 28회 · 09-18 168회다.
사고 당시 로그가 방증이다: `api down (인스턴스 없음)` 직후 `restart-api-only.sh` 의 `stop` 이
**PID 를 잡아 세웠다**(그 순간 인스턴스는 살아 있었다는 뜻이다).

**재현**(읽기 전용, start/stop 안 한다):

```bash
APPT=$( . platform/infra/scripts/_common.sh >/dev/null 2>&1; echo "$APPTAINER" )
for k in 1 2 3 4 5 6; do ( for ((j=0;j<600;j++)); do "$APPT" instance list --json >/dev/null 2>&1; done ) & done
fail=0; for ((i=0;i<600;i++)); do
  "$APPT" instance list --json 2>/dev/null | grep -q '"instance": *"koorm_api"' || fail=$((fail+1))
done; wait; echo "거짓 음성 $fail / 600"
```

### 고친 내용

| | 무엇 | 자리 |
|---|---|---|
| ① | 파이프 제거 **+ 조회 실패(2)와 부재(1)를 가른다.** 감독자는 2 면 그 회차를 건너뛴다(`gone_for_sure`). 다만 **헬스가 독립적으로 나쁘면 그때는 재기동한다** — 모른다고 손 놓지 않는다 | `_common.sh` · `supervisor.sh` |
| ② | `rc=$?` 를 else 가지 **첫 문장**으로. mcp 실패 가지도 rc 를 남긴다 | `supervisor.sh` |
| ③ | 설치가 감독자를 **지금** 띄운다(이미 돌면 안 띄운다 — 둘이면 서로의 재기동을 밟는다) | `install-autostart.sh` |
| ④ | 설정 > 프록시 경로 > **(호출자가 루프백일 때만)** 루프백, 그 밖에는 **모른다고 한다.** 모르면 `claude mcp add` 명령을 아예 만들지 않고 무엇을 설정해야 하는지 알린다 | `users/routes.py` · `system/routes.py` |
| + | 같은 꼴 네 자리 — `status.sh`(ss 가 필터 없어 실제로 위험) · `start.sh` 둘(점유된 포트를 "비었다"로 추천) · `dist-from-drive.sh`(조용히 낡은 dist 로 강등). 행 전체 일치 의미는 지켰다 | 요청서 §①의 "다른 스크립트도 함께 본다" |

⚠ ③에서 **함정을 하나 밟았다가 고쳤다** — 데몬을 `( cd X && nohup … & )` 서브셸로 띄우면 **호출자가 자식
수명만큼 매달린다**(실측: 스텁 감독자 `sleep 4` 에 호출 4.0초, `sleep 6` 에 6.0초). 자식 fd 는 깨끗한데도
그렇다. 사람이 손으로 부를 땐 안 보이고, 출력을 받아 가는 자동화(CI·설치 래퍼·`$(...)`)에서는 **영영 안
끝난다.** `nohup … & disown` 으로 바꾸고 시험에 **경과시간 단언**을 넣었다(기능 단언만으론 안 잡힌다).

### 시험

`platform/backend/tests/test_deploy_defects_20260919.py` **9건**. 스크립트의 **실제 텍스트**를 떼어 가짜
apptainer 로 돌리므로, 누가 그 스크립트를 고치면 이 시험이 그 고친 것을 돈다(`.env.example` 로 가짜 트리를
만들고 `--once` 로 감독자를 실제 실행한다 — 크론은 건드리지 않는다).

무력화 **7/7** — 옛 구현 복귀 · 모름을 부재로 뭉갬 · 감독자가 모름에 재기동 · `rc=$?` 를 echo 뒤로 ·
서브셸로 되돌림 · 중복 기동 가드 제거 · 원격에 루프백 건네기. 기존 회귀 포함 `pytest tests/ -q` →
**100 passed, 3 skipped**.

### 반영 — 우리는 하지 않았다

```bash
git merge fix/deploy-defects-20260919        # 브랜치를 그쪽 줄기에 얹는다
pkill -f 'bash .*/platform/infra/scripts/supervisor.sh'   # 옛 코드로 도는 감독자를 내린다
bash platform/infra/scripts/install-autostart.sh          # 새 코드로 다시 띄운다(크론은 멱등)
```

⚠ **머지만 하면 안 멎는다.** 감독자는 상주 프로세스라 파일을 다시 읽지 않는다 — 재기동이 필요하다.
확인은 로그다: `platform/infra/data/supervisor.log` 에 `api down (인스턴스 없음)` 이 멎고, 실패가 나면
`rc=0` 이 아닌 **진짜 종료코드**가 찍힌다.

### 틀린 곳이 있으면 알려 달라

위 수치는 전부 dev 에서 직접 센 것이고 **그쪽 서버 상태는 미확인**이다. 특히 ①의 경합 재현은 박스마다
인스턴스 수·부하가 달라 값이 다를 수 있다 — 위 재현 명령을 그쪽에서 돌려 보고 판단하면 된다.
우리 진단이 한 번 반쯤 틀렸던 것처럼(재현 조건 누락), 이 회신도 틀릴 수 있다.

---

## 회신 — 2026-09-20, DynaForge

브랜치 `integrate/defects-20260918`. 백엔드 시험 **124 passed, 3 skipped**(이 요청서 몫 17건 포함).
셸은 가짜 apptainer·crontab 으로 **스크립트째** 돌려 확인했다.

첫 수정(`71edaf1`)이 ①~④ 를 다뤘고, 그것을 적대적으로 다시 검토해 **남은 구멍을 메웠다.**
아래는 지금 상태다.

### ① 감독자가 멀쩡한 API 를 재기동한다 — 원인 + **순서**까지 고쳤다

- 원인(파이프 조기 종료 → SIGPIPE 141 → `pipefail` 이 "없음" 으로 뭉갬)은 `instance_running` 에서 제거했다.
  이제 **0 있음 · 1 없음 · 2 알 수 없음** 세 값을 낸다.
- ⚠ **그것만으로는 부족했다.** 판정 순서가 "목록 먼저" 인 한, 같은 꼴의 오판이 또 나오면 다시
  재기동으로 번진다. 그래서 감독자가 **헬스를 먼저** 본다 — 헬스 200 이면 목록이 무어라 하든 손대지 않는다.
  09-18 의 `restart 성공` 106회가 정확히 "목록은 없다, 헬스는 200" 이었다. 시험으로 고정했다
  (`test_it_does_not_restart_a_healthy_api_when_the_listing_says_gone`).
- ⚠ 요청서 §① 의 "다른 스크립트도 함께 본다" 를 **파이프 모양이 아니라 뜻으로** 확장했다.
  파이프는 첫 수정이 다 없앴지만, **모름(2)을 없음으로 읽는 자리**가 감독자 밖에 다섯 곳 남아 있었다.
  그중 하나는 파괴적이다.

  | 자리 | 모름일 때 옛 동작 | 지금 |
  |---|---|---|
  | `reset-db.sh` | postgres 를 멈추지 않고 **pgdata 를 rm -rf** | 지우지 않고 rc=1 로 멈춘다 |
  | `stop.sh` | `✓ not running` **거짓 성공** → 배포가 옛 인스턴스 위에서 계속 | stop 을 시도한다 |
  | `restart-api-only.sh` | stop 건너뜀 → `already exists`(09-18 실패 62회) | stop 을 시도한다 |
  | `restart.sh` | 같음 | stop 을 시도한다 |
  | `backup-db.sh` | `✗ not running` 오안내 | "상태를 알 수 없다" 로 구분 |
  | `start.sh` | — | 모르면 `✓ already running` 이라 단정하지 않는다 |

  기준은 하나다 — **없을 때만 해도 되는 일**은 확실할 때만, **있든 모르든 무해한 일**(stop 시도)은 모를 때도.
  `_common.sh:instance_absent_for_sure` 가 그 구분을 한 자리에서 준다.

### ② 재기동 실패 rc 가 늘 0 — api 말고 **모든 가지**를 맞췄다

`rc=$?` 를 첫 문장으로 옮긴 것에 더해, 결과를 아예 안 남기던 두 가지를 채웠다 —
`postgres`(`|| true` 로 성공·실패를 똑같이 삼켰다)와 `nginx`(`>/dev/null … || true`). dev 는
`KOORM_ENABLE_NGINX=1` 이라 nginx 가지가 살아 있는 경로인데, 매 회차 같은 이유로 못 뜨는 상태를
로그로 알 길이 없었다.

### ③ 감독 공백 — **둘째 안(권장)으로 갔다.** 첫 안은 절반만 막는다

첫 수정은 첫째 안(설치 때 지금 띄운다)이었다. 그것은 "설치~재부팅 공백" 은 막지만 요청서가 함께
지적한 **"루프가 죽으면 되살릴 주체가 없다"** 는 그대로 남는다. 그리고 중복 기동 가드가
`pgrep -f "bash <절대경로>/supervisor.sh"` 였는데, README 가 권하는 기동 방식은
`bash ./infra/scripts/supervisor.sh` 로 떠서 **패턴이 빗나간다**(실측). 감독자가 둘이 된다.

그래서:

- 크론을 `* * * * * supervisor.sh --once` 로 바꿨다. 부팅·루프 사망이 한 번에 풀리고 다른 스택과 모양이 같다.
  기존 `@reboot` 줄은 같은 MARK 라 **재설치가 곧 이관**이다.
- 중복은 프로세스 이름이 아니라 **파일 잠금**(`infra/data/supervisor.lock`)으로 막는다 — 어떻게 띄우든 통하고,
  매분 `--once` 가 앞 회차와 겹치는 것도 같은 잠금이 막는다.
- 설치는 그 자리에서 `--once` 를 한 번 돌린다(다음 정각까지 최대 1분을 비워 두지 않는다). 그 점검이 실패하면
  **설치도 실패로 끝난다** — ✓ 로 끝나면 사람은 감시가 선 줄 안다.

### ④ 주소를 지어내지 않는다 — 요청서 넷 중 **셋을 새로 이행**했다

첫 수정은 루프백 폴백만 좁혔고, 나머지가 남아 있었다.

1. **고침 1 — X-Forwarded-Host 파생을 걷어냈다.** 그것이 실측 세 경로 중 둘에서 틀린 값을 내던 바로 그 경로다.
   루프백 폴백도 없앴다 — `request.client` 는 **TCP 상대**라 MCP 경유 호출은 사람이 어디 있든 늘 127.0.0.1 로
   보인다(가드가 될 수 없다). 이제 `mcp_public_url()` 은 **설정만** 본다.
2. **고침 2 — 세 자리가 한 함수를 쓴다.** `system_status`·`system_capabilities`·토큰 화면이 모두
   `mcp_add_command()` 를 탄다.
   ⚠ 첫 수정에는 여기에 **새 결함**이 들어가 있었다 — `capabilities` 가 빈 주소를 f-string 에 그대로 끼워
   `claude mcp add --transport http kooremapper  --header "…"` 라는 **URL 칸만 빈 명령**을 냈고, 시스템 화면이
   그것을 복사 버튼과 함께 그렸다. 커밋이 없앴다고 한 "반쯤 맞는 명령" 이 토큰 화면 대신 시스템 화면에 남아 있었다.
3. **고침 3 — `.env.example` 에 `KOORM_MCP_PUBLIC_URL` 을 적었다.**
   ⚠ 요청서가 적은 `KOORM_PUBLIC_BASE` 는 **코드에 없다**(백엔드가 읽지 않는다). 있는 것은
   `KOORM_ANALYSIS_PUBLIC_BASE_URL` 뿐이다 — 요청서의 "둘 다 코드에는 있는데" 는 사실과 다르다.
   지금은 키를 하나만 둔다. 베이스에서 파생하는 쪽이 낫다면 말해 달라.
4. **고침 4(운영 조치) — 아직 안 했다.** 그 서버 `platform/.env` 에 아래를 넣고 api 를 재기동해야 증상이 없어진다.
   ```
   KOORM_MCP_PUBLIC_URL=https://<포털오리진:포트>/apps/kooremapper_mcp/mcp
   ```
   ⚠ **지금은 값이 없으면 화면이 "모른다" 를 낸다**(전에는 틀린 주소라도 나왔다). 그것이 요청서가 원한 모양이지만,
   운영에 반영하기 전까지는 포털 경유 사용자에게도 접속 명령이 안 보인다는 뜻이다.

   그리고 하나 더 — **안내 문구가 없는 변수 이름을 말하고 있었다.** `MCP_PUBLIC_URL` 이라고 적혀 있었는데
   실제로 읽히는 키는 `KOORM_` 접두사가 붙은 쪽이다. 시키는 대로 넣어도 화면이 그대로인 닫힌 고리였다.
   이름은 이제 `config.MCP_PUBLIC_URL_ENV` 한 곳에서 끌어 쓴다.

### 시험

`backend/tests/test_deploy_defects_20260919.py` **17건**. 무력화 **7/7** 로 확인했다 —
헬스 우선 판정 되돌리기 · 잠금 가드 제거 · 주소를 다시 지어내기 · capabilities 를 f-string 으로 되돌리기 ·
안내를 접두사 없는 이름으로 되돌리기 · reset-db 가 모름을 없음으로 읽기 · 설치를 @reboot 루프로 되돌리기.

⚠ 그 과정에서 **거짓 초록을 하나 잡았다.** capabilities 시험이 임포트한 함수만 불러서, 엔드포인트를
옛 f-string 으로 되돌려도 초록이었다. 지금은 라우트를 실제로 호출해 응답 봉투에서 값을 꺼내 본다.
③ 시험도 함수 발췌가 아니라 `install-autostart.sh` 를 **스크립트째** 돌린다(호출부를 지우면 빨개진다).

### 2026-09-21 보강 — 남겨 뒀던 셋도 닫았다

회신 첫 판에서 "안 했다" 고 적은 것들이다. 전부 무력화로 확인했다(합계 **12/12**, 시험 22건).

- **`status.sh`** 가 목록 조회 실패를 `· nginx not running` 으로 적었다 — 파괴적이지는 않지만 **사람이 보고
  판단하는 자리**라 더 나쁜 쪽이다. `⚠ nginx 판정 불가` 로 구분한다.
  (`start.sh` 의 스테일 락 정리만 옛 형태로 남겼다 — 블록 안에서 `kill -0` 로 pid 가 살아 있는지 다시 보므로
  판정이 아니라 pid 가 근거다. 이유를 주석에 적었다.)
- **토큰 발급 화면**도 주소를 모를 때 안내문을 복사 버튼 달린 코드 블록에 그리고 있었다 — 시스템 화면과 같이 경고로 바꿨다.
- **`install-autostart.sh --remove`** 가 돌고 있는 감독자를 실제로 멈춘다. 근거는 잠금 파일이 아니라 별도
  `supervisor.pid` 이고, pid 재사용을 감안해 `/proc/<pid>/cmdline` 으로 한 번 더 확인한 뒤 죽인다.
  ⚠ 이 과정에서 **우리가 방금 넣은 잠금에 결함이 있었다** — `exec 9>` 는 여는 순간 파일을 비우므로,
  매분 도는 `--once` 가 잠금을 못 얻고 물러나면서 먼저 돌던 감독자의 기록을 지웠다. `9>>` 로 고쳤다.
- **`start.sh`·`dist-from-drive.sh` 의 새 문자열 판정**에 회귀를 걸었다. `dist-from-drive.sh` 는 옛
  `grep -q '^koorm-bin\.tar\.gz$'` 의 **행 전체 일치**를 지켜야 한다 — 부분 일치로 느슨해지면 전송 중
  파일(`.part`)을 완성본으로 읽고, 조기 종료가 남으면 큰 목록에서 **조용히 낡은 dist 로 강등**한다.

### ⚠ 우리가 만든 사고 하나 — 잠금이 감시를 죽였다 (같은 날 잡음)

솔직히 적는다. ③ 의 중복 방지로 넣은 `flock` 이 **감시를 멈췄다.**

`exec 9>파일` 로 잡은 fd 는 **자식이 물려받는다.** 감독자가 띄운 apptainer 인스턴스는 영원히 살아 있으므로
그 fd 를 들고 잠금을 놓지 않는다. 09-21 01:26 에 감독자가 `koorm_mcp` 를 되살렸고, 그 인스턴스가 fd 9 를
물려받아 **이후 모든 회차가 "이미 감독자가 돌고 있다" 로 물러났다.** 01:29~01:32 로그가 그것이다.
프로세스의 열린 fd 를 훑어 범인을 확인했다(`koorm_mcp`·`appinit`·`python server.py` 가 모두 fd 9 를 쥐고 있었다).

중복을 막으려 넣은 장치가 감시를 통째로 끈 셈이다. `mkdir` 로 바꿨다 — 원자적이고 **fd 를 남기지 않아**
자식에게 새지 않는다. 죽은 감독자가 남긴 잠금은 우리가 적은 pid 와 `/proc/<pid>/cmdline` 으로 알아보고 걷어낸다
(한 번의 사고가 영구 정지가 되지 않도록). 시험 둘을 걸었고, 옛 flock 방식으로 되돌리면 둘 다 빨개진다.

### 운영 반영 — 2026-09-20 밤에 했다

- dev 트리를 통합본으로 fast-forward 했고(`cb1faec`), `install-autostart.sh` 로 **매분 감시**를 걸었다.
  옛 `@reboot` 줄은 이관됐다.
- 실제로 확인했다 — `koorm_mcp` 를 01:25:58 에 내리자 01:26:01 에 크론이 잡아 되살렸고(3초), 로그에
  `mcp restart 성공` 이 남았다(②).
- `platform/.env` 에 `KOORM_MCP_PUBLIC_URL=http://110.15.177.120:8088/apps/kooremapper_mcp/mcp` 를 넣고
  api 를 재기동했다. 그 경로는 인증 없는 GET 에 406 을 낸다(요청서가 결함이 아니라고 한 그 응답).
  돌고 있는 api 에서 확인한 값:
  ```
  claude mcp add --transport http kooremapper \
    http://110.15.177.120:8088/apps/kooremapper_mcp/mcp --header "Authorization: Bearer kr_..."
  ```
  ⚠ 컨테이너 `--env` 목록에는 이 키가 없다 — `Settings` 가 바인드된 `platform/.env` 를 직접 읽어서 통한다.
  나중에 `.env` 를 안 읽는 방식으로 바뀌면 `restart-api-only.sh`·`start.sh` 의 `--env` 목록에 넣어야 한다.

### 그 밖에 알려 둘 것

- **표시명 "System Admin"·406 은 손대지 않았다.** 요청서 판단(계정 문제 / 인증 층 차이)에 동의한다.
  `is_system_admin=false` 도 그대로 둔다.
- **허브 표시명 헤더** — 한글 이름을 퍼센트 인코딩으로 나르는 쪽으로 가고 싶으면 말해 달라. 받는 쪽
  `unquote` 는 소속 헤더에서 이미 같은 모양으로 쓰고 있다(`REQUEST-postprocess-operation.md` §8).
- ⚠ **dev 감독자가 2026-09-19 20:20 ~ 09-20 사이 멈춰 있었다.** 이 검토 중 우리 쪽에서 프로세스를 죽인 것이다.
  09-20 밤에 매분 감시로 복구했다(위 "운영 반영").
