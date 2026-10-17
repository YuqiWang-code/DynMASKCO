"""阶段 1：全仿真接拒面板（3 臂，受控 A/B）—— 动态影子价格 vs 静态影子价格。

与登记面板（``research/.../a1_budget_reserving_admission_root_v4/run.py``）的差别只在
**候选臂的接拒过滤器**：控制臂仍是冻结的 ``SaaReplanner``；候选臂换成
``DynamicDualReplanner``（BwK 次梯度影子价格）。采样器、arm_seed、K、time_limit、
合同、预算、面板天全部对齐。

用法（从扩展根目录）::

    python scripts/evaluation/run_admission_panel.py --days 5 --out results/admission_panel/dev_v1

产物：``<out>/panel.json``（含逐日效用、配对差、λ 轨迹摘要、拒绝原因分布）。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_SCRIPTS, os.path.join(_SCRIPTS, 'evaluation'), os.path.join(_SCRIPTS, 'coldchain'),
           os.path.join(_SCRIPTS, 'simulation'), os.path.join(_SCRIPTS, 'admission')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# 登记冻结常量（与 a1_budget_reserving_admission_root_v4/REGISTRATION.json 一致）
FROZEN = dict(train_seed=20260925, train_instances=200, gate_seed=20260926,
              gate_instances=40, n_orders=200, num_vehicles=15, capacity=50.0,
              booking_horizon=16.0, horizon=16.0, K=10, time_limit=10.0, rho=0.6,
              k_neighbors=10, budget_B=710.6548328611384, arm_seed=7003,
              km_per_unit=20.0, speed_kmh=30.0)
OBJECTIVE = dict(ambient_c=25.0, target_c=[18.0, 4.0, -18.0],
                 precool_energy_per_unit_per_c=0.15)


def make_contract():
    from dataclasses import replace
    from coldchain_contract import ColdChainContractV2, UnitScale
    c = ColdChainContractV2()
    units = UnitScale(distance_km_per_unit=FROZEN['km_per_unit'],
                      hours_per_time_unit=1.0, speed_kmph=FROZEN['speed_kmh'])
    prov = list(c.parameter_provenance)
    for i, p in enumerate(prov):
        if p.parameter_path == 'units.distance_km_per_unit':
            prov[i] = replace(p, sensitivity_high=50.0)
    c = replace(c, units=units, parameter_provenance=tuple(prov))
    c.validate()
    return c


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--days', type=int, default=5)
    ap.add_argument('--eta', type=float, default=0.02)
    ap.add_argument('--lam0', type=float, default=None,
                    help='默认用静态规则在 clock=0/B 处的价格（因果热启动）')
    ap.add_argument('--lam-max', type=float, default=8.0)
    ap.add_argument('--arms', default='control,static,dynamic')
    ap.add_argument('--K', type=int, default=None, help='smoke 用：覆盖采样数')
    ap.add_argument('--time-limit', type=float, default=None, help='smoke 用：覆盖每次决策时限')
    ap.add_argument('--out', required=True)
    args = ap.parse_args(argv)

    from run_a1_step2_gate import run_arm
    from coldchain_evaluator_a1 import add_v2_initial_quality
    from scenario_saa import (ExplicitFeatureSampler, SaaReplanner,
                              build_history, build_history_times_classes)
    from run_exp_encoder_v3 import compute_budget_and_dwell
    import run_exp_reserve as RR
    from admission.policies import (RegisteredShadowPrice, build_clock_grid,
                                    build_lambda_grid, build_train_days, calibrate)
    from admission.panel_replanner import DynamicDualReplanner, StaticPriceReplanner

    t_start = time.perf_counter()
    contract = make_contract()
    train_ds = RR.generate_dataset(FROZEN['train_instances'], FROZEN['n_orders'],
                                   FROZEN['train_seed'])
    gate_ds = add_v2_initial_quality(
        RR.generate_dataset(FROZEN['gate_instances'], FROZEN['n_orders'], FROZEN['gate_seed']),
        contract)

    B = float(FROZEN['budget_B'])
    cooling_share = None
    try:  # 只为记录；失败不阻断（该值与接拒判定无关）
        _B, cooling_share, _ = compute_budget_and_dwell(
            train_ds, contract, FROZEN['num_vehicles'], FROZEN['train_seed'],
            FROZEN['rho'], build_history_times_classes(train_ds), k=FROZEN['k_neighbors'])
    except Exception as exc:  # noqa: BLE001
        cooling_share = None
        print('[warn] compute_budget_and_dwell failed: %r' % (exc,))
    if cooling_share is None:
        cooling_share = 3.7208946347769882   # 登记记录值（仅 SAA 内部使用）

    lam_grid = build_lambda_grid()
    clock_grid = build_clock_grid(FROZEN['horizon'])
    g_table = calibrate(build_train_days(train_ds, OBJECTIVE), OBJECTIVE,
                        FROZEN['horizon'], lam_grid, clock_grid)
    lam0 = float(args.lam0) if args.lam0 is not None else \
        float(RegisteredShadowPrice(lam_grid, clock_grid, g_table).lambda_for(0.0, B)[0])
    n_expected = 193.375

    panel = {k: v[:args.days] for k, v in gate_ds.items()}
    p_c = {0: 0.0, 1: 0.0, 2: 0.0}
    hist = build_history(train_ds)
    arms_wanted = [a.strip() for a in args.arms.split(',') if a.strip()]

    common = dict(K=int(args.K or FROZEN['K']),
                  time_limit=float(args.time_limit or FROZEN['time_limit']),
                  arm_seed=FROZEN['arm_seed'],
                  shadow_mode='greedy', energy_pricing='marginal', future_policy='reveal')
    results = {}
    timings = {}

    if 'control' in arms_wanted:
        t0 = time.perf_counter()
        results['control_frozen_saa'] = run_arm(
            panel, contract, B, FROZEN['capacity'], FROZEN['num_vehicles'], cooling_share,
            ExplicitFeatureSampler(hist), p_c, **common, replanner_cls=SaaReplanner)
        timings['control_frozen_saa'] = time.perf_counter() - t0

    if 'static' in arms_wanted:
        t0 = time.perf_counter()
        results['static_price'] = run_arm(
            panel, contract, B, FROZEN['capacity'], FROZEN['num_vehicles'], cooling_share,
            ExplicitFeatureSampler(hist), p_c, **common, replanner_cls=StaticPriceReplanner,
            extra_kwargs=dict(lambda_grid=lam_grid, clock_grid=clock_grid, g_table=g_table,
                              objective=OBJECTIVE))
        timings['static_price'] = time.perf_counter() - t0

    if 'dynamic' in arms_wanted:
        t0 = time.perf_counter()
        results['dynamic_dual'] = run_arm(
            panel, contract, B, FROZEN['capacity'], FROZEN['num_vehicles'], cooling_share,
            ExplicitFeatureSampler(hist), p_c, **common, replanner_cls=DynamicDualReplanner,
            extra_kwargs=dict(eta=float(args.eta), lam0=lam0, lam_max=float(args.lam_max),
                              n_expected=n_expected, objective=OBJECTIVE))
        timings['dynamic_dual'] = time.perf_counter() - t0

    def util(arm, k):
        try:
            return float(results[arm][k]['utility'])
        except Exception:  # noqa: BLE001
            return None

    per_day = []
    for k in range(args.days):
        row = dict(day=k)
        for arm in results:
            r = results[arm][k]
            row[arm] = dict(utility=r.get('utility'), n_served=r.get('n_served'),
                            revenue=r.get('revenue'), energy_kwh=r.get('energy_kwh'),
                            distance_km=r.get('distance_km'),
                            hard_feasible=r.get('hard_feasible'),
                            budget_violated=r.get('budget_violated'))
        if 'control_frozen_saa' in row and 'dynamic_dual' in row:
            a, b = row['control_frozen_saa']['utility'], row['dynamic_dual']['utility']
            row['delta_dynamic_minus_control'] = (None if (a is None or b is None) else float(b - a))
        if 'static_price' in row and 'dynamic_dual' in row:
            a, b = row['static_price']['utility'], row['dynamic_dual']['utility']
            row['delta_dynamic_minus_static'] = (None if (a is None or b is None) else float(b - a))
        per_day.append(row)

    def mean_of(key):
        vals = [r[key] for r in per_day if r.get(key) is not None]
        return float(np.mean(vals)) if vals else None

    summary = dict(
        stage='admission_panel_stage1', status='DEVELOPMENT_PANEL',
        config=dict(days=args.days, eta=args.eta, lam0=lam0, lam_max=args.lam_max,
                    arms=arms_wanted, budget=B, cooling_share=cooling_share,
                    K=int(args.K or FROZEN['K']),
                    time_limit=float(args.time_limit or FROZEN['time_limit']),
                    arm_seed=FROZEN['arm_seed'], objective=OBJECTIVE,
                    frozen=FROZEN),
        per_day=per_day,
        mean_delta_dynamic_minus_control=mean_of('delta_dynamic_minus_control'),
        mean_delta_dynamic_minus_static=mean_of('delta_dynamic_minus_static'),
        arms_present=list(results.keys()),
        timings_seconds=timings,
        elapsed_seconds=time.perf_counter() - t_start,
        limits=('单个 5 天面板；η/λ_max 未在 5 天上调参（λ0 取 TRAIN 静态价）；'
                'DEVELOPMENT_PANEL，不是预登记的正式阶段'),
    )

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'panel.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False),
                                    encoding='utf-8')

    lines = ['| 天 | 控制 utility | 静态 λ utility | 动态 λ utility | Δ(动态−控制) | Δ(动态−静态) |',
             '|---|---|---|---|---|---|']
    for r in per_day:
        def g(arm, key='utility'):
            v = r.get(arm, {}).get(key)
            return '—' if v is None else ('%.2f' % v)
        lines.append('| %d | %s | %s | %s | %s | %s |' % (
            r['day'], g('control_frozen_saa'), g('static_price'), g('dynamic_dual'),
            '—' if r.get('delta_dynamic_minus_control') is None
            else '%+.2f' % r['delta_dynamic_minus_control'],
            '—' if r.get('delta_dynamic_minus_static') is None
            else '%+.2f' % r['delta_dynamic_minus_static']))
    text = '\n'.join(lines)
    (out / 'panel.md').write_text(text + '\n', encoding='utf-8')
    print(text)
    print(json.dumps({k: v for k, v in summary.items() if k not in ('per_day', 'config')},
                     indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
