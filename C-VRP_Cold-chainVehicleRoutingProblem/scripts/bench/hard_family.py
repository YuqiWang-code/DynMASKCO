#!/usr/bin/env python
"""构造 C 的精确证书：制冷预算 ⇒ 不可撤销插入错误，且**任何密度阈值都拿不到最优**。

对应 `docs/05_理论/I-1_信息价格与不可能性_2026-10-18.md` 的命题 C。
本脚本不做仿真：构造 C 只有两单、一辆车、一个能耗预算，**可以精确枚举**，
因此可以给出"逐位可核验"的证书，而不是统计意义上的实验。

模型（与冻结登记口径一致）
--------------------------
* 预冷能耗（`admission.policies.e_lower_of` 的登记式）：
  ``e(c, q) = 0.15 · q · |25 − target_c|``，target = 18 / 4 / −18 ⇒ 系数 7 / 21 / 43。
* 收入：``REV = {0: 10, 1: 20, 2: 30}``（`coldchain_evaluator_a1.REV`）。
* 单资源：制冷能耗预算 ``B``；接受即承诺、拒绝即终局（`StrictOnlineEnv` 的 reveal 语义）。
* 时间窗：两单都可行；L 在 0 时刻揭示，H 在 δ 时刻揭示（δ > 0）。

构造
----
令 ``B = e_H + η``，``0 < η < e_L``。则 ``e_L + e_H > B``：

* 预知最优 ``OPT``：拒绝 L、接受 H ⇒ ``OPT = r_H = 30``（因为 ``r_H > r_L``）。
* 任何"密度阈值"策略 ``accept ⟺ r/e ≥ ρ``：
  - ``ρ ≤ d_L`` ⇒ 接受 L ⇒ 预算只剩 ``B − e_L = e_H + η − e_L < e_H`` ⇒ H 不可服务 ⇒ ``ALG = r_L = 10``；
  - ``ρ > d_L`` ⇒ 拒绝 L；但 ``d_H < d_L``（冷链的收入比 10:20:30 慢于能耗比 7:21:43）
    ⇒ 同样拒绝 H ⇒ ``ALG = 0``。

⇒ 对**所有** ρ，``ALG/OPT ≤ 1/3``，而最优是 1。这是精确陈述，不是统计结论。

用法::

    python scripts/bench/hard_family.py --out results/bench/hard_C_certificate.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys

REV = {0: 10.0, 1: 20.0, 2: 30.0}
PRECOOL = 0.15
AMBIENT = 25.0
TARGET = {0: 18.0, 1: 4.0, 2: -18.0}


def e_lower(class_id: int, q: float) -> float:
    """登记口径的预冷能耗（与 `admission.policies.e_lower_of` 同式）。"""
    return PRECOOL * float(q) * abs(AMBIENT - TARGET[int(class_id)])


def opt_clairvoyant(rL, eL, rH, eH, B):
    """预知最优（两单全枚举）。返回 (value, chosen_subset)。"""
    best, best_s = 0.0, ()
    for name, val, e in (('L', rL, eL), ('H', rH, eH)):
        if e <= B + 1e-12 and val > best:
            best, best_s = val, (name,)
    if eL + eH <= B + 1e-12 and rL + rH > best:
        best, best_s = rL + rH, ('L', 'H')
    return best, best_s


def alg_threshold(rho, rL, eL, rH, eH, B):
    """密度阈值策略 ``accept ⟺ r/e ≥ ρ`` 在构造 C 上的精确收益。"""
    chosen = []
    rem = B
    for name, r, e in (('L', rL, eL), ('H', rH, eH)):
        d = r / max(e, 1e-12)
        if e <= rem + 1e-12 and d >= rho - 1e-12:
            chosen.append(name)
            rem -= e
    return sum((rL if c == 'L' else rH) for c in chosen), tuple(chosen)


def build_certificate(qL=2.0, qH=2.0, eta_frac=0.5):
    """构造 C：返回一个可逐位核对的证书 dict。"""
    eL, eH = e_lower(0, qL), e_lower(2, qH)
    rL, rH = REV[0], REV[2]
    eta = eta_frac * eL
    B = eH + eta
    assert 0.0 < eta < eL, 'need 0 < eta < eL'
    assert eL + eH > B + 1e-12, 'L and H must not both fit'

    opt, opt_set = opt_clairvoyant(rL, eL, rH, eH, B)
    dL, dH = rL / eL, rH / eH

    # 阈值族：在所有"能区分 L"的 ρ 上取最优（ρ 只需落在 (dH, dL] ∪ (dL, ∞) ∪ [0,dH] 三段）
    cands = sorted({0.0, dH, (dH + dL) / 2.0, dL, dL + 1e-9, 2 * dL})
    rows = []
    for rho in cands:
        val, chosen = alg_threshold(rho, rL, eL, rH, eH, B)
        rows.append(dict(rho=float(rho), alg=float(val), chosen=list(chosen),
                         ratio=float(val / opt)))
    best = max(rows, key=lambda r: r['ratio'])

    return dict(
        stage='hard_family_construct_C', status='EXACT_ENUMERATION_CERTIFICATE',
        params=dict(q_low=qL, q_high=qH, eta_frac=eta_frac),
        energy=dict(e_low=eL, e_high=eH, budget=B, eta=eta,
                    note='e_L + e_H > B, so at most one order can be served'),
        revenue=dict(r_low=rL, r_high=rH),
        density=dict(d_low=dL, d_high=dH,
                     note='d_high < d_low: revenue ratio 3x is slower than energy ratio 6.14x'),
        opt=dict(value=float(opt), chosen=list(opt_set)),
        threshold_family=rows,
        best_threshold=best,
        claim=dict(
            statement=('对所有 ρ，ALG(ρ)/OPT ≤ %.4f < 1；因此"接受 ⟺ 密度 ≥ ρ"这一族'
                       '在本实例上无法达到预知最优。' % best['ratio']),
            bound=float(best['ratio']),
            optimal_is_1=True),
        honesty=dict(
            scope=('只覆盖"单资源 + 两单 + 无路由"的接拒抽象；不含容量、时间窗冲突、'
                   '多车派车与路线耦合'),
            not_a_theorem=('这是一个**实例证书**，不是一般性下界定理；要成为定理需要'
                           '参数化族的完整证明与对任意（含随机化）因果策略的下界'),
            connection=('实测侧对应 PANEL-TIER（硬性排除 −18°C 全负）与 PANEL-OKP'
                        '（密度阈值族全负）：本证书解释了为什么这一族**不可能**赢'),
        ))
def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=None)
    ap.add_argument('--q-low', type=float, default=2.0)
    ap.add_argument('--q-high', type=float, default=2.0)
    ap.add_argument('--eta-frac', type=float, default=0.5)
    args = ap.parse_args(argv)
    cert = build_certificate(args.q_low, args.q_high, args.eta_frac)
    print(json.dumps(cert, indent=2, ensure_ascii=False))
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, 'w', encoding='utf-8') as fh:
            json.dump(cert, fh, indent=2, ensure_ascii=False)
        print('\nwrote %s' % args.out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
