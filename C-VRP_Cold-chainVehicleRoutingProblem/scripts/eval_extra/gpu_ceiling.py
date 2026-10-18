"""GPU 上界（第 99 轮）：把"接拒层最多还能赚多少收入"算到不可辩驳。

为什么需要
----------
G4 要求"对最强基线 ≥1.5% 且 ≥8/10 日"。当前最好臂 batch = +1.16%（8/10）。要判断这 0.34pp
的缺口是**机制不够好**还是**根本不在接拒层**，需要一个与策略无关的上界：

    给定当天全部订单（离线、全知）、预算 B、登记能耗口径 e_lower，
    收入上界 = 0/1 背包最优解（按密度贪心给出分数背包 UB，DP 给出整数背包 UB）。

若整数 UB 只比 control 实际收入高一点点，那么任何**因果**接单策略都不可能跨过 +1.5%
（因为因果策略的可行集是离线可行集的子集），G4 在接拒层就是结构性不可达。
若 UB 远高，则缺口确实在机制侧，应继续做接单/路线机制。

口径
----
* 收入：``REV = {0:10, 1:20, 2:30}``（与 ``admission.policies.REV`` 同源，直接 import，不复制）。
* 能耗：``e_lower = q·k_precool·(T_amb − T_class)``（与 ``admission.policies.e_lower_of`` 同源）。
* 预算：面板冻结值 ``B = 710.6548328611384``（从 run_admission_panel.FROZEN 取）。
* 距离不进 UB（故 UB 是**效用**的合法上界：utility = rev − 0.1·km ≤ rev）。
* 同时在 GPU 上算"若里程保持 control 观测值"的等效效用 UB，便于与 G4 门槛直接对齐。

用法（从扩展根目录）::

    python scripts/eval_extra/gpu_ceiling.py --days 10 --out results/admission_panel/p99_ceiling.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_SCRIPTS, os.path.join(_SCRIPTS, 'evaluation'), os.path.join(_SCRIPTS, 'coldchain'),
           os.path.join(_SCRIPTS, 'simulation'), os.path.join(_SCRIPTS, 'admission')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# 观测到的基线（与 results/admission_panel/*/panel.json 一致；仅用于把 UB 换算成百分比）
OBSERVED = dict(
    control=dict(utility=1796.68, revenue=1846.0, distance_km=493.2),
    static=dict(utility=1815.82, revenue=1868.0, distance_km=521.8),
    batch=dict(utility=1817.61, revenue=1869.0, distance_km=513.9),
)


def load_day_matrix(days, start_day=0):
    """生成与面板完全相同的 gate 数据集，返回 (rev, e, days_available)。"""
    import run_admission_panel as RAP
    from coldchain_evaluator_a1 import add_v2_initial_quality
    import run_exp_reserve as RR
    from admission.policies import REV, e_lower_of

    contract = RAP.make_contract()
    gate_ds = add_v2_initial_quality(
        RR.generate_dataset(RAP.FROZEN['gate_instances'], RAP.FROZEN['n_orders'],
                            RAP.FROZEN['gate_seed']), contract)
    sel = slice(start_day, start_day + days)
    dem = np.asarray(gate_ds['demands'][sel], dtype=np.float64)
    cls = np.asarray(gate_ds['temp_class'][sel], dtype=np.int64)
    rev = np.zeros_like(dem)
    energy = np.zeros_like(dem)
    for c, r in REV.items():
        m = cls == int(c)
        rev[m] = float(r)
    energy = np.asarray([[e_lower_of(int(cls[i, o]), float(dem[i, o]), RAP.OBJECTIVE)
                          for o in range(dem.shape[1])] for i in range(dem.shape[0])],
                        dtype=np.float64)
    active = dem > 0.0
    return rev, energy, active, float(RAP.FROZEN['budget_B'])


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--days', type=int, default=10)
    ap.add_argument('--start-day', type=int, default=0)
    ap.add_argument('--bin', type=float, default=0.01, help='整数背包的预算栅格（kWh）')
    ap.add_argument('--hold', type=float, default=0.0,
                    help='算完后保持进程存活若干秒（供 nvidia-smi 取证）')
    ap.add_argument('--out', default=None)
    args = ap.parse_args(argv)

    import jax
    import jax.numpy as jnp

    print('devices', jax.devices(), flush=True)
    rev_np, e_np, act_np, B = load_day_matrix(args.days, args.start_day)
    nd, nnode = rev_np.shape
    print('gate days=%d nodes=%d active/order-mean=%.1f B=%.4f'
          % (nd, nnode, act_np.sum(axis=1).mean(), B), flush=True)

    # 只保留当天激活的订单：把 (rev, e) 压到 (nd, n_active) 的定长矩阵（多余位 e=+inf）
    mask = act_np
    counts = mask.sum(axis=1)
    nmax = int(counts.max())
    rev = np.zeros((nd, nmax), dtype=np.float64)
    en = np.full((nd, nmax), np.inf, dtype=np.float64)
    for i in range(nd):
        idx = np.where(mask[i])[0]
        rev[i, :len(idx)] = rev_np[i, idx]
        en[i, :len(idx)] = e_np[i, idx]

    # --- 分数背包（密度贪心）-> 收入 UB（比整数 UB 更松，作为参考）
    dens = np.where(np.isfinite(en), rev / np.maximum(en, 1e-12), 0.0)
    order = np.argsort(-dens, axis=1, kind='stable')
    rev_s = np.take_along_axis(rev, order, axis=1)
    e_s = np.take_along_axis(en, order, axis=1)
    cum_e = np.cumsum(e_s, axis=1)
    cum_r = np.cumsum(rev_s, axis=1)
    frac_ub = np.zeros(nd)
    for i in range(nd):
        ok = cum_e[i] <= B + 1e-9
        k = int(ok.sum())
        frac_ub[i] = cum_r[i, k - 1] if k > 0 else 0.0
        if k < nmax and np.isfinite(e_s[i, k]):
            left = B - (cum_e[i, k - 1] if k > 0 else 0.0)
            frac_ub[i] += rev_s[i, k] * min(1.0, max(0.0, left / e_s[i, k]))

    # --- 整数背包 DP（GPU）：价值 = 收入，重量 = 能耗，容量 = B
    nb = int(round(B / args.bin)) + 1
    w = jnp.asarray(np.where(np.isfinite(en), np.ceil(en / args.bin), 10 ** 9), dtype=jnp.int32)
    v = jnp.asarray(np.where(np.isfinite(en), rev, 0.0), dtype=jnp.float32)
    neg = jnp.full((nd, nb), -1e9, dtype=jnp.float32).at[:, 0].set(0.0)

    def step(carry, xs):
        row = carry
        wk, vk = xs
        # 0/1 背包：从后往前（用 jnp.roll 近似"不低于 k-wk 的状态"，即同一物品只用一次）
        cand = jnp.where(
            jnp.arange(nb)[None, :] >= wk[:, None],
            jnp.take_along_axis(row, jnp.maximum(jnp.arange(nb)[None, :] - wk[:, None], 0),
                                axis=1) + vk[:, None],
            -1e9)
        return jnp.maximum(row, cand), None

    rows = neg
    for k in range(nmax):
        rows, _ = step(rows, (w[:, k], v[:, k]))
    int_ub = np.asarray(jnp.max(rows, axis=1))

    obs = OBSERVED['control']
    # 把收入 UB 换成"里程保持 control 观测值"的效用 UB
    ub_util_same_km = int_ub - 0.1 * obs['distance_km']
    ub_util_frac_same_km = frac_ub - 0.1 * obs['distance_km']
    base_u = obs['utility']
    need = 1.015 * base_u

    out = dict(days=int(nd), start_day=int(args.start_day), budget=B, bins=int(nb),
               bin_kwh=float(args.bin), observed=OBSERVED,
               per_day=[dict(day=i,
                             n_active=int(counts[i]),
                             frac_rev_ub=float(frac_ub[i]),
                             int_rev_ub=float(int_ub[i]),
                             ub_utility_same_km=float(ub_util_same_km[i]))
                        for i in range(nd)],
               mean=dict(frac_rev_ub=float(frac_ub.mean()),
                         int_rev_ub=float(int_ub.mean()),
                         ub_utility_same_km=float(ub_util_same_km.mean()),
                         ub_utility_frac_same_km=float(ub_util_frac_same_km.mean()),
                         control_revenue=obs['revenue'],
                         control_utility=base_u,
                         g4_threshold_utility=float(need),
                         headroom_rev_ub_vs_control=float(int_ub.mean() - obs['revenue']),
                         headroom_util_ub_vs_control=float(ub_util_same_km.mean() - base_u),
                         headroom_util_ub_pct=float(100.0 * (ub_util_same_km.mean() / base_u - 1.0)),
                         g4_reachable_in_admission_layer=bool(
                             ub_util_same_km.mean() >= need)))
    print(json.dumps(out['mean'], ensure_ascii=False, indent=1), flush=True)
    print('[ceiling] per-day int UB revenue: %s'
          % ', '.join('%.0f' % x for x in int_ub), flush=True)
    if args.out:
        with open(args.out, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        print('[ceiling] wrote %s' % args.out, flush=True)
    if args.hold > 0:
        import time as _t
        # 取证窗口：进程占着 CUDA 上下文，nvidia-smi 里应能看到本 pid
        print('[ceiling] holding %.0fs (pid=%d) for nvidia-smi' % (args.hold, os.getpid()),
              flush=True)
        _t.sleep(float(args.hold))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
