#!/usr/bin/env bash
# 回收：扫描 results/ 下的运行产物，按 path+sha 去重追加到 metrics.jsonl
# 用法：bash tools/gpu/collect.sh [附加目录...]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
EXT="$ROOT/C-VRP_Cold-chainVehicleRoutingProblem"
METRICS="$ROOT/logs/metrics.jsonl"
mkdir -p "$ROOT/logs" "$(dirname "$METRICS")"
touch "$METRICS"

search_dirs=("$EXT/results" "$ROOT/results")
for extra in "$@"; do search_dirs+=("$extra"); done

n_new=0
n_seen=0
for base in "${search_dirs[@]}"; do
  [ -d "$base" ] || continue
  while IFS= read -r f; do
    sha=$(sha256sum "$f" | cut -d' ' -f1)
    key="$f|$sha"
    if grep -Fq "$key" "$METRICS" 2>/dev/null; then
      n_seen=$((n_seen + 1)); continue
    fi
    rel="${f#$ROOT/}"
    size=$(stat -c %s "$f")
    mtime=$(date -r "$f" '+%FT%T')
    printf '{"collected_at":"%s","file":"%s","sha256":"%s","bytes":%s,"mtime":"%s"}\n' \
      "$(date '+%FT%T')" "$rel" "$sha" "$size" "$mtime" >> "$METRICS"
    n_new=$((n_new + 1))
  done < <(find "$base" -maxdepth 3 -type f \( -name 'panel.json' -o -name 'summary.json' \
             -o -name 'metrics.json' -o -name 'rule_inversion.json' -o -name 'train.json' \) 2>/dev/null)
done

echo "collected new=$n_new already_seen=$n_seen -> ${METRICS#$ROOT/}"

# 完成信号：logs/*.exit 里非零的列出
echo "--- failed jobs ---"
grep -l '^[^0]' "$ROOT"/logs/*.exit 2>/dev/null | while read -r f; do
  echo "$(basename "$f" .exit): exit=$(cat "$f")"
done || true
