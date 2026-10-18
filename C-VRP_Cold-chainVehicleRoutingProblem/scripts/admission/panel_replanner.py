"""把 admission 控制器接到 strict-online 仿真上的 replanner 适配层。

两个 replanner（都继承冻结的 ``SaaReplanner``，只覆盖 ``_saa_decide``）：

* ``StaticPriceReplanner``  —— 用本仓库的 ``RegisteredShadowPrice``（与登记规则等价，单测已对拍）。
* ``DynamicDualReplanner``  —— 用 ``DynamicDual``（BwK 次梯度影子价格）。

设计要点
--------
1. **只在接单侧加过滤**：判定不允许 → 记入 ``_rejected`` 并直接返回；允许 → 交给父类
   ``_saa_decide`` 走原有 SAA 流程（场景评估、插入、承诺），保证其余语义逐字节不变。
2. **按 inst_idx 重置**：``SaaReplanner`` 以天为单位复用实例，控制器状态按 inst_idx 懒重置。
3. **成本/收入口径**：``e_lower``（预冷能耗，登记口径）与 ``REV``；``p_c`` 不进接拒判定。
4. **审计**：每天的 λ 轨迹、接受/拒绝计数、拒绝原因分布都写进 ``admission_log``。
"""
from __future__ import annotations

import os
import sys

import numpy as np

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_SCRIPTS, os.path.join(_SCRIPTS, 'admission'), os.path.join(_SCRIPTS, 'evaluation')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from admission.controller import AdmissionController, OrderView  # noqa: E402
from scenario_saa import SaaReplanner  # noqa: E402
from admission.policies import REV, e_lower_of  # noqa: E402


class _AdmissionMixin:
    """共用：把 (env, inst_idx, o) 变成 OrderView，并维护 AdmissionController。"""

    def _admission_init(self, objective: dict, horizon: float = 16.0):
        self._adm_objective = dict(objective)
        self._adm_horizon = float(horizon)
        self._adm_ctrl = None
        self._adm_inst = -1
        self.admission_log = []
        self.admission_days = []

    # --- 内部工具 ---------------------------------------------------------
    def _adm_ensure_day(self, env, inst_idx, budget: float):
        if self._adm_ctrl is None or int(inst_idx) != self._adm_inst:
            if self._adm_ctrl is not None:
                self.admission_days.append(dict(inst=self._adm_inst, **self._adm_ctrl.summary()))
            self._adm_inst = int(inst_idx)
            self._adm_ctrl = AdmissionController(self._make_policy(env, inst_idx), budget=budget)
            self._adm_ctrl.begin_day([], horizon=self._adm_horizon, day_index=int(inst_idx))

    def _order_view(self, env, inst_idx, o, revenue=None) -> OrderView:
        cls = int(env.dataset['temp_class'][inst_idx, o])
        q = float(env.demands[inst_idx, o])
        e = e_lower_of(cls, q, self._adm_objective)
        return OrderView.build(int(o), cls, q, e,
                              reveal_time=float(env.dataset['reveal_time'][inst_idx, o]),
                              revenue=revenue)

    # --- 判定 -------------------------------------------------------------
    def _admission_allows(self, env, inst_idx, clock, o, revenue=None) -> bool:
        self._adm_ensure_day(env, inst_idx, float(self.budget))
        view = self._order_view(env, inst_idx, o, revenue=revenue)
        dec = self._adm_ctrl.decide(view, float(clock))
        if len(self.admission_log) < 2000:
            self.admission_log.append(dict(inst=int(inst_idx), clock=float(clock), order=int(o),
                                           accept=bool(dec.accept), reason=dec.reason,
                                           lam=(None if dec.lam is None else float(dec.lam)),
                                           e_hat=float(dec.e_hat), revenue=float(dec.revenue),
                                           budget_remaining=float(dec.budget_remaining)))
        return bool(dec.accept)

    def admission_summary(self) -> dict:
        days = list(self.admission_days)
        if self._adm_ctrl is not None:
            days.append(dict(inst=self._adm_inst, **self._adm_ctrl.summary()))
        return dict(n_days=len(days), days=days)


class StaticPriceReplanner(SaaReplanner, _AdmissionMixin):
    """登记静态影子价格（本仓库实现）作为接单过滤器。"""

    name = 'static_price'

    def __init__(self, *args, lambda_grid=None, clock_grid=None, g_table=None,
                 objective=None, **kwargs):
        super().__init__(*args, **kwargs)
        from admission.policies import RegisteredShadowPrice
        self._adm_policy_cls = RegisteredShadowPrice
        self._adm_policy_kwargs = dict(lambda_grid=lambda_grid, clock_grid=clock_grid,
                                       g_table=g_table)
        self._admission_init(objective or {})

    def _make_policy(self, env, inst_idx):
        return self._adm_policy_cls(**self._adm_policy_kwargs)

    def _saa_decide(self, env, inst_idx, clock, vehicles, served_mask, o, scenarios, t0):
        if not self._admission_allows(env, inst_idx, clock, o):
            self._rejected.add(o)
            return
        super()._saa_decide(env, inst_idx, clock, vehicles, served_mask, o, scenarios, t0)


class DynamicDualReplanner(SaaReplanner, _AdmissionMixin):
    """BwK 动态对偶影子价格作为接单过滤器。"""

    name = 'dynamic_dual'

    def __init__(self, *args, eta=0.02, lam0=2.5, lam_max=8.0, n_expected=193.375,
                 objective=None, **kwargs):
        super().__init__(*args, **kwargs)
        from admission.policies import DynamicDual
        self._adm_policy_cls = DynamicDual
        self._adm_policy_kwargs = dict(eta=float(eta), lam0=float(lam0),
                                       lam_max=float(lam_max),
                                       n_expected=float(n_expected))
        self._admission_init(objective or {})

    def _make_policy(self, env, inst_idx):
        return self._adm_policy_cls(**self._adm_policy_kwargs)

    def _saa_decide(self, env, inst_idx, clock, vehicles, served_mask, o, scenarios, t0):
        if not self._admission_allows(env, inst_idx, clock, o):
            self._rejected.add(o)
            return
        super()._saa_decide(env, inst_idx, clock, vehicles, served_mask, o, scenarios, t0)


class MarginalGateReplanner(StaticPriceReplanner):
    """边际净价值门控（阶段 1b）：把燃油与品质损耗写进接拒判据。

    上一轮（stage1）的负结果说明：只按**收入**做预算预留，会在全仿真里被距离与品质
    损耗吃掉。这里把判据换成

        net(i) = REV[c] - fuel_weight * 0.1 * km_hat(i) - quality_weight * Q_hat(i)
        接受  <=>  net(i) - lambda(clock) * e_lower(i) > 0

    其中
      * ``km_hat``：把订单插入当前计划（``self._plan``）的最小绕行量（取所有车的最小值），
        再乘以 ``KM_PER_UNIT``；拿不到计划时退化为 depot 往返。
      * ``Q_hat``：绕行导致的在车时间增加 ``2*delta_units / (SPEED_KMH/KM_PER_UNIT)`` 小时，
        按 v1 的零阶/一阶近似 ``PVAL[c]*q*(1-exp(-K_EFF[c]*dwell_h))`` 折算成品质损耗。
    这两个量都是**增量**（相对当前计划），符合方案 §1b 的要求。
    """

    name = 'marginal_gate'

    def __init__(self, *args, fuel_weight=1.0, quality_weight=1.0, **kwargs):
        super().__init__(*args, **kwargs)
        self.fuel_weight = float(fuel_weight)
        self.quality_weight = float(quality_weight)

    # --- 增量估计 ---------------------------------------------------------
    def _delta_units(self, env, inst_idx, vehicles, served_mask, o) -> float:
        import math as _m
        d = env.dist_mat[inst_idx]
        best = _m.inf
        for v in vehicles:
            route = [x for x in self._plan.get(v.vehicle_id, []) if not served_mask[x]]
            cur = int(v.current_node) if getattr(v, 'current_node', 0) else 0
            seq = [cur] + route + [0]
            for pos in range(len(seq) - 1):
                a, b = seq[pos], seq[pos + 1]
                delta = float(d[a, o] + d[o, b] - d[a, b])
                if delta < best:
                    best = delta
        if not _m.isfinite(best):
            best = float(d[0, o]) * 2.0
        return max(best, 0.0)

    def _net_value(self, env, inst_idx, vehicles, served_mask, o) -> float:
        from run_exp_reserve import (FUEL_COST_PER_KM, KM_PER_UNIT, K_EFF, PVAL,
                                     SPEED_KMH)
        cls = int(env.dataset['temp_class'][inst_idx, o])
        q = float(env.demands[inst_idx, o])
        delta_units = self._delta_units(env, inst_idx, vehicles, served_mask, o)
        km = delta_units * KM_PER_UNIT
        fuel = FUEL_COST_PER_KM * km
        dwell_h = 2.0 * delta_units / (SPEED_KMH / KM_PER_UNIT)
        quality = PVAL[cls] * q * (1.0 - np.exp(-K_EFF[cls] * dwell_h))
        from admission.policies import REV
        return float(REV[cls] - self.fuel_weight * fuel - self.quality_weight * quality)

    def _saa_decide(self, env, inst_idx, clock, vehicles, served_mask, o, scenarios, t0):
        net = self._net_value(env, inst_idx, vehicles, served_mask, o)
        if not self._admission_allows(env, inst_idx, clock, o, revenue=net):
            self._rejected.add(o)
            return
        super(StaticPriceReplanner, self)._saa_decide(env, inst_idx, clock, vehicles,
                                                      served_mask, o, scenarios, t0)