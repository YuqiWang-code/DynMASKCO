#!/usr/bin/env bash
# 安装/更新本项目的服务器定时任务（幂等：只替换标记块）。
# 用法：bash tools/cron/install_cron.sh [--dry-run]
#
# 只装两条最轻的：
#   T1 每 30 分钟  dispatch（有卡则出队）
#   T2 每 2 小时   collect（回收结果 → logs/metrics.jsonl）
# 训练/评测任务由 tools/gpu/queue_run.sh 入队，由 T1 派发。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DRY=0
[ "${1:-}" = "--dry-run" ] && DRY=1
MARK_BEGIN="# >>> dynmaskco-self-iteration >>>"
MARK_END="# <<< dynmaskco-self-iteration <<<"

BLOCK="$MARK_BEGIN
*/30 * * * * cd $ROOT && bash tools/gpu/dispatch.sh >> logs/t1_dispatch.log 2>&1
0 */2 * * * cd $ROOT && bash tools/gpu/collect.sh >> logs/t2_collect.log 2>&1
$MARK_END"

current="$(crontab -l 2>/dev/null || true)"
cleaned="$(printf '%s\n' "$current" | awk -v b="$MARK_BEGIN" -v e="$MARK_END" '
  $0==b {skip=1; next} $0==e {skip=0; next} skip!=1 {print}')"
new_cron="$(printf '%s\n%s\n' "$cleaned" "$BLOCK" | sed '/^$/N;/^\n$/D')"

if [ "$DRY" = "1" ]; then
  echo "=== would install ==="; echo "$new_cron"; exit 0
fi

printf '%s\n' "$new_cron" | crontab -
echo "installed. current crontab:"
crontab -l | sed -n '1,40p'
