"""接拒控制器单测（纯 NumPy，CPU，秒级）。

跑法（从扩展根目录）::

    python scripts/tests/test_admission_controller.py

覆盖
----
T1  登记规则等价：``RegisteredShadowPrice`` 与 evidence root 里的原始
    ``reserving_admission.BudgetReservingAdmission`` 在随机状态上逐条对拍（决策/理由/λ 全等）。
T2  λ 关于剩余预算单调非增（预算越紧，价格越高）。
T3  接受集合关于 λ 单调（λ 越大接受越少），且边界是严格 ``> 0``。
T4  硬预算闸：任何策略在闭环都不越过预算。
T5  BwK 对偶方向性：超支使 λ 上升、欠支使 λ 下降，并夹在 [0, λ_max]。
T6  因果性：把未来订单截断后，截断点之前的决策逐位不变。
T7  确定性：同一输入两次运行结果逐位相同。
"""
from __future__ import annotations

import importlib.util
import os
import random
import sys

import numpy as np

SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from admission.controller import AdmissionController, OrderView, REV  # noqa: E402
from admission.policies import (DynamicDual, DynamicPriceCurve, FixedThreshold,  # noqa: E402
                                RegisteredShadowPrice, build_clock_grid, build_lambda_grid,
                                calibrate, e_lower_of)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
EVIDENCE = os.path.join(
    ROOT, 'research', 'review_3080_20261010', 'pickup',
    'a1_budget_reserving_admission_root_v4', 'reserving_admission.py')

OBJECTIVE = dict(ambient_c=25.0, target_c=[18.0, 4.0, -18.0],
                 precool_energy_per_unit_per_c=0.15)


# --------------------------------------------------------------------------
# 工具
# --------------------------------------------------------------------------
def load_evidence_module():
    spec = importlib.util.spec_from_file_location('evidence_reserving_admission', EVIDENCE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def make_table(lam_grid, clock_grid, days):
    return calibrate(days, OBJECTIVE, horizon=16.0, lambda_grid=lam_grid,
                     clock_grid=clock_grid)


def synthetic_days(n_days=6, n_orders=120, seed=11):
    rng = np.random.default_rng(seed)
    days = []
    for _ in range(n_days):
        n = int(rng.poisson(n_orders))
        t = np.sort(rng.uniform(0.0, 16.0, n))
        cls = rng.choice(3, size=n, p=[0.5, 0.3, 0.2]).astype(np.int64)
        q = rng.uniform(1.0, 3.0, n)
        est = np.asarray([e_lower_of(int(c), float(qq), OBJECTIVE) for c, qq in zip(cls, q)])
        rv = np.asarray([REV[int(c)] for c in cls], dtype=np.float64)
        days.append((t, est, rv))
    return days


def orders_from_day(day, rng=None):
    t, est, rv = day
    out = []
    for i in range(len(t)):
        cls = 0 if rv[i] == REV[0] else (1 if rv[i] == REV[1] else 2)
        q = est[i] / (OBJECTIVE['precool_energy_per_unit_per_c']
                      * (OBJECTIVE['ambient_c'] - OBJECTIVE['target_c'][cls]))
        out.append(OrderView.build(i, cls, q, float(est[i]), reveal_time=float(t[i])))
    return out


def run_day(policy, orders, budget, horizon=16.0):
    ctrl = AdmissionController(policy, budget=budget)
    ctrl.begin_day(orders, horizon=horizon)
    for o in orders:
        ctrl.decide(o, clock=o.reveal_time)
    return ctrl


# --------------------------------------------------------------------------
# T1 登记规则等价
# --------------------------------------------------------------------------
def t1_registered_equivalence():
    ev = load_evidence_module()
    rng = np.random.default_rng(7)
    lam_grid = build_lambda_grid()
    clock_grid = build_clock_grid(16.0)
    days = synthetic_days()
    g_table = make_table(lam_grid, clock_grid, days)

    # 原始实现需要的 env 形状
    class FakeEnv:
        def __init__(self, cls_row, dem_row):
            self.dataset = {'temp_class': np.asarray(cls_row, dtype=np.int64)[None, :]}
            self.demands = np.asarray(dem_row, dtype=np.float64)[None, :]

    class Original(ev.BudgetReservingAdmission):
        def __init__(self, budget, obj):
            self.budget = float(budget)
            self._accepted = set()
            self._reserving_init(lam_grid, clock_grid, g_table, obj)

    n_checks = 0
    for trial in range(40):
        budget = float(rng.uniform(120.0, 420.0))
        n_orders = int(rng.integers(30, 120))
        cls_row = np.zeros(n_orders + 1, dtype=np.int64)
        dem_row = np.zeros(n_orders + 1, dtype=np.float64)
        t_row = np.zeros(n_orders + 1, dtype=np.float64)
        for o in range(1, n_orders + 1):
            cls_row[o] = int(rng.integers(0, 3))
            dem_row[o] = float(rng.uniform(1.0, 3.0))
            t_row[o] = float(rng.uniform(0.0, 16.0))
        env = FakeEnv(cls_row, dem_row)

        orig = Original(budget, OBJECTIVE)
        ours = AdmissionController(
            RegisteredShadowPrice(lam_grid, clock_grid, g_table), budget=budget)
        orders = []
        for o in range(1, n_orders + 1):
            cls = int(cls_row[o])
            q = float(dem_row[o])
            e = e_lower_of(cls, q, OBJECTIVE)
            orders.append(OrderView.build(o, cls, q, e, reveal_time=float(t_row[o])))
        ours.begin_day(orders, horizon=16.0)

        for o in range(1, n_orders + 1):
            clock = float(t_row[o])
            # --- 原件 ---
            token = {}
            orig_ok = orig._reserving_allows(env, 0, clock, o, token)
            # --- 我们的 ---
            view = orders[o - 1]
            dec = ours.decide(view, clock)
            # 同步"已接受"集合（原件用 self._accepted 计算已花能耗）
            if dec.accept:
                orig._accepted.add(o)
            assert dec.accept == bool(orig_ok), (
                'T1 accept 不一致 trial=%d order=%d ours=%s orig=%s' % (trial, o, dec.accept, orig_ok))
            assert dec.reason == token.get('reason'), (
                'T1 reason 不一致 trial=%d order=%d ours=%s orig=%s'
                % (trial, o, dec.reason, token.get('reason')))
            assert abs(dec.e_hat - float(token.get('est', 0.0))) < 1e-12, 'T1 e_hat 不一致'
            assert abs(dec.revenue - float(token.get('revenue', 0.0))) < 1e-12, 'T1 revenue 不一致'
            if token.get('lambda') is not None:
                assert abs(float(dec.lam) - float(token['lambda'])) < 1e-12, (
                    'T1 lambda 不一致 trial=%d order=%d ours=%s orig=%s'
                    % (trial, o, dec.lam, token['lambda']))
                assert dec.lam_bucket == token.get('clock_bucket'), 'T1 clock_bucket 不一致'
            n_checks += 1
    print('  [PASS] T1 登记规则等价: %d 条决策逐条一致' % n_checks)
    return True


# --------------------------------------------------------------------------
# T2 λ 关于预算单调
# --------------------------------------------------------------------------
def t2_lambda_monotone_in_budget():
    lam_grid = build_lambda_grid()
    clock_grid = build_clock_grid(16.0)
    days = synthetic_days()
    g_table = make_table(lam_grid, clock_grid, days)
    pol = RegisteredShadowPrice(lam_grid, clock_grid, g_table)
    prev = None
    for budget in np.linspace(10.0, 900.0, 90):
        lam, li, ti = pol.lambda_for(7.0, float(budget))
        if prev is not None:
            assert lam <= prev + 1e-12, 'T2 预算放宽后 λ 反而升高 (%s -> %s)' % (prev, lam)
        prev = lam
    # 空预算 → 最高价；充足预算 → 最低价
    assert pol.lambda_for(7.0, -1.0)[0] == lam_grid[-1], 'T2 空预算应取网格最高价'
    assert pol.lambda_for(7.0, 1e9)[0] == lam_grid[0], 'T2 充足预算应取网格最低价'
    print('  [PASS] T2 λ 关于剩余预算单调非增（%d 档）' % 90)
    return True


# --------------------------------------------------------------------------
# T3 接受关于 λ 单调 + 严格边界
# --------------------------------------------------------------------------
def t3_accept_monotone_in_lambda():
    orders = [OrderView.build(i, c, 1.0, 10.0) for i, c in enumerate([0, 1, 2])]
    state_accepts = []
    for lam in [0.0, 0.5, 0.99, 1.0, 1.01, 2.0, 3.01]:
        pol = FixedThreshold(theta=lam)
        accepts = [pol.decide(o, 1.0, _StateStub(1e9)).accept for o in orders]
        state_accepts.append((lam, accepts))
    for (lam_a, acc_a), (lam_b, acc_b) in zip(state_accepts, state_accepts[1:]):
        for a, b in zip(acc_a, acc_b):
            assert (not (b and not a)), 'T3 λ 升高后反而接受了更多'
    # ratio: 类0=1.0, 类1=2.0, 类2=3.0（e=10）
    assert state_accepts[2][1] == [True, True, True], 'T3 θ=0.99 应全接受'
    assert state_accepts[3][1] == [True, True, True], 'T3 θ=1.0 边界应接受（>=）'
    assert state_accepts[4][1] == [False, True, True], 'T3 θ=1.01 应拒类 0'
    print('  [PASS] T3 接受集合关于价格单调 + 阈值边界行为正确')
    return True


class _StateStub:
    def __init__(self, budget, spent=0.0):
        self.budget = float(budget)
        self.spent_e = float(spent)
        self.accepted = []
        self.rejected = []
        self.trace = []

    @property
    def budget_remaining(self):
        return self.budget - self.spent_e

    def note(self, decision, order):
        self.trace.append(decision)
        if decision.accept:
            self.accepted.append(order.order_id)
            self.spent_e += order.e_hat
        else:
            self.rejected.append(order.order_id)

    def lambda_path(self):
        return [d.lam for d in self.trace if d.lam is not None]


# --------------------------------------------------------------------------
# T4 预算在闭环下不被越过
# --------------------------------------------------------------------------
def t4_budget_respected():
    lam_grid = build_lambda_grid()
    clock_grid = build_clock_grid(16.0)
    days = synthetic_days()
    g_table = make_table(lam_grid, clock_grid, days)
    day_orders = orders_from_day(days[0])
    total_e = sum(o.e_hat for o in day_orders)
    budget = 0.35 * total_e  # 故意紧
    policies = [
        FixedThreshold(theta=1.5),
        RegisteredShadowPrice(lam_grid, clock_grid, g_table),
        DynamicDual(eta=0.05, lam0=1.0, n_expected=len(day_orders)),
        DynamicPriceCurve(),
    ]
    for pol in policies:
        ctrl = run_day(pol, day_orders, budget)
        s = ctrl.summary()
        assert not s['budget_violated'], 'T4 %s 越界: %.3f > %.3f' % (pol.name, s['spent_e'], budget)
        assert s['spent_e'] <= budget + 1e-9
    print('  [PASS] T4 四种策略闭环均不越预算（budget=%.1f, 订单总能耗=%.1f）' % (budget, total_e))
    return True


# --------------------------------------------------------------------------
# T5 BwK 对偶方向
# --------------------------------------------------------------------------
def t5_dynamic_dual_direction():
    # --- 欠支：每轮配额 100，拒绝单消耗 0 → λ 必须下降并夹在 0 ---
    pol = DynamicDual(eta=0.1, lam0=1.0, lam_max=8.0, n_expected=10)
    st = _StateStub(1000.0)
    pol.reset(st, horizon=16.0, budget=1000.0)   # per_round = 1000/10 = 100
    d = pol.decide(OrderView.build(0, 2, 1.0, 30.0), 1.0, st)  # 30 - 1*30 = 0 → 拒绝
    assert not d.accept, 'T5 阈值相等时应拒绝（严格 > 0）'
    assert pol.lam == 0.0 and d.lam == 1.0, 'T5 欠支未把 λ 压到 0（lam=%s）' % pol.lam

    # --- 超支：每轮配额 5，接受 e=30 → λ 必须上升 ---
    pol2 = DynamicDual(eta=0.1, lam0=0.0, lam_max=8.0, n_expected=200)
    st2 = _StateStub(1000.0)
    pol2.reset(st2, horizon=16.0, budget=1000.0)  # per_round = 5
    d2 = pol2.decide(OrderView.build(0, 2, 1.0, 30.0), 2.0, st2)  # λ=0 → 接受
    assert d2.accept, 'T5 λ=0 时应接受'
    assert abs(pol2.lam - 2.5) < 1e-12, 'T5 超支更新量不对: %s (期望 0.1*(30-5)=2.5)' % pol2.lam
    assert d2.extra.get('lambda_after') == pol2.lam

    # --- 夹紧：每轮配额 0.5，接受 e=1（rev 30）→ 每次 +0.5，必须顶到 lam_max=8 ---
    pol3 = DynamicDual(eta=1.0, lam0=0.0, lam_max=8.0, n_expected=2000)
    st3 = _StateStub(1000.0)
    pol3.reset(st3, horizon=16.0, budget=1000.0)   # per_round = 1000/2000 = 0.5
    assert abs(pol3.per_round_budget - 0.5) < 1e-12
    for _ in range(100):
        pol3.decide(OrderView.build(0, 2, 1.0, 1.0), 3.0, st3)
    assert 0.0 <= pol3.lam <= 8.0 + 1e-12, 'T5 λ 未夹紧: %s' % pol3.lam
    assert pol3.lam == 8.0, 'T5 连续超支后应顶到 lam_max（实际 %s）' % pol3.lam
    print('  [PASS] T5 BwK 对偶方向性（欠支→0、超支→2.5、上限→8.0）与夹紧正确')
    return True


# --------------------------------------------------------------------------
# T6 因果性（截断未来不改过去）
# --------------------------------------------------------------------------
def t6_causality():
    lam_grid = build_lambda_grid()
    clock_grid = build_clock_grid(16.0)
    days = synthetic_days()
    g_table = make_table(lam_grid, clock_grid, days)
    day_orders = orders_from_day(days[1])
    cut = 8.0
    past = [o for o in day_orders if o.reveal_time <= cut]
    full = run_day(RegisteredShadowPrice(lam_grid, clock_grid, g_table), day_orders, 300.0)
    trunc = run_day(RegisteredShadowPrice(lam_grid, clock_grid, g_table), past, 300.0)
    a = [d.as_dict() for d in full.state.trace if d.clock <= cut]
    b = [d.as_dict() for d in trunc.state.trace]
    assert a == b, 'T6 截断未来后过去决策发生变化（%d vs %d 条）' % (len(a), len(b))
    print('  [PASS] T6 因果性：截断未来后 %d 条过去决策逐字段不变' % len(a))
    return True


# --------------------------------------------------------------------------
# T7 确定性
# --------------------------------------------------------------------------
def t7_determinism():
    lam_grid = build_lambda_grid()
    clock_grid = build_clock_grid(16.0)
    days = synthetic_days()
    g_table = make_table(lam_grid, clock_grid, days)
    day_orders = orders_from_day(days[2])
    runs = []
    for _ in range(2):
        ctrl = run_day(DynamicDual(eta=0.05, lam0=1.0, n_expected=len(day_orders)), day_orders, 200.0)
        runs.append([d.as_dict() for d in ctrl.state.trace]
                    + [ctrl.summary()])
    assert runs[0] == runs[1], 'T7 同一输入两次运行结果不同'
    print('  [PASS] T7 确定性：%d 条决策逐位一致' % (len(runs[0]) - 1))
    return True


TESTS = [
    ('T1_registered_equivalence', t1_registered_equivalence),
    ('T2_lambda_monotone_in_budget', t2_lambda_monotone_in_budget),
    ('T3_accept_monotone_in_lambda', t3_accept_monotone_in_lambda),
    ('T4_budget_respected', t4_budget_respected),
    ('T5_dynamic_dual_direction', t5_dynamic_dual_direction),
    ('T6_causality', t6_causality),
    ('T7_determinism', t7_determinism),
]


def main():
    random.seed(0)
    np.random.seed(0)
    failed = 0
    for name, fn in TESTS:
        try:
            ok = fn()
            if not ok:
                failed += 1
                print('  [FAIL] %s 返回 False' % name)
        except AssertionError as exc:
            failed += 1
            print('  [FAIL] %s: %s' % (name, exc))
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print('  [ERROR] %s: %r' % (name, exc))
    print('\n结果: %d/%d 通过' % (len(TESTS) - failed, len(TESTS)))
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
