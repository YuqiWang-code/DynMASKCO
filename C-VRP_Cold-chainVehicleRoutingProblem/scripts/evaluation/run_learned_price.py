"""学习型影子价格（JAX / GPU）：用 ES 训练一个"可见状态 → λ"的小网络。

为什么用 ES 而不是梯度：接拒是 `revenue − λ·e > 0` 的**分段常数**决策，λ 的微小变化
几乎不改变目标（梯度为零），所以用**黑盒进化策略**（OpenAI-ES 风格，对偶采样 + Adam）
在 TRAIN 天的订单流上直接优化"日收入"。

环境（可批量、可复现）
----------------------
一天 = 一条按揭示时刻排序的订单流 ``(t, revenue, e_lower)``（与登记口径一致）。
决策只依赖**因果特征**（时钟、剩余预算、已见单数、已花比例、已接受的平均性价比），
不含任何未来信息。

用法（服务器，GPU）::

    python scripts/evaluation/run_learned_price.py --iters 200 --pop 64 --days-limit 200 \
        --out results/admission_learned/v1

产物：``learned_price.npz``（参数）、``train.json``（曲线 + 特征配置 + 评估）。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_SCRIPTS, os.path.join(_SCRIPTS, 'evaluation'), os.path.join(_SCRIPTS, 'admission')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

N_FEATURES = 6
LAM_MIN, LAM_MAX = 0.25, 8.0


# --------------------------------------------------------------------------
# 数据：把 A-v1 数据集变成定长 (t, rev, e, mask)
# --------------------------------------------------------------------------
def build_arrays(dataset, objective, max_orders=None):
    from admission.policies import REV, e_lower_of
    dem = np.asarray(dataset['demands'], dtype=np.float64)
    rev_t = np.asarray(dataset['reveal_time'], dtype=np.float64)
    cls_t = np.asarray(dataset['temp_class'], dtype=np.int64)
    n_days = dem.shape[0]
    lists = []
    for d in range(n_days):
        mask = dem[d, 1:] > 0
        cls = cls_t[d, 1:][mask]
        q = dem[d, 1:][mask]
        t = rev_t[d, 1:][mask]
        est = np.asarray([e_lower_of(int(c), float(qq), objective) for c, qq in zip(cls, q)])
        rv = np.asarray([REV[int(c)] for c in cls], dtype=np.float64)
        order = np.argsort(t, kind='stable')
        lists.append((t[order], rv[order], est[order]))
    n = max_orders or max(len(x[0]) for x in lists)
    out_t = np.full((n_days, n), 1e9, dtype=np.float32)
    out_r = np.zeros((n_days, n), dtype=np.float32)
    out_e = np.zeros((n_days, n), dtype=np.float32)
    out_m = np.zeros((n_days, n), dtype=np.float32)
    for d, (t, r, e) in enumerate(lists):
        k = min(len(t), n)
        out_t[d, :k] = t[:k]
        out_r[d, :k] = r[:k]
        out_e[d, :k] = e[:k]
        out_m[d, :k] = 1.0
    return out_t, out_r, out_e, out_m, np.array([len(x[0]) for x in lists])


# --------------------------------------------------------------------------
# JAX 环境与策略
# --------------------------------------------------------------------------
def make_env(budget, horizon):
    import jax
    import jax.numpy as jnp

    def features(clock, b_rem, n_seen, rev_sum, e_sum, n_expected):
        ratio = jnp.clip(b_rem / budget, 0.0, 1.0)
        progress = jnp.clip(clock / horizon, 0.0, 1.0)
        seen = jnp.clip(n_seen / jnp.maximum(n_expected, 1.0), 0.0, 1.0)
        spent = jnp.clip(1.0 - ratio, 0.0, 1.0)
        # 已接受订单的平均性价比（没有接受过时为 0）——纯因果统计量
        avg_ratio = jnp.where(e_sum > 1e-9, rev_sum / jnp.maximum(e_sum, 1e-9) / 30.0, 0.0)
        # 剩余视野的"预算充裕度"代理：ratio / (1 - progress + 1e-3)
        pace = jnp.clip(ratio / (1.0 - progress + 1e-3), 0.0, 4.0) / 4.0
        return jnp.stack([progress, spent, seen, avg_ratio, pace, ratio])

    def policy(params, x):
        h = jnp.tanh(x @ params['w1'] + params['b1'])
        h = jnp.tanh(h @ params['w2'] + params['b2'])
        z = (h @ params['w3'] + params['b3'])[0]   # squeeze: 标量 λ
        s = jax.nn.sigmoid(z)                      # (0,1)
        return LAM_MIN + (LAM_MAX - LAM_MIN) * s

    def day_replay(params, t, rev, e, m, n_expected):
        def step(carry, xs):
            b_rem, n_seen, rev_sum, e_sum, total, acc = carry
            ti, ri, ei, mi = xs
            x = features(ti, b_rem, n_seen, rev_sum, e_sum, n_expected)
            lam = policy(params, x)
            admit = (ri - lam * ei > 0.0) & (ei <= b_rem + 1e-9) & (mi > 0.5)
            b_rem = jnp.where(admit, b_rem - ei, b_rem)
            rev_sum = jnp.where(admit, rev_sum + ri, rev_sum)
            e_sum = jnp.where(admit, e_sum + ei, e_sum)
            total = jnp.where(admit, total + ri, total)
            acc = jnp.where(admit, acc + 1.0, acc)
            # n_seen 只对真实订单推进
            n_seen = n_seen + mi
            return (b_rem, n_seen, rev_sum, e_sum, total, acc), (lam, admit)

        init = (jnp.float32(budget), jnp.float32(0.0), jnp.float32(0.0), jnp.float32(0.0),
                jnp.float32(0.0), jnp.float32(0.0))
        out, _ = jax.lax.scan(step, init, (t, rev, e, m))
        return out[4], out[5], out[0]

    def batch_objective(params, t, rev, e, m, n_expected):
        totals, accs, brems = jax.vmap(day_replay, in_axes=(None, 0, 0, 0, 0, None))(
            params, t, rev, e, m, n_expected)
        return jnp.mean(totals), jnp.mean(accs), jnp.mean(brems)

    return features, policy, day_replay, batch_objective


def init_params(rng, hidden=32):
    import jax.numpy as jnp
    import jax
    rngs = jax.random.split(rng, 4)
    scale = 1.0 / np.sqrt(32.0)
    return dict(
        w1=jax.random.normal(rngs[0], (N_FEATURES, hidden)) * scale,
        b1=jnp.zeros(hidden),
        w2=jax.random.normal(rngs[1], (hidden, hidden)) * scale,
        b2=jnp.zeros(hidden),
        w3=jax.random.normal(rngs[2], (hidden, 1)) * scale,
        b3=jnp.zeros(1),
    )


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--iters', type=int, default=200)
    ap.add_argument('--pop', type=int, default=64)
    ap.add_argument('--sigma', type=float, default=0.05)
    ap.add_argument('--lr', type=float, default=0.02)
    ap.add_argument('--day-limit', type=int, default=200)
    ap.add_argument('--seed', type=int, default=1017)
    ap.add_argument('--out', required=True)
    args = ap.parse_args(argv)

    import jax
    import jax.numpy as jnp

    from run_exp_reserve import generate_dataset
    from admission.policies import (AlwaysAccept, DynamicDual, RegisteredShadowPrice,
                                    build_clock_grid, build_lambda_grid, build_train_days,
                                    calibrate)

    OBJECTIVE = dict(ambient_c=25.0, target_c=[18.0, 4.0, -18.0],
                     precool_energy_per_unit_per_c=0.15)
    FROZEN = dict(train_seed=20260925, train_instances=200, gate_seed=20260926,
                  gate_instances=40, n_orders=200, budget_B=710.6548328611384)
    B = float(FROZEN['budget_B']); HORIZON = 16.0

    train = generate_dataset(FROZEN['train_instances'], FROZEN['n_orders'], FROZEN['train_seed'])
    gate = generate_dataset(FROZEN['gate_instances'], FROZEN['n_orders'], FROZEN['gate_seed'])
    t_tr, r_tr, e_tr, m_tr, n_tr = build_arrays(train, OBJECTIVE)
    t_ga, r_ga, e_ga, m_ga, n_ga = build_arrays(gate, OBJECTIVE)
    day_limit = min(args.day_limit, t_tr.shape[0])
    t_tr, r_tr, e_tr, m_tr = t_tr[:day_limit], r_tr[:day_limit], e_tr[:day_limit], m_tr[:day_limit]
    n_expected = float(np.mean(n_tr[:day_limit]))

    features, policy, day_replay, batch_obj = make_env(B, HORIZON)
    obj_jit = jax.jit(batch_obj)
    obj_grad = jax.jit(jax.value_and_grad(lambda p, t, r, e, m, ne:
                                          batch_obj(p, t, r, e, m, ne)[0], argnums=0))
    vec_params = jax.jit(jax.vmap(lambda leaves: leaves, in_axes=0)) if False else None

    rng = jax.random.PRNGKey(args.seed)
    params = init_params(rng)
    flat, treedef = jax.tree_util.tree_flatten(params)
    n_par = int(sum(x.size for x in flat))

    def unflatten(vec):
        shapes = [x.shape for x in flat]
        sizes = [int(np.prod(s)) for s in shapes]
        out, i = [], 0
        for s, n in zip(shapes, sizes):
            out.append(vec[i:i + n].reshape(s))
            i += n
        return jax.tree_util.tree_unflatten(treedef, out)

    mu = jnp.concatenate([x.ravel() for x in flat])
    m_adam = jnp.zeros_like(mu)
    v_adam = jnp.zeros_like(mu)
    beta1, beta2, eps = 0.9, 0.999, 1e-8

    def eval_mu(vec):
        p = unflatten(vec)
        total, acc, brem = obj_jit(p, t_tr, r_tr, e_tr, m_tr, n_expected)
        return float(total), float(acc), float(brem)

    curve = []
    t0 = time.time()
    for it in range(args.iters):
        # 对偶采样
        rng, sub = jax.random.split(rng)
        noise = jax.random.normal(sub, (args.pop // 2, n_par))
        eps_pair = jnp.concatenate([noise, -noise], axis=0)
        totals = []
        for k in range(args.pop):
            vec = mu + args.sigma * eps_pair[k]
            p = unflatten(vec)
            total, _, _ = obj_jit(p, t_tr, r_tr, e_tr, m_tr, n_expected)
            totals.append(total)
        totals = jnp.stack(totals)
        # 适应度整形（rank-based, 抗尺度）
        ranks = jnp.argsort(jnp.argsort(totals)).astype(jnp.float32)
        shaped = ranks / (args.pop - 1) - 0.5
        grad = jnp.mean(shaped[:, None] * eps_pair, axis=0) / args.sigma
        # Adam
        m_adam = beta1 * m_adam + (1 - beta1) * grad
        v_adam = beta2 * v_adam + (1 - beta2) * (grad ** 2)
        mhat = m_adam / (1 - beta1 ** (it + 1))
        vhat = v_adam / (1 - beta2 ** (it + 1))
        mu = mu - args.lr * mhat / (jnp.sqrt(vhat) + eps)
        if it % 10 == 0 or it == args.iters - 1:
            total, acc, brem = eval_mu(mu)
            curve.append(dict(it=it, train_revenue=total, train_accepted=acc,
                              train_budget_remaining=brem, elapsed_s=time.time() - t0))
            print('it=%4d  revenue=%9.2f  accepted=%6.1f  budget_left=%8.2f  %.1fs'
                  % (it, total, acc, brem, time.time() - t0), flush=True)

    # ---- 评估：把学到的 λ 策略回放到 GATE 面板，与静态/动态对偶对照（表级收入） ----
    from admission.controller import AdmissionController, OrderView
    from admission.policies import e_lower_of

    p_final = unflatten(mu)
    day_fn = jax.jit(day_replay)
    totals_g, accs_g = [], []
    for d in range(min(5, t_ga.shape[0])):
        total, acc, brem = day_fn(p_final, jnp.asarray(t_ga[d]), jnp.asarray(r_ga[d]),
                                  jnp.asarray(e_ga[d]), jnp.asarray(m_ga[d]),
                                  jnp.float32(n_expected))
        totals_g.append(float(total))
        accs_g.append(float(acc))

    # 静态 / 动态对偶的同期对照（同一批 GATE 天，表级收入口径）
    lam_grid = build_lambda_grid()
    clock_grid = build_clock_grid(HORIZON)
    g_tab = calibrate(build_train_days(train, OBJECTIVE), OBJECTIVE, HORIZON,
                      lam_grid, clock_grid)
    lam0 = float(RegisteredShadowPrice(lam_grid, clock_grid, g_tab).lambda_for(0.0, B)[0])

    def day_orders(ds, d):
        dem = np.asarray(ds['demands'])[d]
        rev_t = np.asarray(ds['reveal_time'])[d]
        cls_t = np.asarray(ds['temp_class'])[d]
        idx = np.where(dem > 0)[0]
        idx = idx[np.argsort(rev_t[idx], kind='stable')]
        out = []
        for k, o in enumerate(idx):
            c = int(cls_t[o])
            q = float(dem[o])
            out.append(OrderView.build(k, c, q, e_lower_of(c, q, OBJECTIVE),
                                       reveal_time=float(rev_t[o])))
        return out

    def make_always():
        return AlwaysAccept()

    def make_static():
        return RegisteredShadowPrice(lam_grid, clock_grid, g_tab)

    def make_dynamic():
        return DynamicDual(eta=0.02, lam0=lam0, lam_max=8.0, n_expected=n_expected)

    cmp_rows = {}
    for name, factory in (('always_accept', make_always), ('static', make_static),
                          ('dynamic_eta0.02', make_dynamic)):
        revs = []
        for d in range(5):
            ctrl = AdmissionController(factory(), budget=B)
            ctrl.begin_day([], horizon=HORIZON)
            for o in day_orders(gate, d):
                ctrl.decide(o, clock=o.reveal_time)
            revs.append(float(ctrl.state.accepted_revenue))
        cmp_rows[name] = revs

    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    np.savez(out / 'learned_price.npz', **{k: np.asarray(v) for k, v in p_final.items()})
    result = dict(stage='learned_price_es', status='DEVELOPMENT_TRAINING',
                  config=vars(args), n_params=n_par, n_expected=n_expected,
                  budget=B, train_days=day_limit,
                  curve=curve,
                  gate_panel_learned_revenue=[round(x, 2) for x in totals_g],
                  gate_panel_learned_accepted=[round(x, 1) for x in accs_g],
                  gate_panel_baselines={k: [round(x, 2) for x in v] for k, v in cmp_rows.items()},
                  limits=('只训练 TRAIN 天；GATE 5 天仅作开发对照；表级收入口径'
                          '（不含距离/品质/TW）；未做显著性检验'))
    (out / 'train.json').write_text(json.dumps(result, indent=2, ensure_ascii=False),
                                    encoding='utf-8')

    def mean(xs):
        return float(np.mean(xs)) if xs else None

    print('\n=== GATE panel (5 days, table-level revenue) ===')
    print('learned_price     %s  mean=%.2f' % ([round(x, 2) for x in totals_g],
                                               mean(totals_g)))
    for k, v in cmp_rows.items():
        print('%-17s %s  mean=%.2f' % (k, [round(x, 2) for x in v], mean(v)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
