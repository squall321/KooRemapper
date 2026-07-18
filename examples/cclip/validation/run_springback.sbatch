#!/bin/bash
#SBATCH --job-name=cclip_sb
#SBATCH --partition=normal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:20:00
#SBATCH --output=/data/cclip_validation/prestress/slurm-%j.out
#SBATCH --error=/data/cclip_validation/prestress/slurm-%j.err
set -o pipefail
VD=/data/cclip_validation/prestress
SIF=/data/apptainers/LSDynaBasic_aocc420_ompi4.0.5_mpp_d.sif
DYNA=/opt/ls-dyna/lsdyna_R16.1.1
MPIRUN=/opt/openmpi/bin/mpirun
RUN=$VD/run_$SLURM_JOB_ID; mkdir -p "$RUN"; cd "$RUN"
cp "$VD/springback.k" .
E=(--bind /data:/data --env LSTC_FILE=/opt/ls-dyna_license/LSTC_FILE
   --env LSTC_LICENSE_SERVER=192.168.122.1
   --env FI_PROVIDER=tcp --env I_MPI_FABRICS=ofi --env LD_LIBRARY_PATH=/opt/openmpi/lib)
echo "=== host $(hostname) — 선응력 스프링백 (implicit, double) ==="
apptainer exec "${E[@]}" "$SIF" "$MPIRUN" -np 1 "$DYNA" i=springback.k memory=400m ncpu=-2 2>&1 | tail -25
if ls binout* >/dev/null 2>&1; then
  apptainer exec "${E[@]}" "$SIF" bash -lc 'cd "'"$RUN"'" && for x in /opt/ls-dyna/*.l2a; do "$x" binout* && break; done' 2>&1 | tail -4
fi
grep -icE 'normal termination' d3hsp 2>/dev/null | sed 's/^/normal_termination_hits=/'
echo; echo "=== 판정 ==="
cp "$VD/parse_sb.py" "$VD/report.json" .
python3 parse_sb.py
echo "PARSE_EXIT=$?"
