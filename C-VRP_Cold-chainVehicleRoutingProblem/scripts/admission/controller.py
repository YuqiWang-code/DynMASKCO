"""在线接拒控制器（纯函数层）：把 A-v1 的 accept/reject 决策从仿真器里解耦出来。

设计约束（与仓库既有约定一致）
--------------------------------
* **不导入仿真器**：本模块只接收标量/数组（订单视图 + 时钟 + 剩余预算），因此可以在
  毫秒级单测里迭代接拒策略，而不必跑完整 CVRPTW 仿真。
* **无 ``__init__.py``**：扩展目录下按既有规则通过 ``sys.path.insert`` 导入。
* **因果性**：``decide()`` 只看 (订单特征, clock, 已接受集合/剩余预算)，绝不读取未来订单；
  单测 ``test_admission_controller.test_causality`` 用"截断未来订单流"来验证。
* **可复现**：所有策略都是确定性的；同一输入必须给出逐位相同的 ``Decision``。

术语（与登记文件一致）
----------------------
* ``e_hat``：登记的成本口径 = 不可避免的**预冷能耗** ``q · k_precool · (T_amb − T_target)``，
  不是 cooling_share 边际估计（后者是每单常数，会颠倒类别排序）。
* ``revenue``：类别收入 ``REV = {0: 10, 1: 20, 2: 30}``（元）。``p_c = 0`` 时不扣拒绝损失。
* ``lambda``：预冷能耗的**影子价格**（元 / kWh 当量）。接受准则 ``revenue − lambda·e_hat > 0``。

参考
----
* 现有登记规则（静态影子价格 + 预算预留）：``research/.../a1_budget_reserving_admission_root_v4/reserving_admission.py``
* BwK 对偶/影子价格：见 ``docs/02_参考文献/`` 里的 BwK 调研笔记。
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

# 登记的类别收入（与 evidence root 的 REV 常量一致）。
REV = {0: 10.0, 1: 20.0, 2: 30.0}


@dataclass(frozen=True)
class OrderView:
    """一条待决策订单的最小充分信息（全部来自已揭示信息）。"""

    order_id: int
    class_id: int
    quantity: float
    revenue: float
    e_hat: float
    reveal_time: float = 0.0

    @staticmethod
    def build(order_id: int, class_id: int, quantity: float, e_hat: float,
              reveal_time: float = 0.0, revenue: float | None = None) -> "OrderView":
        rev = float(REV[int(class_id)]) if revenue is None else float(revenue)
        return OrderView(order_id=int(order_id), class_id=int(class_id),
                         quantity=float(quantity), revenue=rev,
                         e_hat=float(e_hat), reveal_time=float(reveal_time))

    @property
    def ratio(self) -> float:
        """每单位预冷能耗的收入（rank 用）。"""
        return self.revenue / self.e_hat if self.e_hat > 0 else math.inf


@dataclass
class Decision:
    """一次接拒决策的完整记录（可直接写成 audit trail）。"""

    accept: bool
    reason: str
    policy: str
    clock: float = 0.0
    lam: float | None = None
    lam_bucket: int | None = None
    e_hat: float = 0.0
    revenue: float = 0.0
    budget_remaining: float = 0.0
    arm: int | None = None
    extra: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        d = dict(accept=bool(self.accept), reason=self.reason, policy=self.policy,
                 clock=float(self.clock), lam=(None if self.lam is None else float(self.lam)),
                 lam_bucket=self.lam_bucket, e_hat=float(self.e_hat),
                 revenue=float(self.revenue), budget_remaining=float(self.budget_remaining),
                 arm=self.arm)
        d.update(self.extra)
        return d


class AdmissionState:
    """一天的接受集合、已花预冷能耗与审计轨迹。"""

    def __init__(self, budget: float, day_index: int | None = None):
        self.day_index = day_index
        self.budget = float(budget)
        self.accepted: list[int] = []
        self.rejected: list[int] = []
        self.spent_e = 0.0
        self.accepted_revenue = 0.0
        self.trace: list[Decision] = []

    # --- 读写 -------------------------------------------------------------
    @property
    def budget_remaining(self) -> float:
        return self.budget - self.spent_e

    @property
    def n_accepted(self) -> int:
        return len(self.accepted)

    def accepted_set(self) -> set[int]:
        return set(self.accepted)

    def note(self, decision: Decision, order: OrderView) -> None:
        self.trace.append(decision)
        if decision.accept:
            self.accepted.append(order.order_id)
            self.spent_e += order.e_hat
            self.accepted_revenue += order.revenue
        else:
            self.rejected.append(order.order_id)

    def lambda_path(self) -> list[float]:
        return [d.lam for d in self.trace if d.lam is not None]


class AdmissionController:
    """把策略（policy）与状态（state）组装成可复用的接拒器。

    policy 只需实现两个方法::

        reset(day_orders: list[OrderView], budget: float, horizon: float) -> None
        decide(order: OrderView, clock: float, state: AdmissionState) -> Decision
    """

    def __init__(self, policy, budget: float):
        self.policy = policy
        self.budget = float(budget)
        self.state = AdmissionState(self.budget)
        self._day_orders: list[OrderView] = []
        self._horizon = 0.0

    # --- 生命周期 ---------------------------------------------------------
    def begin_day(self, day_orders: list[OrderView], horizon: float, day_index: int | None = None) -> None:
        """开始新的一天。``day_orders`` 只用于策略校准（不得含未来信息的使用）。

        注意：需要"剩余视野期望能耗"的策略（如登记静态影子价格）只能读 **已揭示** 订单，
        因此这里的 ``day_orders`` 仅作为可选的离线表查询的上下文，由具体策略自行决定是否使用；
        因果性由策略实现保证（见 ``RegisteredShadowPrice`` 的说明）。
        """
        self.state = AdmissionState(self.budget, day_index=day_index)
        self._day_orders = list(day_orders)
        self._horizon = float(horizon)
        self.policy.reset(self.state, horizon=self._horizon, budget=self.budget)

    def decide(self, order: OrderView, clock: float) -> Decision:
        decision = self.policy.decide(order, float(clock), self.state)
        self.state.note(decision, order)
        return decision

    # --- 一天结束后的指标 -------------------------------------------------
    def summary(self) -> dict:
        st = self.state
        used = st.spent_e / st.budget if st.budget > 0 else float("nan")
        return dict(policy=getattr(self.policy, "name", type(self.policy).__name__),
                    day_index=st.day_index,
                    n_decisions=len(st.trace), n_accepted=st.n_accepted,
                    accepted_revenue=st.accepted_revenue, spent_e=st.spent_e,
                    budget=st.budget, budget_used_ratio=used,
                    budget_violated=bool(st.spent_e > st.budget + 1e-9),
                    n_below_shadow_price=sum(1 for d in st.trace if d.reason == "below_shadow_price"),
                    n_over_budget=sum(1 for d in st.trace if d.reason == "over_remaining_budget"),
                    n_route_infeasible=sum(1 for d in st.trace if d.reason == "route_infeasible"),
                    lambda_first=(st.lambda_path()[0] if st.lambda_path() else None),
                    lambda_last=(st.lambda_path()[-1] if st.lambda_path() else None),
                    lambda_mean=(sum(st.lambda_path()) / len(st.lambda_path())
                                 if st.lambda_path() else None))
