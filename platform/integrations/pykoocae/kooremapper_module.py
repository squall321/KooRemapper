# pyKooCAE Runner/체인에서 KooRemapper op를 한 스텝으로 실행하는 Generator 모듈 래퍼.
"""KooRemapper as a pyKooCAE Generator-style module.

Wraps the stateless CLI SIF (or the raw binary) so a Runner/chain step can run a
KooRemapper operation against a case directory and get back the produced files —
no service (api/postgres/mcp) required. Mirrors how pyKooCAE calls other tool
modules (a subprocess to a run.sh / apptainer image).

Two invocation shapes cover chain use:
  - yaml ops  (matdb, warpage, assemble, …): pass a `config` dict or a config.yaml
  - positional ops (generate, map, info, …): pass `argv` (list of tokens)

For a fully dict-driven invocation of ANY op (arg validation + config
generation from a plain dict), install `kooremapper-core` and build the argv/yaml
with it; this module keeps the dependency-free subprocess path.

Example:
    m = KooRemapperModule(sif="/opt/kooremapper/cli.sif")
    out = m.run("matdb", workdir="/cases/phone", config={
        "model": "model.k", "output": "mapped.k",
        "database": "/opt/kooremapper/materials/material_db.json",
        "materials": [{"match": "AL7003H", "mat_type": "MAT_PIECEWISE_LINEAR_PLASTICITY"},
                      {"match": "*"}],
    })
    # out == ["mapped.k", ...]  (new files created in the case dir)
"""
from __future__ import annotations

import io
import subprocess
from pathlib import Path

try:
    import yaml  # optional — only needed for dict-based yaml ops

    class _IndentDumper(yaml.SafeDumper):
        # Indent block sequences UNDER their key ("materials:\n  - match: …").
        # matdb's minimal YAML parser requires list items to be more-indented than
        # the key; PyYAML's default aligns them at the key's column, which the
        # parser then ignores (rules silently dropped → everything hits the '*').
        def increase_indent(self, flow=False, indentless=False):
            return super().increase_indent(flow, False)

    class CardSerializationError(ValueError):
        """A multi-line card cannot be emitted as a `|` block — fail instead of
        letting a quoted scalar become a silently wrong deck."""

    _CARD_BREAKS = "\x85  "  # characters YAML reads as line breaks

    def _normalize_block_text(data):
        """Make a multi-line card safe to emit as a `|` literal block.

        LS-DYNA cards are fixed-width, so trailing blanks and blank lines around the
        card carry no meaning, and \r\n / lone \r are just line separators — but each
        of them makes PyYAML drop the literal block (a quoted "*MAT_ELASTIC\n…"
        scalar, or a `|2` header). KooRemapper's line-oriented parser then reads that
        one line as the card and silently emits a deck with mid=0. None of this moves
        a column.
        """
        text = data.replace("\r\n", "\n").replace("\r", "\n")
        lines = [line.rstrip() for line in text.split("\n")]
        while lines and not lines[0]:
            lines.pop(0)
        while lines and not lines[-1]:
            lines.pop()
        return "\n".join(lines) + "\n" if lines else ""

    def _check_block_card(text):
        """Reject cards whose meaning would change on the way out (tabs, YAML line
        breaks, a first line starting with a blank, or anything the emitter refuses
        to write as a block)."""
        for i, line in enumerate(text.rstrip("\n").split("\n"), start=1):
            if "\t" in line:
                # Expanding a tab shifts every field after it (tab width 8? 4?) —
                # the deck would look fine and be numerically wrong.
                raise CardSerializationError(
                    f"material_card line {i} contains a TAB — pad fixed-width "
                    "LS-DYNA columns with spaces"
                )
            bad = next((ch for ch in line if ch in _CARD_BREAKS), None)
            if bad is not None:
                raise CardSerializationError(
                    f"material_card line {i} contains U+{ord(bad):04X}, which YAML "
                    "reads as a line break — use \\n only"
                )
        if text.startswith(" "):
            # A first line starting with a blank forces a `|2` header, and the
            # receiver takes its block indent from the first content line — those
            # leading blanks get eaten and the MID column shifts.
            raise CardSerializationError(
                "material_card starts with a blank on its first line — a card must "
                "begin with its *KEYWORD line"
            )
        if not yaml.emitter.Emitter(io.StringIO()).analyze_scalar(text).allow_block:
            raise CardSerializationError(
                "material_card cannot be emitted as a YAML literal block — check it "
                "for control/special characters"
            )

    def _represent_str(dumper, data):
        # Multi-line strings (restack layers' material_card, assemble cards) must go
        # out as `key: |`; PyYAML's default quoted scalar is not a card to KooRemapper.
        text = _normalize_block_text(data)
        if "\n" in text.rstrip("\n"):
            _check_block_card(text)
            return dumper.represent_scalar("tag:yaml.org,2002:str", text, style="|")
        if not text and ("\n" in data or "\r" in data):
            raise CardSerializationError("material_card is blank")
        # Emit the normalized text in this branch too — `data` would resurrect the
        # blank lines and tabs normalization just removed.
        return dumper.represent_scalar("tag:yaml.org,2002:str", text.rstrip("\n"))

    _IndentDumper.add_representer(str, _represent_str)
except Exception:  # pragma: no cover
    yaml = None
    _IndentDumper = None


class KooRemapperModule:
    """Run KooRemapper ops for a pyKooCAE chain step."""

    def __init__(self, sif: str | None = None, binary: str | None = None, timeout: float = 1800):
        """Provide either a CLI SIF (preferred, portable) or a native binary path."""
        if not sif and not binary:
            raise ValueError("provide sif=... (cli.sif) or binary=... (KooRemapper)")
        # Resolve to absolute — run() executes with cwd=workdir, so a relative
        # sif/binary path would resolve against the case dir and be missed.
        self.sif = str(Path(sif).resolve()) if sif else None
        self.binary = str(Path(binary).resolve()) if binary else None
        self.timeout = timeout

    def _invoke(self, workdir: Path, argv: list[str]) -> subprocess.CompletedProcess:
        if self.sif:
            cmd = ["apptainer", "run", "--bind", f"{workdir}:/work", "--pwd", "/work", self.sif, *argv]
        else:
            cmd = [self.binary, *argv]
        return subprocess.run(cmd, cwd=str(workdir), capture_output=True, text=True, timeout=self.timeout)

    @staticmethod
    def _snapshot(workdir: Path) -> set[str]:
        return {p.relative_to(workdir).as_posix() for p in workdir.rglob("*") if p.is_file()}

    def run(self, operation: str, workdir: str, *, argv: list[str] | None = None,
            config: dict | None = None, config_name: str = "config.yaml") -> list[str]:
        """Run `operation` in `workdir`. Returns the relative paths of files created.

        - yaml ops: pass `config` (dict → written to config_name) or point argv at an
          existing yaml. - positional ops: pass `argv` tokens after the op name.
        Raises RuntimeError on non-zero exit.
        """
        wd = Path(workdir).resolve()
        if not wd.is_dir():
            raise FileNotFoundError(f"workdir not found: {wd}")

        if config is not None:
            if yaml is None:
                raise RuntimeError("PyYAML required for dict config; pass a config.yaml via argv instead")
            (wd / config_name).write_text(
                yaml.dump(config, Dumper=_IndentDumper, sort_keys=False, default_flow_style=False),
                encoding="utf-8",
            )
            call_argv = [operation, config_name]
        elif argv is not None:
            call_argv = [operation, *argv]
        else:
            call_argv = [operation]

        before = self._snapshot(wd)
        proc = self._invoke(wd, call_argv)
        if proc.returncode != 0:
            raise RuntimeError(
                f"KooRemapper {operation} failed (exit {proc.returncode}):\n{proc.stderr[-1500:]}"
            )
        after = self._snapshot(wd)
        return sorted(after - before)
