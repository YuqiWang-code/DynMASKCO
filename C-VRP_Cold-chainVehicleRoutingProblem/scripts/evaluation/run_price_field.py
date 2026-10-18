"""温区影子价格场（λ_k）最小检验：接拒层，PF-1。

预登记：`docs/04_实施与结果/2026-10-18_预登记_PF1_温区价格场.md`

做法
----
* 单标量价格（D4 v2 的 λ\\*）vs **每温区一个价格** λ_k（3 个参数）；
* 仅用 TRAIN 200 天做坐标上升选参，GATE 5 天只评估一次；
* 口径与 D4 一致：`net = REV − 燃油 − 品质`（depot 绕行估计），接受规则 `net − λ_k·e > 0` + 预算硬闸。

判据：`mean_net(λ_k)/mean_net(λ*) − 1 ≥ 1%` ⇒ PASS，否则 DOMINATED。

用法::

    python scripts/evaluation/run_price_field.py --out results/price_field/pf1
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
GRID = np.round(np.arange(0.75, 5.0 + 1e-9, 0.25), 6)


def load_days(dataset):
    from run_information_price import load_days as _ld
    return _ld(dataset)


def zones_for(dataset):
    """每个订单的空间区（2x2 网格：0..3），顺序与 load_days 一致。"""
    coords = np.asarray(dataset['coords'], dtype=np.float64)
    dem = np.asarray(dataset['demands'], dtype=np.float64)
    rev = np.asarray(dataset['reveal_time'], dtype=np.float64)
    out = []
    for d in range(dem.shape[0]):
        idx = np.where(dem[d] > 0)[0]
        idx = idx[np.argsort(rev[d][idx], kind='stable')]
        xy = coords[d, idx]
        z = (xy[:, 0] >= 0.5).astype(np.int64) + 2 * (xy[:, 1] >= 0.5).astype(np.int64)
        out.append(z)
    return out


def replay_day_zone(day, zone, lam_field, budget):
    """lam_field: (3, 4) [class, zone]；按揭示顺序回放。"""
    order = np.argsort(day['clock'], kind='stable')
    rem, total = float(budget), 0.0
    for i in order:
        k = int(day['cls'][i])
        lam = float(lam_field[k, int(zone[i])])
        if day['e'][i] <= rem + 1e-9 and (day['net'][i] - lam * day['e'][i]) > 0.0:
            rem -= day['e'][i]
            total += day['net'][i]
    return float(total)


def mean_zone(days, zones, lam_field, budget):
    return float(np.mean([replay_day_zone(d, z, lam_field, budget)
                          for d, z in zip(days, zones)]))


def replay_day(day, lam_by_class, budget):
    """按揭示顺序回放；lam_by_class: (3,) 每温区价格。返回 (net, spent, accepted_by_class)。"""
    order = np.argsort(day['clock'], kind='stable')
    rem, total = float(budget), 0.0
    acc = np.zeros(3, dtype=np.int64)
    for i in order:
        k = int(day['cls'][i])
        lam = float(lam_by_class[k])
        if day['e'][i] <= rem + 1e-9 and (day['net'][i] - lam * day['e'][i]) > 0.0:
            rem -= day['e'][i]
            total += day['net'][i]
            acc[k] += 1
    return float(total), float(budget - rem), acc


def mean_on(days, lam_by_class, budget):
    return float(np.mean([replay_day(d, lam_by_class, budget)[0] for d in days]))


def scalar_best(train_days, budget):
    scores = [(mean_on(train_days, np.full(3, float(lam)), budget), float(lam)) for lam in GRID]
    scores.sort(key=lambda x: -x[0])
    return scores[0][1], scores[0][0]


def coordinate_ascent(train_days, budget, start_lams, grid, passes=2):
    lam = np.asarray(start_lams, dtype=np.float64).copy()
    path = []
    for _ in range(passes):
        for k in range(3):
            best = (mean_on(train_days, lam, budget), float(lam[k]))
            for g in grid:
                trial = lam.copy()
                trial[k] = float(g)
                s = mean_on(train_days, trial, budget)
                if s > best[0]:
                    best = (s, float(g))
            lam[k] = best[1]
            path.append(dict(class_id=k, lam=float(lam[k]), train_score=float(best[0])))
    return lam, float(mean_on(train_days, lam, budget)), path


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--days', type=int, default=FROZEN['days'])
    ap.add_argument('--budget', type=float, default=FROZEN['budget_B'])
    ap.add_argument('--grid-max', type=float, default=5.0)
    ap.add_argument('--spatial', action='store_true',
                    help='额外检验 (温区 × 2x2 空间区) 的价格场（12 个参数）')
    ap.add_argument('--out', required=True)
    args = ap.parse_args(argv)

    from run_exp_reserve import generate_dataset
    train = generate_dataset(FROZEN['train_instances'], FROZEN['n_orders'], FROZEN['train_seed'])
    gate = generate_dataset(FROZEN['gate_instances'], FROZEN['n_orders'], FROZEN['gate_seed'])
    train_days = load_days(train)
    gate_days = load_days(gate)[:args.days]
    B = float(args.budget)
    grid = np.round(np.arange(0.75, args.grid_max + 1e-9, 0.25), 6)

    # 1) 标量最优（TRAIN）
    lam_star, train_scalar = scalar_best(train_days, B)
    scalar_gate = [replay_day(d, np.full(3, lam_star), B) for d in gate_days]
    scalar_mean = float(np.mean([x[0] for x in scalar_gate]))

    # 2) 温区价格场（TRAIN 坐标上升）
    lams, train_field, path = coordinate_ascent(train_days, B, np.full(3, lam_star), grid)
    field_gate = [replay_day(d, lams, B) for d in gate_days]
    field_mean = float(np.mean([x[0] for x in field_gate]))

    # 3) 事后最优（GATE，仅参考，不进判据）
    hindsight = []
    for k in range(3):
        best = (-1e18, lam_star)
        for g in grid:
            trial = lams.copy()
            trial[k] = float(g)
            s = float(np.mean([replay_day(d, trial, B)[0] for d in gate_days]))
            if s > best[0]:
                best = (s, float(g))
        hindsight.append(best)

    gain = field_mean / scalar_mean - 1.0

    spatial = None
    if args.spatial:
        train_z = zones_for(train)
        gate_z = zones_for(gate)[:args.days]
        lam2 = np.repeat(lams[:, None], 4, axis=1)          # 从 (class) 解出发
        best_score = mean_zone(train_days, train_z, lam2, B)
        for _ in range(2):
            for k in range(3):
                for zz in range(4):
                    cur = best_score
                    cur_val = float(lam2[k, zz])
                    for g in grid:
                        trial = lam2.copy()
                        trial[k, zz] = float(g)
                        s = mean_zone(train_days, train_z, trial, B)
                        if s > cur + 1e-9:
                            cur, cur_val = s, float(g)
                    lam2[k, zz] = cur_val
                    best_score = cur
        spatial_gate = float(np.mean([replay_day_zone(d, z, lam2, B)
                                      for d, z in zip(gate_days, gate_z)]))
        spatial = dict(lambdas=[[float(x) for x in row] for row in lam2],
                       train_mean=float(best_score), gate_mean=spatial_gate,
                       gain_vs_scalar=spatial_gate / scalar_mean - 1.0)
    at_bound = int(np.sum((lams <= grid[0] + 1e-9) | (lams >= grid[-1] - 1e-9)))
    if at_bound >= 2:
        verdict = 'MECHANISM_NULL'
    elif gain >= 0.01:
        verdict = 'PASS'
    else:
        verdict = 'DOMINATED'

    report = dict(stage='price_field_pf1', status='PREREGISTERED_PF1',
                  config=dict(days=args.days, budget=B, grid=list(grid),
                              horizon=FROZEN['horizon'], train_days=len(train_days)),
                  scalar=dict(lam_star=lam_star, train_mean=train_scalar,
                              gate_mean=scalar_mean,
                              gate_per_day=[round(x[0], 2) for x in scalar_gate]),
                  field=dict(lambdas=[float(x) for x in lams], train_mean=train_field,
                             gate_mean=field_mean,
                             gate_per_day=[round(x[0], 2) for x in field_gate],
                             accepted_by_class=[list(map(int, x[2])) for x in field_gate]),
                  coordinate_path=path,
                  hindsight_gate=[dict(class_id=i, lam=v[1], gate_score=round(v[0], 2))
                                  for i, v in enumerate(hindsight)],
                  gain=gain, n_at_bound=at_bound, verdict=verdict,
                  spatial=spatial,
                  criterion=dict(threshold=0.01, at_bound_rule=2),
                  limits=('接拒层净价值（depot 绕行估计燃油/品质），不含路线耦合与 TW；'
                          'TRAIN 上坐标上升、GATE 只评估一次；5 天、单 seed、n=5'))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'price_field.json').write_text(json.dumps(report, indent=2, ensure_ascii=False),
                                          encoding='utf-8')

    print('| 量 | 值 |')
    print('|---|---|')
    print('| 标量 λ* (TRAIN) | %.3f |' % lam_star)
    print('| GATE 净价值（标量） | %.2f |' % scalar_mean)
    print('| 温区价格 λ_k (TRAIN) | [%.3f, %.3f, %.3f] |' % tuple(lams))
    print('| GATE 净价值（λ_k） | %.2f |' % field_mean)
    print('| 增益 | **%+.2f%%** |' % (100 * gain))
    print('| 触边参数个数 | %d |' % at_bound)
    print('| 判定 | **%s** |' % verdict)
    if spatial is not None:
        print()
        print('| 空间×温区价格场 | 值 |')
        print('|---|---|')
        print('| GATE 净价值（12 参数） | %.2f |' % spatial['gate_mean'])
        print('| 相对标量增益 | **%+.2f%%** |' % (100 * spatial['gain_vs_scalar']))
        print('| λ 场 | %s |' % [[round(x, 2) for x in row] for row in spatial['lambdas']])
    print('\n事后最优（GATE，仅参考）: %s'
          % [(i, round(v[1], 2), round(v[0], 1)) for i, v in enumerate(hindsight)])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
