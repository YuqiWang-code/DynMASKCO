"""构造 C 的**松弛实例对**证书 v3 —— 按第二轮独立复核重写。

复核 v2 的结论是"算术对、主张与守卫不合格"，因此 v3 只做一件事：
把主张写对、把前提守住、把闭式与网格对齐、把不该主张的删掉。

模型（**松弛**，不是 CC-DVRP-3T 的一般界）
-----------------------------------------
单车辆、单一能耗预算、**两单**、订单**不可分割**、目标 = 被接入订单的收入、
接受即服务（不可撤销）。在此模型下：

* 实例 A = {L}：阶段 1 只有 L（18 °C, r_L=10, e_L=2.1）；
* 实例 C = {L, H}：阶段 1 也只有 L；阶段 2 出现 H（−18 °C, r_H=30, e_H=12.9）；
* 预算 `B = e_H + η`，`0 < η < e_L` ⇒ `e_L + e_H > B`（两单装不下）且 `e_L ≤ B`（L 单独可行）。

两实例在阶段 1 观测相同 ⇒ 任何因果策略在阶段 1 必须做同一决策（以概率 p 接 L 编码）。

结论（**上确界**，不是"任意策略都等于"）
----------------------------------------
* 比值：`ratio_A = p`、`ratio_C = (p·r_L + (1−p)·r_H) / r_H`；
* 确定性最优（p∈{0,1}）：`r_L / r_H`；
* 随机化最优：`p* = r_H / (2·r_H − r_L)`，值 `= p*`（若 `2·r_H ≤ r_L` 则退化为 1）。

⇒ 严谨表述："**任何**因果策略的最坏情形比值**不超过** X，且 X 由某策略**达到**（上确界）"，
**不是**"任意策略都等于 X"。

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

# 与 run_admission_panel.OBJECTIVE 一致的本地副本（复核意见 L-3：panel 侧无 import 出口）
OBJECTIVE = dict(ambient_c=25.0, target_c=[18.0, 4.0, -18.0],
                 precool_energy_per_unit_per_c=0.15)


def _consts():
    from admission.policies import REV, e_lower_of
    return REV, e_lower_of


def _guards(e_L, e_H, B, eta):
    """全部前提显式检查；任一不成立即拒绝输出结论（非零退出）。"""
    problems = []
    if not (0.0 < eta < e_L):
        problems.append('0 < eta < e_L 不成立 (eta=%.6f, e_L=%.6f)' % (eta, e_L))
    if not (e_L + e_H > B + 1e-12):
        problems.append('e_L + e_H <= B：两单可同时服务，构造失效')
    if not (e_L <= B + 1e-12):
        problems.append('e_L > B：L 单独不可行 ⇒ OPT_A = 0、比值无定义（复核 H-2）')
    if not (e_H <= B + 1e-12):
        problems.append('e_H > B：H 单独不可行，构造失效')
    if problems:
        raise SystemExit('INVALID_PREMISE: ' + '; '.join(problems))


def _alg_threshold(rho, r_L, e_L, r_H, e_H, B):
    """密度阈值策略在实例 C 上的精确收益（按到达顺序逐单判定）。"""
    chosen = 0.0
    left = B
    for r, e in ((r_L, e_L), (r_H, e_H)):
        if e <= left + 1e-12 and (r / e) >= rho - 1e-12:
            chosen += r
            left -= e
    return chosen


def build_certificate(q_low=2.0, q_high=2.0, eta_frac=0.5, p_grid=2001):
    REV, e_lower_of = _consts()
    e_L, e_H = e_lower_of(0, q_low, OBJECTIVE), e_lower_of(2, q_high, OBJECTIVE)
    r_L, r_H = float(REV[0]), float(REV[2])
    eta = float(eta_frac) * e_L
    B = e_H + eta
    _guards(e_L, e_H, B, eta)

    opt_A, opt_C = r_L, max(r_L, r_H)          # 两单装不下 ⇒ C 的预知最优取较优单

    # 闭式
    p_star = 1.0 if (2.0 * r_H <= r_L) else r_H / (2.0 * r_H - r_L)
    rand_value = min(p_star, (p_star * r_L + (1.0 - p_star) * r_H) / r_H)
    det_value = min(1.0, r_L / r_H)            # p=1 拿 min(1, r_L/r_H)；p=0 拿 0

    # 网格核对（必须与闭式一致，否则拒绝标 EXACT）
    grid = []
    for p in np.linspace(0.0, 1.0, int(p_grid)):
        ra = p * r_L / opt_A
        rc = (p * r_L + (1.0 - p) * r_H) / opt_C
        grid.append(dict(p=float(p), ratio_A=float(ra), ratio_C=float(rc),
                         worst=float(min(ra, rc))))
    best = max(grid, key=lambda r: r['worst'])
    grid_ok = abs(best['worst'] - rand_value) <= 2.0 / max(int(p_grid) - 1, 1)
    if not grid_ok:
        raise SystemExit('GRID_MISMATCH: 网格最优 %.6f 与闭式 %.6f 不一致（拒绝标 EXACT）'
                         % (best['worst'], rand_value))

    # 阈值子族（显式计算，不再复制）
    rho_rows = []
    for rho in sorted({0.0, (r_L / e_L + r_H / e_H) / 2.0, r_L / e_L, 2 * r_L / e_L,
                       r_H / e_H, 2 * r_H / e_H}):
        a = r_L if r_L / e_L >= rho - 1e-12 else 0.0          # A 只有 L
        c = _alg_threshold(rho, r_L, e_L, r_H, e_H, B)
        rho_rows.append(dict(rho=float(rho), alg_A=float(a), alg_C=float(c),
                             ratio_A=float(a / opt_A), ratio_C=float(c / opt_C),
                             worst=float(min(a / opt_A, c / opt_C))))
    thr_best = max(rho_rows, key=lambda r: r['worst'])

    return dict(
        stage='construct_C_relaxation_pair', status='EXACT_RELAXATION_PAIR_CERTIFICATE',
        model=dict(orders=2, vehicles=1, resource='energy_budget_only',
                   objective='admitted_revenue', divisibility='indivisible',
                   acceptance='irrevocable_immediate', future_info='none'),
        constants_from='admission.policies.{REV,e_lower_of}',
        energy=dict(e_L=e_L, e_H=e_H, budget=B, eta=eta),
        revenue=dict(r_L=r_L, r_H=r_H), density=dict(d_L=r_L / e_L, d_H=r_H / e_H),
        opt=dict(A=opt_A, C=opt_C),
        deterministic=dict(best_worst_ratio=float(det_value)),
        randomized=dict(p_star=float(p_star), best_worst_ratio=float(rand_value),
                        convention='max_p min(E[ALG_A]/OPT_A, E[ALG_C]/OPT_C)，oblivious 对手'),
        threshold_subfamily=dict(best_worst_ratio=float(thr_best['worst']),
                                 rows=rho_rows),
        closed_form=dict(p_star='r_H/(2 r_H - r_L)',
                         value='p_star（若 2 r_H <= r_L 则为 1）',
                         grid_checked=bool(grid_ok), p_grid=int(p_grid)),
        claim=dict(
            quantifier='上确界（sup），对任意因果策略成立；且由某策略达到',
            statement=('在该松弛实例对上，**任何**因果策略的最坏情形比值不超过 '
                       '%.4f（确定性）与 %.4f（随机化，期望意义、oblivious），两者均可达到。'
                       % (det_value, rand_value)),
            not_an_equality=('不主张"每个策略都等于该值"：拒 L 的确定性策略最坏比值为 0，'
                             'p=1 的策略为 %.4f。' % det_value)),
        honesty=dict(
            scope=('单车辆、单一能耗预算、两单、不可分割、目标=被接入收入、接受即服务。'
                   '**不是** CC-DVRP-3T 的一般实例族界，也**不是**确定性策略之外的部署能力：'
                   '本仓库控制器要求策略确定性（同一输入给出逐位相同 Decision）。'),
            indivisibility_load_bearing=('若允许"部分服务"，OPT_C = r_L + r_H·(B−e_L)/e_H > r_H，'
                                         '且"接 L 再部分服务 H"在 A、C 上都得 1 ⇒ 界消失。'),
            no_transfer=('真实族含 200 单/15 车/时间窗/路线能耗，且面板指标是 '
                         'utility = revenue − fuel（不是收入）。**包含**该实例对**不足以**把比值搬到真实族：'
                         '路由与时间窗同时改变 ALG 与 OPT。'),
            no_information_price=('本证书**不**主张信息价格：实例 C 上常数 ρ > d_L 是纯因果的、直接拿 OPT ⇒ '
                                  '该实例信息价格为 0。'),
            randomized_convention=('随机化值按"期望比值 + oblivious 对手"给出；逐实现保证为 0，'
                                   'E[min] 口径为 %.4f。' % (p_star * det_value)),
        ))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--q-low', type=float, default=2.0)
    ap.add_argument('--q-high', type=float, default=2.0)
    ap.add_argument('--eta-frac', type=float, default=0.5)
    ap.add_argument('--p-grid', type=int, default=2001)
    ap.add_argument('--out', default=None)
    args = ap.parse_args(argv)
    cert = build_certificate(args.q_low, args.q_high, args.eta_frac, args.p_grid)
    print('det=%.4f  rand=%.4f (p*=%.4f)  threshold=%.4f  grid_ok=%s'
          % (cert['deterministic']['best_worst_ratio'],
             cert['randomized']['best_worst_ratio'],
             cert['randomized']['p_star'],
             cert['threshold_subfamily']['best_worst_ratio'],
             cert['closed_form']['grid_checked']))
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, 'w', encoding='utf-8') as fh:
            json.dump(cert, fh, indent=2, ensure_ascii=False)
        print('wrote %s' % args.out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
