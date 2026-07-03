#!/usr/bin/env bash
# SLURM job: run a KooRemapper matdb material mapping via the stateless CLI SIF.
# Usage:  sbatch slurm-matdb.sh <config.yaml>
#   config.yaml lives in the submit dir with its input .k; outputs land there too.
#SBATCH --job-name=koorm-matdb
#SBATCH --output=koorm-matdb-%j.log
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --time=00:30:00
set -euo pipefail

CONFIG="${1:?usage: sbatch slurm-matdb.sh <config.yaml>}"
SIF="${KOOREMAPPER_CLI_SIF:-$(dirname "$0")/../infra/apptainer/cli.sif}"
WORK="$(pwd)"

module load apptainer 2>/dev/null || true   # site-specific; ignore if apptainer is on PATH

apptainer run --bind "$WORK:/work" --pwd /work "$SIF" matdb "$CONFIG"
echo "done → outputs in $WORK"
