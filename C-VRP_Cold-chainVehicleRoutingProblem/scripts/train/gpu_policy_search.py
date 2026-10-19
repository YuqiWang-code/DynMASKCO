"""GPU 跨 regime 策略搜索 v1：把接单决策从"只看密度"升级成"距离感知价值 + 时间/预算节流"。

为什么这是冲 SOTA 的新方向（第 162 轮）
----------------------------------------
第 99–158 轮的结论是：**接单层阈值族（只看 rev/e 密度）在万天级 GPU 仿真上已经榨干**，
而闭环里最强臂（登记静态 λ）恰恰就是这一族 —— 它**完全看不见距离**（决策量是 rev/e），
可是效用是 ``revenue − 0.1·distance_km``。

所以真正没被 GPU 训过的东西是「**距离感知的价值** + **时间/预算节流**」这两个旋钮的联合：
    价值   v_i = rev_i − 0.1·dist_km_i          （dist_km_i = 2·‖x_i − depot‖·km_per_unit）
    门槛   ρ_eff(t, r) = ρ0 · exp(a_t·(t̂ − 0.5) + a_b·(r − 1))，r = 剩余预算比例
    接受   ⇔ v_i / e_i ≥ ρ_eff 且 预算够
四个参数 θ = (ρ0, a_t, a_b, κ) 用 **ES（无梯度）在 GPU 上训**，训完 **零样本** 换 regime 评测。

模型边界（必须写清楚，不得含糊）
--------------------------------
* 距离用"每单独立往返"近似（``2·‖x‖``）。闭环实测的每单里程 ≈ 4.7 km 与这个近似同量级，
  但**不建模拼趟**，所以这是**保守**近似（拼趟只会让距离更小）。
* 能耗只用登记预冷 ``e = 0.15·q·|25−T|``，再按实测 **32% 固定开销** 把可用预算压到 ``0.68·B``
  （第 99 轮能耗三分：``B_eff = 486.6 / 710.65 = 68.5%``）。
* ⇒ 本脚本给的是**候选策略的筛选器**，最终判定必须在真实闭环面板（`run_admission_panel.py`）里做。

用法::

    python scripts/train/gpu_policy_search.py \
        --train-npz data/bench/R1_CAL/instances.npz \
        --eval-npz data/bench/R1c_GATE/instances.npz data/bench/R3_GATE/instances.npz \
        --out results/train/policy_r1.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np

REV = np.array([10.0, 20.0, 30.0], dtype=np.float32)
DT = np.array([7.0, 21.0, 43.0], dtype=np.float32)
PRECOOL = 0.15
KM_PER_UNIT = 20.0
DIST_COST = 0.1          # 元 / km（登记 a1 效用恒等式）
OVERHEAD_SHARE = 0.32    # 第 99 轮实测：固定开销占预算 32%


def load_days(npz_path, horizon=16.0):
    """返回 (rev, e, clk, dist_km) 四个 (days, orders) 数组，订单按 reveal_time 排序。"""
    z = np.load(npz_path)
    dem = np.asarray(z['demands'], dtype=np.float64)
    cls = np.asarray(z['temp_class'], dtype=np.int64)
    rt = np.asarray(z['reveal_time'], dtype=np.float64)
    xy = np.asarray(z['coords'], dtype=np.float64)
    R, E, C, D = [], [], [], []
    for d in range(dem.shape[0]):
        m = dem[d, 1:] > 0
        c, q, t, p = cls[d, 1:][m], dem[d, 1:][m], rt[d, 1:][m], xy[d, 1:][m]
        o = np.argsort(t, kind='stable')
        c, q, t, p = c[o], q[o], t[o], p[o]
        R.append(REV[c])
        E.append(PRECOOL * q * DT[c])
        C.append(t)
        D.append(2.0 * np.linalg.norm(p, axis=-1) * KM_PER_UNIT)   # 往返近似
    n = min(len(x) for x in R)
    return (np.stack([x[:n] for x in R]).astype(np.float32),
            np.stack([x[:n] for x in E]).astype(np.float32),
            np.stack([x[:n] for x in C]).astype(np.float32),
            np.stack([x[:n] for x in D]).astype(np.float32))


def policy_scan(jnp, jax, R, E, C, KM, B, theta, horizon):
    """θ = (rho0, a_t, a_b)；返回逐日 (utility, revenue, energy, 接单数)。"""
    def step(carry, xs):
        used, util, rev, cnt = carry
        r, ei, c, km = xs
        t_hat = c / horizon
        r_ratio = 1.0 - used / B
        rho = theta[0] * jnp.exp(theta[1] * (t_hat - 0.5) + theta[2] * (r_ratio - 1.0))
        rho = jnp.maximum(rho, 0.25)
        v = r - DIST_COST * km
        ok = ((v / ei) >= rho) & (used + ei <= B + 1e-6)
        used = jnp.where(ok, used + ei, used)
        util = jnp.where(ok, util + v, util)
        rev = jnp.where(ok, rev + r, rev)
        cnt = jnp.where(ok, cnt + 1.0, cnt)
        return (used, util, rev, cnt), None

    z = jnp.zeros(R.shape[0], jnp.float32)
    out, _ = jax.lax.scan(step, (z, z, z, z), (R.T, E.T, C.T, KM.T))
    return out[1], out[2], out[0], out[3]


def static_grid(jnp, jax, R, E, C, KM, B, horizon, lo=0.5, hi=8.0, step=0.05):
    """静态密度阈值族（距离盲，对照臂）：网格在 GPU 上批量扫。"""
    def sim(rho):
        def step(carry, xs):
            used, util = carry
            r, ei, km = xs
            v = r - DIST_COST * km
            ok = ((r / ei) >= rho) & (used + ei <= B + 1e-6)
            used = jnp.where(ok, used + ei, used)
            util = jnp.where(ok, util + v, util)
            return (used, util), None
        z = jnp.zeros(R.shape[0], jnp.float32)
        out, _ = jax.lax.scan(step, (z, z), (R.T, E.T, KM.T))
        return out[1]

    grid = jnp.arange(lo, hi + 1e-9, step)
    vals = jax.vmap(sim)(grid)          # (n_grid, n_days)
    vals.block_until_ready()
    vals_mean = vals.mean(axis=1)       # 每个 rho 的平均效用
    i = int(jnp.argmax(vals_mean))
    return float(grid[i]), float(vals_mean[i]), vals_mean, grid


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--train-npz', required=True)
    ap.add_argument('--eval-npz', nargs='+', default=[])
    ap.add_argument('--horizon', type=float, default=16.0)
    ap.add_argument('--rho-full', type=float, default=0.6,
                    help='登记式预算口径：B = (1-rho_full)·mean(全天满服务能耗)')
    ap.add_argument('--pop', type=int, default=32)
    ap.add_argument('--iters', type=int, default=80)
    ap.add_argument('--sigma', type=float, default=0.25)
    ap.add_argument('--lr', type=float, default=0.12)
    ap.add_argument('--hold', type=float, default=0.0, help='算完后保活若干秒，供 nvidia-smi 取证')
    ap.add_argument('--out', default=None)
    args = ap.parse_args(argv)

    import jax
    import jax.numpy as jnp

    t0 = time.time()
    print('devices', jax.devices(), flush=True)
    Rr, Er, Cr, Dr = load_days(args.train_npz, args.horizon)
    B_raw = float((1.0 - args.rho_full) * Er.sum(axis=1).mean())
    B = (1.0 - OVERHEAD_SHARE) * B_raw          # 可用接单预算（扣固定开销）
    print('train days=%d orders=%d B_raw=%.3f B_eff=%.3f' % (Rr.shape[0], Rr.shape[1], B_raw, B),
          flush=True)

    R, E, C, D = (jnp.asarray(x) for x in (Rr, Er, Cr, Dr))

    # --- 基线：静态密度阈值族（GPU 网格扫，train 上最优） ---
    rho_star_tr, val_star_tr, _, _ = static_grid(jnp, jax, R, E, C, D, B, args.horizon)
    print('static(rev/e) rho*=%.2f  train utility=%.3f' % (rho_star_tr, val_star_tr), flush=True)

    # --- ES 训 3 参数策略 ---
    theta = jnp.array([rho_star_tr, 0.0, 0.0], jnp.float32)
    key = jax.random.PRNGKey(20261019)

    def score(th):
        u, rev, e, cnt = policy_scan(jnp, jax, R, E, C, D, B, th, args.horizon)
        return u.mean()

    score_j = jax.jit(score)
    hist = []
    for it in range(args.iters):
        key, k = jax.random.split(key)
        noise = jax.random.normal(k, (args.pop, 3), jnp.float32) * args.sigma
        cand = theta[None, :] + noise
        vals = jax.vmap(score_j)(cand)
        vals.block_until_ready()
        best = float(vals.max())
        # 排名加权（抗尺度）
        order = jnp.argsort(jnp.argsort(vals))
        w = jnp.exp((order - (args.pop - 1) / 2.0) / 3.0)
        w = w / w.sum()
        g = (w[:, None] * noise).sum(0) / args.sigma
        theta = theta + args.lr * g
        theta = theta.at[0].set(jnp.clip(theta[0], 0.5, 8.0))
        theta = theta.at[1].set(jnp.clip(theta[1], -3.0, 3.0))
        theta = theta.at[2].set(jnp.clip(theta[2], -3.0, 3.0))
        hist.append(best)
        if it % 20 == 0:
            print('  es it=%2d best=%.3f theta=%s' % (it, best, np.round(np.asarray(theta), 4)),
                  flush=True)
    train_u = float(score_j(theta))
    print('ES theta=%s  train utility=%.3f  gain vs static: %+.3f (%.2f%%)'
          % (np.round(np.asarray(theta), 4), train_u, train_u - val_star_tr,
             100.0 * (train_u / val_star_tr - 1.0)), flush=True)

    out = dict(train_npz=os.path.abspath(args.train_npz), B_raw=B_raw, B_eff=B,
               rho_star_train=rho_star_tr, static_train=val_star_tr,
               theta=[float(x) for x in np.asarray(theta)], es_train=train_u,
               es_gain_pct=100.0 * (train_u / val_star_tr - 1.0),
               eval={}, devices=[str(d) for d in jax.devices()],
               elapsed_s=round(time.time() - t0, 1))

    # --- 零样本跨 regime 评测 ---
    for path in args.eval_npz:
        Rr2, Er2, Cr2, Dr2 = load_days(path, args.horizon)
        B2_raw = float((1.0 - args.rho_full) * Er2.sum(axis=1).mean())
        B2 = (1.0 - OVERHEAD_SHARE) * B2_raw
        R2, E2, C2, D2 = (jnp.asarray(x) for x in (Rr2, Er2, Cr2, Dr2))
        u_es, rev_es, e_es, cnt_es = policy_scan(jnp, jax, R2, E2, C2, D2, B2, theta, args.horizon)
        # 对照 1：静态族在**同一评测集**上网格最优（这是"作弊上界"，最强对照）
        rho2, val2, _, _ = static_grid(jnp, jax, R2, E2, C2, D2, B2, args.horizon)
        # 对照 2：把 train 最优 rho 直接搬过去（未重标定）
        u_tr_rho, _, _, _ = policy_scan(jnp, jax, R2, E2, C2, D2, B2,
                                       jnp.array([rho_star_tr, 0.0, 0.0]), args.horizon)
        u_es_m = float(u_es.mean())
        val2 = float(val2)
        u_tr_m = float(u_tr_rho.mean())
        print('[eval] %s  ES=%.3f  static(oracle-on-eval)=%.3f  static(train rho)=%.3f  '
              'gain_vs_oracle=%+.2f%%  gain_vs_trainrho=%+.2f%%'
              % (os.path.basename(os.path.dirname(path)), u_es_m, val2, u_tr_m,
                 100.0 * (u_es_m / val2 - 1.0), 100.0 * (u_es_m / u_tr_m - 1.0)), flush=True)
        out['eval'][os.path.basename(os.path.dirname(path))] = dict(
            es=u_es_m, static_oracle_on_eval=val2, rho_star_eval=rho2,
            static_train_rho=u_tr_m,
            gain_vs_oracle_pct=100.0 * (u_es_m / val2 - 1.0),
            gain_vs_trainrho_pct=100.0 * (u_es_m / u_tr_m - 1.0),
            mean_served=float(cnt_es.mean()))

    out['elapsed_s'] = round(time.time() - t0, 1)
    if args.out:
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        with open(args.out, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        print('[out] %s' % args.out, flush=True)
    if args.hold > 0:
        print('[hold] pid=%d %.0fs' % (os.getpid(), args.hold), flush=True)
        time.sleep(args.hold)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
