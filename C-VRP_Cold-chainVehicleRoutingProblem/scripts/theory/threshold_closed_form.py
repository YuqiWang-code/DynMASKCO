"""B4：阈值类（常数密度阈值 ρ）的**解析**上界与随机化闭式解 —— 精确有理数，无浮点。

被替换的证据：``audit_g3_recompute.q3_thresholds`` 的 20001 点 ρ 网格扫描。

模型（与 ``audit_g3_recompute`` 同一登记口径，本文件独立重写）
------------------------------------------------------------
* 预冷能耗 ``e = q·k·(T_amb − T_class)``，``k=0.15, T_amb=25``；
* ``e_L``（18℃）、``e_H``（−18℃）；收入 ``r_L < r_H``；预算 ``B = e_H + η``，``0 ≤ η < e_L``；
* 实例 A：只有 L；实例 C：先 L，若拒 L 则出现 H（预算仍为 B）；
* ``OPT_A = r_L``，``OPT_C = r_H``；
* 常数密度阈值策略：``accept ⟺ r/e ≥ ρ``，且须 ``e ≤ 剩余预算``。

结论（见 ``docs/04_实施与结果/2026-10-20_定理线B4_阈值类解析上界.md``）
---------------------------------------------------------------------
命题 a：对任意 ``ρ ≥ 0``，最坏竞争比 ``w(ρ) = (r_L/r_H)·1[ρ ≤ d_L]``
        ⇒ ``sup_ρ w(ρ) = r_L/r_H = 1/3``，且**与 d_H 的大小关系无关**；
命题 b：阈值族的**随机化**混合同样达到 LP 值 ``3/5``
        （``x=3/5`` 取"接 L"、``2/5`` 取"拒 L"），故 1/3 → 3/5 的差距**只来自随机化**，
        不来自阈值结构本身；
命题 c：20001 点网格扫描**原理上**只能看到 1/3（因为 w 是分段常数，取值只有
        ``{0, r_L/r_H}``），所以"阈值族 ≤ 1/3"不能写成"阈值族被排除"。

运行：``python scripts/theory/threshold_closed_form.py``（退出码 0 = 全部断言通过）
"""
from __future__ import annotations

from fractions import Fraction as F

K = F(15, 100)          # k = 0.15
T_AMB = F(25)
T_L = F(18)
T_H = F(-18)
Q = F(2)                # 每单数量（登记实例）
REV = {0: F(10), 1: F(20), 2: F(30)}


def e_of(cls: int) -> F:
    """预冷能耗（登记口径，精确有理数）。"""
    t = T_L if cls == 0 else T_H
    return Q * K * (T_AMB - t)


def make_inst(eta_frac: F):
    e_L = e_of(0)
    e_H = e_of(2)
    eta = eta_frac * e_L
    return dict(e_L=e_L, e_H=e_H, r_L=REV[0], r_H=REV[2], eta=eta, B=e_H + eta)


def payoff_threshold(inst, rho: F):
    """常数密度阈值策略在两实例上的收入（精确）。"""
    e_L, e_H, r_L, r_H, B = inst['e_L'], inst['e_H'], inst['r_L'], inst['r_H'], inst['B']
    d_L, d_H = r_L / e_L, r_H / e_H
    # 实例 A
    a = r_L if (d_L >= rho and e_L <= B) else F(0)
    # 实例 C：L 先到
    c, left = F(0), B
    if e_L <= left and d_L >= rho:
        c += r_L
        left -= e_L
    if e_H <= left and d_H >= rho:
        c += r_H
        left -= e_H
    return a, c


def worst_ratio(inst, rho: F) -> F:
    a, c = payoff_threshold(inst, rho)
    ra = a / inst['r_L']
    rc = c / inst['r_H']
    return min(ra, rc)


def analytic(inst, rho: F) -> F:
    """命题 a 的闭式：w(ρ) = (r_L/r_H)·1[ρ ≤ d_L]。"""
    r_L, r_H = inst['r_L'], inst['r_H']
    d_L = r_L / inst['e_L']
    return (r_L / r_H) if rho <= d_L else F(0)


def intervals(inst):
    """ρ 轴上的精确分段点：0、min(d_L,d_H)、max(d_L,d_H)、∞。"""
    d_L = inst['r_L'] / inst['e_L']
    d_H = inst['r_H'] / inst['e_H']
    lo, hi = min(d_L, d_H), max(d_L, d_H)
    return [F(0), lo, hi, None]


def reps(inst):
    """每个开区间的有理代表点 + 端点本身。"""
    cuts = intervals(inst)
    out = []
    for i in range(len(cuts) - 1):
        left = cuts[i]
        right = cuts[i + 1]
        out.append(('cut[%d]=%s' % (i, left), left))
        if right is None:
            out.append(('int[%d] open→+' % i, left + F(1) / F(1000)))
        else:
            out.append(('int[%d] (%s,%s)' % (i, left, right), (left + right) / 2))
    return out


def threshold_mixture_lp(inst):
    """阈值两纯策略（接 L / 拒 L）的混合 LP：精确解 = 3/5。"""
    # 纯策略收益向量：接 L ⇒ (实例A, 实例C) = (r_L, r_L)；拒 L ⇒ (0, r_H)
    v_accept = (F(1), inst['r_L'] / inst['r_H'])
    v_reject = (F(0), F(1))
    # x = 接 L 的概率；最坏比 = min(x·1, x·(r_L/r_H) + (1−x)·1)
    best = (F(-1), None)
    for i in range(0, 1001):
        x = F(i, 1000)
        w = min(x * v_accept[0] + (1 - x) * v_reject[0],
                x * v_accept[1] + (1 - x) * v_reject[1])
        if w > best[0]:
            best = (w, x)
    # 解析解：x* = r_H/(r_H + r_L·(1−...)) 由 1−2x/3 = x ⇒ x = 3/5（当 r_L/r_H=1/3）
    x_star = (v_reject[1] - v_reject[0]) / ((v_accept[0] - v_reject[0])
                                           + (v_reject[1] - v_accept[1]))
    w_star = x_star
    return best, x_star, w_star


def grid_scan(inst, n=20001):
    """复刻 20001 点网格扫描（仅作为"原理上只能看到什么"的对照）。"""
    d_max = max(inst['r_L'] / inst['e_L'], inst['r_H'] / inst['e_H']) * F(3, 2)
    best = (F(-1), None)
    seen = set()
    for i in range(n + 1):
        rho = d_max * F(i, n)
        w = worst_ratio(inst, rho)
        seen.add(w)
        if w > best[0]:
            best = (w, rho)
    return best, sorted(seen)


def main() -> int:
    ok = True
    for eta_frac in (F(1, 10), F(1, 2), F(9, 10)):
        inst = make_inst(eta_frac)
        d_L = inst['r_L'] / inst['e_L']
        d_H = inst['r_H'] / inst['e_H']
        print('[inst] eta_frac=%s  e_L=%s e_H=%s B=%s  d_L=%s d_H=%s  d_H<d_L=%s'
              % (eta_frac, inst['e_L'], inst['e_H'], inst['B'], d_L, d_H, d_H < d_L))
        # (1) 逐段核对闭式
        for tag, rho in reps(inst):
            w = worst_ratio(inst, rho)
            an = analytic(inst, rho)
            same = (w == an)
            ok = ok and same
            print('   %-22s rho=%-12s w=%-8s closed=%-8s %s'
                  % (tag, rho, w, an, 'OK' if same else 'DIFF'))
        # (2) 随机取有理点再核一遍闭式
        import random
        random.seed(11)
        for _ in range(200):
            rho = F(random.randint(0, 500), 100)
            w, an = worst_ratio(inst, rho), analytic(inst, rho)
            if w != an:
                ok = False
                print('   RANDOM DIFF rho=%s w=%s closed=%s' % (rho, w, an))
        # (3) 上确界 = 1/3，且混合同样可达 3/5
        best, x_star, w_star = threshold_mixture_lp(inst)
        sup_w = max(worst_ratio(inst, r) for _t, r in reps(inst))
        sup_ok = (sup_w == inst['r_L'] / inst['r_H'])
        mix_ok = (best[0] == F(3, 5))
        ok = ok and sup_ok and mix_ok
        print('   sup_rho w = %s (=r_L/r_H=%s) %s' % (sup_w, inst['r_L'] / inst['r_H'],
                                                     'OK' if sup_ok else 'FAIL'))
        print('   deterministic sup = max over pure = %s'
              % max(min(F(1), inst['r_L'] / inst['r_H']), min(F(0), F(1))))
        print('   mixture best = %s at x(accept L)=%s ; closed-form x*=%s w*=%s  %s'
              % (best[0], best[1], x_star, w_star, 'OK' if mix_ok else 'FAIL'))
        # (4) 网格扫描取值集合（证明原理上只能看到 {0, 1/3}）
        (gb, gbest), seen = grid_scan(inst, n=2001)
        only = set(seen) <= {F(0), inst['r_L'] / inst['r_H']}
        ok = ok and only
        print('   grid(2001) best=%s at rho=%s ; distinct values=%s ; 只取 {0,1/3}=%s'
              % (gb, gbest, [str(v) for v in seen], only))
        print()
    print('[VERDICT]', 'ALL ASSERTIONS PASS' if ok else 'FAILURE')
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
