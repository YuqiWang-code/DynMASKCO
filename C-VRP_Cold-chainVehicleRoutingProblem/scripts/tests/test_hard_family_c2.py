"""`hard_family_c2.build_certificate` 的单测（复核意见 M-6：闭式必须被断言，不能靠网格 argmax）。

运行::

    python scripts/tests/test_hard_family_c2.py
"""
from __future__ import annotations

import os
import sys

_S = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_S, os.path.join(_S, 'bench'), os.path.join(_S, 'admission')):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _fails(fn):
    try:
        fn()
    except SystemExit:
        return True
    return False


def main() -> int:
    from hard_family_c2 import build_certificate

    checks = []

    cert = build_certificate()
    checks.append(('closed_form_matches_grid', cert['closed_form']['grid_checked'] is True))
    checks.append(('deterministic_1_of_3',
                   abs(cert['deterministic']['best_worst_ratio'] - 1.0 / 3.0) < 1e-9))
    checks.append(('randomized_3_of_5',
                   abs(cert['randomized']['best_worst_ratio'] - 0.6) < 1e-9))
    checks.append(('p_star_3_of_5', abs(cert['randomized']['p_star'] - 0.6) < 1e-9))
    # 闭式再算一遍，独立于脚本内部
    rL, rH = cert['revenue']['r_L'], cert['revenue']['r_H']
    p_star = rH / (2.0 * rH - rL)
    checks.append(('p_star_formula', abs(p_star - cert['randomized']['p_star']) < 1e-9))
    # 阈值子族显式计算，应等于确定性最优（ρ ≤ d_L 时接 L）
    checks.append(('threshold_equals_det',
                   abs(cert['threshold_subfamily']['best_worst_ratio']
                       - cert['deterministic']['best_worst_ratio']) < 1e-9))
    # 前提守卫：e_L > B 必须拒绝
    checks.append(('guard_eL_le_B', _fails(lambda: build_certificate(q_high=0.1))))
    # 前提守卫：eta_frac = 1.0 使 eta == e_L，必须拒绝
    checks.append(('guard_eta_positive', _fails(lambda: build_certificate(eta_frac=0.0))))
    # 粗网格必须被**拒绝**（复核第三轮 §5：p_grid 太小时闭式检查可被绕过）
    checks.append(('coarse_grid_rejected', _fails(lambda: build_certificate(p_grid=11))))

    ok = all(v for _, v in checks)
    for name, v in checks:
        print('%-26s %s' % (name, 'PASS' if v else 'FAIL'))
    print('verdict:', 'ALL_PASS' if ok else 'FAIL')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
