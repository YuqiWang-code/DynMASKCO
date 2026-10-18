"""GPU 批量路径构造：把"一天的服务集合"用 JAX 批量构造路线，比较不同打分规则的**总里程**。

为什么这是冲 G4 的正确方向
--------------------------
实测闭环口径是 ``utility = revenue − 0.1·distance_km``：

| 臂 | 收入 | 里程 | 效用 |
|---|---:|---:|---:|
| control | 1860 | 514.7 | 1808.53 |
| static λ | 1884 | 553.5 | 1828.65 |

静态 λ 多接单（+24 收入）却多跑 38.8 km（−3.88 效用），净 +20.12。
若能在**同样的 1884 收入**下把里程压回 514.7，效用就是 1832.53；若里程还能再降到 492.7，
就跨过 +1.5% 的 G4 门槛（1835.6）。**⇒ G4 的缺口不在阈值，在"每单位收入的里程"。**

而接拒层已被万天级 GPU 仿真实证榨干（分时段阈值仅 +0.25%~+0.48%），
所以唯一还没被认真优化过的量就是**路线构造**。

本脚本
------
* 输入：某天被接受的订单（坐标、需求、时间窗），来自 `gpu_admission_batch` 的接收集合；
* 构造器：贪心插入（每次从 depot 出发，按打分函数选下一个可行订单；无可行则回仓、换下一辆车）；
* 打分函数：``score(j) = w0·d(i,j)/D + w1·tw_slack(j) + w2·q(j)/Q``，``w`` 由 **ES 在 GPU 上训练**；
* 对照：``w = (1, 0, 0)`` 即最近邻（NN）；
* 目标：总里程最小（未服务订单给大惩罚）。

用法::

    python gpu_route_batch.py --npz data/bench/R1_CAL/instances.npz --day 0 --reps 32
"""
from __future__ import annotations

import argparse
import json
import sys

import numpy as np

REV = np.array([10.0, 20.0, 30.0], dtype=np.float32)
DT = np.array([7.0, 21.0, 43.0], dtype=np.float32)
PRECOOL = 0.15
CAPACITY = 50.0
N_VEH = 15
SPEED_KMPH = 30.0
KM_PER_UNIT = 20.0
SPEED_UNITS = SPEED_KMPH / KM_PER_UNIT   # 单位/小时


def pick_day(npz_path, day, rho):
    """取出该天被 ρ 阈值接受的订单子集（坐标/需求/tw_end），外加 depot。"""
    z = np.load(npz_path)
    dem = np.asarray(z['demands'], dtype=np.float64)[day]
    cls = np.asarray(z['temp_class'], dtype=np.int64)[day]
    rt = np.asarray(z['reveal_time'], dtype=np.float64)[day]
    tw_end = np.asarray(z['tw_end'], dtype=np.float64)[day]
    xy = np.asarray(z['coords'], dtype=np.float64)[day]
    idx = [o for o in range(1, dem.shape[0]) if dem[o] > 0]
    e = PRECOOL * dem[idx] * DT[cls[idx]]
    rev = REV[cls[idx]]
    dens = rev / np.maximum(e, 1e-9)
    keep = [o for o, dd in zip(idx, dens) if dd >= rho]
    return dict(depot=xy[0], xy=xy[keep], q=dem[keep], tw_end=tw_end[keep],
                rt=rt[keep], n=len(keep))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--npz', required=True)
    ap.add_argument('--day', type=int, default=0)
    ap.add_argument('--rho', type=float, default=3.0)
    ap.add_argument('--reps', type=int, default=32, help='把同一实例复制多少份用于 GPU 并行')
    ap.add_argument('--iters', type=int, default=80)
    args = ap.parse_args(argv)

    import jax
    import jax.numpy as jnp

    d = pick_day(args.npz, args.day, args.rho)
    n = d['n']
    print('devices', jax.devices(), flush=True)
    print('day=%d  accepted=%d  capacity=%.0f  vehicles=%d'
          % (args.day, n, CAPACITY, N_VEH), flush=True)

    XY = np.concatenate([d['depot'][None, :], d['xy']], axis=0).astype(np.float32)  # (n+1,2)
    Q = np.concatenate([[0.0], d['q']]).astype(np.float32)
    TW = np.concatenate([[1e9], d['tw_end']]).astype(np.float32)
    D = np.linalg.norm(XY[:, None, :] - XY[None, :, :], axis=-1).astype(np.float32)
    Dn = float(D.max())

    reps = int(args.reps)
    XYb = jnp.asarray(np.repeat(XY[None], reps, axis=0))     # (reps, n+1, 2)
    Qb = jnp.asarray(np.repeat(Q[None], reps, axis=0))
    TWb = jnp.asarray(np.repeat(TW[None], reps, axis=0))
    Db = jnp.asarray(np.repeat(D[None], reps, axis=0))

    def construct(w):
        """w = (w_dist, w_slack, w_load)。返回 (总里程, 未服务数)。"""
        w = w * jnp.ones((reps, 3))                          # (reps,3)
        wd, ws, wl = w[:, 0], w[:, 1], w[:, 2]

        def one_day(day_key):
            xy, q, tw, Dm, wd_i, ws_i, wl_i = day_key
            V = XYb.shape[1] - 1
            served = jnp.zeros((V + 1,), jnp.bool_)           # idx 0 = depot
            served = served.at[0].set(True)
            # state: (cur, load, veh, clock, dist, served)
            st = (jnp.int32(0), jnp.float32(0.0), jnp.int32(0),
                  jnp.float32(0.0), jnp.float32(0.0), served)

            def step(st, _x):
                cur, load, veh, clock, dist, srv = st
                dist_to = Dm[cur]                              # (V+1,)
                slack = jnp.maximum(tw - (clock + dist_to / SPEED_UNITS), 0.0)
                score = (wd_i * dist_to / Dn + ws_i * slack / 24.0 + wl_i * q / CAPACITY)
                feasible = (~srv) & (load + q <= CAPACITY + 1e-6) & (slack > 0.0)
                score = jnp.where(feasible, score, 1e9)
                nxt = jnp.argmin(score)
                can = feasible[nxt]
                # 不可行 ⇒ 回仓并换车（重新负载、clock 归零、车辆数 +1）
                new_cur = jnp.where(can, nxt, 0)
                new_load = jnp.where(can, load + q[nxt], 0.0)
                new_veh = jnp.where(can, veh, veh + 1)
                trav = dist_to[new_cur]
                new_dist = dist + trav
                new_clock = jnp.where(can, clock + trav / SPEED_UNITS, 0.0)
                new_srv = jnp.where(can, srv.at[nxt].set(True), srv)
                # 车用光且仍有未服务 ⇒ 强制放弃（把未服务记在末尾统计）
                new_veh = jnp.where(new_veh > N_VEH, N_VEH, new_veh)
                return (new_cur, new_load, new_veh, new_clock, new_dist, new_srv), None

            (cur, load, veh, clock, dist, srv), _ = jax.lax.scan(
                step, st, None, length=int(V * 2))
            # 回仓
            dist = dist + Dm[cur, 0]
            unserved = jnp.sum(~srv)
            return dist, unserved.astype(jnp.float32)

        dist, unserved = jax.vmap(one_day)((XYb, Qb, TWb, Db, wd, ws, wl))
        return dist.mean(), unserved.mean()

    nn_w = jnp.asarray([1.0, 0.0, 0.0], jnp.float32)
    nn_dist, nn_uns = construct(nn_w)
    nn_dist.block_until_ready()
    print('NN  : dist=%.2f km  unserved=%.2f' % (float(nn_dist) * KM_PER_UNIT, float(nn_uns)), flush=True)

    key = jax.random.PRNGKey(1)
    mu = jnp.asarray([1.0, 0.0, 0.0], jnp.float32)
    pop, sigma, lr = 24, 0.3, 0.1
    best = (float(nn_dist), np.asarray(mu))
    for it in range(int(args.iters)):
        key, k1 = jax.random.split(key)
        noise = jax.random.normal(k1, (pop, 3), jnp.float32) * sigma
        cand = mu[None, :] + noise
        sc = jax.vmap(lambda w: construct(w)[0] + 50.0 * construct(w)[1])(cand)
        sc.block_until_ready()
        w = jnp.exp(-(sc - sc.min()) / 5.0)
        w = w / w.sum()
        mu = mu + lr * (w[:, None] * noise).sum(0) / sigma
        if float(sc.min()) < best[0]:
            best = (float(sc.min()), np.asarray(cand[int(jnp.argmin(sc))]))
        if it % 20 == 0:
            print('  es it=%2d best=%.2f mu=%s' % (it, best[0], np.round(np.asarray(mu), 3)),
                  flush=True)

    fin_d, fin_u = construct(jnp.asarray(best[1], jnp.float32))
    fin_d.block_until_ready()
    print('ES  : dist=%.2f km  unserved=%.2f  w=%s' % (float(fin_d) * KM_PER_UNIT, float(fin_u),
                                                    np.round(best[1], 3)), flush=True)
    print('distance gain vs NN: %+.1f km (%+.2f%%)'
          % ((float(nn_dist) - float(fin_d)) * KM_PER_UNIT,
             100.0 * (float(fin_d) / float(nn_dist) - 1.0)), flush=True)
    print('=> utility delta at revenue 1884: %+.2f'
          % (0.1 * (float(nn_dist) - float(fin_d))), flush=True)

    json.dump(dict(npz=args.npz, day=args.day, accepted=int(n), reps=reps,
                   nn=dict(dist=float(nn_dist), unserved=float(nn_uns)),
                   es=dict(dist=float(fin_d), unserved=float(fin_u),
                           w=[float(x) for x in best[1]],
                           gain_km=float(nn_dist) - float(fin_d),
                           utility_delta=0.1 * (float(nn_dist) - float(fin_d))),
                   devices=[str(x) for x in jax.devices()]),
              open('/tmp/gpu_route_batch.json', 'w', encoding='utf-8'), indent=2,
              ensure_ascii=False)
    return 0


if __name__ == '__main__':
    sys.exit(main())
