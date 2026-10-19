"""诊断（第 99 轮）：闭环里"每辆车一天跑几趟、每趟几单"——路线构造器到底有没有空间。

背景
----
G4 唯一还没被否掉的方向是"路线构造"。要判断它有没有空间，必须先回答一个纯观测问题：

* 现在的闭环规划器到底是不是**一单一趟**（每次派车只取一单就回仓）？
* 若是，则"同温区多单拼一趟"能直接压里程（里程系数 0.1 元/km，里程占比 ~2.8% 效用）；
* 若不是（已经是多单拼趟），则里程由半径决定，路线构造器没有空间，G4 应判结构性不可达。

口径
----
``traces[v].services[k].prev_node == 0`` 表示该段是从仓库出发的第一腿 ⇒ 一趟（trip）。
本脚本只做**观测**，不改变任何规划语义：接的是与面板完全相同的冻结 ``SaaReplanner``
（control）或 ``BatchedDispatchReplanner``（batch）。

用法（从扩展根目录）::

    python scripts/eval_extra/trip_structure.py --arm control --days 1
    python scripts/eval_extra/trip_structure.py --arm batch --days 1
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_SCRIPTS, os.path.join(_SCRIPTS, 'evaluation'), os.path.join(_SCRIPTS, 'coldchain'),
           os.path.join(_SCRIPTS, 'simulation'), os.path.join(_SCRIPTS, 'admission')):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def build_panel_and_replanner(arm, days, start_day=0, or_ms=500):
    """复刻 run_admission_panel 的构造（不修改任何已登记文件）。"""
    import run_admission_panel as RAP
    from coldchain_evaluator_a1 import add_v2_initial_quality, evaluate_trace_a1
    from scenario_saa import ExplicitFeatureSampler, SaaReplanner, build_history
    import run_exp_reserve as RR
    from admission.policies import (RegisteredShadowPrice, build_clock_grid,
                                    build_lambda_grid, build_train_days, calibrate)
    from admission.panel_replanner import BatchedDispatchReplanner

    contract = RAP.make_contract()
    train_ds = add_v2_initial_quality(
        RR.generate_dataset(RAP.FROZEN['train_instances'], RAP.FROZEN['n_orders'],
                            RAP.FROZEN['train_seed']), contract)
    gate_ds = add_v2_initial_quality(
        RR.generate_dataset(RAP.FROZEN['gate_instances'], RAP.FROZEN['n_orders'],
                            RAP.FROZEN['gate_seed']), contract)
    B = float(RAP.FROZEN['budget_B'])
    lam_grid = build_lambda_grid()
    clock_grid = build_clock_grid(RAP.FROZEN['horizon'])
    g_table = calibrate(build_train_days(train_ds, RAP.OBJECTIVE), RAP.OBJECTIVE,
                        RAP.FROZEN['horizon'], lam_grid, clock_grid)
    panel = {k: v[start_day:start_day + days] for k, v in gate_ds.items()}
    hist = build_history(train_ds)
    common = dict(K=int(RAP.FROZEN['K']), time_limit=float(RAP.FROZEN['time_limit']),
                  arm_seed=RAP.FROZEN['arm_seed'], shadow_mode='greedy',
                  energy_pricing='marginal', future_policy='reveal')
    p_c = {0: 0.0, 1: 0.0, 2: 0.0}
    base = dict(budget=B, capacity=RAP.FROZEN['capacity'],
                booking_horizon=RAP.FROZEN['booking_horizon'] if 'booking_horizon' in RAP.FROZEN
                else 16.0,
                contract=contract, cooling_share=float(RAP.FROZEN['cooling_share']),
                sampler=ExplicitFeatureSampler(hist), reject_penalty=p_c, **common)
    if arm == 'control':
        kw = dict(base)
        rp = SaaReplanner(**kw)
    elif arm == 'batch':
        kw = dict(base)
        rp = BatchedDispatchReplanner(
            batch_k=8, batch_wait_h=1.0,
            lambda_grid=lam_grid, clock_grid=clock_grid, g_table=g_table,
            objective=RAP.OBJECTIVE, **kw)
    elif arm == 'ortools':
        # 第 101 轮：把 OR 臂也按"逐趟/逐车"口径拆开，用来定位它 903 kWh 的来源。
        from admission.panel_replanner import ORToolsSaaReplanner
        kw = dict(base)
        rp = ORToolsSaaReplanner(
            time_limit_ms=int(or_ms), or_objective='distance',
            or_capacity=float(RAP.FROZEN['capacity']),
            or_num_vehicles=int(RAP.FROZEN['num_vehicles']),
            lambda_grid=lam_grid, clock_grid=clock_grid, g_table=g_table,
            objective=RAP.OBJECTIVE, **kw)
    else:
        raise SystemExit('arm 只支持 control|batch|ortools，收到 %r' % (arm,))
    # 与面板一致：run_arm 里用 inspect 过滤未知 kwargs；上面两臂签名已对齐，无需过滤。
    kw_env = dict(capacity=RAP.FROZEN['capacity'], num_vehicles=RAP.FROZEN['num_vehicles'],
                  tw_speed=RAP.FROZEN['speed_kmh'] / RAP.FROZEN['km_per_unit'], replanner=rp,
                  coldchain_contract=contract,
                  booking_horizon=base['booking_horizon'])
    return dict(panel=panel, rp=rp, env_kw=kw_env, B=B, contract=contract,
                p_c=p_c, evaluate=evaluate_trace_a1, gate_ds=gate_ds, single=RAP._single,
                start_day=start_day)


def trip_stats(traces, class_of=None):
    """把 traces 折成"趟"结构，并按趟统计温区构成与能耗。

    关键口径：一趟 = ``prev_node == 0`` 的那条服务记录开启的一段（车从仓库出发到回仓）。
    * ``classes``：该趟服务订单的温区集合（由 ``class_of(node)`` 给出，环境 dataset 的
      ``temp_class``）；``homogeneous`` 当且仅当只有一个温区。
    * ``energy_kwh``：该趟各段 ``segment_energy_kwh`` 之和 + 回仓段。
    """
    if class_of is None:
        class_of = lambda node: -1  # noqa: E731
    per_veh = {}
    trips_all = []
    for tr in traces:
        n_first = 0
        n_srv = len(tr.services)
        sizes = []
        cur = 0
        seg_km = 0.0
        open_trip = None
        for s in tr.services:
            seg_km += float(getattr(s, 'segment_distance_km', 0.0))
            e = float(getattr(s, 'segment_energy_kwh', 0.0))
            if int(s.prev_node) == 0:
                if open_trip is not None:
                    trips_all.append(open_trip)
                open_trip = dict(vehicle=int(tr.vehicle_id), n=0, classes=set(),
                                 energy=e, distance=float(getattr(s, 'segment_distance_km', 0.0)),
                                 start=float(getattr(s, 'depart_time', 0.0)))
                n_first += 1
                cur = 0
            elif open_trip is None:
                open_trip = dict(vehicle=int(tr.vehicle_id), n=0, classes=set(),
                                 energy=0.0, distance=0.0,
                                 start=float(getattr(s, 'depart_time', 0.0)))
            open_trip['n'] += 1
            open_trip['classes'].add(int(class_of(int(s.node))))
            open_trip['quantities'] = open_trip.get('quantities', 0.0)
            open_trip['energy'] += e
            open_trip['distance'] += float(getattr(s, 'segment_distance_km', 0.0))
            cur += 1
        if cur:
            sizes.append(cur)
        if open_trip is not None:
            open_trip['energy'] += float(getattr(tr, 'return_segment_energy_kwh', 0.0))
            open_trip['distance'] += float(getattr(tr, 'return_segment_distance_km', 0.0))
            open_trip['dispatch_preconditioning'] = float(
                getattr(tr, 'dispatch_preconditioning_energy_kwh', 0.0))
            trips_all.append(open_trip)
            open_trip = None
        per_veh[int(tr.vehicle_id)] = dict(trips=n_first, services=n_srv, sizes=sizes,
                                           seg_km=seg_km)
    # 只保留真的服务了订单的趟
    trips = [t for t in trips_all if t['n'] > 0]
    for t in trips:
        t['classes'] = sorted(t['classes'])
        t['homogeneous'] = len(t['classes']) == 1
        t['single_leg'] = t['n'] == 1
    all_sizes = [x for v in per_veh.values() for x in v['sizes']]
    n_srv = sum(v['services'] for v in per_veh.values())
    n_trips = len(trips)
    hist = {str(k): int(sum(1 for x in all_sizes if (x >= k if k < 4 else x >= 4)))
            for k in (1, 2, 3, 4)}
    by_comp = {}
    for t in trips:
        key = '+'.join(str(c) for c in t['classes'])
        b = by_comp.setdefault(key, dict(trips=0, orders=0, energy=0.0, distance=0.0))
        b['trips'] += 1
        b['orders'] += int(t['n'])
        b['energy'] += float(t['energy'])
        b['distance'] += float(t['distance'])
    for k, b in by_comp.items():
        b['energy_per_order'] = b['energy'] / b['orders'] if b['orders'] else None
        b['orders_per_trip'] = b['orders'] / b['trips'] if b['trips'] else None
    # 第 101 轮：在车时长（dispatch → 回仓）。冷机能耗 ∝ 在车时长，这是定位"能耗翻倍"的关键量。
    in_veh_h = 0.0
    per_veh_h = {}
    for tr in traces:
        d = getattr(tr, 'dispatch_time', None)
        r = getattr(tr, 'return_arrival', None)
        if d is None:
            continue
        end = float(r) if r is not None else max(
            [float(getattr(s, 'service_finish', d) or d) for s in tr.services] or [float(d)])
        per_veh_h[int(tr.vehicle_id)] = max(0.0, end - float(d))
        in_veh_h += per_veh_h[int(tr.vehicle_id)]
    sum_trip_energy = float(sum(t['energy'] for t in trips))
    return dict(n_services=int(n_srv), n_trips=int(n_trips),
                orders_per_trip=(n_srv / n_trips if n_trips else None),
                size_hist=hist,
                vehicles_used=int(sum(1 for v in per_veh.values() if v['services'] > 0)),
                homogeneous_trips=int(sum(1 for t in trips if t['homogeneous'])),
                single_leg_trips=int(sum(1 for t in trips if t['single_leg'])),
                total_in_vehicle_h=in_veh_h,
                per_vehicle_in_vehicle_h=per_veh_h,
                energy_per_in_vehicle_h=(sum_trip_energy / in_veh_h if in_veh_h else None),
                by_composition=by_comp,
                trips=[{k: v for k, v in t.items()} for t in trips],
                per_vehicle={str(k): v for k, v in sorted(per_veh.items())})


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--arm', default='control', choices=['control', 'batch', 'ortools'])
    ap.add_argument('--days', type=int, default=1)
    ap.add_argument('--start-day', type=int, default=0)
    ap.add_argument('--or-ms', dest='or_ms', type=int, default=500,
                    help='ortools 臂：每个事件点的求解时限（毫秒）')
    ap.add_argument('--out', default=None)
    args = ap.parse_args(argv)

    from strict_online_env import StrictOnlineEnv

    ctx = build_panel_and_replanner(args.arm, args.days, args.start_day, or_ms=int(getattr(args, 'or_ms', 500)))
    env = StrictOnlineEnv(ctx['panel'], **ctx['env_kw'])
    out = dict(arm=args.arm, days=int(args.days), start_day=int(args.start_day),
               env=dict(num_vehicles=ctx['env_kw']['num_vehicles'],
                        capacity=ctx['env_kw']['capacity']), per_day=[])
    for i in range(args.days):
        t0 = time.time()
        traces, _ = env.run(i)
        t1 = time.time()
        ev = ctx['evaluate'](traces, ctx['single'](ctx['gate_ds'], ctx['start_day'] + i),
                             ctx['contract'], set(ctx['rp']._accepted), set(ctx['rp']._rejected),
                             ctx['B'], ctx['p_c'])
        st = trip_stats(traces, class_of=lambda node, _d=ctx['start_day'] + i: int(
            ctx['panel']['temp_class'][_d, node]))
        st.update(day=i, utility=float(ev['utility']), revenue=float(ev['revenue']),
                  distance_km=float(ev['distance_km']), energy_kwh=float(ev['energy_kwh']),
                  n_served=int(ev['n_served']), elapsed_s=round(t1 - t0, 1))
        print('[trip] arm=%s day=%d srv=%d trips=%d orders/trip=%.2f sizes=%s '
              'veh_used=%d km=%.1f U=%.2f (%.1fs)'
              % (args.arm, i, st['n_services'], st['n_trips'], st['orders_per_trip'] or -1,
                 st['size_hist'], st['vehicles_used'], st['distance_km'], st['utility'],
                 t1 - t0), flush=True)
        out['per_day'].append(st)
    if args.out:
        with open(args.out, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        print('[trip] wrote %s' % args.out, flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
