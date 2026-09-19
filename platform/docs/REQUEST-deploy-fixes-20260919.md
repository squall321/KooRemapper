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
