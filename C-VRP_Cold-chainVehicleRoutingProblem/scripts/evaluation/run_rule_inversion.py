"""决策反演测试（rule inversion）：把策略的接拒决策蒸馏成浅模型。

总纲 §1.2 / §7.2 的合入门槛：

    若在**在线可见特征**上用浅模型（决策树 depth≤3 / 逻辑回归）复现某策略的接拒决策，
    且 AUC > 0.98、闭环效用损失 < 5%，则该策略判为 **RULE_CAPTURABLE**，不得作为创新点。

本脚本做三件事：
1. 用与 `run_admission_offline_regret.py` 同一套登记数据/校准表，回放若干策略，记录
   **逐单决策日志**（特征 + 决策）。
2. 用 **按日簇留一（leave-one-day-out）** 训练浅模型，报 AUC / 一致率。
3. 把浅模型当成策略重放，报**净价值**损失，并按预登记判据给出 `RULE_CAPTURABLE` / `NOT_CAPTURED`。

用法（从扩展根目录）::

    python scripts/evaluation/run_rule_inversion.py --out results/rule_inversion/inv1
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path

import numpy as np

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_SCRIPTS, os.path.join(_SCRIPTS, 'evaluation'), os.path.join(_SCRIPTS, 'admission')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

FROZEN = dict(train_seed=20260925, train_instances=200, gate_seed=20260926,
              gate_instances=40, n_orders=200, budget_B=710.6548328611384,
              horizon=16.0, days=5)
OBJECTIVE = dict(ambient_c=25.0, target_c=[18.0, 4.0, -18.0],
                 precool_energy_per_unit_per_c=0.15)
LAM_MIN, LAM_MAX = 0.25, 8.0

FEATURES = ['clock', 'budget_ratio', 'e_hat', 'revenue', 'ratio', 'seen',
            'spent', 'cls0', 'cls1', 'cls2']


# --------------------------------------------------------------------------
# 数据与成本口径（与 v2 学习型 λ 完全一致）
# --------------------------------------------------------------------------
def load_days(dataset, objective, fuel_weight=1.0, quality_weight=1.0):
    """返回每天 [(clock, class, qty, revenue, e_lower, fuel, quality)]，按 reveal 排序。"""
    from admission.policies import REV, e_lower_of
    from run_exp_reserve import FUEL_COST_PER_KM, KM_PER_UNIT, K_EFF, PVAL, SPEED_KMH

    dem = np.asarray(dataset['demands'], dtype=np.float64)
    rev_t = np.asarray(dataset['reveal_time'], dtype=np.float64)
    cls_t = np.asarray(dataset['temp_class'], dtype=np.int64)
    coords = np.asarray(dataset['coords'], dtype=np.float64)
    days = []
    for d in range(dem.shape[0]):
        idx = np.where(dem[d] > 0)[0]
        idx = idx[np.argsort(rev_t[d][idx], kind='stable')]
        rows = []
        for o in idx:
            c = int(cls_t[d, o])
            q = float(dem[d, o])
            detour = 2.0 * float(np.linalg.norm(coords[d, o] - coords[d, 0]))
            fuel = FUEL_COST_PER_KM * detour * KM_PER_UNIT
            dwell_h = 2.0 * detour / (SPEED_KMH / KM_PER_UNIT)
            quality = PVAL[c] * q * (1.0 - math.exp(-K_EFF[c] * dwell_h))
            rows.append(dict(clock=float(rev_t[d, o]), cls=c, qty=q,
                             rev=float(REV[c]), e=e_lower_of(c, q, objective),
                             fuel=fuel, quality=quality))
        days.append(rows)
    return days


# --------------------------------------------------------------------------
# 策略：静态 λ / 动态对偶 / 学习型（线性，读 npz）
# --------------------------------------------------------------------------
class StaticLambda:
    name = 'static_lambda'

    def __init__(self, lam_grid, clock_grid, g_table):
        from admission.policies import RegisteredShadowPrice
        self.p = RegisteredShadowPrice(lam_grid, clock_grid, g_table)

    def reset(self, budget):
        self.accepted, self.spent, self.budget = [], 0.0, float(budget)

    def decide(self, row, lam_state):
        from admission.controller import OrderView
        view = OrderView.build(0, row['cls'], row['qty'], row['e'], revenue=row['rev'])
        from admission.controller import AdmissionState
        st = AdmissionState(self.budget)
        st.spent_e = self.spent
        dec = self.p.decide(view, row['clock'], st)
        if dec.accept:
            self.spent += row['e']
        return dec.accept, ('%.6f' % (dec.lam or 0.0))


class DynamicDual:
    name = 'dynamic_dual_eta0.02'

    def __init__(self, eta=0.02, lam0=2.5, lam_max=8.0, n_expected=193.375):
        from admission.policies import DynamicDual as DD
        self.p = DD(eta=eta, lam0=lam0, lam_max=lam_max, n_expected=n_expected)

    def reset(self, budget):
        from admission.controller import AdmissionState
        self.st = AdmissionState(float(budget))
        self.p.reset(self.st, horizon=FROZEN['horizon'], budget=float(budget))

    def decide(self, row, lam_state):
        from admission.controller import OrderView
        view = OrderView.build(0, row['cls'], row['qty'], row['e'], revenue=row['rev'])
        dec = self.p.decide(view, row['clock'], self.st)
        self.st.note(dec, view)
        return dec.accept, ('%.6f' % (dec.lam or 0.0))


class LearnedLinear:
    """v2 学习型 λ：λ = λmin + (λmax−λmin)·sigmoid(w·x + b)。"""

    name = 'learned_linear_v2'

    def __init__(self, npz_path):
        z = np.load(npz_path)
        self.w = np.asarray(z['w'], dtype=np.float64).reshape(-1)
        self.b = float(np.asarray(z['b']).reshape(-1)[0])

    @staticmethod
    def features(clock, b_rem, n_seen, rev_sum, e_sum, n_expected, budget):
        ratio = min(max(b_rem / budget, 0.0), 1.0)
        progress = min(max(clock / FROZEN['horizon'], 0.0), 1.0)
        seen = min(max(n_seen / max(n_expected, 1.0), 0.0), 1.0)
        spent = 1.0 - ratio
        avg_ratio = (rev_sum / max(e_sum, 1e-9) / 30.0) if e_sum > 1e-9 else 0.0
        pace = min(max(ratio / (1.0 - progress + 1e-3), 0.0), 4.0) / 4.0
        return np.asarray([progress, spent, seen, avg_ratio, pace, ratio], dtype=np.float64)

    def reset(self, budget):
        self.budget = float(budget)
        self.b_rem = float(budget)
        self.n_seen = 0.0
        self.rev_sum = 0.0
        self.e_sum = 0.0

    def decide(self, row, lam_state):
        x = self.features(row['clock'], self.b_rem, self.n_seen, self.rev_sum,
                          self.e_sum, 193.375, self.budget)
        z = float(x @ self.w + self.b)
        lam = LAM_MIN + (LAM_MAX - LAM_MIN) / (1.0 + math.exp(-z))
        ok = (row['rev'] - lam * row['e'] > 0.0) and (row['e'] <= self.b_rem + 1e-9)
        if ok:
            self.b_rem -= row['e']
            self.rev_sum += row['rev']
            self.e_sum += row['e']
        self.n_seen += 1.0
        return ok, ('%.6f' % lam)


# --------------------------------------------------------------------------
# 回放 → 决策日志
# --------------------------------------------------------------------------
def replay(policy, days, budget, fw=1.0, qw=1.0):
    rows = []
    for d, day in enumerate(days):
        policy.reset(budget)
        spent = 0.0
        for row in day:
            accept, lam = policy.decide(row, None)
            net = row['rev'] - fw * row['fuel'] - qw * row['quality']
            rows.append(dict(day=d, clock=row['clock'], budget_ratio=1.0 - spent / budget,
                             e_hat=row['e'], revenue=row['rev'],
                             ratio=row['rev'] / max(row['e'], 1e-9),
                             seen=0.0, spent=spent / budget,
                             cls=row['cls'], accept=bool(accept), lam=lam, net=net))
            if accept:
                spent += row['e']
    # 补齐逐单进度特征（seen 与 spent 都在决策后）
    for d in range(len(days)):
        day_rows = [r for r in rows if r['day'] == d]
        for i, r in enumerate(day_rows):
            r['seen'] = i / max(len(day_rows), 1)
    return rows


def to_matrix(rows):
    X = np.zeros((len(rows), len(FEATURES)), dtype=np.float64)
    y = np.zeros(len(rows), dtype=np.int64)
    days = np.zeros(len(rows), dtype=np.int64)
    for i, r in enumerate(rows):
        X[i] = [r['clock'] / FROZEN['horizon'], r['budget_ratio'], r['e_hat'],
                r['revenue'], min(r['ratio'], 20.0), r['seen'], r['spent'],
                float(r['cls'] == 0), float(r['cls'] == 1), float(r['cls'] == 2)]
        y[i] = int(r['accept'])
        days[i] = r['day']
    return X, y, days


def net_value(rows):
    return float(sum(r['net'] for r in rows if r['accept']))


# --------------------------------------------------------------------------
# 反演
# --------------------------------------------------------------------------
def loo_inversion(X, y, days, max_depth=3):
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    from sklearn.tree import DecisionTreeClassifier

    out = []
    for d in sorted(set(days)):
        tr, te = days != d, days == d
        if tr.sum() < 30 or te.sum() < 20:
            continue
        tree = DecisionTreeClassifier(max_depth=max_depth, random_state=0).fit(X[tr], y[tr])
        lr = LogisticRegression(max_iter=1000).fit(X[tr], y[tr])
        p_tree = tree.predict_proba(X[te])[:, 1]
        p_lr = lr.predict_proba(X[te])[:, 1]
        entry = dict(day=int(d), n_train=int(tr.sum()), n_test=int(te.sum()),
                     auc_tree=float(roc_auc_score(y[te], p_tree))
                     if len(set(y[te])) > 1 else None,
                     auc_logreg=float(roc_auc_score(y[te], p_lr))
                     if len(set(y[te])) > 1 else None,
                     agreement_tree=float(np.mean((p_tree >= 0.5) == y[te])),
                     agreement_logreg=float(np.mean((p_lr >= 0.5) == y[te])))
        out.append(entry)
    return out


def distilled_utility(rows, X, y, days, max_depth=3):
    """用全部数据训练浅模型，再把它当策略重放（预测 accept），比较净价值。"""
    from sklearn.linear_model import LogisticRegression
    from sklearn.tree import DecisionTreeClassifier

    tree = DecisionTreeClassifier(max_depth=max_depth, random_state=0).fit(X, y)
    lr = LogisticRegression(max_iter=1000).fit(X, y)
    p_tree = tree.predict_proba(X)[:, 1]
    p_lr = lr.predict_proba(X)[:, 1]

    def replay_with(mask):
        # 按原来的接受顺序重放预算（保持因果：只有被预测为接受的单才消耗预算）
        spent = {d: 0.0 for d in set(days)}
        total = 0.0
        for i, r in enumerate(rows):
            d = r['day']
            if mask[i] and r['e_hat'] <= FROZEN['budget_B'] - spent[d] + 1e-9:
                spent[d] += r['e_hat']
                total += r['net']
        return total

    return dict(original_net=net_value(rows),
                tree_net=replay_with(p_tree >= 0.5),
                logreg_net=replay_with(p_lr >= 0.5))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--days', type=int, default=FROZEN['days'])
    ap.add_argument('--fuel-weight', type=float, default=1.0)
    ap.add_argument('--quality-weight', type=float, default=1.0)
    ap.add_argument('--learned-npz', type=str, default=None,
                    help='默认用 results/admission_learned/v2_net/learned_price.npz')
    ap.add_argument('--out', required=True)
    args = ap.parse_args(argv)

    # scripts/evaluation/run_rule_inversion.py -> 扩展根（再上两级）
    op = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from run_exp_reserve import generate_dataset
    from admission.policies import build_clock_grid, build_lambda_grid, build_train_days, calibrate

    train = generate_dataset(FROZEN['train_instances'], FROZEN['n_orders'], FROZEN['train_seed'])
    gate = generate_dataset(FROZEN['gate_instances'], FROZEN['n_orders'], FROZEN['gate_seed'])
    lam_grid = build_lambda_grid()
    clock_grid = build_clock_grid(FROZEN['horizon'])
    g_table = calibrate(build_train_days(train, OBJECTIVE), OBJECTIVE,
                        FROZEN['horizon'], lam_grid, clock_grid)
    days = load_days(gate, OBJECTIVE, args.fuel_weight, args.quality_weight)[:args.days]
    B = FROZEN['budget_B']

    npz = args.learned_npz or os.path.join(op, 'results', 'admission_learned', 'v2_net',
                                           'learned_price.npz')
    policies = [StaticLambda(lam_grid, clock_grid, g_table),
                DynamicDual(),
                LearnedLinear(npz)]

    report = dict(stage='rule_inversion', status='PREREGISTERED_THRESHOLD',
                  threshold=dict(auc=0.98, utility_loss=0.05),
                  config=dict(days=args.days, budget=B, features=FEATURES,
                              fuel_weight=args.fuel_weight,
                              quality_weight=args.quality_weight,
                              learned_npz=os.path.relpath(npz, op)),
                  policies={})

    for pol in policies:
        rows = replay(pol, days, B, args.fuel_weight, args.quality_weight)
        X, y, dvec = to_matrix(rows)
        loo = loo_inversion(X, y, dvec)
        util = distilled_utility(rows, X, y, dvec)
        aucs = [e['auc_tree'] for e in loo if e['auc_tree'] is not None]
        mean_auc = float(np.mean(aucs)) if aucs else None
        loss_tree = (util['original_net'] - util['tree_net']) / util['original_net'] \
            if util['original_net'] else None
        loss_lr = (util['original_net'] - util['logreg_net']) / util['original_net'] \
            if util['original_net'] else None
        capturable = bool(mean_auc is not None and mean_auc > 0.98
                          and loss_tree is not None and abs(loss_tree) < 0.05)
        verdict = 'RULE_CAPTURABLE' if capturable else 'NOT_CAPTURED'
        report['policies'][pol.name] = dict(
            n_decisions=len(rows), accept_rate=float(np.mean(y)),
            loo=loo, loo_mean_auc_tree=mean_auc,
            utility=util,
            loss_tree=loss_tree, loss_logreg=loss_lr,
            verdict=verdict)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'rule_inversion.json').write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')

    print('| policy | n | accept | LOO AUC(tree) | net(original) | net(tree) | loss | verdict |')
    print('|---|---:|---:|---:|---:|---:|---:|---|')
    for name, r in report['policies'].items():
        print('| %s | %d | %.3f | %s | %.1f | %.1f | %s | **%s** |' % (
            name, r['n_decisions'], r['accept_rate'],
            ('%.4f' % r['loo_mean_auc_tree']) if r['loo_mean_auc_tree'] is not None else '—',
            r['utility']['original_net'], r['utility']['tree_net'],
            ('%+.1f%%' % (100 * r['loss_tree'])) if r['loss_tree'] is not None else '—',
            r['verdict']))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
