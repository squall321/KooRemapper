#!/usr/bin/env bash
# pyKooCAE Runner가 KooMeshModifier(/opt/KooMeshModifier/run.sh)처럼 호출하는 KooRemapper 진입점.
# Standard module entry: run one KooRemapper op via the stateless CLI SIF against
# a work dir. Mirrors the /opt/<module>/run.sh convention pyKooCAE's Runner uses.
#
# Usage:
#   run.sh <workdir> <op> [args...]
#   run.sh /path/to/case matdb job.yaml
#   run.sh /path/to/case generate torus t --dim-i 10 --dim-j 5 --dim-k 5
#
# Env:
#   KOOREMAPPER_CLI_SIF  path to cli.sif (default: alongside this script)
set -euo pipefail

WORK="${1:?usage: run.sh <workdir> <op> [args...]}"; shift
[ -d "$WORK" ] || { echo "✗ workdir not found: $WORK" >&2; exit 2; }

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SIF="${KOOREMAPPER_CLI_SIF:-$HERE/../../infra/apptainer/cli.sif}"
[ -f "$SIF" ] || { echo "✗ cli.sif not found: $SIF (build with infra/scripts/build-cli.sh)" >&2; exit 2; }

exec apptainer run --bind "$WORK:/work" --pwd /work "$SIF" "$@"
