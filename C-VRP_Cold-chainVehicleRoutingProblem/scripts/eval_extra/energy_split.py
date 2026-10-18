"""诊断（第 99 轮）：把闭环能耗拆成"登记预冷能耗 e_lower"与"其余（在途/待机/预冷门件）"。

为什么关键
----------
``admission.policies`` 的接单口径只认 ``e_lower = q·k·ΔT``（预冷）。但闭环里的
``energy_kwh`` 还包括在途制冷、回仓、门件预冷等固定量。若固定量占了预算的一半，
那么"预算 710 kWh"对应的**可用接单预算**其实只有 ~350 kWh，接单层的真实上界要按它来算。

本脚本用已有的 ``served_ids`` 面板（dump_control5 / dump_static5）逐日精确分解：

* ``precool_sum``    = Σ_{o∈served} e_lower(o)
* ``actual``         = 面板记录的当日能耗
* ``overhead``       = actual − precool_sum（固定/在途部分）
* ``overhead_share`` = overhead / actual

再按 ``capacity_eff = B − mean(overhead)`` 重算离线整数背包上界（收入），
得到"接单层真实可达上界"的第二版数字。

用法（从扩展根目录）::

    python scripts/eval_extra/energy_split.py --out results/admission_panel/p99_energy_split.json
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

import numpy as np

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_SCRIPTS, os.path.join(_SCRIPTS, 'evaluation'), os.path.join(_SCRIPTS, 'coldchain'),
           os.path.join(_SCRIPTS, 'simulation'), os.path.join(_SCRIPTS, 'admission')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

PANELS = [('control', 'results/admission_panel/dump_control5', 'control_frozen_saa'),
          ('static', 'results/admission_panel/dump_static5', 'static_price')]


def load_gate():
    import run_admission_panel as RAP
    from coldchain_evaluator_a1 import add_v2_initial_quality
    import run_exp_reserve as RR
    return add_v2_initial_quality(
        RR.generate_dataset(RAP.FROZEN['gate_instances'], RAP.FROZEN['n_orders'],
                            RAP.FROZEN['gate_seed']), RAP.make_contract()), RAP


def per_order(ds_day, RAP):
    from admission.policies import REV, e_lower_of
    dem = np.asarray(ds_day['demands'], dtype=np.float64)
    cls = np.asarray(ds_day['temp_class'], dtype=np.int64)
    rev = np.zeros_like(dem)
    e = np.zeros_like(dem)
    for c, r in REV.items():
        rev[cls == int(c)] = float(r)
    for o in range(dem.shape[0]):
        if dem[o] > 0:
            e[o] = e_lower_of(int(cls[o]), float(dem[o]), RAP.OBJECTIVE)
    return dem, cls, rev, e


def knapsack_ub(rev, e, active, cap, binw=0.01):
    """0/1 整数背包（numpy 版，容量栅格 binw）。"""
    nb = int(round(cap / binw)) + 1
    if nb <= 1:
        return 0.0
    dp = np.full(nb, -1e9, dtype=np.float64)
    dp[0] = 0.0
    for o in np.where(active)[0]:
        w = int(np.ceil(e[o] / binw))
        v = float(rev[o])
        if w > nb - 1 or w <= 0:
            continue
        cand = dp[:nb - w] + v
        np.maximum(dp[w:], cand, out=dp[w:])
    return float(dp.max())


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=None)
    args = ap.parse_args(argv)

    gate_ds, RAP = load_gate()
    B = float(RAP.FROZEN['budget_B'])
    out = dict(budget=B, panels=[], per_class={})
    all_rows = []
    for name, pdir, arm in PANELS:
        pj = os.path.join(pdir, 'panel.json')
        if not os.path.exists(pj):
            print('[split] skip %s (no panel.json)' % pdir)
            continue
        d = json.load(open(pj, encoding='utf-8'))
        for r in d['per_day']:
            v = r.get(arm)
            if not v or not v.get('served_ids'):
                continue
            day = int(r['day'])
            dem, cls, rev, e = per_order({k: v_[day] for k, v_ in gate_ds.items()}, RAP)
            served = [int(x) for x in v['served_ids']]
            precool = float(e[served].sum())
            revenue = float(rev[served].sum())
            actual = float(v['energy_kwh'])
            row = dict(panel=name, day=day, n_served=len(served),
                       precool_kwh=precool, actual_kwh=actual,
                       overhead_kwh=actual - precool,
                       overhead_share=(actual - precool) / actual if actual else None,
                       revenue=revenue, utility=float(v['utility']),
                       precool_per_order=precool / len(served) if served else None,
                       actual_per_order=actual / len(served) if served else None)
            all_rows.append(row)
            cls_cnt = {int(c): int(((cls[served] == c)).sum()) for c in (0, 1, 2)}
            row['served_class_count'] = cls_cnt
            row['served_class_precool'] = {str(c): float(e[served][cls[served] == c].sum())
                                           for c in (0, 1, 2)}
            out['panels'].append(row)
            print('[split] %-7s day=%d srv=%d precool=%.1f actual=%.1f overhead=%.1f (%.1f%%)'
                  % (name, day, len(served), precool, actual, actual - precool,
                     100.0 * (actual - precool) / actual), flush=True)

    if all_rows:
        ov = float(np.mean([r['overhead_kwh'] for r in all_rows]))
        cap_eff = B - ov
        # 用 control 的观测集合做上界对比
        ub_rows = []
        for day in sorted({r['day'] for r in all_rows}):
            dem, cls, rev, e = per_order({k: v_[day] for k, v_ in gate_ds.items()}, RAP)
            ub = knapsack_ub(rev, e, dem > 0, cap_eff)
            ub_rows.append(dict(day=day, cap_eff=cap_eff, rev_ub_eff=ub))
        ctrl_rev = float(np.mean([r['revenue'] for r in all_rows if r['panel'] == 'control']))
        out['summary'] = dict(
            n_days=len(all_rows),
            mean_overhead_kwh=ov,
            mean_overhead_share=float(np.mean([r['overhead_share'] for r in all_rows])),
            capacity_eff=cap_eff,
            mean_rev_ub_eff=float(np.mean([u['rev_ub_eff'] for u in ub_rows])),
            mean_control_rev=ctrl_rev,
            headroom_vs_control=float(np.mean([u['rev_ub_eff'] for u in ub_rows]) - ctrl_rev),
            headroom_vs_control_pct=float(100.0 * (np.mean([u['rev_ub_eff'] for u in ub_rows])
                                                   / ctrl_rev - 1.0)))
        out['ub_rows'] = ub_rows
        print(json.dumps(out['summary'], ensure_ascii=False, indent=1), flush=True)
    if args.out:
        with open(args.out, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        print('[split] wrote %s' % args.out, flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
