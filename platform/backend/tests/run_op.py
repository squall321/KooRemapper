"""Run a single KooRemapper op through the platform's argbuild + binary, in a
work dir, and report the result as JSON. Used by the Phase 6 integration tests.

Usage:
  python tests/run_op.py <op> --workdir <dir> --args '<json>'
  python tests/run_op.py <op> --workdir <dir> --example     # use catalog example args

Prints a JSON object: {op, argv, exit_code, ok, new_files, stdout_tail, stderr_tail, error}.
Exit status 0 if the op ran with exit_code 0, else 1.
"""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True  # don't litter app/ with .pyc (would trip file watchers)

import argparse
import json
import subprocess
from pathlib import Path

# allow running from anywhere
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings  # noqa: E402
from app.runner import catalog  # noqa: E402
from app.runner.argbuild import build_command  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("op")
    ap.add_argument("--workdir", required=True)
    ap.add_argument("--args", default=None, help="JSON args object")
    ap.add_argument("--example", action="store_true", help="use catalog example args")
    ns = ap.parse_args()

    wd = Path(ns.workdir)
    wd.mkdir(parents=True, exist_ok=True)

    entry = catalog.get_operation(ns.op)
    if entry is None:
        print(json.dumps({"op": ns.op, "error": "unknown op"}))
        return 1

    if ns.example:
        args = entry["example"]["args"]
    elif ns.args:
        args = json.loads(ns.args)
    else:
        args = {}

    before = {p.name for p in wd.iterdir() if p.is_file()}
    built = build_command(ns.op, args, wd)
    result = {"op": ns.op, "argv": built.argv, "error": built.error}
    if built.error:
        print(json.dumps(result, ensure_ascii=False))
        return 1

    cmd = [str(settings.kooremapper_bin), *built.argv]
    proc = subprocess.run(cmd, cwd=str(wd), capture_output=True, text=True, timeout=600)
    after = {p.name for p in wd.iterdir() if p.is_file()}
    new_files = sorted(after - before - set(built.written_files))

    result.update(
        exit_code=proc.returncode,
        ok=proc.returncode == 0,
        new_files=new_files,
        stdout_tail=proc.stdout[-1500:],
        stderr_tail=proc.stderr[-1500:],
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0 if proc.returncode == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
