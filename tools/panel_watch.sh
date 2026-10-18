#!/bin/bash
# ?????????????????????????
cd /home/hzeng/project/ZH/MASKCO_v1/C-VRP_Cold-chainVehicleRoutingProblem
PY=/home/hzeng/miniconda3/envs/MASKCO_env/bin/python
OUT=results/admission_panel/FINAL_SUMMARY.txt
WAIT="stage6_conf stage6_okp_x1 stage6_okp_x2 stage3_control10 stage3_static10"
for i in $(seq 1 360); do            # ??? 6 ???60 s/??
  done_all=1
  for d in $WAIT; do
    [ -f "results/admission_panel/$d/panel.json" ] || done_all=0
  done
  if [ "$done_all" = "1" ]; then
    { echo "=== all panels complete at $(date) ==="
      $PY scripts/evaluation/summarize_panels.py
      echo
      echo "=== per-arm deltas vs control (5-day GATE, frozen a1) ==="
      $PY - <<'PYEOF'
import json, glob
base = {}
for p in sorted(glob.glob('results/admission_panel/*/panel.json')):
    d = json.load(open(p)); name = p.split('/')[-2]
    for r in d['per_day']:
        for arm, v in r.items():
            if arm == 'day' or not isinstance(v, dict): continue
            base.setdefault((name, arm), []).append(v['utility'])
def mean(x):
    return sum(x)/len(x) if x else None
ctrl = mean(base.get(('stage1_control','control_frozen_saa'), []))
stat = mean(base.get(('stage1_static','static_price'), []))
print('control %.2f   static %.2f' % (ctrl, stat))
for (name, arm), v in sorted(base.items()):
    m = mean(v)
    print('%-24s %-22s n=%-2d mean=%8.2f  d(ctrl)=%+8.2f  d(static)=%+8.2f  pos_days=%d/%d'
          % (name, arm, len(v), m, m-ctrl, m-stat,
             sum(1 for x in v if x > ctrl) if len(v)==5 else -1, len(v)))
PYEOF
    } > $OUT 2>&1
    echo done > results/admission_panel/.final_summary_ready
    exit 0
  fi
  sleep 60
done
echo "timeout" > results/admission_panel/.final_summary_ready