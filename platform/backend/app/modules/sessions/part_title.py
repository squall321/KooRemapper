# 세션 덱 파일의 *PART 제목 줄 하나를 바꾸는 순수 함수 — 바이트를 보존하며 그 줄만 고친다(줄 끝 꼴 · 다른 줄 그대로)
"""파트 이름 바꾸기(요청서 DF-15 · 계획 docs/01-plan/features/df-hotspot-session-1122.plan.md 4절).

키워드는 1열의 `*` 다(리더와 같다). `*PART` 블록에서 「제목 줄 + PID 가 맞는 Card 1」 을 찾는다 — Card 1 의 첫 칸(고정폭 10 · long 20 · 콤마)이
그 PID 이고 다음 두 칸(SECID · MID)이 정수인 줄의 바로 앞 자료 줄이 제목이다. 그런 자리가 하나가 아니면 바꾸지 않는다.
"""
from __future__ import annotations

import re

_OPTS = {"INERTIA", "CONTACT", "PRINT", "ATTACHMENT_NODES", "AVERAGED"}
_INT = re.compile(r"^[+-]?\d+$")


class TitleError(ValueError):
    """바꿀 수 없다 — 글이 까닭이다."""


def _kw(line: bytes) -> str | None:
    if len(line) > 1 and line[:1] == b"*" and chr(line[1]).isalpha():
        return line.split()[0].decode("latin-1").upper()
    return None


def _is_part_kw(kw: str) -> bool:
    if kw == "*PART":
        return True
    if not kw.startswith("*PART_"):
        return False
    rest = kw[len("*PART_"):]
    toks, i = rest.split("_"), 0
    while i < len(toks):
        two = "_".join(toks[i:i + 2])
        if two in _OPTS:
            i += 2
        elif toks[i] in _OPTS:
            i += 1
        else:
            return False
    return True


def _fields(line: str, w: int) -> list[str]:
    if "," in line:
        return [x.strip() for x in line.split(",")]
    return [line[k:k + w].strip() for k in range(0, len(line), w)]


def _is_card1(line: bytes, pid: int) -> bool:
    s = line.decode("latin-1").rstrip("\r\n")
    for w in (10, 20):
        f = _fields(s, w)
        if len(f) >= 3 and _INT.match(f[0] or "") and int(f[0]) == pid and _INT.match(f[1] or "") and _INT.match(f[2] or ""):
            return True
    return False


def check_title(title: str) -> None:
    if len(title) > 70:
        raise TitleError("제목은 70 자까지입니다(*PART 제목 칸 A70)")
    if any(ord(ch) < 0x20 or ord(ch) > 0x7E for ch in title):
        raise TitleError("제목은 출력 가능한 ASCII 글자만 씁니다(줄바꿈 · 한글 같은 여러 바이트 글자는 칸 셈이 어긋난다)")
    if title[:1] in ("*", "$"):
        raise TitleError("제목은 `*` · `$` 로 시작할 수 없습니다(키워드 · 주석으로 읽힌다)")


def rename(data: bytes, pid: int, title: str) -> tuple[bytes, dict]:
    """`data`(덱 바이트)에서 PID 의 제목 줄을 바꾼 바이트와 `{line_no, old_title}` — 자리가 하나가 아니면 `TitleError`."""
    check_title(title)
    lines = data.splitlines(keepends=True)
    in_part = False
    hits = []
    prev_data = None
    for i, ln in enumerate(lines):
        kw = _kw(ln)
        if kw is not None:
            in_part = _is_part_kw(kw)
            prev_data = None
            if kw == "*END":
                break
            continue
        if not in_part or ln[:1] == b"$":
            continue
        if prev_data is not None and _is_card1(ln, pid):
            hits.append(prev_data)
        prev_data = i
    if not hits:
        raise TitleError(f"주 덱의 *PART 에 파트 {pid} 가 없습니다 — 인클루드 안이면 그 파일을 file_id 로 주세요")
    if len(hits) > 1:
        raise TitleError(f"파트 {pid} 의 *PART 정의가 {len(hits)} 곳입니다(줄 {', '.join(str(h + 1) for h in hits)}) — 바꾸지 않았습니다")
    i = hits[0]
    old = lines[i]
    body = old.rstrip(b"\r\n")
    end = old[len(body):]
    lines[i] = title.encode("ascii") + end
    return b"".join(lines), {"line_no": i + 1, "old_title": body.decode("latin-1").strip()}
