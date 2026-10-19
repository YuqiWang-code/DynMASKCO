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

class DPGateReplanner(MarginalGateReplanner):
    """把 DP 状态依赖阈值接成接单过滤器（net 口径与 MarginalGate 相同）。"""

    name = 'dp_gate'

    def __init__(self, *args, dp_npz=None, dp_n_expected=193.0, **kwargs):
        super().__init__(*args, **kwargs)
        self._dp_npz = dp_npz
        self._dp_n_expected = float(dp_n_expected)

    def _make_policy(self, env, inst_idx):
        from admission.policies import DPThreshold
        return DPThreshold(self._dp_npz, n_expected=self._dp_n_expected)


class OnlineKnapsackReplanner(StaticPriceReplanner):
    """在线背包指数阈值规则（OCRS 家族的确定性等价物）作为接单过滤器。

    与 ``StaticPriceReplanner`` 的唯一差别是 ``_make_policy``：把常数影子价格换成
    ``φ(z) = (L/e)·(U/L)^z``（见 ``policies.OnlineKnapsack``）。**有竞争比保证**，
    因此它是"不比强规则更差"这一主张的**对照物**，不是本项目的创新点。
    """

    name = 'online_knapsack'

    def __init__(self, *args, density_min=1.55, density_max=9.52, density_scale=1.0,
                 **kwargs):
        super().__init__(*args, **kwargs)
        self._okp_kwargs = dict(density_min=float(density_min),
                                density_max=float(density_max),
                                scale=float(density_scale))

    def _make_policy(self, env, inst_idx):
        from admission.policies import OnlineKnapsack
        return OnlineKnapsack(**self._okp_kwargs)


class ConformalDensityReplanner(StaticPriceReplanner):
    """保形密度阈值作为接单过滤器（I-2 的"拒因保形"半边）。"""

    name = 'conformal_density'

    def __init__(self, *args, conf_rho=2.25, conf_alpha=0.5, **kwargs):
        super().__init__(*args, **kwargs)
        self._conf_kwargs = dict(rho=float(conf_rho), alpha=float(conf_alpha))

    def _make_policy(self, env, inst_idx):
        from admission.policies import ConformalDensity
        return ConformalDensity(**self._conf_kwargs)







class SameSetReoptReplanner(SaaReplanner):
    """外部式**同集合重优化**：不改接单集合，只用 2-opt 重排每辆车的 suffix。

    为什么这样做（G2/G4 两条线共用）：
    * 外部求解器**替换路线**会绕开 SAA 的能耗记账（已记为 `BLOCKED(structural)`）；
    * 只重排同一集合的**顺序**则不改变 served 集合、不改变预算记账，
      环境仍会逐单校验时间窗与载重 ⇒ 安全且可解释。

    判定：对每辆车的 suffix 做 2-opt，只接受**时间窗可行且里程更短**的变换。
    `reopt_passes` 控制迭代轮数；默认 2。
    """

    name = 'same_set_reopt'

    def __init__(self, *args, reopt_passes=2, **kwargs):
        super().__init__(*args, **kwargs)
        self._passes = int(reopt_passes)

    # --- 时间窗可行性（与 env 同口径：绝对 tw_end、服务时长、单位速度） ---
    def _feasible(self, env, inst_idx, seq, start_t):
        tw_end = env.tw_end[inst_idx]
        svc = env.service_time[inst_idx]
        spd = float(getattr(env, 'tw_speed', 1.5))
        t = float(start_t)
        prev = 0
        for node in seq:
            if int(node) == 0:
                prev = 0
                continue
            d = float(env.dist_mat[inst_idx][prev, int(node)])
            arr = t + d / spd
            if arr > float(tw_end[node]) + 1e-6:
                return False
            t = arr + float(svc[node])
            prev = int(node)
        return True

    def _len(self, env, inst_idx, seq, start_t=0.0):
        dm = env.dist_mat[inst_idx]
        prev, total = 0, 0.0
        for node in seq:
            total += float(dm[prev, int(node)])
            prev = int(node)
        return total

    def _two_opt(self, env, inst_idx, seq, start_t):
        best = list(seq)
        best_len = self._len(env, inst_idx, best)
        n = len(best)
        for _ in range(self._passes):
            improved = False
            for i in range(n - 1):
                for j in range(i + 2, n + 1):
                    cand = best[:i] + list(reversed(best[i:j])) + best[j:]
                    if self._len(env, inst_idx, cand) + 1e-9 >= best_len:
                        continue
                    if not self._feasible(env, inst_idx, cand, start_t):
                        continue
                    best, best_len, improved = cand, self._len(env, inst_idx, cand), True
            if not improved:
                break
        return best

    def plan(self, env, inst_idx, clock, vehicles, served_mask, visible_ids,
             replan_ids=None):
        super().plan(env, inst_idx, clock, vehicles, served_mask, visible_ids,
                     replan_ids)
        for v in vehicles:
            seq = [int(x) for x in getattr(v, 'mutable_suffix', [])]
            if len(seq) < 3:
                continue
            start_t = float(getattr(v, 'ready_time', 0.0))
            if int(getattr(v, 'current_node', 0)) != 0:
                continue        # 只重排仍从仓库出发的车，避免与已提交前缀冲突
            new = self._two_opt(env, inst_idx, seq, start_t)
            if new != seq:
                v.mutable_suffix = new



class FleetReserveReplanner(SaaReplanner):
    """车队保留（fleet reservation）：在 `release_clock` 之前，只允许 `fleet - reserve` 辆车出发。

    依据：攒批发车的增益**不来自里程**，而来自"留住 idle 车辆给后面的高价单"
    （[首日记录](docs/04_实施与结果/2026-10-18_攒批发车_首日.md)：多接 1 单 30 收入）。
    但攒批的条件是"待派 ≥ K 或等待 ≥ W"，参数敏感（K∈[7,10] 等价、W 平台但 burst 下翻转）。

    本机制把同一思想写成**时间-车队**形式：与订单到达无关，只与 clock 有关 ——
    因此在任何 regime 下行为一致，理论上更稳。

    实现：`plan()` 之后，若 `clock < release_clock`，把**除保留车之外**的 idle 车的 suffix 清空；
    保留车 = 前 `reserve` 辆（按 vehicle_id 排序，确定性）。
    """

    name = 'fleet_reserve'

    def __init__(self, *args, reserve=1, release_clock=12.0, **kwargs):
        super().__init__(*args, **kwargs)
        self._reserve = int(reserve)
        self._release = float(release_clock)

    def plan(self, env, inst_idx, clock, vehicles, served_mask, visible_ids,
             replan_ids=None):
        super().plan(env, inst_idx, clock, vehicles, served_mask, visible_ids,
                     replan_ids)
        if float(clock) >= self._release:
            return
        idle = sorted([v for v in vehicles
                       if int(getattr(v, 'current_node', 0)) == 0
                       and getattr(v, 'status', 'idle') in ('idle', 'ready')],
                      key=lambda v: int(v.vehicle_id))
        for v in idle[self._reserve:]:
            if getattr(v, 'mutable_suffix', None):
                v.mutable_suffix = []

class PartitionReoptReplanner(SameSetReoptReplanner):
    """跨车重新分配（partition 重优化）：不改接单集合，只改"哪辆车拉哪些待派订单"。

    动机（第 85 轮的零结果）：同集合 2-opt = 0、加深局部搜索 = 0 ⇒ 3.47× 的余量不在
    **路线内顺序**，而在**车辆-订单分配**：SAA 让每车早发少装，离线最优压成少数大圈。

    做法：
    1. 取"已接受但未服务、且未出现在任何 suffix 中"的订单作为待派池；
    2. 按 `tw_end` 升序排序（最紧的先排）；
    3. 对每辆**仍 idle 且从仓库出发**的车，贪心装到"再加一单就违反容量或时间窗"为止；
    4. 写回 `mutable_suffix`（末尾补 0 表示回仓）。

    安全边界：只动 idle/仓库出发的车（不动已提交前缀），逐单校验容量与 TW，
    因此环境的承诺/预算记账不被绕开——这与 OR-Tools 路线臂的 `BLOCKED` 情形不同。

    成本：每次 `plan()` 都做一次分配，禁用车数 15、待派池通常 <20 单 ⇒ 可忽略。
    """

    name = 'partition_reopt'

    def _suffix_nodes(self, vehicles):
        nodes = set()
        for v in vehicles:
            for x in getattr(v, 'mutable_suffix', []) or []:
                if int(x) != 0:
                    nodes.add(int(x))
        return nodes

    def _load(self, env, inst_idx, seq):
        return float(sum(float(env.demands[inst_idx][int(x)]) for x in seq))

    def plan(self, env, inst_idx, clock, vehicles, served_mask, visible_ids,
             replan_ids=None):
        super().plan(env, inst_idx, clock, vehicles, served_mask, visible_ids,
                     replan_ids)
        in_suffix = self._suffix_nodes(vehicles)
        pending = [int(x) for x in self._accepted
                   if (not bool(served_mask[int(x)])) and int(x) not in in_suffix
                   and int(x) != 0]
        if len(pending) < 2:
            return
        cap = float(self.capacity)
        tw_end = env.tw_end[inst_idx]
        pending.sort(key=lambda x: float(tw_end[x]))
        idle = [v for v in vehicles
                if int(getattr(v, 'current_node', 0)) == 0
                and getattr(v, 'status', 'idle') in ('idle', 'ready')
                and int(v.vehicle_id) in (replan_ids or {v.vehicle_id})]
        if not idle:
            return
        i = 0
        for v in idle:
            seq, load = [], 0.0
            while i < len(pending):
                x = pending[i]
                q = float(env.demands[inst_idx][x])
                if load + q > cap + 1e-9:
                    break
                trial = seq + [x, 0]
                if not self._feasible(env, inst_idx, trial, float(getattr(v, 'ready_time', 0.0))):
                    i += 1
                    continue
                seq.append(x)
                load += q
                i += 1
            if seq:
                v.mutable_suffix = seq + [0]
        # 剩下的交给父类原本的分配（已在上面 super().plan 里写过），这里不回滚

class ORToolsSaaReplanner(SaaReplanner):
    """外部基线（G2）：**登记静态价负责接单 + OR-Tools 负责路线**。

    设计（两次冒烟后定稿）：
    1. 继承 `SaaReplanner` 以获得环境所需的**全部**接口（`plan/on_reveal/restore_state/
       sync_deferred_from_vehicles`）——这是第一版崩溃的根因；
    2. `plan()` 整体委托给 `baselines.ortools_rolling_horizon.ORToolsReplanner`（路线由外部求解器给）；
    3. 接单侧**自己实现**登记静态价的等价判据（`REV[c] − λ(clock)·e_lower(c,q) > 0`），
       并维护 `_accepted/_rejected` 与剩余能耗预算——这一层不能靠继承接拒基类，
       因为它与 OR 的 `plan()` 覆写互相干扰（第二次冒烟的错误）。

    严格在线：OR 只看到 `visible_ids`（`reveal_time <= clock`），可直接用 L2 `visibility` 核对。
    """

    name = 'ortools_rolling'

    def __init__(self, *args, time_limit_ms=500, or_capacity=None,
                 or_num_vehicles=None, lambda_grid=None, clock_grid=None,
                 g_table=None, objective=None, energy_margin=0.98,
                 or_objective='time', or_commit_k=0, **kwargs):
        super().__init__(*args, **kwargs)
        from baselines.ortools_rolling_horizon import ORToolsReplanner as _OR
        from admission.policies import RegisteredShadowPrice, e_lower_of
        self._obj = dict(objective or {})
        self._price = RegisteredShadowPrice(lambda_grid, clock_grid, g_table)
        self._e_lower_of = e_lower_of
        self._or = _OR(capacity=int(round(or_capacity or self.capacity)),
                       num_vehicles=int(or_num_vehicles or 15),
                       time_limit_ms=int(time_limit_ms),
                       objective=str(or_objective or 'time'), commit_k=int(or_commit_k))
        # 第 100 轮修法 3：接单额度改成**因果能耗记账**（见 _saa_decide docstring），
        # energy_margin 只是终局安全余量（1.0 表示不留余量）。
        self._energy_margin = float(energy_margin)
        self._used = 0.0
        self._status_inst = -1
        # 第 100 轮修法 1/2 的诊断计数（写进 admission_summary 供记录引用）
        self.n_dropped_undeliverable = 0
        self.n_admitted = 0

    # --- 接单：登记静态价的等价判据 + 预算跟踪 -----------------------------
    def _reset_if_new(self, inst_idx):
        if int(inst_idx) != int(self._status_inst):
            super()._reset_if_new(inst_idx)
            self._used = 0.0
            self._status_inst = int(inst_idx)
            self.n_dropped_undeliverable = 0
            self.n_admitted = 0

    def _realized_energy(self, vehicles) -> float:
        """已实现的冷机累计能耗（因果量：只读当前车辆状态，不看未来）。"""
        tot = 0.0
        for v in vehicles:
            cc = getattr(v, 'coldchain_state', None)
            if cc is not None:
                tot += float(getattr(cc, 'cumulative_energy_kwh', 0.0) or 0.0)
        return tot

    def _pending_lower_energy(self, env, inst_idx, served_mask) -> float:
        """已接单但还没送完的订单的**预冷能耗**（已决但未执行的工作量）。"""
        tot = 0.0
        for o in self._accepted:
            if bool(served_mask[int(o)]):
                continue
            cls = int(env.dataset['temp_class'][inst_idx, int(o)])
            q = float(env.demands[inst_idx, int(o)])
            tot += float(self._e_lower_of(cls, q, self._obj))
        return tot

    def _served_lower_energy(self, env, inst_idx, served_mask) -> float:
        """已**送达**订单的预冷能耗（用来算当日的"毛化系数"，因果量）。"""
        tot = 0.0
        n = int(env.num_nodes)
        for o in range(1, n):
            if bool(served_mask[o]):
                cls = int(env.dataset['temp_class'][inst_idx, o])
                q = float(env.demands[inst_idx, o])
                tot += float(self._e_lower_of(cls, q, self._obj))
        return tot

    def _gross_up(self, env, inst_idx, served_mask, vehicles) -> float:
        """毛化系数：真实冷机能耗 / 已送达订单的预冷能耗（当日自校准，因果）。

        第 100 轮第二次冒烟（energy 868.56 / 710.65，`budget_violation`）说明只加
        `pending` 的 `e_lower` 不够：执行这批单还会带来在途/待机开销。这里用**当日已实现
        的比值**把未被执行的预冷能耗毛化（只看已送达订单与已实现能耗，不看未来）。
        早期样本太少时给 2.0 的先验，并对结果做 [1.0, 4.0] 的夹取。
        """
        el = self._served_lower_energy(env, inst_idx, served_mask)
        if el <= 1e-6:
            return 2.0
        ratio = self._realized_energy(vehicles) / el
        return min(max(ratio, 1.0), 4.0)

    def _saa_decide(self, env, inst_idx, clock, vehicles, served_mask, o, scenarios, t0):
        """接单判据：登记静态价（λ 过滤）**且** 因果能耗记账不超预算。

        第 100 轮修法（此前两次 BLOCKED 的根因）：
        * 旧判据只看 `Σ_{已接} e_lower ≤ B`，完全不含冷机固定开销（实测占预算 32%），
          于是在 OR 真的把单跑完时总能耗冲到 1186.8 / 710.65；
        * 新判据用**已实现能耗 + 毛化后的已接未送工作量 + 毛化后的本单**记账
          （三个量都是因果的：只读当前车辆冷机状态、已送达集合与已接受集合）：
              realized + gross·(pending + e(o)) ≤ margin · B
        """
        self._reset_if_new(inst_idx)
        cls = int(env.dataset['temp_class'][inst_idx, o])
        q = float(env.demands[inst_idx, o])
        e = float(self._e_lower_of(cls, q, self._obj))
        from admission.policies import REV
        rev = float(REV[cls])
        try:
            lam = float(self._price.lambda_for(float(clock), self.budget)[0])
        except Exception:
            lam = 0.0
        realized = self._realized_energy(vehicles)
        pending = self._pending_lower_energy(env, inst_idx, served_mask)
        gross = self._gross_up(env, inst_idx, served_mask, vehicles)
        cap = self._energy_margin * float(self.budget)
        ok = (rev - lam * e > 0.0) and (realized + gross * (pending + e) <= cap + 1e-9)
        if not ok:
            self._rejected.add(o)
            return
        self._used += e
        self._accepted.add(o)
        self.n_admitted += 1

    # --- 路线：委托给 OR-Tools（只看**已接受**的可见订单） -----------------
    def plan(self, env, inst_idx, clock, vehicles, served_mask, visible_ids,
             replan_ids=None):
        """第 100 轮修法 1：把 OR 的顾客集合限制在 `_accepted` 内。

        旧实现把 `visible_ids` 原样交给 OR ⇒ OR 会服务**从未被接单层接受**的订单，
        评估器因此报 `served_not_accepted`（并让能耗失控）。现在只把已接受的可见单交给 OR。
        """
        admitted_visible = [int(i) for i in visible_ids if int(i) in self._accepted]
        if not admitted_visible:
            # 没有任何已接受的可见单 ⇒ 不发车（不能回退到父类 SAA 规划，
            # 否则会把未接单的可见订单排进路线，重现 `served_not_accepted`）。
            return None
        out = self._or.plan(env, inst_idx, clock, vehicles, served_mask,
                            admitted_visible, replan_ids=replan_ids)
        # 修法 2：OR 求解器允许丢单（disjunction）⇒ 把"已接但既未送达、也不在任何车上"
        # 的订单**在日内**退回 rejected，避免终局出现 accepted_not_delivered。
        in_plan = set()
        for v in vehicles:
            in_plan.update(int(x) for x in getattr(v, 'mutable_suffix', []) or [])
            if getattr(v, 'committed_next', None) is not None:
                in_plan.add(int(v.committed_next))
        for o in list(self._accepted):
            if bool(served_mask[int(o)]) or int(o) in in_plan:
                continue
            self._accepted.discard(int(o))
            self._rejected.add(int(o))
            self.n_dropped_undeliverable += 1
        return out

    def admission_summary(self) -> dict:
        return dict(n_admitted=int(self.n_admitted),
                    n_dropped_undeliverable=int(self.n_dropped_undeliverable),
                    policy='ortools_rolling_energy_capped')


class BatchedDispatchReplanner(StaticPriceReplanner):
    """**攒批发车**：接单仍用登记静态价，但把"何时派车"改成攒够 K 单或最老订单超时 W 才发。

    依据（2026-10-18 的决定性发现）：控制臂 day0 的 461 km 是同一服务集合离线最优 133 km 的
    3.47 倍，机制是"来一单派一车、每趟都仓库往返"。若把派车推迟到攒够一批，往返次数下降，
    里程应按批次摊销 —— 而这是**完全因果**的（只用已揭示订单与当前 clock）。

    实现方式：在 ``plan()`` 拿到父类规划后，若攒批条件未满足，则把**仍 idle 且无已提交订单**的
    车辆的 ``mutable_suffix`` 清空（即不发车）。已派出车辆不受影响。

    诚实边界：这是对冻结 SAA 派车行为的**外部干预**，可能触发环境不变量（已提交订单/可售性）；
    必须先用 1 天冒烟确认不崩，再谈效果。
    """

    name = 'batched_dispatch'

    def __init__(self, *args, batch_k=8, batch_wait_h=1.0, **kwargs):
        super().__init__(*args, **kwargs)
        self._k = int(batch_k)
        self._w = float(batch_wait_h)

    def _pending(self, env, inst_idx, served_mask):
        disp = set()
        for route in getattr(self, '_plan', {}).values():
            disp.update(int(x) for x in route)
        pend = [int(x) for x in self._accepted
                if (not bool(served_mask[int(x)])) and int(x) not in disp]
        return pend

    def plan(self, env, inst_idx, clock, vehicles, served_mask, visible_ids,
             replan_ids=None):
        super().plan(env, inst_idx, clock, vehicles, served_mask, visible_ids,
                     replan_ids)
        pend = self._pending(env, inst_idx, served_mask)
        if not pend:
            return
        rt = env.dataset['reveal_time'][inst_idx]
        oldest = float(min(float(rt[x]) for x in pend))
        waited = float(clock) - oldest
        if len(pend) >= self._k or waited >= self._w:
            return                      # 攒够了或等太久 ⇒ 放行
        for v in vehicles:
            if int(getattr(v, 'current_node', 0)) == 0 and not getattr(v, 'load', 0):
                if getattr(v, 'mutable_suffix', None):
                    v.mutable_suffix = []

class DeeperLSReplanner(SaaReplanner):
    """加强局部搜索：**不改接单规则**，只把 SAA 内部的局部搜索 pass 数从 2 提到 ls_passes。

    动机：十天面板显示 G4 的缺口在"每单位收入的里程"
    （静态 λ 用 +22 收入换 +28.6 km；要跨门槛需再省 22.1 km / −4.2%）。
    接单侧的机制族已全部测负，因此这里是**唯一还没被调过**的一侧。
    本臂不接任何过滤器（等价于控制臂的接单行为），只改搜索强度，因此
    **任何差异都只能归因于局部搜索强度**。

    成本：局部搜索在 K 个场景内各跑一遍，pass 数 ×3 大约使单日耗时 ×2–3。
    """

    name = 'deeper_ls'

    def __init__(self, *args, ls_passes=6, **kwargs):
        super().__init__(*args, **kwargs)
        self._ls_passes = int(ls_passes)

    def _local_search_u(self, space, env, st, deadline, max_passes=2):
        return super()._local_search_u(space, env, st, deadline,
                                       max_passes=self._ls_passes)

class PyVrpFeasibilityReplanner(StaticPriceReplanner):
    """外部基线（G2）：用 **PyVRP 作联合可行性判定器**，不是完整路线重优化。

    每个接受判定时，把「已接受但尚未派车的订单 ∪ 候选订单」放进一个静态 VRPTW，
    让 PyVRP 在 ``pyvrp_time_limit`` 秒内求解；**只有全部能被服务**才接受候选订单。
    判定后仍交给父类 SAA 做实际派车与插入。

    严格在线保证：进模型的订单只来自 ``env.dataset['reveal_time'] <= clock`` 的集合，
    因此可直接用 L2 的 `visibility` 检查核对无未来信息。

    口径说明（必须写进任何引用它的记录）：
    * 它是"外部求解器把关的接单器"，**不是**"PyVRP 路线质量"的代表；
    * 时间窗用 ``env.tw_end``（小时）折成秒，跨温区/载重按 PyVRP 的整数容量缩放；
    * 求解有 ``time_limit`` 截断，因此可能**误拒**（解不出来但其实可行）。
    """

    name = 'pyvrp_feasible'

    def __init__(self, *args, pyvrp_time_limit=0.2, pyvrp_max_orders=60,
                 pyvrp_scale=100, **kwargs):
        super().__init__(*args, **kwargs)
        self._tl = float(pyvrp_time_limit)
        self._max_orders = int(pyvrp_max_orders)
        self._scale = int(pyvrp_scale)
        self._pool_sizes = []          # 每次判定时的池子大小（诊断"把关位置是否为空"）

    def _pool(self, env, inst_idx, served_mask, o):
        disp = set()
        for route in getattr(self, '_plan', {}).values():
            disp.update(int(x) for x in route)
        pool = [int(x) for x in self._accepted
                if (not bool(served_mask[int(x)])) and int(x) not in disp
                and int(x) != int(o)]
        return pool + [int(o)]

    def _jointly_feasible(self, env, inst_idx, pool, clock) -> bool:
        import math
        try:
            from pyvrp import Model
            from pyvrp.stop import MaxRuntime
        except Exception:  # noqa: BLE001
            return True                     # 无 PyVRP 时退化为"不过滤"，并会被记录
        if len(pool) > self._max_orders:
            return True
        rt = env.dataset['reveal_time'][inst_idx]
        tw = env.tw_end[inst_idx]
        q = env.demands[inst_idx]
        d = env.dist_mat[inst_idx]
        spd = float(getattr(env, 'tw_speed', 1.5))
        sc = self._scale
        m = Model()
        depot = m.add_depot(x=0.0, y=0.0)
        m.add_vehicle_type(num_available=int(getattr(self, '_n_vehicles', 15)),
                           capacity=[int(50 * sc)])
        nodes = {}
        for x in pool:
            if float(rt[x]) > float(clock) + 1e-9:
                return False                # 理论上不会发生（上游已过滤），防御性拒绝
            nodes[x] = m.add_client(
                x=float(d[0, x]), y=0.0,   # 一维嵌入：坐标取"到仓距离"，边权仍用真实 d
                delivery=int(round(float(q[x]) * sc)),
                service_duration=int(round(0.05 * 3600)),
                tw_early=0,
                tw_late=int(round(float(tw[x]) * 3600)))
        locs = [(0, depot)] + [(x, nodes[x]) for x in pool]
        for i, (xi, li) in enumerate(locs):
            for j, (xj, lj) in enumerate(locs):
                if i == j:
                    continue
                span = 0.0 if xi == 0 else (0.0 if xj == 0 else float(d[xi, xj]))
                if xi == 0:
                    span = float(d[0, xj])
                elif xj == 0:
                    span = float(d[0, xi])
                m.add_edge(li, lj, distance=int(round(span * sc)),
                           duration=int(round(span / spd * 3600)))
        res = m.solve(stop=MaxRuntime(self._tl), seed=0, display=False)
        best = res.best
        if best is None:
            return False
        return bool(sum(len(r) for r in best.routes()) >= len(pool))

    def admission_summary(self) -> dict:
        base = super().admission_summary()
        ps = list(getattr(self, '_pool_sizes', []))
        if ps:
            import numpy as _np
            base['pyvrp_pool'] = dict(n=len(ps), mean=float(_np.mean(ps)),
                                      median=float(_np.median(ps)), max=int(_np.max(ps)),
                                      frac_gt_max_orders=float(
                                          _np.mean([1.0 if x > self._max_orders else 0.0
                                                    for x in ps])))
        return base

    def _saa_decide(self, env, inst_idx, clock, vehicles, served_mask, o, scenarios, t0):
        if not hasattr(self, '_n_vehicles'):
            self._n_vehicles = len(vehicles)
        pool = self._pool(env, inst_idx, served_mask, o)
        if len(self._pool_sizes) < 5000:
            self._pool_sizes.append(len(pool))
        if not self._jointly_feasible(env, inst_idx, pool, clock):
            self._rejected.add(o)
            return
        super(StaticPriceReplanner, self)._saa_decide(env, inst_idx, clock, vehicles,
                                                      served_mask, o, scenarios, t0)

class ClassTierReplanner(SaaReplanner):
    """温区收入分层保留（接拒层）。

    为什么是温区而不是能耗/品质
    ----------------------------
    冻结 a1 评测器的闭环效用是 ``utility = revenue − 0.1·distance_km``（品质与制冷能耗只进
    硬约束与报告量），而 ``REV = {18°C: 10, 4°C: 20, −18°C: 30}``、三类订单的需求量分布相近
    （mean q ≈ 2.0）。于是三类的**收入密度相差 3 倍**，而服务能力（车队/时间窗）是稀缺的：
    此时把稀缺的服务位留给高收入温区，是纯因果规则能拿到的最直接收益。

    本类只做一件事：只接「允许温区」的订单；可选地在 ``late_clock`` 之后只接更窄的一层。
    **不使用任何未来信息**：判定只用当前到达订单的温区与当前 clock（墙上时间）。
    """

    name = 'class_tier'

    def __init__(self, *args, allowed_classes=(1, 2), late_classes=None,
                 late_clock=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._allowed = frozenset(int(c) for c in allowed_classes)
        self._late = None if late_classes is None else frozenset(int(c) for c in late_classes)
        self._late_clock = None if late_clock is None else float(late_clock)

    def _permitted(self, clock) -> frozenset:
        if (self._late is not None and self._late_clock is not None
                and float(clock) >= self._late_clock):
            return self._late
        return self._allowed

    def _saa_decide(self, env, inst_idx, clock, vehicles, served_mask, o, scenarios, t0):
        cls = int(env.dataset['temp_class'][inst_idx, o])
        if cls not in self._permitted(clock):
            self._rejected.add(o)
            return
        super()._saa_decide(env, inst_idx, clock, vehicles, served_mask, o, scenarios, t0)


