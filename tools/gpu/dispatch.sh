#!/usr/bin/env bash
# 出队：若当前有卡且队列非空，取队首任务启动（定时任务 T1 每 30 分钟调用）。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PENDING="$ROOT/queue/pending.txt"
mkdir -p "$ROOT/logs" "$ROOT/queue"
touch "$PENDING"

[ -s "$PENDING" ] || { echo "queue empty"; exit 0; }

if ! GPU=$(bash "$ROOT/tools/gpu/acquire.sh"); then
  echo "no free GPU; $(wc -l < "$PENDING") job(s) pending"
  exit 0
fi

# 取队首（行内为 name<TAB>cmd）
line="$(head -n 1 "$PENDING")"
tail -n +2 "$PENDING" > "$PENDING.tmp" && mv "$PENDING.tmp" "$PENDING"
JOB_NAME="$(printf '%s' "$line" | cut -f1)"
JOB_CMD="$(printf '%s' "$line" | cut -f2-)"

export CUDA_VISIBLE_DEVICES="$GPU"
export XLA_PYTHON_CLIENT_PREALLOCATE=false
SESSION="${JOB_NAME}-gpu${GPU}"
tmux kill-session -t "$SESSION" 2>/dev/null || true
tmux new-session -d -s "$SESSION" \
  "cd '$ROOT' && ($JOB_CMD) > 'logs/${JOB_NAME}.log' 2>&1; echo \$? > 'logs/${JOB_NAME}.exit'"
echo "[$JOB_NAME] dispatched on GPU $GPU; $(wc -l < "$PENDING") left"
