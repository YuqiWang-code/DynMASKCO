"""构造 C 的**实例对**证书（v2，独立复核后的重做版）。

为什么重做
----------
v1（`hard_family.py`）被独立复核判 `UNPROVEN`，两处 HIGH：
1. "信息价格 = 2/3" 错误 —— 常数 ρ>d_L 是纯因果的、在该实例上就拿到 OPT；
2. 证书只覆盖"单值、阶段无关"的 ρ。

本版按复核建议改成**实例对**（两实例在阶段 1 的观测完全相同）：

* 实例 A = {只有 L}：阶段 1 揭示 L（18 °C, q=2, e_L=2.1, r_L=10）；
* 实例 C = {L 然后 H}：阶段 1 同样只有 L；阶段 2 揭示 H（−18 °C, q=2, e_H=12.9, r_H=30）；
* 预算 `B = e_H + η`，`0 < η < e_L` ⇒ 两单装不下。

于是任何因果策略在阶段 1 必须对两实例做**同一个**决策（观测相同）：

| 阶段 1 决策 | 实例 A 比值 | 实例 C 比值 | 最坏 |
|---|---:|---:|---:|
| 接 L（确定性） | 10/10 = 1 | 10/30 = 1/3 | **1/3** |
| 拒 L（确定性） | 0/10 = 0 | 0/30 = 0 | 0 |
| 以 p 接 L（随机化） | p | `(10p + 30(1−p))/30` | `min(p, 1 − (2/3)p)` |

随机化的最优点 `p = 3/5` ⇒ 最坏比值 **3/5**。

诚实结论：**确定性 1/3、随机化 3/5**（不是"2/3 的信息价格"）。

常量来源
--------
`admission.policies.REV` 与 `admission.policies.e_lower_of`（登记源），不再硬编码。

用法::

    python scripts/bench/hard_family_c2.py --out docs/04_实施与结果/certificates/hard_C_pair.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

_S = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_S, os.path.join(_S, 'admission')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

OBJECTIVE = dict(ambient_c=25.0, target_c=[18.0, 4.0, -18.0],
                 precool_energy_per_unit_per_c=0.15)


def _consts():
    """从登记源取常量（复核意见 #9）。"""
    from admission.policies import REV, e_lower_of
    return REV, e_lower_of


def build_certificate(q_low=2.0, q_high=2.0, eta_frac=0.5, p_grid=101):
    REV, e_lower_of = _consts()
    eL, eH = e_lower_of(0, q_low, OBJECTIVE), e_lower_of(2, q_high, OBJECTIVE)
    rL, rH = float(REV[0]), float(REV[2])
    eta = float(eta_frac) * eL
    B = eH + eta
    if not (0.0 < eta < eL):
        raise SystemExit('INVALID_PREMISE: 需要 0 < eta < e_L')
    if not (eL + eH > B + 1e-12):
        raise SystemExit('INVALID_PREMISE: 需要 e_L + e_H > B（否则两单可同时服务）')

    # 两实例的预知最优
    opt_a = rL                      # A 只有 L
    opt_c = max(rL, rH)             # C：B 装不下两单，取较优
    # 因果策略：阶段 1 决策 p（接 L 的概率），阶段 2 在 C 中若能装下就接 H
    rows = []
    for p in np.linspace(0.0, 1.0, int(p_grid)):
        alg_a = p * rL
        # C：接 L 的部分把预算吃光（e_L + e_H > B），因此 H 只在"未接 L"时可得
        alg_c = p * rL + (1.0 - p) * rH
        ra, rc = alg_a / opt_a, alg_c / opt_c
        rows.append(dict(p=float(p), ratio_A=float(ra), ratio_C=float(rc),
                         worst=float(min(ra, rc))))
    best = max(rows, key=lambda r: r['worst'])
    det = [r for r in rows if r['p'] in (0.0, 1.0)]
    det_best = max(det, key=lambda r: r['worst'])

    # 顺带：密度阈值子族（ρ ≤ d_L 等价于 p=1；ρ > d_L 等价于 p=0）
    dL = rL / eL
    dH = rH / eH
    return dict(
        stage='hard_family_construct_C_pair', status='EXACT_PAIR_CERTIFICATE',
        constants_from='admission.policies.{REV,e_lower_of}',
        energy=dict(e_L=eL, e_H=eH, budget=B, eta=eta),
        revenue=dict(r_L=rL, r_H=rH), density=dict(d_L=dL, d_H=dH),
        opt=dict(instance_A=opt_a, instance_C=opt_c),
        deterministic=dict(best_p=float(det_best['p']), worst_ratio=float(det_best['worst'])),
        randomized=dict(best_p=float(best['p']), worst_ratio=float(best['worst'])),
        threshold_subfamily=dict(
            note='密度阈值族只能取 p∈{0,1}（ρ≤d_L 或 ρ>d_L）',
            best_worst_ratio=float(det_best['worst'])),
        grid=rows,
        claim=dict(
            statement=('对任意因果策略：确定性最坏比值 = 1/3，随机化最坏比值 = %.4f（p=%.2f）；'
                       '密度阈值子族只能取到 1/3。' % (best['worst'], best['p'])),
            quantifier='任意因果（含随机化）策略，限定于本实例对'),
        honesty=dict(
            scope=('两单、一辆车、单一能耗预算；不含路由/时间窗/多车。'
                   '两个实例在阶段 1 的观测相同，这是配对论证成立的关键前提。'),
            not_a_theorem=('这是**实例对**上的精确界，不是 CC-DVRP-3T 一般实例族的下界；'
                           '要成为定理需证明真实问题族包含此类实例对。'),
            no_information_price_claim=('本证书**不**主张"信息价格"：在实例 C 上常数 ρ>d_L 是纯因果的，'
                                        '该实例信息价格为 0；配对给出的是**最坏情形比值**。'),
            randomized_caveat=('随机化把最坏情形从 1/3 抬到 %.2f —— 与构造 B 的勘误同型：'
                               '两实例论证会被随机化削弱。' % best['worst']),
        ))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--q-low', type=float, default=2.0)
    ap.add_argument('--q-high', type=float, default=2.0)
    ap.add_argument('--eta-frac', type=float, default=0.5)
    ap.add_argument('--p-grid', type=int, default=101)
    ap.add_argument('--out', default=None)
    args = ap.parse_args(argv)
    cert = build_certificate(args.q_low, args.q_high, args.eta_frac, args.p_grid)
    text = json.dumps(cert, indent=2, ensure_ascii=False)
    print(text[:1600])
    print('...')
    print('det=%.4f  rand=%.4f (p=%.2f)' % (cert['deterministic']['worst_ratio'],
                                            cert['randomized']['worst_ratio'],
                                            cert['randomized']['best_p']))
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, 'w', encoding='utf-8') as fh:
            json.dump(cert, fh, indent=2, ensure_ascii=False)
        print('wrote %s' % args.out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
