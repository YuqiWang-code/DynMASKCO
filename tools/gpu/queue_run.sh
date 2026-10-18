#!/usr/bin/env bash
# 有卡即跑、无卡入队。
# 用法：bash tools/gpu/queue_run.sh "<命令>" <任务名>
# 完成信号：logs/<任务名>.exit（不接受"tmux 还在"作为完成证据）
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
JOB_CMD="${1:?usage: queue_run.sh \"<cmd>\" <name>}"
JOB_NAME="${2:-job}"
mkdir -p "$ROOT/logs" "$ROOT/queue"

if GPU=$(bash "$ROOT/tools/gpu/acquire.sh"); then
  export CUDA_VISIBLE_DEVICES="$GPU"
  export XLA_PYTHON_CLIENT_PREALLOCATE=false
  SESSION="${JOB_NAME}-gpu${GPU}"
  tmux kill-session -t "$SESSION" 2>/dev/null || true
  tmux new-session -d -s "$SESSION" \
    "cd '$ROOT' && ($JOB_CMD) > 'logs/${JOB_NAME}.log' 2>&1; echo \$? > 'logs/${JOB_NAME}.exit'"
  echo "[$JOB_NAME] started on GPU $GPU (session $SESSION)"
else
  printf '%s\t%s\n' "$JOB_NAME" "$JOB_CMD" >> "$ROOT/queue/pending.txt"
  echo "[$JOB_NAME] queued (no free GPU)"
fi
