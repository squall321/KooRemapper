from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, computed_field

from app.shared.diagnostics import redact


class JobCreate(BaseModel):
    operation: str
    args: dict = {}
    # 덱이 참조하는 `*INCLUDE` 가 세션에 없어도 강행한다. 기본은 막는 쪽이다 — 덱을 고쳐 쓰는 op 은
    # 인클루드 안을 고치지 않아 성공하지만 산출물에 그 줄이 보존돼, LS-DYNA 에 넣을 때야 깨진 것이 드러난다.
    # 인클루드를 클러스터에 따로 두는 운용을 위해 남겨 둔 탈출구다.
    allow_missing_includes: bool = False
    # 덱이 **정의되지 않은 것을 가리켜도** 강행한다.
    #
    # ⚠ 기본이 **통과**다(2026-09-27 캠페인 결정). 검사 자체는 P1-6 이 돌연변이까지 태워 정확하고
    # 추적 덱 489장 중 40장이 실제로 이 부류지만, 실사용 덱에 몇 장이 걸리는지 아직 안 세어 봤다.
    # 첫날부터 막으면 멀쩡한 운용이 멈추고, 그러면 사람은 게이트를 통째로 끈다 — 그 뒤엔 진짜를
    # 놓친다. 그래서 **경고로 시작한다**: 잡 기록(`warnings`)과 세션 화면에 남기고 막지는 않는다.
    #
    # `false` 로 주면 막는 쪽이 켜진다(단정 등급만, 422). 실사용 숫자를 센 뒤 기본값을 뒤집는 것이
    # 다음 결정이다 — 그때 이 주석과 `docs/requests/deck-contract-checklist.md` 를 같이 고친다.
    allow_dangling_refs: bool = True


def external_summary(kind: str | None, ref: dict | None) -> dict | None:
    """외부 잡(stcx · 후처리 예약)의 요약 — 원본 `external_ref` 대신 응답에 싣는다(2026-11-12, 포털 낙하 파이프라인 (a)).

    가이드 §4 · §5-1 이 보라는 두 칸(`cluster_state` · `ontology.state`)만 낸다. 원본에는 결과 폴더 경로 · 레지스트리 id ·
    업로드 id 가 있어 그대로 내보내지 않고, 문자열은 진단 번들과 **같은** `redact`(경로 접기 · 이메일 · 토큰)를 거친다.
    외부 잡이 아니면 None.
    """
    if not kind:
        return None
    ref = ref if isinstance(ref, dict) else {}

    def r(v):
        return redact(v) if isinstance(v, str) else v
    onto = ref.get("ontology") if isinstance(ref.get("ontology"), dict) else None
    out = {"kind": kind, "cluster_state": r(ref.get("cluster_state")), "ontology": None}
    if onto is not None:
        out["ontology"] = {"state": r(onto.get("state"))}
        if onto.get("why"):
            out["ontology"]["why"] = r(onto.get("why"))
    return out


class JobRead(BaseModel):
    id: str
    session_id: str
    operation: str
    args: dict
    resolved_cmd: dict | None
    status: str
    progress: int | None
    exit_code: int | None
    input_file_ids: list | None
    output_file_ids: list | None
    error_summary: str | None
    warnings: list | None = None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    # 원본은 받아만 두고 내보내지 않는다 — 응답에는 아래 `external` 요약만 간다.
    external_kind: str | None = Field(default=None, exclude=True)
    external_ref: dict | None = Field(default=None, exclude=True)

    model_config = {"from_attributes": True}

    @computed_field
    @property
    def external(self) -> dict | None:
        return external_summary(self.external_kind, self.external_ref)
