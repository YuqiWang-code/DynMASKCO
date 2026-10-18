#!/usr/bin/env python
"""构造 B 的精确证书：时间窗起点揭示 ⇒ 密度阈值族无有限竞争比（构造内枚举）。

对应 `docs/05_理论/I-1_信息价格与不可能性_2026-10-18.md` 的命题 B。
两阶段、一辆车、容量 1，可精确枚举：

* 阶段 1（t=0）：k 个低价值订单，收入 ε，占用车辆（容量 1 ⇒ 只能接一个）；
* 阶段 2（t=δ）：1 个高价值订单，收入 1，同样需要那辆车。

密度阈值族 ``accept ⟺ r/e ≥ ρ``（两阶段常数 ρ，e 相同）：

* ρ ≤ d_ε ⇒ 阶段 1 接下一个 ε ⇒ 车辆占满 ⇒ 阶段 2 的 1 接不了 ⇒ ALG = ε；
* ρ > d_ε 且 ρ ≤ d_1 ⇒ 阶段 1 全拒，阶段 2 接 ⇒ ALG = 1；
* ρ > d_1 ⇒ 两阶段全拒 ⇒ ALG = 0。

取 d_ε < d_1（ε 订单的密度更低）⇒ **不存在一个 ρ 同时"拒 ε"又"接 1"** ⇒ 该族在构造 B 上
要么得 ε（与 OPT=k·ε 或 1 比都亏），要么得 0。本脚本把三种情形的 ALG/OPT 精确算出来。

用法::

    python scripts/bench/hard_family_b.py --out results/bench/hard_B_certificate.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys


def evaluate(k, eps, d_eps, d_one):
    """返回每个阈值分段下的 (ALG, OPT, ratio, 决策说明)。"""
    opt_full = max(k * eps, 1.0)          # 预知最优：全接 ε 或接 1
    rows = []
    for name, rho, note in (
            ('rho<=d_eps', d_eps, '接受 ε 订单，车辆被占，高价值订单接不了'),
            ('d_eps<rho<=d_one', (d_eps + d_one) / 2.0, '拒绝 ε 订单，接受高价值订单'),
            ('rho>d_one', d_one * 2.0, '两阶段都拒绝')):
        if name == 'rho<=d_eps':
            alg = eps
        elif name == 'd_eps<rho<=d_one':
            alg = 1.0
        else:
            alg = 0.0
        rows.append(dict(segment=name, rho=float(rho), alg=float(alg),
                         opt=float(opt_full), ratio=float(alg / opt_full), note=note))
    best = max(rows, key=lambda r: r['ratio'])
    return rows, best, opt_full


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--k', type=int, default=20)
    ap.add_argument('--eps', type=float, default=0.05)
    ap.add_argument('--d-eps', type=float, default=1.55)
    ap.add_argument('--d-one', type=float, default=9.52)
    ap.add_argument('--out', default=None)
    args = ap.parse_args(argv)

    rows, best, opt = evaluate(args.k, args.eps, args.d_eps, args.d_one)
    cert = dict(
        stage='hard_family_construct_B', status='EXACT_ENUMERATION_CERTIFICATE',
        params=dict(k=args.k, eps=args.eps, d_eps=args.d_eps, d_one=args.d_one),
        opt_value=float(opt),
        note='OPT 取 max(k*eps, 1)：预知最优可择优，但因果策略在两阶段之间无信息',
        segments=rows, best_segment=best,
        claim=dict(
            statement=('两阶段常数密度阈值无法同时"拒 ε 订单"与"接高价值订单"，'
                       '因为 d_eps < d_one 且 ρ 只能取一个值；故 ALG/OPT ≤ %.4f。'
                       % best['ratio']),
            bound=float(best['ratio']),
            mechanism='容量 1 + 逐单不可撤销承诺 ⇒ 阶段 1 的接受会不可逆地封死阶段 2'),
        honesty=dict(
            scope='两阶段、一辆车、容量 1、收入/密度外生给定；不含路由、时间窗冲突与多车',
            not_a_theorem=('这是实例级枚举，不是一般性下界定理；对任意（含随机化/带信念）'
                           '因果策略的下界需要额外论证'),
            relation=('机制与 Chawla & Christou (APPROX/RANDOM 2024) 的"无预测 ⇒ 无有限竞争比"'
                      '同型；本项目只是把它做成冷链可执行实例流，不声称新竞争比结果'),
        ))
    print(json.dumps(cert, indent=2, ensure_ascii=False))
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, 'w', encoding='utf-8') as fh:
            json.dump(cert, fh, indent=2, ensure_ascii=False)
        print('\nwrote %s' % args.out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
