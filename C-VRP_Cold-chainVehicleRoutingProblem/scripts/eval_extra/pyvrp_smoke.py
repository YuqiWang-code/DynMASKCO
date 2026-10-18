"""PyVRP 冒烟：确认本机 0.11.3 能构造带时间窗的实例并求解。

G2 基线半边需要外部非学习强基线（PyVRP / OR-Tools / HGS）以 **replanner 适配器** 形式
进入严格在线协议；适配器的第一块砖是"给定静态 VRPTW，解出路线"。本脚本只验证这块砖。

用法::

    python pyvrp_smoke.py
"""
from __future__ import annotations

import math
import sys


def build_solve(n_orders=12, n_vehicles=3, capacity=50, seed=0, runtime_s=2.0):
    import numpy as np
    from pyvrp import Model
    from pyvrp.stop import MaxRuntime

    rng = np.random.default_rng(seed)
    coords = [(0.0, 0.0)] + [tuple(rng.uniform(0, 100, size=2)) for _ in range(n_orders)]
    demands = [0] + [int(rng.integers(1, 4)) for _ in range(n_orders)]
    tw_late = [0] + [int(rng.uniform(4.0, 12.0)) for _ in range(n_orders)]

    m = Model()
    depot = m.add_depot(x=0.0, y=0.0)
    m.add_vehicle_type(num_available=int(n_vehicles), capacity=[int(capacity)])
    clients = []
    for i in range(1, n_orders + 1):
        clients.append(m.add_client(
            x=float(coords[i][0]), y=float(coords[i][1]),
            delivery=int(demands[i]),
            service_duration=int(round(0.05 * 3600)),
            tw_early=0,
            tw_late=int(tw_late[i] * 3600)))
    locs = [depot] + clients
    for i, li in enumerate(locs):
        for j, lj in enumerate(locs):
            if i == j:
                continue
            km = math.hypot(coords[i][0] - coords[j][0], coords[i][1] - coords[j][1])
            m.add_edge(li, lj, distance=int(round(km)),
                       duration=int(round(km / 30.0 * 3600)))
    res = m.solve(stop=MaxRuntime(float(runtime_s)), seed=int(seed), display=False)
    best = res.best
    if best is None:
        return dict(feasible=False, cost=None, n_routes=0, served=0, n_clients=n_orders)
    return dict(feasible=bool(res.is_feasible()),
                cost=float(best.distance()),
                n_routes=int(len([r for r in best.routes() if len(r) > 0])),
                served=int(sum(len(r) for r in best.routes())),
                n_clients=int(n_orders))


def main() -> int:
    try:
        import importlib.metadata as md
        import pyvrp  # noqa: F401
        try:
            ver = md.version('pyvrp')
        except Exception:  # noqa: BLE001
            ver = getattr(pyvrp, 'version', 'unknown')
        print('pyvrp', ver, flush=True)
    except Exception as exc:  # noqa: BLE001
        print('pyvrp import failed: %r' % (exc,))
        return 1
    try:
        out = build_solve()
        print('smoke:', out, flush=True)
        ok = bool(out['feasible']) and out['served'] == out['n_clients']
        print('PYVRP_SMOKE_OK' if ok else 'PYVRP_SMOKE_PARTIAL')
        return 0 if ok else 2
    except Exception as exc:  # noqa: BLE001
        print('build/solve failed: %r' % (exc,))
        return 3


if __name__ == '__main__':
    sys.exit(main())
