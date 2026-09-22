"""Translate (operation, args) into an actual KooRemapper invocation.

The runner executes with cwd = the session storage dir, so file references are
plain filenames (relative paths resolve naturally, exactly like the examples).

Invocation models (driven by the catalog entry):
  positional : argv = [op, *flags, *ordered_positionals]
               - role flag    : boolean→[flag]; valued→[flag, str(value)]
               - role config  : write args[name] dict to <name>.yaml, use that path
               - else         : use args[name] as the positional token (filename/value)
  yaml/structured : build a nested dict from each param's yaml_path, write config.yaml
  yaml/freeform   : write args["config"] verbatim to config.yaml
In both yaml cases argv = [op, "config.yaml"].
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from kooremapper_core import catalog



class _KDumper(yaml.SafeDumper):
    """YAML dumper matching KooRemapper's custom C++ parser expectations:
    - block sequences are INDENTED under their key (`  - item`), and
    - scalar-only collections use flow style (`[0, 0, 1]`, `[1, 2, 3]`, `[3, 3]`).
    This reproduces the style of the example .yaml files the parser was built for.
    """


def _increase_indent(self, flow=False, indentless=False):  # noqa: ANN001
    return super(_KDumper, self).increase_indent(flow, False)


_KDumper.increase_indent = _increase_indent  # type: ignore[assignment]


def _represent_list(dumper, data):  # noqa: ANN001
    # Scalar-only sequences → flow ([0, 0, 1] / [1, 2, 3]); anything containing a
    # mapping or nested list → block (one indented `- ` per item). Mappings always
    # stay block (the C++ parser is line-oriented).
    scalar = all(isinstance(x, (int, float, str, bool)) or x is None for x in data)
    return dumper.represent_sequence(
        "tag:yaml.org,2002:seq", data, flow_style=scalar
    )


_KDumper.add_representer(list, _represent_list)


# Job.args is stored as JSONB, which does NOT preserve key order. KooRemapper's
# YAML parser is order-sensitive (it needs the discriminator `type`/`action` key
# before the type-specific fields — e.g. indent reads r1/r2 into a default
# profile if `type` hasn't been seen yet). Emit those keys first in every mapping.
_PRIORITY_KEYS = ("type", "action")


def _represent_dict(dumper, data):  # noqa: ANN001
    keys = [k for k in _PRIORITY_KEYS if k in data] + [k for k in data if k not in _PRIORITY_KEYS]
    return dumper.represent_mapping("tag:yaml.org,2002:map", [(k, data[k]) for k in keys])


_KDumper.add_representer(dict, _represent_dict)


# 여러 줄 문자열(material_card 등)은 리터럴 블록 `key: |` 로 나가야 한다. PyYAML 이 블록 표기를
# 포기해 따옴표 문자열 한 줄이 되면 C++ 파서는 그 한 줄을 카드로 읽어 조용히 mid=0 짜리 덱을 낸다.
# 그래서 뜻이 없는 차이(줄 끝 공백, 줄 구분자 표기, 카드 앞뒤 빈 줄)는 정규화하고, 칸 위치를 흔들거나
# 블록으로 내보낼 수 없는 카드는 조용히 넘기지 않고 거절한다 — 애매한 카드는 오답 덱보다 실패가 낫다.
_CARD_BREAKS = "\x85  "  # YAML 이 줄바꿈으로 읽는 문자들(블록에 그대로 나가면 줄이 쪼개진다)


class CardSerializationError(ValueError):
    """여러 줄 카드를 리터럴 블록으로 안전하게 내보낼 수 없다(조용한 오답 덱 대신 실패시킨다)."""


def _normalize_block_text(data: str) -> str:
    # \r\n 과 단독 \r 은 줄 구분자이므로 \n 으로 통일한다. 줄 끝 공백과 카드 앞뒤 빈 줄은 고정 폭
    # 카드에서 뜻이 없다. 어느 것도 칸 위치(10칸 정렬)를 바꾸지 않는다.
    text = data.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines) + "\n" if lines else ""


def _check_block_card(text: str) -> None:
    """블록으로 내보내면 조용히 뜻이 바뀌는 카드를 거절한다(TAB·줄바꿈 문자·첫 줄 선행 공백)."""
    for i, line in enumerate(text.rstrip("\n").split("\n"), start=1):
        if "\t" in line:
            # 탭을 펴면 탭 폭 가정(8? 4?)에 따라 뒤 칸이 밀린다 → RO 가 사라지는 식으로 조용히 틀린다.
            raise CardSerializationError(
                f"material_card line {i} contains a TAB — "
                "LS-DYNA 고정폭 카드는 공백으로 칸을 맞춰 주세요"
            )
        bad = next((ch for ch in line if ch in _CARD_BREAKS), None)
        if bad is not None:
            # 블록으로는 나가지만 읽을 때 한 줄이 두 줄로 쪼개진다(카드 줄 수가 달라진다).
            raise CardSerializationError(
                f"material_card line {i} contains U+{ord(bad):04X}, which YAML reads as a line "
                "break — 줄바꿈은 \\n 만 쓰세요"
            )
    if text.startswith(" "):
        # 첫 줄이 공백으로 시작하면 YAML 은 `|2` 명시 들여쓰기 헤더를 붙이는데, 받는 쪽은 블록
        # 들여쓰기를 '첫 내용 줄' 기준으로 잡아 그 선행 공백을 먹는다 → MID 칸이 밀린다.
        raise CardSerializationError(
            "material_card 의 첫 줄이 공백으로 시작합니다 — "
            "카드는 *KEYWORD 줄로 시작해야 합니다(선행 공백을 떼 주세요)"
        )
    if not yaml.emitter.Emitter(io.StringIO()).analyze_scalar(text).allow_block:
        # 위에서 걸러낸 것 말고도 emitter 가 블록을 포기하는 입력이 있으면(특수 문자 등) 따옴표
        # 스칼라로 조용히 떨어진다. 그게 바로 원래 결함이므로 여기서 멈춘다.
        raise CardSerializationError(
            "material_card 를 YAML 리터럴 블록으로 내보낼 수 없습니다 — "
            "카드에 제어·특수 문자가 있는지 확인해 주세요"
        )


def _represent_str(dumper, data):  # noqa: ANN001
    text = _normalize_block_text(data)
    if "\n" in text.rstrip("\n"):
        _check_block_card(text)
        return dumper.represent_scalar("tag:yaml.org,2002:str", text, style="|")
    if not text and ("\n" in data or "\r" in data):
        # 여러 줄이었는데 내용 줄이 하나도 남지 않았다 = 빈 카드. 통과시키면 mid=0 덱이 된다.
        raise CardSerializationError("material_card is blank — 카드 내용이 없습니다")
    # 한 줄로 접히는 값도 정규화한 쪽을 내보낸다(원본을 내보내면 앞뒤 빈 줄·TAB 가 되살아난다).
    return dumper.represent_scalar("tag:yaml.org,2002:str", text.rstrip("\n"))


_KDumper.add_representer(str, _represent_str)


def _dump_yaml(obj) -> str:
    return yaml.dump(
        obj, Dumper=_KDumper, default_flow_style=False, allow_unicode=True, sort_keys=False
    )


@dataclass
class BuiltCommand:
    argv: list[str]  # WITHOUT the binary path (runner prepends it)
    written_files: dict[str, str] = field(default_factory=dict)  # filename -> yaml text (audit)
    error: str | None = None


def _set_dotted(d: dict, dotted: str, value: Any) -> None:
    keys = dotted.split(".")
    cur = d
    for k in keys[:-1]:
        cur = cur.setdefault(k, {})
    cur[keys[-1]] = value


def build_command(op: str, args: dict, work_dir: Path,
                  material_db_default: str | None = None) -> BuiltCommand:
    entry = catalog.get_operation(op)
    if entry is None:
        return BuiltCommand(argv=[], error=f"unknown operation: {op}")

    # matdb convenience: if no database given and a default library path is
    # provided by the caller, inject it (so callers can use a bundled DB).
    if op == "matdb" and not args.get("database") and material_db_default:
        args = {**args, "database": str(material_db_default)}

    # Validate against the op's JSON Schema first.
    errs = catalog.validate_args(op, args)
    if errs:
        return BuiltCommand(argv=[], error="; ".join(errs))

    params = entry.get("params", [])
    invocation = entry.get("invocation")

    # 외부 작업(다른 클러스터에서 도는 것)은 여기서 argv 를 만들지 않는다. 워커가 그 앞에서
    # 갈라 나가지만, 그 분기를 누가 빠뜨리면 여기로 떨어진다 — 빈 argv 로 조용히 "성공" 하는
    # 대신 어디서 도는 작업인지 말한다.
    if invocation == "external":
        return BuiltCommand(
            argv=[],
            error=f"'{op}' is an external operation — it runs on another cluster, "
                  f"not via the local binary",
        )

    # 카드를 안전하게 직렬화할 수 없으면 덱을 내지 않고 오류로 돌려준다(조용한 mid=0 덱 방지).
    try:
        if invocation == "positional":
            return _build_positional(op, entry, params, args, work_dir)
        if invocation == "yaml":
            return _build_yaml(op, entry, params, args, work_dir)
    except CardSerializationError as exc:
        return BuiltCommand(argv=[], error=str(exc))
    return BuiltCommand(argv=[], error=f"unknown invocation: {invocation}")


def _build_positional(op, entry, params, args, work_dir) -> BuiltCommand:
    flags: list[str] = []
    positionals: list[tuple[int, str]] = []
    written: dict[str, str] = {}

    for p in params:
        name, role = p["name"], p["role"]
        if name not in args and not p.get("required"):
            if role == "flag":
                continue
            # optional positional omitted
            continue
        val = args.get(name)
        if role == "flag":
            flag = p.get("flag") or f"--{name}"
            if p["type"] == "boolean":
                if bool(val):
                    flags.append(flag)
            elif val is not None:
                flags.extend([flag, str(val)])
        elif role == "config" or p["type"] == "config":
            fname = f"{name}.yaml"
            text = _dump_yaml(val or {})
            (work_dir / fname).write_text(text, encoding="utf-8")
            written[fname] = text
            positionals.append((p.get("order", len(positionals)), fname))
        else:  # input_file / output / value
            positionals.append((p.get("order", len(positionals)), str(val)))

    positionals.sort(key=lambda t: t[0])
    # Positionals FIRST, then flags: extract-surface requires positionals before
    # options, and the other positional ops (map/prestress/shellmap/generate)
    # accept flags in either position.
    argv = [op, *[v for _, v in positionals], *flags]
    return BuiltCommand(argv=argv, written_files=written)


def _build_yaml(op, entry, params, args, work_dir) -> BuiltCommand:
    style = entry.get("config_style")
    if style == "freeform":
        config = args.get("config") or {}
        if not isinstance(config, dict):
            return BuiltCommand(argv=[], error="`config` must be an object")
    else:  # structured
        config = {}
        for p in params:
            name = p["name"]
            if name not in args:
                continue
            path = p.get("yaml_path") or name
            _set_dotted(config, path, args[name])

    text = _dump_yaml(config)
    cfg_path = work_dir / "config.yaml"
    cfg_path.write_text(text, encoding="utf-8")
    # Absolute path so ops that resolve companion files (dat_file, model, …)
    # relative to the CONFIG's directory (e.g. warpage/bend) find them in the
    # session dir. cwd is already the session dir, so this is strictly safer.
    return BuiltCommand(argv=[op, str(cfg_path)], written_files={"config.yaml": text})
