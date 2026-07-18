#!/bin/bash
#SBATCH --job-name=cclip_val
#SBATCH --partition=normal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:20:00
#SBATCH --output=/data/cclip_validation/deck_stiffness/slurm-%j.out
#SBATCH --error=/data/cclip_validation/deck_stiffness/slurm-%j.err

# cclip 압축덱을 컨테이너 LS-DYNA(MPP double, implicit)로 풀고 rcforc F-δ를 자체 검증한다.
set -o pipefail
VD=/data/cclip_validation/deck_stiffness
SIF=/data/apptainers/LSDynaBasic_aocc420_ompi4.0.5_mpp_d.sif
DYNA=/opt/ls-dyna/lsdyna_R16.1.1        # 컨테이너 내부 double R16.1.1
MPIRUN=/opt/openmpi/bin/mpirun

RUN=$VD/run_$SLURM_JOB_ID
mkdir -p "$RUN"; cd "$RUN"
cp "$VD/deck.k" .

# 성공 잡 d3hsp 와 동일한 license env (server 192.168.122.1, LSTC_FILE 컨테이너 내장)
APPT_ENV=(--bind /data:/data
  --env LSTC_FILE=/opt/ls-dyna_license/LSTC_FILE
  --env LSTC_LICENSE_SERVER=192.168.122.1
  --env FI_PROVIDER=tcp --env I_MPI_FABRICS=ofi
  --env LD_LIBRARY_PATH=/opt/openmpi/lib)

echo "=== host: $(hostname)  sif: $(basename $SIF)  dyna: $DYNA ==="
echo "=== solve (apptainer + mpirun -np 1, implicit, double) ==="
apptainer exec "${APPT_ENV[@]}" "$SIF" \
  "$MPIRUN" -np 1 "$DYNA" i=deck.k memory=400m ncpu=-2 2>&1 | tail -45

echo "=== l2a: binout -> ascii (rcforc/nodout) ==="
if ls binout* >/dev/null 2>&1; then
  apptainer exec "${APPT_ENV[@]}" "$SIF" bash -lc 'cd "'"$RUN"'" && for x in /opt/ls-dyna/*.l2a; do "$x" binout* && break; done' 2>&1 | tail -5
fi
echo "--- 산출물 ---"
ls -la | grep -iE 'rcforc|nodout|binout|d3hsp|glstat|messag' | awk '{print "  "$5, $NF}'

echo "=== 종료 상태 ==="
grep -iE 'normal termination|error termination' d3hsp messag 2>/dev/null | tail -3

echo
echo "=== F-δ 파싱/검증 ==="
cp "$VD/parse_fd.py" "$VD/report.json" .
python3 parse_fd.py
echo "PARSE_EXIT=$?"
