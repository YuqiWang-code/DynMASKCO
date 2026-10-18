#!/usr/bin/env python
"""构造 B 的**两实例**精确下界（替代已被否掉的单实例枚举）。

对应 `docs/04_实施与结果/2026-10-18_G3b_构造B表述勘误.md`：不可能性命题是"族对策略"的，
所以必须在**实例对**上取最坏情形，而不是在单个实例上枚举阈值。

模型（与 `StrictOnlineEnv` 的 reveal 语义一致）
------------------------------------------------
* 一条路线、容量 1 ⇒ **一天最多服务 1 单**；
* 阶段 1（t=0）揭示 $k$ 个低价值订单，每单收入 $\epsilon$；
* 阶段 2（t=δ）在实例 $B$ 里再揭示 1 个高价值订单，收入 1；实例 $A$ 里没有；
* 两个实例在阶段 1 的**观测完全相同** ⇒ 任何因果策略在两个实例上必须做同一个阶段 1 决策。

预知最优：$OPT_A = \epsilon$（容量 1，只能服务 1 个 $\epsilon$ 单），$OPT_B = 1$。

结论（可手算，脚本只是把数算出来）
----------------------------------
令策略在阶段 1 接受的概率为 $p$（确定性策略 $p\in\{0,1\}$；随机化允许 $p\in[0,1]$）：

* 实例 $A$：$\mathbb{E}[ALG_A] = p\epsilon$（接了就没别的可接），$OPT_A=\epsilon$ ⇒ 比值 $p$；
* 实例 $B$：$\mathbb{E}[ALG_B] = p\epsilon + (1-p)\cdot 1$，$OPT_B=1$ ⇒ 比值 $p\epsilon + 1 - p$。

最坏情形比值 $= \min(p,\; p\epsilon + 1 - p)$。因 $\epsilon < 1$，$p\epsilon+1-p \ge p$ 当且仅当 $1-p \ge p(1-\epsilon)$，
于是 $\min$ 在 $p=1$ 处取到最大值 $\epsilon$。⇒ **对任意（含随机化）因果策略，竞争比 $\le \epsilon$**，
令 $\epsilon\to 0$ 即得"无有限竞争比"。

用法::

    python scripts/bench/hard_family_b2.py --out results/bench/hard_B_certificate.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys


def worst_case_ratio(p, k, eps):
    """给定阶段 1 接受概率 p，返回 (A 比值, B 比值, 最坏情形比值)。"""
    ratio_a = (p * eps) / eps                 # OPT_A = eps
    ratio_b = (p * eps + (1.0 - p) * 1.0) / 1.0
    return ratio_a, ratio_b, min(ratio_a, ratio_b)


def build(k=20, eps=0.05):
    grid = [i / 20.0 for i in range(21)]      # p = 0, 0.05, ..., 1
    rows = []
    for p in grid:
        a, b, w = worst_case_ratio(p, k, eps)
        rows.append(dict(p=float(p), ratio_instance_A=float(a),
                         ratio_instance_B=float(b), worst=float(w)))
    best = max(rows, key=lambda r: r['worst'])
    return dict(
        stage='hard_family_construct_B_two_instance',
        status='EXACT_TWO_INSTANCE_BOUND',
        params=dict(k=k, eps=eps, capacity=1, orders_per_day=1,
                    note='两个实例在阶段 1 观测完全相同 ⇒ 阶段 1 决策必须相同'),
        opt=dict(instance_A=eps, instance_B=1.0),
        grid=rows,
        bound=dict(best_worst_ratio=float(best['worst']), at_p=float(best['p']),
                   equals_eps=bool(abs(best['worst'] - eps) < 1e-12),
                   statement=('对任意因果策略（含随机化），最坏情形竞争比 ≤ ε = %.4f；'
                              'ε 可任意小 ⇒ 该实例族上不存在有限竞争比。' % eps)),
        supersedes=dict(
            script='scripts/bench/hard_family_b.py',
            why=('单实例枚举把容量 1 的 OPT 写成 max(k·ε, 1)，属建模错误；'
                 '单实例也只能给出"某策略在某实例上亏"，给不出不可能性'),
            record='docs/04_实施与结果/2026-10-18_G3b_构造B表述勘误.md'),
        honesty=dict(
            scope=('一天一条路线、容量 1、最多服务 1 单；收入与 ε 外生给定；'
                   '不含路由、时间窗冲突、多车与能耗'),
            not_a_theorem=('这是**该实例对**上的精确界，不是 CC-DVRP-3T 一般实例族的下界；'
                           '要用它谈"无有限竞争比"，需说明真实问题族包含此类实例对'),
            relation=('与 Chawla & Christou (APPROX/RANDOM 2024) 的"无预测 ⇒ 无有限竞争比"'
                      '同型；本项目只做冷链实例化，不声称新竞争比结果'),
        ))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--k', type=int, default=20)
    ap.add_argument('--eps', type=float, default=0.05)
    ap.add_argument('--out', default=None)
    args = ap.parse_args(argv)
    cert = build(args.k, args.eps)
    print(json.dumps(cert, indent=2, ensure_ascii=False)[:1200])
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, 'w', encoding='utf-8') as fh:
            json.dump(cert, fh, indent=2, ensure_ascii=False)
        print('\nwrote %s' % args.out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
