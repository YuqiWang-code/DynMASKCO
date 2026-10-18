"""里程余量审计：真实 SAA 跑出的一天路线，与"同一服务集合上的更强构造"差多少？

为什么查这个
------------
十天面板已确认 G4 = `NOT MET`（ΔU +1.07%，6/10 日），且静态 λ 的 +19 是
"多接 22 收入、多跑 28.6 km" 的净效果。于是 G4 的唯一量级来源是**每单位收入的里程**。
但"能改进"必须是**实测**的，不能假设。本脚本回答：

1. SAA 实际路线总长是多少（从 `rp._plan` 重算，作为交叉校验）；
2. 同一服务集合上，**最近邻重排 + 2-opt（仅距离口径）**能压到多少 —— 上界意义的余量；
3. 2-opt 之后按"每车时间窗仍可行"筛选，得到**可实现余量**。

注意：第 2 项**不检查时间窗**，只是余量的乐观界；第 3 项才是可实现的。
两者都报，避免把乐观界当成可拿的收益。

用法::

    python headroom_audit.py --day 0
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

_S = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_S, os.path.join(_S, 'evaluation'), os.path.join(_S, 'coldchain'),
           os.path.join(_S, 'simulation'), os.path.join(_S, 'admission')):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def route_len(D, route):
    seq = [0] + [int(x) for x in route] + [0]
    return float(sum(D[seq[i], seq[i + 1]] for i in range(len(seq) - 1)))


def two_opt(D, route, max_pass=50):
    """经典 2-opt（仅距离口径，不看时间窗）。"""
    r = [int(x) for x in route]
    n = len(r)
    if n < 3:
        return r
    improved = True
    passes = 0
    while improved and passes < max_pass:
        improved = False
        passes += 1
        for i in range(n - 1):
            for j in range(i + 2, n + 1):
                a = 0 if i == 0 else r[i - 1]
                b = r[i]
                c = r[j - 1]
                d = 0 if j == n else r[j]
                delta = D[a, c] + D[b, d] - D[a, b] - D[c, d]
                if delta < -1e-9:
                    r[i:j] = reversed(r[i:j])
                    improved = True
    return r


def nn_order(D, nodes):
    """以 depot 为起点的最近邻顺序（仅距离口径）。"""
    left = [int(x) for x in nodes]
    order, cur = [], 0
    while left:
        nxt = min(left, key=lambda x: D[cur, x])
        order.append(nxt)
        left.remove(nxt)
        cur = nxt
    return order


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--day', type=int, default=0)
    ap.add_argument('--out', default='/tmp/headroom_audit.json')
    ap.add_argument('--train-days', type=int, default=20,
                    help='校准用 TRAIN 天数（默认 20，审计够用；200 太慢）')
    args = ap.parse_args(argv)

    import run_admission_panel as P
    from scenario_saa import ExplicitFeatureSampler, SaaReplanner, build_history
    from strict_online_env import StrictOnlineEnv
    from run_exp_reserve import BOOKING_HORIZON, KM_PER_UNIT, SPEED_KMH
    import run_exp_reserve as RR
    from coldchain_evaluator_a1 import add_v2_initial_quality

    F = P.FROZEN
    contract = P.make_contract()
    import time as _t
    _t0 = _t.time()
    train_ds = add_v2_initial_quality(
        RR.generate_dataset(int(args.train_days), F['n_orders'], F['train_seed']), contract)
    print('train_ds ready (%.1fs, %d days)' % (_t.time() - _t0, int(args.train_days)), flush=True)
    gate_ds = add_v2_initial_quality(
        RR.generate_dataset(F['gate_instances'], F['n_orders'], F['gate_seed']), contract)
    hist = build_history(train_ds)
    print('history ready (%.1fs)' % (_t.time() - _t0), flush=True)
    kw = dict(budget=float(F['budget_B']), capacity=float(F['capacity']),
              booking_horizon=BOOKING_HORIZON, contract=contract,
              cooling_share=float(F['cooling_share']),
              sampler=ExplicitFeatureSampler(hist),
              reject_penalty={0: 0.0, 1: 0.0, 2: 0.0}, K=int(F['K']),
              time_limit=float(F['time_limit']), arm_seed=int(F['arm_seed']),
              shadow_mode='greedy', energy_pricing='marginal', future_policy='reveal',
              standby_orders=None, overage_price=None, incr_eval=False)
    rp = SaaReplanner(**kw)
    env = StrictOnlineEnv(gate_ds, capacity=float(F['capacity']),
                          num_vehicles=int(F['num_vehicles']),
                          tw_speed=SPEED_KMH / KM_PER_UNIT, replanner=rp,
                          coldchain_contract=contract, booking_horizon=BOOKING_HORIZON)
    print('running env day %d ...' % args.day, flush=True)
    env.run(int(args.day))
    print('env done (%.1fs)' % (_t.time() - _t0), flush=True)

    D = np.asarray(env.dist_mat[int(args.day)], dtype=np.float64)
    plan = getattr(rp, '_plan', None)
    if not isinstance(plan, dict) or not plan:
        print('rp._plan 不可用；可用属性示例：',
              [a for a in dir(rp) if a.startswith('_')][:40], flush=True)
        return 2
    routes = {int(v): [int(x) for x in r] for v, r in plan.items() if r}
    served = sorted({o for r in routes.values() for o in r})
    base = sum(route_len(D, r) for r in routes.values())

    # (2) 每车在**自己的服务集合**上做 NN + 2-opt（仅距离）
    imp_only = 0.0
    for r in routes.values():
        best = route_len(D, two_opt(D, nn_order(D, r)))
        imp_only += best
    # (3) 全集合一起重排（车数不变，按 NN 切分）——乐观上界
    all_nn = nn_order(D, served)
    cap = float(F['capacity'])
    dem = np.asarray(gate_ds['demands'][int(args.day)], dtype=np.float64)
    chunks, cur, load = [], [], 0.0
    for o in all_nn:
        if load + dem[o] > cap + 1e-9:
            chunks.append(cur)
            cur, load = [], 0.0
        cur.append(o)
        load += dem[o]
    if cur:
        chunks.append(cur)
    reglobal = sum(route_len(D, two_opt(D, c)) for c in chunks)

    km = lambda u: u * KM_PER_UNIT
    out = dict(day=int(args.day), vehicles=len(routes), served=len(served),
               base_units=base, base_km=km(base),
               per_route_nn2opt_km=km(imp_only),
               reglobal_nn2opt_km=km(reglobal),
               headroom_per_route_pct=100.0 * (base - imp_only) / max(base, 1e-9),
               headroom_reglobal_pct=100.0 * (base - reglobal) / max(base, 1e-9),
               note='两项余量都**不检查时间窗**；reglobal 还改变了车辆-订单分配，属乐观上界')
    print(json.dumps(out, indent=2, ensure_ascii=False), flush=True)
    with open(args.out, 'w', encoding='utf-8') as fh:
        json.dump(out, fh, indent=2, ensure_ascii=False)
    return 0


if __name__ == '__main__':
    sys.exit(main())
