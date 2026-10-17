"""接拒层的离线（表级）策略对照：**开发用诊断**，不是登记过的正式实验。

为什么先做这一步
----------------
完整 A/B 面板（``research/.../a1_budget_reserving_admission_root_v4/run.py``）要跑两臂
CVRPTW 仿真，5 天 × 2 臂 ≈ 20 分钟；而"是否接受"这一步只依赖 (收入, 预冷能耗, 时钟, 剩余预算)。
因此先在**订单流 + 登记校准表**这一层比较策略，可以在秒级回答：

  H1（可证伪）：动态影子价格 λ_t 是否比静态 λ 在更多天上改变并改善结果？

本脚本的诚实边界（务必随结果一起引用）
--------------------------------------
* 目标只有**收入**（``revenue``），**不含**距离、品质损耗、时间窗可行性 ⇒ 与登记面板的
  ``utility`` 不可直接比较；这里只作"接拒层"的机制诊断（candidate-level 代理）。
* 上界是**分数背包**（LP 松弛），不是真问题的最优；真问题上界见 ``a1_budget_reachability_bound``。
* 结果是 **exploratory / dev**，不得写成正式增益；正式结论必须走预登记 40 天阶段。

用法（从扩展根目录）::

    python scripts/evaluation/run_admission_offline_regret.py --out results/admission_offline/dev_v1

依赖：numpy（无 JAX、无 GPU、无仿真器）。
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_SCRIPTS, os.path.join(_SCRIPTS, 'evaluation'), os.path.join(_SCRIPTS, 'admission')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from admission.controller import AdmissionController, OrderView  # noqa: E402
from admission.policies import (AlwaysAccept, DynamicDual, DynamicPriceCurve,  # noqa: E402
                                FixedThreshold, RegisteredShadowPrice, build_clock_grid,
                                build_lambda_grid, build_train_days, calibrate)

# 登记冻结值（与 a1_budget_reserving_admission_root_v4/REGISTRATION.json 一致）
REGISTERED = dict(train_seed=20260925, train_instances=200,
                  gate_seed=20260926, gate_instances=40,
                  n_orders=200, num_vehicles=15, capacity=50.0,
                  booking_horizon=16.0, horizon=16.0, panel_days=5,
                  budget_B=710.6548328611384)
OBJECTIVE = dict(ambient_c=25.0, target_c=[18.0, 4.0, -18.0],
                 precool_energy_per_unit_per_c=0.15)


# --------------------------------------------------------------------------
# 上界与参照
# --------------------------------------------------------------------------
def lp_fractional_bound(rev: np.ndarray, e: np.ndarray, budget: float) -> float:
    """分数背包上界：按 rev/e 降序装满预算（可切分）。"""
    rev = np.asarray(rev, dtype=np.float64)
    e = np.asarray(e, dtype=np.float64)
    if budget <= 0 or rev.size == 0:
        return 0.0
    ratio = np.where(e > 0, rev / np.maximum(e, 1e-12), np.inf)
    order = np.argsort(-ratio, kind='stable')
    rem, total = float(budget), 0.0
    for i in order:
        if e[i] <= 0:
            total += rev[i]
            continue
        if e[i] <= rem + 1e-12:
            rem -= e[i]
            total += rev[i]
        else:
            total += rev[i] * (rem / e[i])
            break
    return float(total)


def integral_greedy_bound(rev: np.ndarray, e: np.ndarray, budget: float) -> float:
    """整数贪婪参照：按 rev/e 降序、放得下就收（可行解，不是上界的最优）。"""
    rev = np.asarray(rev, dtype=np.float64)
    e = np.asarray(e, dtype=np.float64)
    ratio = np.where(e > 0, rev / np.maximum(e, 1e-12), np.inf)
    order = np.argsort(-ratio, kind='stable')
    rem, total = float(budget), 0.0
    for i in order:
        if e[i] <= rem + 1e-12:
            rem -= e[i]
            total += rev[i]
    return float(total)


# --------------------------------------------------------------------------
# 数据
# --------------------------------------------------------------------------
def load_dataset(instances: int, seed: int, n_orders: int):
    """复用登记脚本的生成器（纯 NumPy，保证与冻结面板同分布同种子）。"""
    sys.path.insert(0, os.path.join(_SCRIPTS, 'evaluation'))
    import run_exp_reserve as RR  # noqa: E402
    return RR.generate_dataset(instances, n_orders, seed)


def day_orders_of(dataset, day_index: int):
    dem = np.asarray(dataset['demands'], dtype=np.float64)
    rev_t = np.asarray(dataset['reveal_time'], dtype=np.float64)
    cls_t = np.asarray(dataset['temp_class'], dtype=np.int64)
    mask = dem[day_index, 1:] > 0
    cls = cls_t[day_index, 1:][mask]
    q = dem[day_index, 1:][mask]
    t = rev_t[day_index, 1:][mask]
    from admission.policies import e_lower_of
    est = np.asarray([e_lower_of(int(c), float(qq), OBJECTIVE) for c, qq in zip(cls, q)],
                     dtype=np.float64)
    order = np.argsort(t, kind='stable')
    out = []
    for rank, idx in enumerate(order):
        out.append(OrderView.build(rank, int(cls[idx]), float(q[idx]), float(est[idx]),
                                   reveal_time=float(t[idx])))
    return out


# --------------------------------------------------------------------------
# 一天的策略回放
# --------------------------------------------------------------------------
def run_policy_day(policy, orders, budget: float, horizon: float) -> dict:
    ctrl = AdmissionController(policy, budget=budget)
    ctrl.begin_day(orders, horizon=horizon, day_index=None)
    for o in orders:
        ctrl.decide(o, clock=o.reveal_time)
    s = ctrl.summary()
    s['accepted_ids'] = list(ctrl.state.accepted)
    # λ 轨迹摘要（只对给出 λ 的策略有意义）
    path = [d.lam for d in ctrl.state.trace if d.lam is not None]
    s['lambda_trajectory_head'] = [round(float(x), 4) for x in path[:12]]
    return s


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--train-instances', type=int, default=REGISTERED['train_instances'])
    ap.add_argument('--train-seed', type=int, default=REGISTERED['train_seed'])
    ap.add_argument('--gate-instances', type=int, default=REGISTERED['gate_instances'])
    ap.add_argument('--gate-seed', type=int, default=REGISTERED['gate_seed'])
    ap.add_argument('--n-orders', type=int, default=REGISTERED['n_orders'])
    ap.add_argument('--days', type=int, default=REGISTERED['panel_days'])
    ap.add_argument('--horizon', type=float, default=REGISTERED['horizon'])
    ap.add_argument('--budget', type=float, default=REGISTERED['budget_B'],
                    help='默认取登记重算值 B；亦可用 --budget-mode accept_all 现算')
    ap.add_argument('--budget-mode', choices=['registered', 'accept_all'], default='registered')
    ap.add_argument('--out', required=True)
    args = ap.parse_args(argv)

    train = load_dataset(args.train_instances, args.train_seed, args.n_orders)
    gate = load_dataset(args.gate_instances, args.gate_seed, args.n_orders)
    train_days = build_train_days(train, OBJECTIVE)

    B = float(args.budget)
    if args.budget_mode == 'accept_all':
        from admission.policies import e_lower_of
        tot = []
        for t, est, _rv in train_days:
            tot.append(float(np.sum(est)))
        B = float(np.mean(tot)) if tot else B

    lam_grid = build_lambda_grid()
    clock_grid = build_clock_grid(args.horizon)
    g_table = calibrate(train_days, OBJECTIVE, args.horizon, lam_grid, clock_grid)
    n_expected = float(np.mean([len(d[0]) for d in train_days]))

    # 静态规则的当日起始价（用于给动态策略做**因果**热启动：只看 clock=0 与预算 B）
    static_probe = RegisteredShadowPrice(lam_grid, clock_grid, g_table)
    lam_start = float(static_probe.lambda_for(0.0, B)[0])

    policies = []
    policies.append(('always_accept', AlwaysAccept()))
    for theta in (1.5, 2.0, 2.5):
        policies.append(('fixed_threshold@%.1f' % theta, FixedThreshold(theta)))
    policies.append(('registered_shadow_price', RegisteredShadowPrice(lam_grid, clock_grid, g_table)))
    for eta in (0.02, 0.05, 0.2):
        policies.append(('dynamic_dual@eta%.2f' % eta,
                         DynamicDual(eta=eta, lam0=lam_start, lam_max=8.0, n_expected=n_expected)))
    for gamma in (0.5, 1.0, 2.0):
        policies.append(('price_curve@gamma%.1f' % gamma,
                         DynamicPriceCurve(lam_min=lam_grid[0], lam_max=lam_grid[-1], gamma=gamma)))

    per_day = []
    for d in range(args.days):
        orders = day_orders_of(gate, d)
        rev = np.asarray([o.revenue for o in orders])
        e = np.asarray([o.e_hat for o in orders])
        total_e = float(e.sum())
        row = dict(day=d, n_orders=len(orders), total_energy=total_e,
                   total_revenue_if_all=float(rev.sum()),
                   lp_bound=lp_fractional_bound(rev, e, B),
                   integral_greedy=integral_greedy_bound(rev, e, B),
                   budget=B, energy_over_budget_ratio=total_e / B if B > 0 else None,
                   policies={})
        for name, pol in policies:
            s = run_policy_day(pol, orders, B, args.horizon)
            s['regret_vs_lp'] = row['lp_bound'] - s['accepted_revenue']
            s['regret_ratio_vs_lp'] = (s['regret_vs_lp'] / row['lp_bound']
                                       if row['lp_bound'] > 0 else None)
            row['policies'][name] = s
        per_day.append(row)

    # 配对比较：每个动态策略 vs 静态规则（逐日 revenue 差）
    base = 'registered_shadow_price'
    paired = {}
    for name, _ in policies:
        if name == base:
            continue
        deltas = [row['policies'][name]['accepted_revenue']
                  - row['policies'][base]['accepted_revenue'] for row in per_day]
        paired[name] = dict(deltas=[float(x) for x in deltas],
                            mean=float(np.mean(deltas)),
                            n_positive=int(sum(1 for x in deltas if x > 0)),
                            n_negative=int(sum(1 for x in deltas if x < 0)),
                            n_zero=int(sum(1 for x in deltas if x == 0)))

    summary = dict(
        stage='admission_offline_table_level',
        status='DEVELOPMENT_DIAGNOSTIC_NOT_A_REGISTERED_RESULT',
        honesty=('目标仅为收入，不含距离/品质/TW；上界为分数背包；'
                 '结果不得表述为正式增益，正式结论需预登记 40 天阶段'),
        config=dict(train_instances=args.train_instances, train_seed=args.train_seed,
                    gate_instances=args.gate_instances, gate_seed=args.gate_seed,
                    n_orders=args.n_orders, days=args.days, horizon=args.horizon,
                    budget=B, budget_mode=args.budget_mode,
                    n_expected_train=n_expected, lambda_start=lam_start,
                    lambda_grid_size=len(lam_grid), clock_grid_size=len(clock_grid)),
        per_day=per_day,
        paired_vs_registered=paired,
        h1_decision=dict(
            statement=('H1: 动态影子价格 λ_t 严格优于静态 λ（更多非零改进天）'),
            dynamic_nonzero_days={k: dict(n_nonzero=v['n_positive'] + v['n_negative'],
                                          n_positive=v['n_positive'], mean=v['mean'])
                                  for k, v in paired.items() if k.startswith(('dynamic_dual', 'price_curve'))},
            static_nonzero_days=dict(
                n_nonzero=sum(1 for row in per_day
                              if row['policies'][base]['accepted_revenue']
                              != row['policies']['always_accept']['accepted_revenue']),
                note='静态规则相对 always_accept 改变结果的天数（机制是否真的起作用）'),
        ),
    )

    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, 'summary.json'), 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    # 人读表
    lines = ['| policy | ' + ' | '.join('day%d' % d for d in range(args.days)) + ' | mean revenue | mean regret vs LP |',
             '|---' * (args.days + 3) + '|']
    for name, _ in policies:
        revs = [row['policies'][name]['accepted_revenue'] for row in per_day]
        regs = [row['policies'][name]['regret_vs_lp'] for row in per_day]
        lines.append('| %s | ' % name + ' | '.join('%.2f' % x for x in revs)
                     + ' | %.2f | %.2f |' % (float(np.mean(revs)), float(np.mean(regs)))) 
    lp = [row['lp_bound'] for row in per_day]
    lines.append('| **LP 上界** | ' + ' | '.join('%.2f' % x for x in lp)
                 + ' | %.2f | 0 |' % float(np.mean(lp)))
    ig = [row['integral_greedy'] for row in per_day]
    lines.append('| **整数贪婪参照** | ' + ' | '.join('%.2f' % x for x in ig)
                 + ' | %.2f | — |' % float(np.mean(ig)))
    with open(os.path.join(args.out, 'summary.md'), 'w', encoding='utf-8') as f:
        f.write('# 接拒层离线对照（开发诊断，非正式结果）\n\n')
        f.write('budget B = %.4f，天数 = %d，每日订单 = %d，λ_start = %.3f\n\n'
                % (B, args.days, args.n_orders, lam_start))
        f.write('\n'.join(lines) + '\n')

    print(json.dumps({k: v for k, v in summary.items() if k not in ('per_day',)}, indent=2,
                     ensure_ascii=False)[:4000])
    print('\n' + '\n'.join(lines))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
