# 결정 노트 — 10-16 마무리

- **(2026-10-16) 낡은 말의 뿌리는 하나다.** 07a6802 가 분석 op(info · modelmeta · section · surfview · stackdiagram)이
  인클루드 닫힘을 읽게 바꿨는데, 「리더는 `*INCLUDE` 를 읽지 않는다」를 전제로 쓴 문장을 함께 고치지 않았다. 점검에서 찾은 자리 —
  MCP 도구 설명 둘(`upload_kfile`·`session_includes`) · 카탈로그 그림 셋 `model` · `section` 콘솔 안내 · `info` 경고 한 줄 ·
  주석 넷 · 백엔드 주석 셋. 덱을 **고쳐 쓰는** op 은 여전히 주 덱만 고치므로 인클루드 게이트(빠지면 422)의 근거는 그대로다 —
  문장만 「분석은 읽고, 고쳐 쓰기는 주 덱만」으로 가른다.
- **`*INCLUDE 안은 보지 않았습니다:` 줄은 고치지 않는다.** 플랫폼 `kfile_inspect._RE_REF_UNREAD` 와 시험 셋이 그 글자를
  잡는다. 항목마다 까닭(없다 · 따라가지 않았다 · 깊이 상한)이 붙어 있어 지금도 거짓이 아니다.
- **`allow_missing_includes` 는 MCP 로 못 넘긴다(실측 — `run_operation` 이 `operation`·`args` 만 보낸다 · 웹에도 없다).**
  그런데 `session_includes` 설명과 422 문구가 「true 로 넘어갈 수 있다」고 안내해, AI 가 그것을 `args` 에 넣으면 구조화 op
  검증이 「Additional properties」로 또 거절한다. 길을 여는 것은 사용자 결정 — 지금은 설명을 사실대로 고친다.
