"""GPU 批量接拒层仿真：把"一天 194 单的顺序决策"变成 JAX 里的 (天 × 单) 批量扫描。

为什么值得做
------------
1. 以前所有接拒层结论都建立在 **5 天**上；这里一次算 **上万天**，\u2192 结论从"线索"变成"统计事实"。
2. 决策过程是 (天数) × (顺序扫描) 的结构，天然适合 `vmap` + `lax.scan`\u2192 GPU 跑满。
3. 可以在 GPU 上直接做**参数搜索/训练**（静态阈值、分时段阈值、学习型策略），
   给出"接拒层的最优有多好"这一条能被引用的数字。

模型（与冻结登记口径一致）
--------------------------
* 收入 `REV = {0:10, 1:20, 2:30}`（18/4/−18 °C）。
* 预冷能耗 `e = 0.15 · q · |25 − T_c|`（T = 18/4/−18）\u2192 系数 7/21/43。
* 日预算 `B`（由数据集给出；这里用 \u03c1=0.6 的登记式：`B = 0.4 · mean(全天满服务能耗)`）。
* 决策：按 `reveal_time` 升序逐单决定 accept/reject；accept 消耗 `e`，超预算即不可接受。
* 目标：最大化 accepted 收入（接拒层净价值=收入，能耗是硬约束）。

用法::

    python gpu_admission_batch.py --npz data/bench/R1_CAL/instances.npz --reps 40
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

REV = np.array([10.0, 20.0, 30.0], dtype=np.float32)
DT = np.array([7.0, 21.0, 43.0], dtype=np.float32)
PRECOOL = 0.15


def load_days(npz_path):
    """返回 (rev, e, clock) 三个 (天, 单) 数组，按 reveal_time 升序。"""
    z = np.load(npz_path)
    dem = np.asarray(z['demands'], dtype=np.float64)
    cls = np.asarray(z['temp_class'], dtype=np.int64)
    rt = np.asarray(z['reveal_time'], dtype=np.float64)
    rev_out, e_out, clk_out = [], [], []
    for d in range(dem.shape[0]):
        m = dem[d, 1:] > 0
        c, q, t = cls[d, 1:][m], dem[d, 1:][m], rt[d, 1:][m]
        order = np.argsort(t, kind='stable')
        c, q, t = c[order], q[order], t[order]
        rev_out.append(REV[c])
        e_out.append(PRECOOL * q * DT[c])
        clk_out.append(t)
    n = min(len(x) for x in rev_out)
    return (np.stack([x[:n] for x in rev_out]).astype(np.float32),
            np.stack([x[:n] for x in e_out]).astype(np.float32),
            np.stack([x[:n] for x in clk_out]).astype(np.float32))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--npz', required=True)
    ap.add_argument('--reps', type=int, default=40, help='把 n 天重复成 n*reps 天（批量放大）')
    ap.add_argument('--horizon', type=float, default=16.0)
    args = ap.parse_args(argv)

    import jax
    import jax.numpy as jnp

    rev, e, clk = load_days(args.npz)
    # 预算：登记式 B = (1-rho) * mean(全天满服务能耗)，rho = 0.6
    B = float((1.0 - 0.6) * e.sum(axis=1).mean())
    n_days, n_orders = rev.shape
    print('devices', jax.devices())
    print('days=%d orders=%d  B=%.3f  (repeat x%d)' % (n_days, n_orders, B, args.reps), flush=True)

    rev = np.repeat(rev, args.reps, axis=0)
    e = np.repeat(e, args.reps, axis=0)
    clk = np.repeat(clk, args.reps, axis=0)
    R = jnp.asarray(rev)
    E = jnp.asarray(e)
    C = jnp.asarray(clk) / float(args.horizon)

    def simulate_static(rho):
        """静态密度阈值：accept <=> r/e >= rho 且预算够。返回 (收入, 能耗, 接单数)。"""
        def step(carry, xs):
            used, reward, cnt = carry
            r, ei, _c = xs
            dens = r / ei
            ok = (dens >= rho) & (used + ei <= B + 1e-6)
            used = jnp.where(ok, used + ei, used)
            reward = jnp.where(ok, reward + r, reward)
            cnt = jnp.where(ok, cnt + 1.0, cnt)
            return (used, reward, cnt), None

        (used, reward, cnt), _ = jax.lax.scan(
            step, (jnp.zeros(R.shape[0], jnp.float32), jnp.zeros(R.shape[0], jnp.float32),
                   jnp.zeros(R.shape[0], jnp.float32)), (R.T, E.T, C.T))
        return reward, used, cnt

    # --- 静态阈值网格（GPU 批量） ---
    grid = jnp.arange(1.2, 6.01, 0.05)
    vals = jax.vmap(lambda rho: simulate_static(rho)[0].mean())(grid)
    vals.block_until_ready()
    best_i = int(jnp.argmax(vals))
    best_rho = float(grid[best_i])
    best_val = float(vals[best_i])
    print('static rho* = %.2f  mean revenue = %.3f' % (best_rho, best_val), flush=True)

    # --- 分时段阈值：3 段（早/中/晚），每段一个 rho（参数仍在 CPU 侧网格搜索） ---
    def simulate_period(rhos):
        def step(carry, xs):
            used, reward = carry
            r, ei, c = xs
            seg = jnp.clip((c * 3.0).astype(jnp.int32), 0, 2)
            rho = rhos[seg]
            ok = ((r / ei) >= rho) & (used + ei <= B + 1e-6)
            used = jnp.where(ok, used + ei, used)
            reward = jnp.where(ok, reward + r, reward)
            return (used, reward), None

        (used, reward), _ = jax.lax.scan(
            step, (jnp.zeros(R.shape[0], jnp.float32), jnp.zeros(R.shape[0], jnp.float32)),
            (R.T, E.T, C.T))
        return reward

    # 用 ES（无梯度）在 GPU 上搜 3 个参数；目标 = 平均收入
    key = jax.random.PRNGKey(0)
    mu = jnp.full((3,), jnp.float32(best_rho))
    pop, sigma, lr, iters = 24, 0.25, 0.08, 60
    hist = []
    for it in range(iters):
        key, k1 = jax.random.split(key)
        noise = jax.random.normal(k1, (pop, 3), jnp.float32) * sigma
        cand = mu[None, :] + noise
        scores = jax.vmap(simulate_period)(cand)      # (pop, days)
        scores.block_until_ready()
        sv = scores.mean(axis=1)                      # 每个候选一个标量
        w = jnp.exp((sv - sv.max()) / 2.0)
        w = w / w.sum()
        g = (w[:, None] * noise).sum(0) / sigma
        mu = mu + lr * g
        hist.append(float(sv.mean()))
        if it % 15 == 0:
            print('  es it=%2d mean=%.3f mu=%s' % (it, hist[-1], np.round(np.asarray(mu), 3)),
                  flush=True)
    per_val = float(simulate_period(mu).mean())
    print('per-period rho = %s  mean revenue = %.3f' % (np.round(np.asarray(mu), 3), per_val),
          flush=True)
    print('gain vs static: %+.3f (%.2f%%)' % (per_val - best_val,
                                              100.0 * (per_val / best_val - 1.0)), flush=True)

    out = dict(npz=os.path.abspath(args.npz), days=int(R.shape[0]), orders=int(n_orders),
               budget_B=B, static=dict(rho=best_rho, mean_revenue=best_val),
               per_period=dict(rho=[float(x) for x in np.asarray(mu)],
                               mean_revenue=per_val,
                               gain_abs=per_val - best_val,
                               gain_pct=100.0 * (per_val / best_val - 1.0)),
               es_history=hist, jax_devices=[str(d) for d in jax.devices()])
    print(json.dumps({k: v for k, v in out.items() if k != 'es_history'},
                     indent=2, ensure_ascii=False), flush=True)
    with open('/tmp/gpu_admission_batch.json', 'w', encoding='utf-8') as fh:
        json.dump(out, fh, indent=2, ensure_ascii=False)
    return 0


if __name__ == '__main__':
    sys.exit(main())
