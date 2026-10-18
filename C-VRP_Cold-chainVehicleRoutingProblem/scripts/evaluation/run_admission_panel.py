"""阶段 1：全仿真接拒面板（3 臂，受控 A/B）—— 动态影子价格 vs 静态影子价格。

与登记面板（``research/.../a1_budget_reserving_admission_root_v4/run.py``）的差别只在
**候选臂的接拒过滤器**：控制臂仍是冻结的 ``SaaReplanner``；候选臂换成本仓库的
``StaticPriceReplanner`` / ``DynamicDualReplanner``。采样器、arm_seed、K、time_limit、
合同、预算、面板天全部对齐。

为什么自己实现 arm 循环：``run_a1_step2_gate.run_arm`` 在当前树上 import 失败
（它引用了 ``scenario_saa.SoftKNNHistoricalSampler``，该类在当前源码里已不存在）。
这里按该函数**逐行等价**地内联，不修改任何已登记文件。

用法（从扩展根目录）::

    python scripts/evaluation/run_admission_panel.py --days 5 --eta 0.02 \
        --out results/admission_panel/stage1_v1

产物：``<out>/panel.json`` + ``panel.md``（逐日效用、配对差、预算利用率、λ 轨迹摘要）。
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
              km_per_unit=20.0, speed_kmh=30.0, cooling_share=3.7208946347769882)
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


def _single(ds, i):
    return {k: v[i] for k, v in ds.items()}


def run_arm(gate_ds, contract, B, capacity, num_vehicles, cooling_share, sampler, p_c,
            K, time_limit, arm_seed, *, shadow_mode='greedy', energy_pricing='marginal',
            future_policy='reveal', replanner_cls, extra_kwargs=None, progress_file=None):
    """``run_a1_step2_gate.run_arm`` 的等价内联版（见模块 docstring）。"""
    from strict_online_env import StrictOnlineEnv
    from coldchain_evaluator_a1 import evaluate_trace_a1
    from run_exp_reserve import BOOKING_HORIZON, SPEED_KMH, KM_PER_UNIT

    kw = dict(budget=B, capacity=capacity, booking_horizon=BOOKING_HORIZON,
              contract=contract, cooling_share=cooling_share, sampler=sampler,
              reject_penalty=p_c, K=K, time_limit=time_limit, arm_seed=arm_seed,
              shadow_mode=shadow_mode, energy_pricing=energy_pricing,
              future_policy=future_policy, standby_orders=None, overage_price=None,
              incr_eval=False, anytime_vote=False)
    if extra_kwargs:
        kw.update(extra_kwargs)
    # 别名兼容：冻结的 SaaReplanner 不接受 anytime_vote（那是 RolloutVReplanner 的），
    # 按目标 replanner 的真实签名过滤一次，避免把陈旧参数带进去。
    kw.pop('anytime_vote', None)   # RolloutVReplanner 专用，冻结 SaaReplanner 不接受
    import inspect
    sig = inspect.signature(replanner_cls.__init__)
    if not any(p.kind == p.VAR_KEYWORD for p in sig.parameters.values()):
        dropped = sorted(set(kw) - set(sig.parameters))
        kw = {k: v for k, v in kw.items() if k in sig.parameters}
        if dropped:
            print('[run_arm] dropped unsupported kwargs: %s' % ','.join(dropped))
    rp = replanner_cls(**kw)
    env = StrictOnlineEnv(gate_ds, capacity=capacity, num_vehicles=num_vehicles,
                          tw_speed=SPEED_KMH / KM_PER_UNIT, replanner=rp,
                          coldchain_contract=contract, booking_horizon=BOOKING_HORIZON)
    rows = []
    for i in range(gate_ds['coords'].shape[0]):
        t0 = time.time()
        try:
            traces, _ = env.run(i)
            acc, rej = set(rp._accepted), set(rp._rejected)
            ev = evaluate_trace_a1(traces, _single(gate_ds, i), contract, acc, rej, B, p_c)
        except Exception as exc:  # noqa: BLE001 —— 异常按缺失日记为不可裁决，不伪造
            if os.environ.get('MASKCO_TRACEBACK') == '1':
                import traceback as _tb
                _tb.print_exc()
            rows.append(dict(i=int(i), utility=None, hard_feasible=False,
                             failures=['execution_crash'], error=repr(exc),
                             n_served=None, n_rejected=None, n_fish_unsalable=None,
                             energy_kwh=None, budget_violated=None, revenue=None,
                             fuel_cost=None, reject_loss=None, distance_km=None,
                             service_rate=None, reject_rate=None, salable_rate=None,
                             tomato_mean_quality=None,
                             timeouts=int(getattr(rp, 'timeouts', 0)),
                             partial_commits=int(getattr(rp, 'partial_commits', 0)),
                             early_stops=int(getattr(rp, 'early_stops', 0)),
                             saa_completion_rate=None,
                             n_decisions=int(getattr(rp, 'n_decisions', 0)),
                             elapsed_s=float(time.time() - t0),
                             admission=None))
            if progress_file:
                with open(progress_file, 'a', encoding='utf-8') as pf:
                    pf.write('%d %.1f crash\n' % (i, time.time() - t0))
            continue
        print('[arm] day %d ok %s utility=%s %.1fs'
              % (i, replanner_cls.__name__,
                 ('%.2f' % ev['utility']) if np.isfinite(ev['utility']) else 'nan',
                 time.time() - t0), flush=True)
        if progress_file:
            with open(progress_file, 'a', encoding='utf-8') as pf:
                pf.write('%d %.1f ok\n' % (i, time.time() - t0))
        adm = None
        if hasattr(rp, 'admission_summary'):
            try:
                adm = rp.admission_summary()
            except Exception:  # noqa: BLE001
                adm = None
        rows.append(dict(
            i=int(i),
            utility=(float(ev['utility']) if np.isfinite(ev['utility']) else None),
            hard_feasible=bool(ev['hard_feasible']),
            failures=sorted(set(ev['failures'])),
            n_served=int(ev['n_served']), n_rejected=int(ev['n_rejected']),
            n_fish_unsalable=int(ev['n_fish_unsalable']),
            energy_kwh=float(ev['energy_kwh']),
            budget_violated=bool(ev['budget_violated']),
            revenue=float(ev['revenue']), fuel_cost=float(ev['fuel_cost']),
            reject_loss=float(ev['reject_loss']), distance_km=float(ev['distance_km']),
            service_rate=ev['service_rate'], reject_rate=ev['reject_rate'],
            salable_rate=ev['salable_rate'],
            tomato_mean_quality=ev['tomato_mean_quality'],
            timeouts=int(getattr(rp, 'timeouts', 0)),
            partial_commits=int(getattr(rp, 'partial_commits', 0)),
            early_stops=int(getattr(rp, 'early_stops', 0)),
            saa_completion_rate=(float(rp.saa_completion_rate)
                                 if getattr(rp, 'saa_completion_rate', None) is not None else None),
            n_decisions=int(getattr(rp, 'n_decisions', 0)),
            elapsed_s=float(time.time() - t0),
            admission=adm,
            served_ids=(sorted(int(x) for x in rp._accepted)
                        if os.environ.get('MASKCO_DUMP_SERVED') == '1' else None)))
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--days', type=int, default=5)
    ap.add_argument('--start-day', type=int, default=0,
                    help='从第几天开始（用于真正盲测的留出日，例如 10..14）')
    ap.add_argument('--eta', type=float, default=0.02)
    ap.add_argument('--lam0', type=float, default=None,
                    help='默认用静态规则在 clock=0/B 处的价格（因果热启动）')
    ap.add_argument('--lam-max', type=float, default=8.0)
    ap.add_argument('--arms', default='control,static,dynamic')   # 可选 marginal
    ap.add_argument('--dp-npz', default=None,
                    help='dp 臂：DP 值表 npz（run_causal_dp.py --save-v 生成）')
    ap.add_argument('--dp-n-expected', type=float, default=193.0)
    ap.add_argument('--fuel-weight', type=float, default=1.0,
                    help='marginal 臂：燃油项权重')
    ap.add_argument('--quality-weight', type=float, default=1.0,
                    help='marginal 臂：品质损耗项权重')
    ap.add_argument('--K', type=int, default=None, help='smoke 用：覆盖采样数')
    ap.add_argument('--time-limit', type=float, default=None, help='smoke 用：覆盖时限')
    ap.add_argument('--dataset', choices=['gate', 'train'], default='gate',
                    help='在哪批实例上跑面板；train 用于 TRAIN 侧标定（不得用于最终判定）')
    ap.add_argument('--tier-allowed', default='1,2',
                    help='tier 臂：允许的温区集合（逗号分隔，如 "1,2"）')
    ap.add_argument('--tier-late', default=None,
                    help='tier 臂：晚段允许的温区集合（留空表示不分段）')
    ap.add_argument('--tier-late-clock', type=float, default=None,
                    help='tier 臂：切换到 --tier-late 的 clock 阈值（小时）')
    ap.add_argument('--okp-l', type=float, default=1.55,
                    help='okp 臂：收入密度下界 L（由 REV 与 e_lower 定义域算出）')
    ap.add_argument('--okp-u', type=float, default=9.52,
                    help='okp 臂：收入密度上界 U')
    ap.add_argument('--okp-tags', default='x1',
                    help='okp 臂：要跑的阈值缩放变体（逗号分隔，x1 / x2）')
    ap.add_argument('--reopt-passes', type=int, default=2,
                    help='reopt 臂：同集合 2-opt 的迭代轮数')
    ap.add_argument('--ortools-ms', type=int, default=500,
                    help='ortools 臂：每个事件点的求解时限（毫秒）')
    ap.add_argument('--batch-k', type=int, default=8,
                    help='batch 臂：攒够多少待派订单才发车')
    ap.add_argument('--batch-wait', type=float, default=1.0,
                    help='batch 臂：最老待派订单最多等多久（小时）')
    ap.add_argument('--ls-passes', type=int, default=6,
                    help='ls 臂：SAA 内部局部搜索的 pass 数（冻结实现默认 2）')
    ap.add_argument('--pyvrp-time-limit', type=float, default=0.2,
                    help='pyvrp 臂：每次联合可行性判定的求解时限（秒）')
    ap.add_argument('--pyvrp-max-orders', type=int, default=60,
                    help='pyvrp 臂：池子超过该单数则不过滤（控制成本）')
    ap.add_argument('--conf-alphas', default='0.5',
                    help='conf 臂：保形分位水平 α 列表（逗号分隔，如 "0.4,0.5"）')
    ap.add_argument('--out', required=True)
    args = ap.parse_args(argv)

    from coldchain_evaluator_a1 import add_v2_initial_quality
    from scenario_saa import ExplicitFeatureSampler, SaaReplanner, build_history
    import run_exp_reserve as RR
    from admission.policies import (RegisteredShadowPrice, build_clock_grid,
                                    build_lambda_grid, build_train_days, calibrate)
    from admission.panel_replanner import (DPGateReplanner, DynamicDualReplanner,
                                         MarginalGateReplanner, StaticPriceReplanner)

    t_start = time.perf_counter()
    contract = make_contract()
    train_ds = add_v2_initial_quality(
        RR.generate_dataset(FROZEN['train_instances'], FROZEN['n_orders'],
                            FROZEN['train_seed']), contract)
    gate_ds = add_v2_initial_quality(
        RR.generate_dataset(FROZEN['gate_instances'], FROZEN['n_orders'], FROZEN['gate_seed']),
        contract)

    B = float(FROZEN['budget_B'])
    cooling_share = float(FROZEN['cooling_share'])   # 登记记录值（仅 SAA 内部使用）

    lam_grid = build_lambda_grid()
    clock_grid = build_clock_grid(FROZEN['horizon'])
    g_table = calibrate(build_train_days(train_ds, OBJECTIVE), OBJECTIVE,
                        FROZEN['horizon'], lam_grid, clock_grid)
    lam0 = float(args.lam0) if args.lam0 is not None else \
        float(RegisteredShadowPrice(lam_grid, clock_grid, g_table).lambda_for(0.0, B)[0])
    n_expected = 193.375

    source = train_ds if args.dataset == 'train' else gate_ds
    _s0 = int(args.start_day)
    panel = {k: v[_s0:_s0 + args.days] for k, v in source.items()}
    p_c = {0: 0.0, 1: 0.0, 2: 0.0}
    hist = build_history(train_ds)
    arms_wanted = [a.strip() for a in args.arms.split(',') if a.strip()]

    common = dict(K=int(args.K or FROZEN['K']),
                  time_limit=float(args.time_limit or FROZEN['time_limit']),
                  arm_seed=FROZEN['arm_seed'],
                  shadow_mode='greedy', energy_pricing='marginal', future_policy='reveal')
    results, timings = {}, {}
    conf_cal = {}

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

    if 'dp' in arms_wanted:
        t0 = time.perf_counter()
        dp_npz = args.dp_npz or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            'results', 'causal_dp', 'v1', 'dp_v.npz')
        results['dp_gate'] = run_arm(
            panel, contract, B, FROZEN['capacity'], FROZEN['num_vehicles'], cooling_share,
            ExplicitFeatureSampler(hist), p_c, **common, replanner_cls=DPGateReplanner,
            extra_kwargs=dict(lambda_grid=lam_grid, clock_grid=clock_grid, g_table=g_table,
                              objective=OBJECTIVE,
                              fuel_weight=float(args.fuel_weight),
                              quality_weight=float(args.quality_weight),
                              dp_npz=dp_npz,
                              dp_n_expected=float(args.dp_n_expected)))
        timings['dp_gate'] = time.perf_counter() - t0

    if 'marginal' in arms_wanted:
        t0 = time.perf_counter()
        results['marginal_gate'] = run_arm(
            panel, contract, B, FROZEN['capacity'], FROZEN['num_vehicles'], cooling_share,
            ExplicitFeatureSampler(hist), p_c, **common, replanner_cls=MarginalGateReplanner,
            extra_kwargs=dict(lambda_grid=lam_grid, clock_grid=clock_grid, g_table=g_table,
                              objective=OBJECTIVE,
                              fuel_weight=float(args.fuel_weight),
                              quality_weight=float(args.quality_weight)))
        timings['marginal_gate'] = time.perf_counter() - t0

    if 'tier' in arms_wanted:
        from admission.panel_replanner import ClassTierReplanner
        allowed = tuple(int(x) for x in str(args.tier_allowed).split(',') if x.strip())
        late = None
        if args.tier_late not in (None, ''):
            late = tuple(int(x) for x in str(args.tier_late).split(',') if x.strip())
        t0 = time.perf_counter()
        results['class_tier'] = run_arm(
            panel, contract, B, FROZEN['capacity'], FROZEN['num_vehicles'], cooling_share,
            ExplicitFeatureSampler(hist), p_c, **common, replanner_cls=ClassTierReplanner,
            extra_kwargs=dict(allowed_classes=allowed, late_classes=late,
                              late_clock=args.tier_late_clock))
        timings['class_tier'] = time.perf_counter() - t0

    if 'okp' in arms_wanted:
        from admission.panel_replanner import OnlineKnapsackReplanner
        for tag, scale in (('x1', 1.0), ('x2', 2.0)):
            if tag not in [t.strip() for t in str(args.okp_tags).split(',') if t.strip()]:
                continue
            t0 = time.perf_counter()
            results['online_knapsack' + ('' if tag == 'x1' else '_' + tag)] = run_arm(
                panel, contract, B, FROZEN['capacity'], FROZEN['num_vehicles'],
                cooling_share, ExplicitFeatureSampler(hist), p_c, **common,
                replanner_cls=OnlineKnapsackReplanner,
                extra_kwargs=dict(lambda_grid=lam_grid, clock_grid=clock_grid,
                                  g_table=g_table, objective=OBJECTIVE,
                                  density_min=float(args.okp_l),
                                  density_max=float(args.okp_u),
                                  density_scale=float(scale)))
            timings['online_knapsack' + ('' if tag == 'x1' else '_' + tag)] = (
                time.perf_counter() - t0)

    if 'conf' in arms_wanted:
        from admission.panel_replanner import ConformalDensityReplanner
        from admission.policies import conformal_density_threshold
        for alpha in [float(a) for a in str(args.conf_alphas).split(',') if a.strip()]:
            cal = conformal_density_threshold(train_ds, OBJECTIVE, alpha)
            tag = 'a%02d' % int(round(alpha * 100))
            key = 'conformal_density' + ('' if tag == 'a50' else '_' + tag)
            print('[conf] alpha=%.2f rho=%.4f n=%d order_stat=%d frac>=rho=%.4f'
                  % (alpha, cal['rho'], cal['n'], cal['order_stat'], cal['frac_at_or_above']),
                  flush=True)
            t0 = time.perf_counter()
            results[key] = run_arm(
                panel, contract, B, FROZEN['capacity'], FROZEN['num_vehicles'],
                cooling_share, ExplicitFeatureSampler(hist), p_c, **common,
                replanner_cls=ConformalDensityReplanner,
                extra_kwargs=dict(lambda_grid=lam_grid, clock_grid=clock_grid,
                                  g_table=g_table, objective=OBJECTIVE,
                                  conf_rho=float(cal['rho']), conf_alpha=float(alpha)))
            timings[key] = time.perf_counter() - t0
            conf_cal[key] = cal

    if 'part' in arms_wanted:
        from admission.panel_replanner import PartitionReoptReplanner
        t0 = time.perf_counter()
        results['partition_reopt'] = run_arm(
            panel, contract, B, FROZEN['capacity'], FROZEN['num_vehicles'], cooling_share,
            ExplicitFeatureSampler(hist), p_c, **common,
            replanner_cls=PartitionReoptReplanner,
            extra_kwargs=dict(reopt_passes=int(args.reopt_passes)))
        timings['partition_reopt'] = time.perf_counter() - t0

    if 'reopt' in arms_wanted:
        from admission.panel_replanner import SameSetReoptReplanner
        t0 = time.perf_counter()
        results['same_set_reopt'] = run_arm(
            panel, contract, B, FROZEN['capacity'], FROZEN['num_vehicles'], cooling_share,
            ExplicitFeatureSampler(hist), p_c, **common,
            replanner_cls=SameSetReoptReplanner,
            extra_kwargs=dict(reopt_passes=int(args.reopt_passes)))
        timings['same_set_reopt'] = time.perf_counter() - t0

    if 'ortools' in arms_wanted:
        from admission.panel_replanner import ORToolsSaaReplanner as ORToolsReplanner
        t0 = time.perf_counter()
        results['ortools_rolling'] = run_arm(
            panel, contract, B, FROZEN['capacity'], FROZEN['num_vehicles'], cooling_share,
            ExplicitFeatureSampler(hist), p_c, **common,
            replanner_cls=ORToolsReplanner,
            extra_kwargs=dict(time_limit_ms=int(args.ortools_ms),
                              or_capacity=float(FROZEN['capacity']),
                              or_num_vehicles=int(FROZEN['num_vehicles']),
                              lambda_grid=lam_grid, clock_grid=clock_grid,
                              g_table=g_table, objective=OBJECTIVE))
        timings['ortools_rolling'] = time.perf_counter() - t0

    if 'batch' in arms_wanted:
        from admission.panel_replanner import BatchedDispatchReplanner
        t0 = time.perf_counter()
        results['batched_dispatch'] = run_arm(
            panel, contract, B, FROZEN['capacity'], FROZEN['num_vehicles'], cooling_share,
            ExplicitFeatureSampler(hist), p_c, **common,
            replanner_cls=BatchedDispatchReplanner,
            extra_kwargs=dict(lambda_grid=lam_grid, clock_grid=clock_grid, g_table=g_table,
                              objective=OBJECTIVE,
                              batch_k=int(args.batch_k), batch_wait_h=float(args.batch_wait)))
        timings['batched_dispatch'] = time.perf_counter() - t0

    if 'ls' in arms_wanted:
        from admission.panel_replanner import DeeperLSReplanner
        t0 = time.perf_counter()
        results['deeper_ls'] = run_arm(
            panel, contract, B, FROZEN['capacity'], FROZEN['num_vehicles'], cooling_share,
            ExplicitFeatureSampler(hist), p_c, **common,
            replanner_cls=DeeperLSReplanner,
            extra_kwargs=dict(ls_passes=int(args.ls_passes)))
        timings['deeper_ls'] = time.perf_counter() - t0

    if 'pyvrp' in arms_wanted:
        from admission.panel_replanner import PyVrpFeasibilityReplanner
        t0 = time.perf_counter()
        results['pyvrp_feasible'] = run_arm(
            panel, contract, B, FROZEN['capacity'], FROZEN['num_vehicles'], cooling_share,
            ExplicitFeatureSampler(hist), p_c, **common,
            replanner_cls=PyVrpFeasibilityReplanner,
            extra_kwargs=dict(lambda_grid=lam_grid, clock_grid=clock_grid, g_table=g_table,
                              objective=OBJECTIVE,
                              pyvrp_time_limit=float(args.pyvrp_time_limit),
                              pyvrp_max_orders=int(args.pyvrp_max_orders)))
        timings['pyvrp_feasible'] = time.perf_counter() - t0

    if 'dynamic' in arms_wanted:
        t0 = time.perf_counter()
        results['dynamic_dual'] = run_arm(
            panel, contract, B, FROZEN['capacity'], FROZEN['num_vehicles'], cooling_share,
            ExplicitFeatureSampler(hist), p_c, **common, replanner_cls=DynamicDualReplanner,
            extra_kwargs=dict(eta=float(args.eta), lam0=lam0, lam_max=float(args.lam_max),
                              n_expected=n_expected, objective=OBJECTIVE))
        timings['dynamic_dual'] = time.perf_counter() - t0

    per_day = []
    for k in range(args.days):
        row = dict(day=k)
        for arm in results:
            r = results[arm][k]
            row[arm] = dict(utility=r.get('utility'), n_served=r.get('n_served'),
                            revenue=r.get('revenue'), energy_kwh=r.get('energy_kwh'),
                            distance_km=r.get('distance_km'),
                            hard_feasible=r.get('hard_feasible'),
                            budget_violated=r.get('budget_violated'),
                            n_rejected=r.get('n_rejected'),
                            service_rate=r.get('service_rate'),
                            salable_rate=r.get('salable_rate'),
                            reject_rate=r.get('reject_rate'),
                            n_fish_unsalable=r.get('n_fish_unsalable'),
                            fuel_cost=r.get('fuel_cost'),
                            tomato_mean_quality=r.get('tomato_mean_quality'),
                            served_ids=r.get('served_ids'),
                            failures=r.get('failures'),
                            error=r.get('error'),
                            admission=r.get('admission'),
                            elapsed_s=r.get('elapsed_s'))
        if 'dp_gate' in row and 'control_frozen_saa' in row:
            a, b = row['control_frozen_saa']['utility'], row['dp_gate']['utility']
            row['delta_dp_minus_control'] = (None if (a is None or b is None)
                                             else float(b - a))
        if 'class_tier' in row and 'control_frozen_saa' in row:
            a, b = row['control_frozen_saa']['utility'], row['class_tier']['utility']
            row['delta_class_tier_minus_control'] = (None if (a is None or b is None)
                                                     else float(b - a))
        if 'marginal_gate' in row and 'control_frozen_saa' in row:
            a, b = row['control_frozen_saa']['utility'], row['marginal_gate']['utility']
            row['delta_marginal_minus_control'] = (None if (a is None or b is None)
                                                   else float(b - a))
        if 'dynamic_dual' in row and 'control_frozen_saa' in row:
            a, b = row['control_frozen_saa']['utility'], row['dynamic_dual']['utility']
            row['delta_dynamic_minus_control'] = (None if (a is None or b is None)
                                                  else float(b - a))
        if 'static_price' in row and 'dynamic_dual' in row:
            a, b = row['static_price']['utility'], row['dynamic_dual']['utility']
            row['delta_dynamic_minus_static'] = (None if (a is None or b is None)
                                                 else float(b - a))
        per_day.append(row)

    def mean_of(key):
        vals = [r[key] for r in per_day if r.get(key) is not None]
        return float(np.mean(vals)) if vals else None

    summary = dict(
        stage='admission_panel_stage1', status='DEVELOPMENT_PANEL',
        config=dict(days=args.days, eta=args.eta, lam0=lam0, lam_max=args.lam_max,
                    arms=arms_wanted, dataset=args.dataset,
                    fuel_weight=float(args.fuel_weight),
                    quality_weight=float(args.quality_weight),
                    budget=B, cooling_share=cooling_share,
                    K=int(args.K or FROZEN['K']),
                    time_limit=float(args.time_limit or FROZEN['time_limit']),
                    arm_seed=FROZEN['arm_seed'], objective=OBJECTIVE, frozen=FROZEN),
        per_day=per_day,
        mean_delta_dynamic_minus_control=mean_of('delta_dynamic_minus_control'),
        mean_delta_dynamic_minus_static=mean_of('delta_dynamic_minus_static'),
        mean_delta_marginal_minus_control=mean_of('delta_marginal_minus_control'),
        mean_delta_dp_minus_control=mean_of('delta_dp_minus_control'),
        mean_delta_class_tier_minus_control=mean_of('delta_class_tier_minus_control'),
        conformal_calibration=conf_cal,
        arms_present=list(results.keys()),
        timings_seconds=timings,
        elapsed_seconds=time.perf_counter() - t_start,
        limits=('单个面板；η/λ_max 未在面板上调参（λ0 取 TRAIN 静态价）；'
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
    print(json.dumps({k: v for k, v in summary.items() if k not in ('per_day',)},
                     indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
