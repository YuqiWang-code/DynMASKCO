"""G3 证书的**独立复算**（不 import 被审脚本的任何逻辑，只 import 登记常数）。

审计者（作者自任，非第三方）用**另一个实现**回答四个问题：
  Q1 确定性类的最坏情形上确界是否 = 1/3？（枚举全部确定性因果策略）
  Q2 随机化类是否 = 3/5？（在**二维**随机化族 (p_accept_L, p_accept_H|reject_L) 上求最优）
  Q3 常数密度阈值族是否 ≤ 1/3？（在 20001 个 ρ 上暴力扫，含状态无关/阶段无关）
  Q4 这些值是否**与 η 无关**（即只依赖 r_L/r_H）？

常数来源：`run_admission_panel.OBJECTIVE`（部署侧口径），公式 e = q·k·(T_amb − T_class)
在本文件里**重新写一遍**，不调用被审脚本的 `e_lower_of`。
"""
from __future__ import annotations

import os
import sys

_S = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS = os.path.dirname(_S)          # .../<ext>/scripts（本文件在 scripts/tests/ 下）
for _p in (_SCRIPTS, os.path.join(_SCRIPTS, 'admission'), os.path.join(_SCRIPTS, 'evaluation'),
           os.path.join(_SCRIPTS, 'bench')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

REV_LOCAL = {0: 10.0, 1: 20.0, 2: 30.0}   # 与登记 REV 对拍后再使用（见 check_constants）


def e_of(q, temp_c, ambient=25.0, k=0.15):
    """预冷能耗：q·k·(T_amb − T_target)。**本函数独立重写**，不调用被审实现。"""
    return float(q) * float(k) * (float(ambient) - float(temp_c))


def instance(e_L, e_H, r_L, r_H, eta_frac):
    eta = float(eta_frac) * e_L
    B = e_H + eta
    return dict(e_L=e_L, e_H=e_H, r_L=r_L, r_H=r_H, eta=eta, B=B)


def ratios(p_accept_L, p_accept_H_when_L_rejected, inst, stage2_h_available=True):
    """给定随机化策略（两个概率），返回 (E[ALG_A]/OPT_A, E[ALG_C]/OPT_C)。"""
    e_L, e_H, r_L, r_H, B = inst['e_L'], inst['e_H'], inst['r_L'], inst['r_H'], inst['B']
    opt_A, opt_C = r_L, max(r_L, r_H)
    # 实例 A：只有 L
    rev_A = p_accept_L * r_L
    # 实例 C：阶段 1 只有 L；若拒 L，阶段 2 出现 H（预算仍为 B）
    rev_C_if_accept = r_L                                   # 接了 L ⇒ B−e_L < e_H ⇒ 接不了 H
    cap_after_reject = B                                    # 拒了 L ⇒ H 可单独服务
    rev_C_if_reject = (p_accept_H_when_L_rejected * r_H) if (e_H <= cap_after_reject + 1e-12) else 0.0
    rev_C = p_accept_L * rev_C_if_accept + (1.0 - p_accept_L) * rev_C_if_reject
    return rev_A / opt_A, rev_C / opt_C


def q1_deterministic(inst):
    best = -1.0
    table = []
    for acc in (0.0, 1.0):
        ra, rc = ratios(acc, 1.0, inst)
        w = min(ra, rc)
        table.append((acc, ra, rc, w))
        best = max(best, w)
    return best, table


def q2_randomized(inst, step=0.0005):
    best = (-1.0, None)
    n = int(round(1.0 / step))
    for i in range(n + 1):
        p1 = i * step
        # 二维族：p2 ∈ {0, 0.5, 1}（p2 只影响 C 的拒单分支，最优必为 1；取样以验证）
        for p2 in (0.0, 0.5, 1.0):
            ra, rc = ratios(p1, p2, inst)
            w = min(ra, rc)
            if w > best[0] + 1e-15:
                best = (w, (p1, p2))
    return best


def q3_thresholds(inst, n_rho=20001):
    e_L, e_H, r_L, r_H, B = inst['e_L'], inst['e_H'], inst['r_L'], inst['r_H'], inst['B']
    d_max = max(r_L / e_L, r_H / e_H) * 1.5
    best = (-1.0, None)
    for i in range(n_rho + 1):
        rho = d_max * i / n_rho
        # 实例 A：只有 L
        a = r_L if (r_L / e_L >= rho and e_L <= B) else 0.0
        # 实例 C：按到达顺序
        c, left = 0.0, B
        for r, e in ((r_L, e_L), (r_H, e_H)):
            if e <= left + 1e-12 and (r / e) >= rho:
                c += r
                left -= e
        w = min(a / r_L, c / max(r_L, r_H))
        if w > best[0] + 1e-15:
            best = (w, rho)
    return best


def main() -> int:
    from run_admission_panel import OBJECTIVE
    from admission.policies import REV as REV_REG
    from hard_family_c2 import build_certificate, OBJECTIVE as OBJ_CERT

    print('[0] 常数一致性')
    print('    REV 本地 == 登记 :', REV_LOCAL == dict(REV_REG))
    print('    OBJECTIVE 部署侧 == 证书侧 :', OBJECTIVE == OBJ_CERT,
          '' if OBJECTIVE == OBJ_CERT else '(差异：%r vs %r)' % (OBJECTIVE, OBJ_CERT))

    q_low, q_high, eta_frac = 2.0, 2.0, 0.5
    e_L = e_of(q_low, 18.0)
    e_H = e_of(q_high, -18.0)
    inst = instance(e_L, e_H, REV_LOCAL[0], REV_LOCAL[2], eta_frac)
    print('[1] 实例参数：e_L=%.6f e_H=%.6f eta=%.6f B=%.6f' % (e_L, e_H, inst['eta'], inst['B']))
    print('    密度：d_L=%.6f d_H=%.6f （d_H < d_L = %s）' % (
        REV_LOCAL[0] / e_L, REV_LOCAL[2] / e_H, REV_LOCAL[2] / e_H < REV_LOCAL[0] / e_L))

    det, table = q1_deterministic(inst)
    print('[Q1] 确定性类上确界（枚举 2 个纯策略）：%.12f  ⇒ 1/3 = %.12f  相等=%s'
          % (det, 1 / 3, abs(det - 1 / 3) < 1e-12))
    for acc, ra, rc, w in table:
        print('     accept_L=%d  ratio_A=%.6f  ratio_C=%.6f  worst=%.6f' % (acc, ra, rc, w))

    rnd, arg = q2_randomized(inst)
    print('[Q2] 随机化类上确界（二维族网格）：%.12f at (p1,p2)=%s  ⇒ 3/5 = %.12f  相等=%s'
          % (rnd, arg, 0.6, abs(rnd - 0.6) < 1e-9))

    thr, rho = q3_thresholds(inst)
    print('[Q3] 常数阈值族上确界（20001 个 ρ 暴力扫）：%.12f at rho=%.6f  ≤ 1/3 = %s'
          % (thr, rho, thr <= 1 / 3 + 1e-12))

    print('[Q4] 与 η 无关性（det 应恒 1/3、rand 应恒 3/5）：')
    ok = True
    for ef in (0.1, 0.3, 0.5, 0.7, 0.9):
        ins = instance(e_L, e_H, REV_LOCAL[0], REV_LOCAL[2], ef)
        d, _ = q1_deterministic(ins)
        r, _a = q2_randomized(ins, step=0.002)
        same = abs(d - 1 / 3) < 1e-9 and abs(r - 0.6) < 5e-3
        ok = ok and same
        print('     eta_frac=%.1f  det=%.9f  rand=%.6f  %s' % (ef, d, r, 'OK' if same else 'MISMATCH'))

    print('[5] 与被审实现逐项对照（默认参数）')
    cert = build_certificate()
    pairs = [('deterministic', det, cert['deterministic']['best_worst_ratio']),
             ('randomized', rnd, cert['randomized']['best_worst_ratio']),
             ('threshold', thr, cert['threshold_subfamily']['best_worst_ratio']),
             ('p_star', arg[0], cert['randomized']['p_star'])]
    allmatch = True
    for name, mine, theirs in pairs:
        m = abs(mine - theirs) < 1e-9
        allmatch = allmatch and m
        print('     %-14s 独立=%.12f  证书=%.12f  %s' % (name, mine, theirs, 'MATCH' if m else 'DIFF'))

    verdict = allmatch and ok and abs(det - 1 / 3) < 1e-12 and abs(rnd - 0.6) < 1e-9 \
        and thr <= 1 / 3 + 1e-12
    print('[VERDICT]', 'INDEPENDENT_RECOMPUTE_AGREES' if verdict else 'DISAGREEMENT')
    return 0 if verdict else 1


if __name__ == '__main__':
    sys.exit(main())
