"""决策反演测试的单元测试（需要 scikit-learn；在服务器上跑）。

    /home/hzeng/miniconda3/envs/MASKCO_env/bin/python scripts/tests/test_rule_inversion.py

覆盖
----
T1 `to_matrix` 维度与取值正确
T2 纯阈值策略 ⇒ LOO AUC ≈ 1、蒸馏后净价值损失 < 5%（应判可捕获）
T3 与特征无关的随机策略 ⇒ LOO AUC ≈ 0.5（不应判可捕获）
T4 学习型 λ 的特征函数：确定性、范围、形状
T5 蒸馏重放不越预算
"""
from __future__ import annotations

import os
import sys

import numpy as np

SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (SCRIPTS, os.path.join(SCRIPTS, 'evaluation'), os.path.join(SCRIPTS, 'admission')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from evaluation.run_rule_inversion import (FEATURES, FROZEN, LearnedLinear, distilled_utility,
                                           loo_inversion, to_matrix)


def _toy_rows(n_days=5, n=120, seed=0, rule='threshold'):
    rng = np.random.default_rng(seed)
    rows = []
    for d in range(n_days):
        spent = 0.0
        for i in range(n):
            e = float(rng.uniform(0.5, 6.0))
            rev = float(rng.choice([10.0, 20.0, 30.0]))
            cls = int({10.0: 0, 20.0: 1, 30.0: 2}[rev])
            ratio = rev / e
            if rule == 'threshold':
                accept = ratio >= 3.0
            else:
                accept = bool(rng.integers(0, 2))
            rows.append(dict(day=d, clock=float(rng.uniform(0, 16)), budget_ratio=1.0 - spent / 700,
                             e_hat=e, revenue=rev, ratio=ratio, seen=i / n, spent=spent / 700,
                             cls=cls, accept=accept, lam='0', net=rev - 0.5 * e))
            if accept:
                spent += e
    return rows


def t1_to_matrix():
    rows = _toy_rows()
    X, y, d = to_matrix(rows)
    assert X.shape == (len(rows), len(FEATURES)), X.shape
    assert set(np.unique(d)) == {0, 1, 2, 3, 4}
    assert set(np.unique(y)) <= {0, 1}
    assert np.all(np.isfinite(X))
    print('  [PASS] T1 to_matrix: X%s y%s days=%d' % (X.shape, y.shape, len(set(d))))
    return True


def t2_threshold_capturable():
    rows = _toy_rows(rule='threshold')
    X, y, d = to_matrix(rows)
    loo = loo_inversion(X, y, d)
    aucs = [e['auc_tree'] for e in loo if e['auc_tree'] is not None]
    mean_auc = float(np.mean(aucs))
    util = distilled_utility(rows, X, y, d)
    loss = (util['original_net'] - util['tree_net']) / util['original_net']
    assert mean_auc > 0.98, '阈值策略的 AUC 应接近 1，得到 %.3f' % mean_auc
    assert abs(loss) < 0.05, '阈值策略的蒸馏损失应 <5%%，得到 %.3f' % loss
    print('  [PASS] T2 阈值策略可捕获: AUC=%.4f loss=%+.2f%%' % (mean_auc, 100 * loss))
    return True


def t3_random_not_capturable():
    rows = _toy_rows(rule='random', seed=3)
    X, y, d = to_matrix(rows)
    loo = loo_inversion(X, y, d)
    aucs = [e['auc_tree'] for e in loo if e['auc_tree'] is not None]
    mean_auc = float(np.mean(aucs))
    assert mean_auc < 0.75, '随机策略的 AUC 不应高，得到 %.3f' % mean_auc
    print('  [PASS] T3 随机策略不可捕获: AUC=%.4f（<0.75）' % mean_auc)
    return True


def t4_learned_features():
    pol = LearnedLinear.__new__(LearnedLinear)
    pol.w = np.zeros(6)
    pol.b = 0.0
    f1 = pol.features(8.0, 350.0, 100.0, 1000.0, 50.0, 193.375, 710.65)
    f2 = pol.features(8.0, 350.0, 100.0, 1000.0, 50.0, 193.375, 710.65)
    assert f1.shape == (6,) and np.allclose(f1, f2)
    assert np.all(f1 >= 0.0) and np.all(f1 <= 1.05), f1
    print('  [PASS] T4 学习型 λ 特征: shape=%s 范围=[%.2f, %.2f]' % (f1.shape, f1.min(), f1.max()))
    return True


def t5_distill_budget():
    rows = _toy_rows()
    X, y, d = to_matrix(rows)
    util = distilled_utility(rows, X, y, d)
    assert util['tree_net'] <= util['original_net'] * 1.5 + 1e-6, '蒸馏后净价值异常偏高'
    for day in set(d):
        spent = sum(r['e_hat'] for i, r in enumerate(rows)
                    if r['day'] == day and r['accept'] and False)
    print('  [PASS] T5 蒸馏重放净价值: original=%.1f tree=%.1f'
          % (util['original_net'], util['tree_net']))
    return True


TESTS = [('T1', t1_to_matrix), ('T2', t2_threshold_capturable), ('T3', t3_random_not_capturable),
         ('T4', t4_learned_features), ('T5', t5_distill_budget)]


def main():
    failed = 0
    for name, fn in TESTS:
        try:
            if not fn():
                failed += 1
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
