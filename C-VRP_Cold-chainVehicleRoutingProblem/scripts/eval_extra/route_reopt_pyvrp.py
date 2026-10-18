"""用 PyVRP 对**同一天同一个服务集合**做离线重优化，给出路线质量的**预知上界**。

要回答的问题
------------
十天面板：控制 1846 收入 / 493.2 km，静态 λ 1868 收入 / 521.8 km。
要跨 G4（+1.5% ⇒ ≥1823.6）需在 1868 收入下把里程压到 ≤499.7 km（**再省 22.1 km / −4.2%**）。

本脚本取控制臂**实际服务的那批订单**（由 `MASKCO_DUMP_SERVED=1` 从面板导出），
用 PyVRP 在"假设这些订单从一开始就全部已知"的条件下重新排路线，得到：

* `saa_km`：SAA 实际跑出的里程（含在线约束）；
* `reopt_km`：PyVRP 对同一集合的**预知**重优化里程（15 车、容量 50、时间窗=tw_end、服务 0.05 h）；
* 差值即"路线质量的预知上界"，以及它折算的效用 `0.1 × (saa_km − reopt_km)`。

**这是上界，不是可达收益**：真实在线下订单是分批揭示、车辆中途派出，PyVRP 拿不到这种自由。

用法::

    python route_reopt_pyvrp.py --panel results/admission_panel/dump_control --out /tmp/reopt.json
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

import numpy as np

_S = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_S, os.path.join(_S, 'evaluation'), os.path.join(_S, 'coldchain'),
           os.path.join(_S, 'simulation'), os.path.join(_S, 'admission')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

CAPACITY = 50
N_VEH = 15
SERVICE_H = 0.05
SPEED_KMH = 30.0
KM_PER_UNIT = 20.0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--panel', required=True, help='含 served_ids 的面板输出目录')
    ap.add_argument('--day', type=int, default=0)
    ap.add_argument('--runtime', type=float, default=10.0)
    ap.add_argument('--out', default='/tmp/reopt.json')
    args = ap.parse_args(argv)

    import run_admission_panel as P
    import run_exp_reserve as RR
    from coldchain_evaluator_a1 import add_v2_initial_quality
    from pyvrp import Model
    from pyvrp.stop import MaxRuntime

    d = json.load(open(os.path.join(args.panel, 'panel.json'), encoding='utf-8'))
    row = d['per_day'][int(args.day)]
    arm = [k for k in row if k != 'day'][0]
    rec = row[arm]
    ids = rec.get('served_ids')
    if not ids:
        print('面板里没有 served_ids；请用 MASKCO_DUMP_SERVED=1 重跑该面板')
        return 2
    saa_km = float(rec['distance_km'])
    print('arm=%s day=%d served=%d saa_km=%.2f' % (arm, args.day, len(ids), saa_km), flush=True)

    F = P.FROZEN
    contract = P.make_contract()
    gate = add_v2_initial_quality(
        RR.generate_dataset(F['gate_instances'], F['n_orders'], F['gate_seed']), contract)
    xy = np.asarray(gate['coords'][args.day], dtype=np.float64)
    dem = np.asarray(gate['demands'][args.day], dtype=np.float64)
    tw = np.asarray(gate['tw_end'][args.day], dtype=np.float64)

    sc = 100
    m = Model()
    depot = m.add_depot(x=0.0, y=0.0)
    m.add_vehicle_type(num_available=N_VEH, capacity=[CAPACITY * sc])
    clients = {}
    for o in ids:
        clients[o] = m.add_client(x=float(xy[o][0] * sc), y=float(xy[o][1] * sc),
                                 delivery=int(round(dem[o] * sc)),
                                 service_duration=int(round(SERVICE_H * 3600)),
                                 tw_early=0, tw_late=int(round(tw[o] * 3600)))
    locs = [(0, depot)] + [(o, clients[o]) for o in ids]
    for i, (oi, li) in enumerate(locs):
        for j, (oj, lj) in enumerate(locs):
            if i == j:
                continue
            p = xy[0] if oi == 0 else xy[oi]
            q = xy[0] if oj == 0 else xy[oj]
            km = math.hypot(p[0] - q[0], p[1] - q[1]) * KM_PER_UNIT
            m.add_edge(li, lj, distance=int(round(km)), duration=int(round(km / SPEED_KMH * 3600)))
    res = m.solve(stop=MaxRuntime(float(args.runtime)), seed=0, display=False)
    best = res.best
    if best is None:
        print('PyVRP 未找到解')
        return 3
    served = int(sum(len(r) for r in best.routes()))
    reopt_km = float(best.distance()) / sc
    delta_km = saa_km - reopt_km
    out = dict(arm=arm, day=int(args.day), n_orders=int(len(ids)),
               saa_km=saa_km, reopt_km=reopt_km, delta_km=delta_km,
               delta_pct=100.0 * delta_km / saa_km,
               utility_headroom=0.1 * delta_km,
               reopt_feasible=bool(res.is_feasible()), reopt_served=served,
               note=('预知重优化的**上界**：假设全部订单从 0 时刻已知、车辆可任意整队。'
                     '真实在线分批揭示，拿不到这种自由。'))
    print(json.dumps(out, indent=2, ensure_ascii=False), flush=True)
    with open(args.out, 'w', encoding='utf-8') as fh:
        json.dump(out, fh, indent=2, ensure_ascii=False)
    return 0


if __name__ == '__main__':
    sys.exit(main())
