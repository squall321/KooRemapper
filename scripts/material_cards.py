# LS-DYNA 재료 카드의 칸 배치 한 곳 — 읽기(빌더)와 되쓰기(동기화)가 같은 표를 본다
"""왜 한 곳인가 — `build_material_db.py` 는 카드에서 물성을 **읽고**,
`material_sync.py` 는 갱신값을 카드에 **되쓴다**. 표가 둘로 갈라지면 읽은 자리와 쓴
자리가 어긋나 카드가 조용히 망가진다.

카드는 고정폭 10칸이다.

    $      MID        RO         E        PR      SIGY      ETAN      BETA
        130501 7.800e-09  200000.0    0.3000    260.00    990.72    0.0000
            ^0        ^10       ^20       ^30       ^40       ^50       ^60

⚠ **파생값은 되쓸 수 없다.** MOONEY·VISCOELASTIC 의 `E`·`PR` 은 카드에 그런 칸이 없고
A·B 나 BULK·G0 에서 계산한 것이다. 계산값을 없는 칸에 써 넣을 수는 없으므로
`WRITABLE` 에서 뺀다 — 되쓰기 요청이 오면 거절하고 사유를 든다.
"""
from __future__ import annotations

WIDTH = 10

# mat_type → {필드: 시작칸}. **카드에 실제로 있는 칸만** 적는다(파생값은 넣지 않는다).
CARD_FIELDS: dict[str, dict[str, int]] = {
    "MAT_ELASTIC":                     {"RHO": 10, "E": 20, "PR": 30},
    "MAT_RIGID":                       {"RHO": 10, "E": 20, "PR": 30},
    "MAT_PIECEWISE_LINEAR_PLASTICITY": {"RHO": 10, "E": 20, "PR": 30, "SIGY": 40,
                                        "ETAN": 50},
    "MAT_PLASTIC_KINEMATIC":           {"RHO": 10, "E": 20, "PR": 30, "SIGY": 40,
                                        "ETAN": 50, "BETA": 60},
    "MAT_SAMP-1":                      {"RHO": 10, "E": 20, "PR": 30},
    "MAT_HYPERELASTIC_RUBBER":         {"RHO": 10, "PR": 20},
    "MAT_ORTHOTROPIC_ELASTIC":         {"RHO": 10, "EA": 20, "EB": 30, "EC": 40,
                                        "PRBA": 50, "PRCA": 60, "PRCB": 70},
    "MAT_MOONEY-RIVLIN_RUBBER":        {"RHO": 10, "PR": 20, "A": 30, "B": 40},
    "MAT_VISCOELASTIC":                {"RHO": 10, "BULK": 20, "G0": 30, "GI": 40,
                                        "BETA": 50},
}

# 되쓸 수 있는 필드 = 카드에 칸이 있는 것. 파생 E·PR(MOONEY·VISCOELASTIC)은 여기 없다.
WRITABLE = {t: set(f) for t, f in CARD_FIELDS.items()}


class CardEditError(ValueError):
    """카드를 안전하게 고칠 수 없다 — 조용히 자르거나 밀어내지 않는다."""


def read_field(line: str, col: int, width: int = WIDTH) -> str:
    return line[col:col + width] if len(line) >= col else ""


def read_float(line: str, col: int, width: int = WIDTH) -> float | None:
    raw = read_field(line, col, width).strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def infer_format(current: str) -> str:
    """**있던 칸의 서식을 그대로 흉내 낸다** — 파일이 읽히는 모습을 바꾸지 않으려고.

    `7.800e-09` → `%10.3e`, `200000.0` → `%10.1f`, `0.3000` → `%10.4f`.
    """
    t = current.strip()
    if not t:
        return "%10.4g"
    if "e" in t.lower():
        mant = t.lower().split("e")[0]
        prec = len(mant.split(".")[1]) if "." in mant else 0
        return f"%{WIDTH}.{prec}e"
    if "." in t:
        return f"%{WIDTH}.{len(t.split('.')[1])}f"
    return f"%{WIDTH}d" if t.lstrip("-").isdigit() else "%10.4g"


def write_float(line: str, col: int, value: float, width: int = WIDTH) -> str:
    """한 칸만 바꾼 줄을 돌려준다. **칸을 넘치면 에러다** — 넘친 값은 옆 칸을 먹는다."""
    if len(line) < col + width:
        line = line.ljust(col + width)
    fmt = infer_format(line[col:col + width])
    try:
        text = fmt % value
    except (TypeError, ValueError) as exc:
        raise CardEditError(f"칸 {col} 에 {value!r} 를 쓸 수 없다: {exc}") from exc
    if len(text) > width:
        text = f"%{width}.3e" % value          # 서식을 좁혀 다시 시도
    if len(text) > width:
        raise CardEditError(f"칸 {col} 에 {value!r} 가 {width}칸을 넘친다 — "
                            f"옆 칸을 먹으므로 쓰지 않는다")
    return line[:col] + text + line[col + width:]


def data_line_index(card: str) -> int:
    """카드 텍스트에서 **첫 데이터 줄**의 인덱스.

    ⚠ `*`·`$` 아닌 첫 줄을 고르면 **제목 줄을 데이터로 오인한다** — `_TITLE` 카드의
    제목은 아무 접두도 없다(실측으로 밟았다: 제목에 물성값을 써 넣을 뻔했다).
    데이터 줄의 진짜 표식은 **첫 10칸이 정수 MID** 라는 것이다.
    """
    for i, line in enumerate(card.splitlines()):
        s = line.strip()
        if not s or s.startswith(("*", "$")):
            continue
        head = line[:WIDTH].strip()
        if head.lstrip("-").isdigit():
            return i
    raise CardEditError("카드에 데이터 줄이 없다(첫 10칸이 정수 MID 인 줄을 못 찾았다)")


def set_card_field(card: str, mat_type: str, field: str, value: float) -> str:
    """카드 원문의 한 칸을 고쳐 돌려준다."""
    cols = CARD_FIELDS.get(mat_type)
    if not cols or field not in cols:
        raise CardEditError(f"{mat_type} 카드에는 {field} 칸이 없다 — "
                            f"쓸 수 있는 것은 {sorted(cols) if cols else '없음'}")
    lines = card.splitlines()
    i = data_line_index(card)
    lines[i] = write_float(lines[i], cols[field], value)
    return "\n".join(lines) + ("\n" if card.endswith("\n") else "")
