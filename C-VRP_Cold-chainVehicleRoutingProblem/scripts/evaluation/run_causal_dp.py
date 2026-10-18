"""D4 v3：简化设定下的**真 causal optimum**（动态规划），给 L_future 一个下界。

设定（与总纲 §4.1「最小可发表包」的简化口径一致）
--------------------------------------------------
* 订单按步到达（每天 T 步），每步一个订单；订单类型 `(net, e)` 独立同分布，
  分布取 TRAIN 200 天的经验分布（这是"已知分布、未知实现"的因果设定）；
* 资源只有能量预算 B（不含路线耦合、时间窗）；
* 每步决策：accept（得 net、扣 e）或 reject；预算不可透支。

DP
--
`V_t(b)` = 剩余 t 步、预算 b 时的最大**期望**净价值：

    V_0(b) = 0
    V_{t}(b) = E_type[ max( V_{t-1}(b),  m + V_{t-1}(b - e) ) ]     （e ≤ b）

这是**任何**非预知策略的期望上界（在该简化设定下），因此：

    L_future_true = (OPT_cl_realized − DP_policy_realized) / OPT_cl_realized  ← 用 DP 策略在 GATE 上的实现值

比 D4 v1/v2 的"价格类视角"更接近真值。

用法::

    python scripts/evaluation/run_causal_dp.py --out results/causal_dp/v1
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_SCRIPTS, os.path.join(_SCRIPTS, 'evaluation'), os.path.join(_SCRIPTS, 'admission')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

FROZEN = dict(train_seed=20260925, train_instances=200, gate_seed=20260926,
              gate_instances=40, n_orders=200, budget_B=710.6548328611384, horizon=16.0,
              days=5)


def types_from(days):
    """把 TRAIN 天展平成 (net, e) 的经验分布。"""
    net = np.concatenate([d['net'] for d in days])
    e = np.concatenate([d['e'] for d in days])
    keep = e > 1e-9
    return net[keep], e[keep]


def build_dp(net, e, budget, n_steps, step=0.5):
    """返回 V[t] 数组（t=0..n_steps），b 网格 0..budget。"""
    nb = int(np.floor(budget / step)) + 1
    b_grid = np.arange(nb) * step
    # 离散化：e 向上取整（保守），超出预算的丢弃
    w = np.maximum(np.round(e / step).astype(np.int64), 1)   # 最近邻离散，避免系统性高估能耗
    keep = w < nb
    net, w = net[keep], w[keep]
    V = np.zeros(nb, dtype=np.float64)
    V_list = [V.copy()]
    for _t in range(1, n_steps + 1):
        base = V                                             # (nb,)
        # 对每个类型构造 accept 值矩阵（分块避免内存峰值）
        acc = np.zeros(nb, dtype=np.float64)
        chunk = 256
        for s in range(0, len(net), chunk):
            ww = w[s:s + chunk]
            mm = net[s:s + chunk]
            mat = np.full((len(ww), nb), -np.inf, dtype=np.float64)
            for j, (wj, mj) in enumerate(zip(ww, mm)):
                if wj < nb:
                    mat[j, wj:] = mj + V[:nb - wj]
            acc += np.maximum(mat, base[None, :]).sum(axis=0)
        V = acc / max(len(net), 1)
        V_list.append(V.copy())
    return V_list, b_grid


def eval_dp_policy(day, V_list, budget, step=0.5):
    """按揭示顺序回放 DP 策略；返回 (net, spent)。"""
    order = np.argsort(day['clock'], kind='stable')
    nb = len(V_list[0])
    b = float(budget)
    total = 0.0
    n = len(order)
    for i, idx in enumerate(order):
        t = n - i                                  # 含当前步的剩余步数
        bi = int(min(np.floor(b / step + 1e-9), nb - 1))
        e = float(day['e'][idx])
        m = float(day['net'][idx])
        w = max(int(np.round(e / step)), 1)
        if w <= bi:
            # DP 递推：V_t(b) = E[max(V_{t-1}(b), m + V_{t-1}(b-w))]
            v_rej = V_list[t - 1][bi]
            v_acc = m + V_list[t - 1][bi - w]
            if v_acc >= v_rej:
                b -= e
                total += m
    return float(total), float(budget - b)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--days', type=int, default=FROZEN['days'])
    ap.add_argument('--step', type=float, default=0.25, help='预算离散化步长（kWh）')
    ap.add_argument('--n-steps', type=int, default=200, help='每天决策步数')
    ap.add_argument('--save-v', default=None,
                    help='把 DP 值表 V_t(b) 存成 npz，供全仿真 DPThreshold 使用')
    ap.add_argument('--out', required=True)
    args = ap.parse_args(argv)

    from run_exp_reserve import generate_dataset
    from run_information_price import (clip_bound, integer_knapsack_bound, load_days,
                                       price_rule_net, registered_rule_net)
    from admission.policies import (build_clock_grid, build_lambda_grid, build_train_days,
                                    calibrate)
    OBJECTIVE = dict(ambient_c=25.0, target_c=[18.0, 4.0, -18.0],
                     precool_energy_per_unit_per_c=0.15)

    train = generate_dataset(FROZEN['train_instances'], FROZEN['n_orders'], FROZEN['train_seed'])
    gate = generate_dataset(FROZEN['gate_instances'], FROZEN['n_orders'], FROZEN['gate_seed'])
    train_days = load_days(train)
    gate_days = load_days(gate)[:args.days]
    B = FROZEN['budget_B']

    net_types, e_types = types_from(train_days)
    V_list, b_grid = build_dp(net_types, e_types, B, args.n_steps, args.step)
    dp_expected = float(V_list[args.n_steps][int(np.floor(B / args.step))])

    # 价格规则（标量，TRAIN 选）与登记规则
    lam_star = None
    best = (-1e18, None)
    for lam in np.round(np.arange(0.75, 5.01, 0.25), 6):
        s = float(np.mean([price_rule_net(d, float(lam), B, FROZEN['horizon'])
                           for d in train_days]))
        if s > best[0]:
            best = (s, float(lam))
    lam_star = best[1]
    lam_grid = build_lambda_grid()
    clock_grid = build_clock_grid(FROZEN['horizon'])
    g_table = calibrate(build_train_days(train, OBJECTIVE), OBJECTIVE, FROZEN['horizon'],
                        lam_grid, clock_grid)

    rows = []
    for i, day in enumerate(gate_days):
        dp_net, dp_spent = eval_dp_policy(day, V_list, B, args.step)
        opt_cl = clip_bound(day, B)
        opt_int = integer_knapsack_bound(day, B)
        price_net = price_rule_net(day, lam_star, B, FROZEN['horizon'])
        rule_net = registered_rule_net(day, lam_grid, clock_grid, g_table, B)
        rows.append(dict(day=i, dp_net=dp_net, dp_spent=dp_spent,
                         opt_clairvoyant=opt_cl, opt_int=opt_int,
                         price_star=price_net, rule_registered=rule_net))
    def mean(k):
        return float(np.mean([r[k] for r in rows]))

    L_future_dp = (mean('opt_clairvoyant') - mean('dp_net')) / mean('opt_clairvoyant')
    rule_over_dp = mean('rule_registered') / mean('dp_net')
    price_over_dp = mean('price_star') / mean('dp_net')

    report = dict(stage='causal_dp', version='v3_simplified_single_resource',
                  status='DEVELOPMENT_DIAGNOSTIC',
                  setting=dict(single_resource='energy only', routing_coupling=False,
                               time_windows=False, arrivals='i.i.d. from TRAIN empirical',
                               n_steps=args.n_steps, budget_step=args.step),
                  dp_expected=V_list and dp_expected, budget=B, lambda_star=lam_star,
                  per_day=rows,
                  mean=dict(dp_net=mean('dp_net'), opt_clairvoyant=mean('opt_clairvoyant'),
                            opt_int=mean('opt_int'), price_star=mean('price_star'),
                            rule_registered=mean('rule_registered')),
                  L_future_dp=L_future_dp,
                  rule_over_dp=rule_over_dp, price_over_dp=price_over_dp,
                  verdict=('PRICE_CLASS_ALREADY_NEAR_CAUSAL'
                           if rule_over_dp >= 0.98 else 'CAUSAL_HEADROOM_EXISTS'),
                  limits=('单资源（能耗）、无路线耦合、无时间窗、i.i.d. 到达；'
                          'DP 值是对该简化设定的期望最优，不是原问题最优；'
                          '5 天、单 seed、n=5；离散化步长 %.2f kWh' % args.step))
    if args.save_v:
        V = np.stack(V_list, axis=0)          # (n_steps+1, nb)
        np.savez_compressed(args.save_v, V=V.astype(np.float32),
                            step=float(args.step), budget=float(B),
                            n_steps=int(args.n_steps),
                            n_types=int(len(net_types)))
        print('saved V table -> %s  shape=%s' % (args.save_v, V.shape))

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'causal_dp.json').write_text(json.dumps(report, indent=2, ensure_ascii=False),
                                        encoding='utf-8')

    print('| 量 | 值 |')
    print('|---|---|')
    print('| DP 期望最优（TRAIN 分布） | %.2f |' % dp_expected)
    print('| DP 策略在 GATE 的实现值 | %.2f |' % mean('dp_net'))
    print('| 标量价格 λ*=%.2f（GATE） | %.2f |' % (lam_star, mean('price_star')))
    print('| 登记规则（GATE） | %.2f |' % mean('rule_registered'))
    print('| 分数背包（预知） | %.2f |' % mean('opt_clairvoyant'))
    print('| 整数背包（预知） | %.2f |' % mean('opt_int'))
    print('| **L_future（vs DP 实现值）** | **%.2f%%** |' % (100 * L_future_dp))
    print('| rule / DP | %.3f |' % rule_over_dp)
    print('| price* / DP | %.3f |' % price_over_dp)
    print('| 判定 | **%s** |' % report['verdict'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
