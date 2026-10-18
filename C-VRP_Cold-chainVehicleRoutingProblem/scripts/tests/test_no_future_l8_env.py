#!/usr/bin/env python
"""L8 环境层重放：并列到达组内重排后，环境接受的订单集合（按属性签名）必须不变。

本测试补上 `scripts/tests/test_no_future_l8.py`（只覆盖接拒层）的缺口：
在完整 `StrictOnlineEnv` + `SaaReplanner` 上做两组重放，一组原序、一组把**同一 reveal_time 的
并列订单在数组位置上互换**，随后比较"被接受订单的属性签名多重集"。

为什么用属性签名而不是 order id：重排后 id 会跟着位置走，直接比 id 会恒等；
签名 = (temp_class, round(demand,6), round(x,6), round(y,6), round(reveal_time,6))，
它在重排下不变，因此是正确的不变量。

用法（服务器上，因为需要 calibration 集与 GPU/大内存环境）::

    python scripts/tests/test_no_future_l8_env.py --days 2 --n-orders 60 --burst-rate 0.3
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np

_S = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_S, os.path.join(_S, 'evaluation'), os.path.join(_S, 'coldchain'),
           os.path.join(_S, 'simulation'), os.path.join(_S, 'admission'),
           os.path.join(_S, 'bench')):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _signature(ds, day, o):
    return (int(ds['temp_class'][day, o]),
            round(float(ds['demands'][day, o]), 6),
            round(float(ds['coords'][day, o, 0]), 6),
            round(float(ds['coords'][day, o, 1]), 6),
            round(float(ds['reveal_time'][day, o]), 6))


def _swap_within_ties(ds, day):
    """把同一 reveal_time 的并列订单在数组位置上循环移位一格。"""
    out = {k: np.array(v, copy=True) for k, v in ds.items()}
    rt = out['reveal_time'][day]
    dem = out['demands'][day]
    idx = [o for o in range(1, rt.shape[0]) if dem[o] > 0]
    by_t: dict = {}
    for o in idx:
        by_t.setdefault(round(float(rt[o]), 6), []).append(o)
    n_swapped = 0
    for _, group in by_t.items():
        if len(group) < 2:
            continue
        shift = group[1:] + group[:1]          # 循环移位
        for src, dst in zip(group, shift):
            for k in out:
                out[k][day, dst] = ds[k][day, src]
        n_swapped += len(group)
    return out, n_swapped


_CANON = True    # L8 修法：并列到达按属性规范化排序


def _run_env(ds, days):
    """跑前 days 天，返回每天被接受订单的属性签名集合。"""
    import run_admission_panel as P
    from scenario_saa import ExplicitFeatureSampler, SaaReplanner, build_history
    from strict_online_env import StrictOnlineEnv
    from run_exp_reserve import BOOKING_HORIZON, KM_PER_UNIT, SPEED_KMH

    F = P.FROZEN
    contract = P.make_contract()
    import run_exp_reserve as RR
    from coldchain_evaluator_a1 import add_v2_initial_quality
    train_ds = add_v2_initial_quality(
        RR.generate_dataset(F['train_instances'], F['n_orders'], F['train_seed']), contract)
    hist = build_history(train_ds)
    p_c = {0: 0.0, 1: 0.0, 2: 0.0}
    kw = dict(budget=float(F['budget_B']), capacity=float(F['capacity']),
              booking_horizon=BOOKING_HORIZON, contract=contract,
              cooling_share=float(F['cooling_share']), sampler=ExplicitFeatureSampler(hist),
              reject_penalty=p_c, K=int(F['K']), time_limit=float(F['time_limit']),
              arm_seed=int(F['arm_seed']), shadow_mode='greedy',
              energy_pricing='marginal', future_policy='reveal', standby_orders=None,
              overage_price=None, incr_eval=False)
    accepted = []
    for day in range(int(days)):
        rp = SaaReplanner(**kw)                      # 每天新建，状态干净
        env = StrictOnlineEnv(ds, capacity=float(F['capacity']),
                              num_vehicles=int(F['num_vehicles']),
                              tw_speed=SPEED_KMH / KM_PER_UNIT, replanner=rp,
                              coldchain_contract=contract,
                              booking_horizon=BOOKING_HORIZON,
                              canonical_tie_order=bool(_CANON))
        env.run(day)
        accepted.append(frozenset(_signature(ds, day, int(o)) for o in rp._accepted))
    return accepted


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--days', type=int, default=2)
    ap.add_argument('--n-orders', type=int, default=60)
    ap.add_argument('--burst-rate', type=float, default=0.3)
    args = ap.parse_args(argv)

    import cc_dvrp3t_gen as G
    import bench_to_a1 as A
    from coldchain_contract import ColdChainContractV2

    G.BURST_RATE = float(args.burst_rate)
    G.BURST_SLOT = 0.25
    bench, _meta = G.build('R1', int(args.n_orders), 1, 20261018)
    # 复制成 args.days 天（内容相同即可：本测试只关心顺序不变性，不关心跨天差异）
    bench = {k: np.repeat(v, int(args.days), axis=0) for k, v in bench.items()}
    ds = A.add_initial_quality(A.to_a1(bench), ColdChainContractV2())

    perm, n_swapped = _swap_within_ties(ds, day=0)
    print('days=%d orders=%d  swapped_slots_in_day0=%d'
          % (ds['coords'].shape[0], int((ds['demands'] > 0).sum()), n_swapped))

    base = _run_env(ds, args.days)
    other = _run_env(perm, args.days)
    bad = [(d, len(base[d]), len(other[d])) for d in range(int(args.days)) if base[d] != other[d]]
    print('accepted sizes base :', [len(x) for x in base])
    print('accepted sizes perm :', [len(x) for x in other])
    print('days with differing accepted set:', bad)
    disc = all(0 < len(x) < int((ds['demands'][0] > 0).sum()) for x in base)
    print('discriminating:', disc)
    ok = (not bad) and disc
    print('verdict:', 'PASS_ENV_LAYER_ORDER_INVARIANT' if ok else
          ('VACUOUS' if not bad else 'FAIL_ORDER_DEPENDENT'))
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
