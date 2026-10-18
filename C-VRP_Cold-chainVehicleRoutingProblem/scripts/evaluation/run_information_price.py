"""信息价格分解（总纲 D4 第一版）：在**接拒层**把余量拆成「未来信息」与「规则空间」。

三个量（同一批冻结日、同一成本口径）：

* `OPT_cl`：**完全预知**下的分数背包上界（clairvoyant，允许切分订单）；
* `OPT_price*`：**价格规则类**内的最优 —— 在 TRAIN 上网格搜索一个固定价格 λ*（非预知），
  把它用到 GATE 天；
* `Rule_now`：登记静态规则（λ 随 clock 变化，来自 TRAIN 校准表）。

两个分解量（**类内**定义，务必按此引用）：

    L_future_price = (OPT_cl − OPT_price*) / OPT_cl      # 预知能拿到、价格类拿不到的部分
    L_rule_price   = (OPT_price* − Rule_now) / OPT_price*  # 价格类内，当前规则还差多少

> **这不是**全空间的信息价格：`OPT_price*` 只是价格规则类的上界（一个受限 causal optimum），
> 所以 `L_future_price` 是"未来信息占比"的一个**偏大**估计，`L_rule_price` 是"当前规则可改进空间"的
> 一个**偏保守**估计。真·causal optimum 需要动态规划/集合级 oracle，留待 D4 第二版。

用法（从扩展根目录）::

    python scripts/evaluation/run_information_price.py --out results/info_price/v1
"""
from __future__ import annotations

import argparse
import json
import math
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
OBJECTIVE = dict(ambient_c=25.0, target_c=[18.0, 4.0, -18.0],
                 precool_energy_per_unit_per_c=0.15)


# --------------------------------------------------------------------------
# 与 v2 / 反演一致的净价值口径
# --------------------------------------------------------------------------
def load_days(dataset, fuel_weight=1.0, quality_weight=1.0):
    from admission.policies import REV, e_lower_of
    from run_exp_reserve import FUEL_COST_PER_KM, KM_PER_UNIT, K_EFF, PVAL, SPEED_KMH

    dem = np.asarray(dataset['demands'], dtype=np.float64)
    rev_t = np.asarray(dataset['reveal_time'], dtype=np.float64)
    cls_t = np.asarray(dataset['temp_class'], dtype=np.int64)
    coords = np.asarray(dataset['coords'], dtype=np.float64)
    days = []
    for d in range(dem.shape[0]):
        idx = np.where(dem[d] > 0)[0]
        idx = idx[np.argsort(rev_t[d][idx], kind='stable')]
        cls = cls_t[d, idx]
        q = dem[d, idx]
        e = np.asarray([e_lower_of(int(c), float(qq), OBJECTIVE) for c, qq in zip(cls, q)])
        rev = np.asarray([REV[int(c)] for c in cls], dtype=np.float64)
        detour = 2.0 * np.linalg.norm(coords[d, idx] - coords[d, 0], axis=-1)
        fuel = FUEL_COST_PER_KM * detour * KM_PER_UNIT
        dwell = 2.0 * detour / (SPEED_KMH / KM_PER_UNIT)
        quality = np.asarray([PVAL[int(c)] * float(qq) * (1.0 - math.exp(-K_EFF[int(c)] * dh))
                              for c, qq, dh in zip(cls, q, dwell)])
        days.append(dict(clock=rev_t[d, idx], cls=cls, q=q, e=e, rev=rev,
                         net=rev - fuel_weight * fuel - quality_weight * quality))
    return days


def clip_bound(day, budget):
    """分数背包：按 net/e 降序装满预算（允许切分）。"""
    net, e = day['net'], day['e']
    order = np.argsort(-(net / np.maximum(e, 1e-12)), kind='stable')
    rem, total = float(budget), 0.0
    for i in order:
        if e[i] <= rem + 1e-12:
            rem -= e[i]
            total += net[i]
        else:
            total += net[i] * (rem / e[i]) if e[i] > 0 else 0.0
            break
    return float(total)


def price_rule_net(day, lam, budget, horizon):
    """固定价格 λ（与 clock 无关）的净价值。"""
    order = np.argsort(day['clock'], kind='stable')
    rem, total = float(budget), 0.0
    for i in order:
        if day['e'][i] <= rem + 1e-9 and (day['net'][i] - lam * day['e'][i]) > 0.0:
            rem -= day['e'][i]
            total += day['net'][i]
    return float(total)


def registered_rule_net(day, lam_grid, clock_grid, g_table, budget):
    """登记静态规则（λ 随 clock）；返回逐日净价值。"""
    from admission.controller import AdmissionController, OrderView
    from admission.policies import RegisteredShadowPrice
    pol = RegisteredShadowPrice(lam_grid, clock_grid, g_table)
    ctrl = AdmissionController(pol, budget=budget)
    ctrl.begin_day([], horizon=FROZEN['horizon'])
    for i in range(len(day['clock'])):
        view = OrderView.build(i, int(day['cls'][i]), float(day['q'][i]), float(day['e'][i]),
                               reveal_time=float(day['clock'][i]), revenue=float(day['net'][i]))
        ctrl.decide(view, float(day['clock'][i]))
    return float(ctrl.state.accepted_revenue)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--days', type=int, default=FROZEN['days'])
    ap.add_argument('--out', required=True)
    args = ap.parse_args(argv)

    from run_exp_reserve import generate_dataset
    from admission.policies import (build_clock_grid, build_lambda_grid, build_train_days,
                                    calibrate)

    train = generate_dataset(FROZEN['train_instances'], FROZEN['n_orders'], FROZEN['train_seed'])
    gate = generate_dataset(FROZEN['gate_instances'], FROZEN['n_orders'], FROZEN['gate_seed'])
    B = FROZEN['budget_B']
    train_days = load_days(train)
    gate_days = load_days(gate)[:args.days]

    # 1) 价格类最优：在 TRAIN 上选 λ*（最大化 TRAIN 平均净价值），再用于 GATE
    grid = np.round(np.arange(0.25, 8.0 + 1e-9, 0.125), 6)
    train_scores = [float(np.mean([price_rule_net(d, float(lam), B, FROZEN['horizon'])
                                   for d in train_days])) for lam in grid]
    best_idx = int(np.argmax(train_scores))
    lam_star = float(grid[best_idx])
    # 事后最优（只在 GATE 上，作参考上界，不进公式）
    gate_scores = [float(np.mean([price_rule_net(d, float(lam), B, FROZEN['horizon'])
                                  for d in gate_days])) for lam in grid]
    lam_star_hindsight = float(grid[int(np.argmax(gate_scores))])

    # 2) 登记规则
    lam_grid = build_lambda_grid()
    clock_grid = build_clock_grid(FROZEN['horizon'])
    g_table = calibrate(build_train_days(train, OBJECTIVE), OBJECTIVE, FROZEN['horizon'],
                        lam_grid, clock_grid)

    rows = []
    for i, day in enumerate(gate_days):
        opt_cl = clip_bound(day, B)
        opt_price = price_rule_net(day, lam_star, B, FROZEN['horizon'])
        opt_price_h = price_rule_net(day, lam_star_hindsight, B, FROZEN['horizon'])
        rule = registered_rule_net(day, lam_grid, clock_grid, g_table, B)
        rows.append(dict(day=i, opt_clairvoyant=opt_cl, opt_price_star=opt_price,
                         opt_price_hindsight=opt_price_h, rule_registered=rule,
                         L_future_price=(opt_cl - opt_price) / opt_cl if opt_cl else None,
                         L_rule_price=(opt_price - rule) / opt_price if opt_price else None,
                         rule_over_price=rule / opt_price if opt_price else None))

    def mean(k):
        vals = [r[k] for r in rows if r[k] is not None]
        return float(np.mean(vals)) if vals else None

    report = dict(stage='information_price_d1', version='v1_admission_layer',
                  status='DEVELOPMENT_DIAGNOSTIC',
                  definition=dict(
                      opt_clairvoyant='fractional knapsack over the whole day (perfect foresight)',
                      opt_price_star='best clock-independent price lambda chosen on TRAIN, applied to GATE',
                      rule_registered='registered static shadow price (lambda varies with clock)',
                      L_future_price='(OPT_cl - OPT_price*)/OPT_cl  (upper-bounded reading)',
                      L_rule_price='(OPT_price* - Rule)/OPT_price*  (within the price class)'),
                  config=dict(days=args.days, budget=B, lambda_star=lam_star,
                              lambda_star_hindsight=lam_star_hindsight,
                              train_lambda_scores_head=train_scores[:5],
                              grid_step=0.125),
                  per_day=rows,
                  mean=dict(opt_clairvoyant=mean('opt_clairvoyant'),
                            opt_price_star=mean('opt_price_star'),
                            opt_price_hindsight=mean('opt_price_hindsight'),
                            rule_registered=mean('rule_registered'),
                            L_future_price=mean('L_future_price'),
                            L_rule_price=mean('L_rule_price'),
                            rule_over_price=mean('rule_over_price')),
                  limits=('只用接拒层净价值（depot 绕行估计的燃油/品质），不含真实路线耦合与 TW；'
                          'OPT_price* 只是价格规则类的上界，不是全空间 causal optimum；'
                          '5 天、单 seed、n=5，不做显著性'))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'info_price.json').write_text(json.dumps(report, indent=2, ensure_ascii=False),
                                         encoding='utf-8')

    m = report['mean']
    print('| 量 | 值 |')
    print('|---|---|')
    for k in ('opt_clairvoyant', 'opt_price_star', 'opt_price_hindsight', 'rule_registered'):
        print('| %s | %.2f |' % (k, m[k]))
    print('| **L_future_price** | **%.2f%%** |' % (100 * m['L_future_price']))
    print('| **L_rule_price** | **%.2f%%** |' % (100 * m['L_rule_price']))
    print('| rule/price* | %.3f |' % m['rule_over_price'])
    print('\nlambda* (TRAIN) = %.3f ; lambda_hindsight (GATE) = %.3f'
          % (lam_star, lam_star_hindsight))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
