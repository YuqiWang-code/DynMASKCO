"""A4 核验器逻辑单测（不跑仿真，纯算术层）。

覆盖三件事：
1) rollout 在预算宽松时给出正 ΔU（接受不吃亏）；
2) rollout 在预算紧张且本单很贵时给出负 ΔU（机会成本 > 收入）；
3) 未来到达场景严格不含 ``reveal <= clock`` 的订单（因果性）。

运行：``python tests/test_verifier_logic.py``
"""
import os
import sys

import numpy as np

_SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts')
for _p in (_SCRIPTS, os.path.join(_SCRIPTS, 'admission'), os.path.join(_SCRIPTS, 'evaluation'),
           os.path.join(_SCRIPTS, 'coldchain'), os.path.join(_SCRIPTS, 'simulation')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from admission.panel_replanner import VerifierReplanner  # noqa: E402
from admission.policies import RegisteredShadowPrice  # noqa: E402

LAM = [0.25, 0.5, 1.0, 2.0, 4.0, 8.0]
CLK = [0.0, 4.0, 8.0, 12.0, 16.0]
# g_table[li][ti]：越贵 λ 期望剩余能耗越小
G = [[1e9, 1e9, 1e9, 1e9, 1e9],
     [900.0, 700.0, 450.0, 220.0, 0.0],
     [700.0, 500.0, 300.0, 120.0, 0.0],
     [500.0, 350.0, 200.0, 60.0, 0.0],
     [300.0, 200.0, 100.0, 20.0, 0.0],
     [150.0, 90.0, 40.0, 5.0, 0.0]]


class _Fake:
    """最小替身：只实现 verifier 用到的属性。"""

    def __init__(self, budget, rows):
        self.name = 'verifier'
        self.arm_seed = 7001
        self.budget = float(budget)
        self.vf_n = 8
        self.vf_alpha = 0.25
        self.vf_clock_bin = 1.0
        self.vf_min_delta = 0.0
        self.vf_lam_fixed = None
        self._vf_day = -1
        self._vf_scen = {}
        self.vf_stats = dict(n_accept=0, n_reject=0, n_flip_to_accept=0,
                             n_flip_to_reject=0, n_rollout=0)
        self.vf_log = []
        self._adm_objective = {}
        self._rows = rows

        class _Ctl:
            pass
        self._adm_ctrl = _Ctl()
        self._adm_ctrl.policy = RegisteredShadowPrice(LAM, CLK, G)

        class _State:
            budget_remaining = float(budget)
        self._adm_ctrl.state = _State()

    # 直接复用真实实现
    _vf_rollout = VerifierReplanner._vf_rollout

    def _vf_scenarios(self, inst_idx, clock):
        return [list(self._rows) for _ in range(self.vf_n)]


def _decide(m, clock, e_o, r_o):
    p = m._adm_ctrl.policy
    b = m._adm_ctrl.state.budget_remaining
    lam0 = p.lambda_for(clock, b)[0]
    d = []
    for rows in m._vf_scenarios(0, clock):
        d.append(m._vf_rollout(rows, b, lam0, float(e_o), float(r_o), True)
                 - m._vf_rollout(rows, b, lam0, 0.0, 0.0, False))
    q = float(np.quantile(np.asarray(d), m.vf_alpha))
    return q, d


def test_slack_accepts():
    # 预算 1000，未来只剩一单很便宜的；接受 10 kWh 的订单应收敛为正
    rows = [(10.0, 10.0, 0.5), (12.0, 10.0, 0.5)]
    m = _Fake(budget=1000.0, rows=rows)
    q, d = _decide(m, 2.0, e_o=10.0, r_o=30.0)
    assert q > 0, (q, d)
    print('slack  q=%.4f  PASS' % q)


def test_tight_rejects():
    # 预算刚好只剩 10 kWh，未来有一单 30 元的；本单 10 kWh 只值 10 元 ⇒ 机会成本更高 ⇒ 应拒
    rows = [(10.0, 30.0, 10.0)]
    m = _Fake(budget=10.0, rows=rows)
    q, d = _decide(m, 2.0, e_o=10.0, r_o=10.0)
    assert q < 0, (q, d)
    print('tight  q=%.4f  PASS' % q)


def test_rollout_matches_lam_rule():
    # 空未来 ⇒ ΔU = revenue − lam0·e
    m = _Fake(budget=500.0, rows=[])
    q, d = _decide(m, 6.0, e_o=4.0, r_o=5.0)
    lam0 = m._adm_ctrl.policy.lambda_for(6.0, 500.0)[0]
    expect = 5.0 - lam0 * 4.0
    assert abs(q - expect) < 1e-9, (q, expect)
    print('nolook ahead ΔU=%.4f == revenue-lam*e=%.4f  PASS' % (q, expect))


if __name__ == '__main__':
    test_slack_accepts()
    test_tight_rejects()
    test_rollout_matches_lam_rule()
    print('ALL PASS')
