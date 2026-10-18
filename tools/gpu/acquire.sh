#!/usr/bin/env bash
# 抢卡：返回一张满足条件的空闲 GPU 编号；没有则非零退出并写队列日志。
# 用法：GPU=$(bash tools/gpu/acquire.sh) || echo "no free gpu"
# 环境变量：MIN_FREE_MEM(MB, 默认 20000) / MAX_LOAD(0-1, 默认 0.30) / LOCKFILE
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOCK="${LOCKFILE:-/tmp/dynmaskco_gpu.lock}"
MIN_FREE_MEM="${MIN_FREE_MEM:-20000}"
MAX_LOAD="${MAX_LOAD:-0.30}"
mkdir -p "$ROOT/logs" "$ROOT/queue"

exec 9>"$LOCK"
if ! flock -w 5 9; then
  echo "another acquirer running" >&2
  exit 1
fi

pick=$(nvidia-smi --query-gpu=index,memory.used,memory.total,utilization.gpu \
        --format=csv,noheader,nounits \
      | awk -F',' -v m="$MIN_FREE_MEM" -v l="$MAX_LOAD" '
        {gsub(/ /,"",$1); gsub(/ /,"",$2); gsub(/ /,"",$3); gsub(/ /,"",$4);
         free=$3-$2; if (free>=m && $4 <= l*100) {print $1; exit}}')

if [ -z "${pick:-}" ]; then
  echo "NO_GPU_FREE at $(TZ='CST-8' date '+%F %T')" >> "$ROOT/logs/gpu_queue.log"
  exit 1
fi
echo "$pick"
