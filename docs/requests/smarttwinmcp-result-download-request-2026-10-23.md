<!-- 요청서 초안 — DynaForge(KooRemapper 플랫폼)가 stcx 전각도 잡의 리포트를 스스로 가져올 길을 SmartTwinMCP · stcx 대시보드 쪽에 청한다 -->
# 요청서(초안) — stcx 잡 결과 리포트를 가져오는 길 (2026-10-23)

대상 SmartTwinMCP(`KooSlurmInstallAutomationRefactory/dashboard/smarttwin_mcp`) · stcx 대시보드 백엔드(:5010) 담당
보내는 쪽 DynaForge(KooRemapper 플랫폼) · 상태 **초안 — 아직 보내지 않았다**

**한 줄**

전각도 낙하 잡이 끝나면 DynaForge 가 그 잡의 `sphere_report.html`(과 딸린 그림 · 영상 폴더)을 스스로 가져와 반입하려 한다.
지금은 cae00 에서 그 파일에 닿는 길이 없다. **새 ssh 신뢰 없이**, 이미 있는 두 길(게이트웨이 MCP · :5010 터널) 중 하나에
읽기 전용 내려받기를 청한다.

---

## 1. 지금 (코드 근거)

- **제출.** DynaForge → 게이트웨이 MCP(9110) → 5013 `fullangle_drop_simulation`. 덱은 그 전에 :5010 청크 업로드
  (`/api/v2/files/upload/{init,chunk,complete}`)로 올린다. cae00 `/data` 와 stcx `/data` 가 다른 저장소라서다.
- **완료.** `job_status` · `job_details` 로 succeeded 를 보고 `registry_id` · `result_dir` · `sphere_report_path` 를 적는다.
  **파일은 가져오지 않는다.** 리포트는 사람이 손으로 올린다.
- **가져올 수단을 찾아봤다.**
  - `fetch_job_output`(5013 catalog 1.0.0) — `local` 은 경로만 준다(같은 파일시스템 전제). `rsync` 는 stcx 쪽이 cae00 에
    passwordless ssh 로 닿아야 한다(새 신뢰). `presigned_url` 은 메타에 「out-of-scope for this build — requires the storage sidecar」.
  - :5010 에는 업로드와 `GET /api/storage/files`(목록)만 있고, 결과 파일을 내려받는 길은 없다(`reports_api` 의 내려받기는
    대시보드 자체 보고서용이다).

## 2. 청하는 것 — 셋 중 하나 (우리 선호 순)

**A. :5010 에 읽기 전용 내려받기 — 업로드의 짝.**
- `GET /api/v2/files/list?registry_id=<id>&glob=<…>` — 그 잡 `result_dir` 안의 이름 · 크기 · mtime.
- `GET /api/v2/files/download?registry_id=<id>&path=<result_dir 기준 상대 경로>` — `Range`(이어받기) · `Content-Length` ·
  sha256(헤더나 별도 호출).
- 범위는 **그 잡의 `result_dir` 안만**이다(`..` · 절대 경로 · 바깥을 가리키는 심링크는 거절). 소유자 제한은 `mode-own` 과 같은 뜻.
- ⚠ 지금 업로드 API 는 인증 헤더가 없다(우리 `StcxUploader` 는 아무 헤더도 보내지 않는다). 내려받기는 결과 파일을 내주므로
  적어도 위 범위 제한이 필요하다. 토큰을 두면 우리는 설정 한 칸으로 받는다.

**B. `fetch_job_output` 의 `presigned_url`.** 스토리지 사이드카가 서고, 그 URL 을 cae00 이 기존 터널로 열 수 있으면 된다.
만료 시간과 1회용 여부를 알려 달라.

**C. 작은 파일 인라인 도구.** catalog 도구 하나(예 `fetch_report`)가 `sphere_report_path` 의 파일(과 사이드카 zip)을 base64 로
돌려준다. 새 엔드포인트는 없지만 상한을 넘는 큰 파일에는 못 쓴다.

## 3. 받는 길이 생기면 우리가 할 것

- 폴링이 succeeded 를 보면 그 잡의 `sphere_report.html`(+ 사이드카)을 받아 `/reports/intake` 와 같은 길로 반입하고, 잡에 리포트를 잇는다.
- 받은 바이트를 sha 로 대조한다(주시면). 가져오기가 실패해도 잡은 succeeded 로 두고 「리포트 가져오기 실패 · 까닭」을 남긴다.
  손 반입은 지금처럼 된다.
- 크기 상한은 설정으로 둔다. 1각도 HTML 은 1.1 MB 였고, 162각도 · 사이드카 포함 크기는 아직 재지 않았다.

## 4. 묻는 것

- **Q1** A · B · C 중 어느 쪽이 그쪽 구조에 맞나. 다른 길이 있으면 그것도 좋다.
- **Q2** `sphere_report_path` 는 언제나 `result_dir` 안인가. 사이드카(그림 · 영상)는 어디에 생기나.
- **Q3** 결과 폴더는 언제까지 남나(정리 정책). 가져오기를 몇 시간 안에 끝내야 하나.
