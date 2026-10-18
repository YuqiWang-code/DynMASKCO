"""接拒策略集合：静态影子价格（复现登记规则）、固定阈值、BwK 动态对偶价格、预算曲线。

每个策略都是确定性的、只依赖已揭示信息与当前状态，符合 A-v1 的 strict-online 因果口径。

命名与来源
----------
``RegisteredShadowPrice``
    逐字复现 ``research/review_3080_20261010/pickup/a1_budget_reserving_admission_root_v4/
    reserving_admission.py`` 的判定逻辑（含 λ 网格搜索的 tie-break 与严格 ``> 0``）；
    单测 ``test_admission_controller.test_registered_equivalence`` 与原件逐条对拍。
``FixedThreshold``
    固定 kWh 阈值基线：``revenue / e_hat >= theta`` 才接受。
``DynamicDual``
    Bandits-with-Knapsacks 风格的在线对偶（次梯度）价格：
    ``λ_{t+1} = clip(λ_t + η·(c_t − B/T), 0, λ_max)``，接受准则 ``revenue − λ_t·e_hat > 0``。
    这里 ``T`` 用 **TRAIN 集**估计的期望轮数（每日订单数）传入，当前日不读未来。
``DynamicPriceCurve``
    "把 λ 写成剩余预算的函数"的版本：``λ(r) = λ_max − (λ_max − λ_min)·r^γ``，
    ``r = 剩余预算 / 预算``。预算充裕 → λ 低（宽松），预算将尽 → λ 高（挑剔）。

所有策略都带**硬预算闸**：``e_hat > 剩余预算`` 时直接拒绝（原因 ``over_remaining_budget``），
与登记规则一致；该拒绝发生在影子价格判定之前。
"""
from __future__ import annotations

import bisect
import math

try:  # 作为命名空间包导入（scripts/ 在 sys.path 上，仓库规则：不建 __init__.py）
    from admission.controller import Decision, OrderView, REV
except ImportError:  # 直接以 scripts/admission 为根导入时
    from controller import Decision, OrderView, REV


class Policy:
    """策略基类：只需实现 ``_decide_impl``。"""

    name = "policy"

    def reset(self, state, *, horizon: float, budget: float) -> None:  # noqa: D401
        self.state = state
        self.horizon = float(horizon)
        self.initial_budget = float(budget)

    def decide(self, order: OrderView, clock: float, state) -> Decision:
        raise NotImplementedError

    # --- 共用工具 ---------------------------------------------------------
    def _base(self, order: OrderView, clock: float, state, *, e_hat: float | None = None) -> dict:
        return dict(policy=self.name, clock=float(clock),
                    e_hat=float(order.e_hat if e_hat is None else e_hat),
                    revenue=float(order.revenue),
                    budget_remaining=float(state.budget_remaining))

    def _reject(self, reason: str, order: OrderView, clock: float, state, **kw) -> Decision:
        kw.setdefault('policy', self.name)
        return Decision(accept=False, reason=reason, clock=float(clock),
                        e_hat=float(order.e_hat), revenue=float(order.revenue),
                        budget_remaining=float(state.budget_remaining), **kw)


class AlwaysAccept(Policy):
    """空臂基线：只要不超预算就接受（复现 base SAA 的"没有拒绝理由"状态）。"""

    name = "always_accept"

    def decide(self, order: OrderView, clock: float, state) -> Decision:
        if order.e_hat > state.budget_remaining + 0.0:
            return self._reject("over_remaining_budget", order, clock, state)
        return Decision(accept=True, reason="admit", policy=self.name, clock=float(clock),
                        lam=0.0, e_hat=float(order.e_hat), revenue=float(order.revenue),
                        budget_remaining=float(state.budget_remaining))


class FixedThreshold(Policy):
    """固定 kWh 阈值：``revenue / e_hat >= theta``。"""

    name = "fixed_threshold"

    def __init__(self, theta: float):
        self.theta = float(theta)

    def decide(self, order: OrderView, clock: float, state) -> Decision:
        if order.e_hat > state.budget_remaining + 0.0:
            return self._reject("over_remaining_budget", order, clock, state)
        ok = order.ratio >= self.theta
        return Decision(accept=ok, reason=("admit" if ok else "below_threshold"), policy=self.name,
                        clock=float(clock), lam=self.theta, e_hat=float(order.e_hat),
                        revenue=float(order.revenue), budget_remaining=float(state.budget_remaining))


class RegisteredShadowPrice(Policy):
    """登记规则（静态影子价格 + 预算预留）的忠实复现。

    ``lambda_for(clock, remaining)`` 返回网格上**最小**的 λ，使得"剩余视野内期望被接受的
    预冷能耗"（由 TRAIN 校准表 ``g_table[li][ti]`` 给出）不超过剩余预算。
    """

    name = "registered_shadow_price"

    def __init__(self, lambda_grid, clock_grid, g_table):
        self.lam_grid = [float(x) for x in lambda_grid]
        self.clock_grid = [float(x) for x in clock_grid]
        self.g_table = [[float(v) for v in row] for row in g_table]
        if len(self.g_table) != len(self.lam_grid):
            raise ValueError("g_table 行数必须等于 lambda_grid 长度")

    # --- 纯函数部分（单测直接调用） --------------------------------------
    def clock_bucket(self, clock: float) -> int:
        ti = bisect.bisect_right(self.clock_grid, float(clock)) - 1
        return min(max(ti, 0), len(self.clock_grid) - 1)

    def lambda_for(self, clock: float, budget_remaining: float):
        ti = self.clock_bucket(clock)
        for li, lam in enumerate(self.lam_grid):
            if self.g_table[li][ti] <= budget_remaining:
                return lam, li, ti
        return self.lam_grid[-1], len(self.lam_grid) - 1, ti

    def expected_energy(self, lam_index: int, clock: float) -> float:
        return self.g_table[int(lam_index)][self.clock_bucket(clock)]

    # --- 决策 -------------------------------------------------------------
    def decide(self, order: OrderView, clock: float, state) -> Decision:
        b_rem = float(state.budget_remaining)
        if order.e_hat > b_rem:
            return self._reject("over_remaining_budget", order, clock, state)
        lam, li, ti = self.lambda_for(clock, b_rem)
        if (order.revenue - lam * order.e_hat) > 0.0:
            return Decision(accept=True, reason="admit", policy=self.name, clock=float(clock),
                            lam=lam, lam_bucket=ti, e_hat=float(order.e_hat),
                            revenue=float(order.revenue), budget_remaining=b_rem,
                            extra=dict(lambda_index=li))
        return self._reject("below_shadow_price", order, clock, state, lam=lam, lam_bucket=ti)


class DynamicDual(Policy):
    """BwK 在线对偶：λ 随"实际消耗 − 每轮预算配额"的次梯度上升/下降。

    参数
    ----
    eta        : 对偶步长（lam 单位 / kWh）
    lam0       : 初始价格；给定 ``warm_start`` 时用其覆盖（通常取静态规则的当日首个 λ）
    lam_max    : 价格上限（防止发散）
    n_expected : **TRAIN** 上估计的每日期望决策轮数（不读当前日的未来）
    eta_decay  : True 时用 ``eta / sqrt(1 + t)`` 的步长调度
    """

    name = "dynamic_dual"

    def __init__(self, eta: float = 0.05, lam0: float = 1.0, lam_max: float = 8.0,
                 n_expected: float = 200.0, eta_decay: bool = False):
        self.eta = float(eta)
        self.lam0 = float(lam0)
        self.lam_max = float(lam_max)
        self.n_expected = max(float(n_expected), 1.0)
        self.eta_decay = bool(eta_decay)

    def reset(self, state, *, horizon: float, budget: float) -> None:
        super().reset(state, horizon=horizon, budget=budget)
        self.lam = min(max(self.lam0, 0.0), self.lam_max)
        self.t = 0
        self.per_round_budget = float(budget) / self.n_expected

    def decide(self, order: OrderView, clock: float, state) -> Decision:
        lam_before = self.lam
        b_rem = float(state.budget_remaining)
        if order.e_hat > b_rem:
            # 硬预算闸不开：拒绝，并且不消耗预算配额（保守：仍推进时钟步）
            self._advance(0.0)
            return self._reject("over_remaining_budget", order, clock, state, lam=lam_before)
        ok = (order.revenue - lam_before * order.e_hat) > 0.0
        self._advance(order.e_hat if ok else 0.0)
        return Decision(accept=ok, reason=("admit" if ok else "below_shadow_price"), policy=self.name,
                        clock=float(clock), lam=lam_before, e_hat=float(order.e_hat),
                        revenue=float(order.revenue), budget_remaining=b_rem,
                        extra=dict(lambda_after=self.lam))

    def _advance(self, consumed: float) -> None:
        eta = self.eta / math.sqrt(1.0 + self.t) if self.eta_decay else self.eta
        self.lam = min(max(self.lam + eta * (float(consumed) - self.per_round_budget), 0.0),
                       self.lam_max)
        self.t += 1


class DynamicPriceCurve(Policy):
    """λ 作为剩余预算比例的函数：``λ(r) = λ_max − (λ_max − λ_min)·r^γ``。"""

    name = "dynamic_price_curve"

    def __init__(self, lam_min: float = 0.25, lam_max: float = 8.0, gamma: float = 1.0):
        self.lam_min = float(lam_min)
        self.lam_max = float(lam_max)
        self.gamma = float(gamma)

    def lambda_for_ratio(self, ratio: float) -> float:
        r = min(max(float(ratio), 0.0), 1.0)
        return self.lam_max - (self.lam_max - self.lam_min) * (r ** self.gamma)

    def decide(self, order: OrderView, clock: float, state) -> Decision:
        b_rem = float(state.budget_remaining)
        if order.e_hat > b_rem:
            return self._reject("over_remaining_budget", order, clock, state)
        ratio = b_rem / self.initial_budget if self.initial_budget > 0 else 1.0
        lam = self.lambda_for_ratio(ratio)
        ok = (order.revenue - lam * order.e_hat) > 0.0
        return Decision(accept=ok, reason=("admit" if ok else "below_shadow_price"), policy=self.name,
                        clock=float(clock), lam=lam, e_hat=float(order.e_hat),
                        revenue=float(order.revenue), budget_remaining=b_rem,
                        extra=dict(budget_ratio=ratio))


# --- 校准表构造（复现登记实现） -------------------------------------------
def build_lambda_grid(lo: float = 0.25, hi: float = 8.0, step: float = 0.125):
    grid, x = [], float(lo)
    while x <= float(hi) + 1e-9:
        grid.append(round(x, 6))
        x += float(step)
    return grid


def build_clock_grid(horizon: float, step: float = 0.5):
    grid, x = [], 0.0
    while x <= float(horizon) + 1e-9:
        grid.append(round(x, 6))
        x += float(step)
    return grid


def e_lower_of(class_id: int, quantity: float, objective: dict) -> float:
    """登记的成本口径：预冷能耗 ``q · k_precool · (T_amb − T_target[class])``。"""
    delta = max(0.0, float(objective["ambient_c"]) - float(objective["target_c"][int(class_id)]))
    return float(quantity) * float(objective["precool_energy_per_unit_per_c"]) * delta


def calibrate(train_days, objective: dict, horizon: float, lambda_grid, clock_grid, *, rev=REV):
    """``g_table[li][ti]`` = 剩余视野（clock ≥ grid[ti]）内、按 λ 放行后的期望已接受预冷能耗。

    ``train_days``：``[(reveal_time[], e_lower[], revenue[]), ...]``（每元素为一天的已揭示订单）。
    与登记实现等价：逐日按 reveal_time 排序后对"放行集合"的 e_lower 做后缀和，再按 clock 二分取值。
    """
    import numpy as np

    clk = np.asarray(clock_grid, dtype=np.float64)
    days = []
    for rev_t, est, rv in train_days:
        rev_t = np.asarray(rev_t, dtype=np.float64)
        est = np.asarray(est, dtype=np.float64)
        rv = np.asarray(rv, dtype=np.float64)
        order = np.argsort(rev_t, kind="stable")
        days.append((rev_t[order], est[order], rv[order]))
    table = []
    for lam in lambda_grid:
        row = np.zeros(len(clock_grid), dtype=np.float64)
        for rev_t, est, rv in days:
            contrib = np.where((rv - float(lam) * est) > 0.0, est, 0.0)
            suffix = np.concatenate([np.cumsum(contrib[::-1])[::-1], np.zeros(1)])
            row += suffix[np.searchsorted(rev_t, clk, side="left")]
        table.append((row / max(len(days), 1)).tolist())
    return table


def build_train_days(dataset, objective: dict, *, rev=REV):
    """把 A-v1 数据集（numpy dict）转成 ``calibrate`` 需要的按天列表。"""
    import numpy as np

    dem = np.asarray(dataset["demands"], dtype=np.float64)
    rev_t = np.asarray(dataset["reveal_time"], dtype=np.float64)
    cls_t = np.asarray(dataset["temp_class"], dtype=np.int64)
    days = []
    for d in range(dem.shape[0]):
        mask = dem[d, 1:] > 0
        cls = cls_t[d, 1:][mask]
        q = dem[d, 1:][mask]
        t = rev_t[d, 1:][mask]
        est = np.asarray([e_lower_of(int(c), float(qq), objective) for c, qq in zip(cls, q)],
                         dtype=np.float64)
        rv = np.asarray([rev[int(c)] for c in cls], dtype=np.float64)
        days.append((t, est, rv))
    return days

class OnlineKnapsack(Policy):
    """在线背包的指数阈值规则（Zhou–Chakrabarty–Lukose, 2008）。

    与静态 λ、BwK 对偶、DP 的区别：这一族**有竞争比保证**，且阈值随预算消耗**指数上升**
    —— 早期宽松、后期挑剔，把"预算该留给谁"这件事写成时间的函数，而不是一个常数价格。

    判定（单资源 = 制冷能耗预算 ``B``）::

        d_i = revenue_i / e_hat_i                      # 收入密度
        z   = 1 - budget_remaining / B                 # 已用比例 ∈ [0,1]
        φ(z) = (L/e) · (U/L)^z                         # 指数阈值
        accept ⟺ d_i ≥ φ(z)  且  e_hat_i ≤ budget_remaining

    其中 ``[L, U]`` 是**已知**的收入密度上下界（由 `REV` 与 `e_lower` 的定义域算出，
    不需要看任何未来到达）。竞争比为 ``ln(U/L) + 1``（Zhou et al. 的经典结果）。

    **为什么不声称这是本项目定理**：竞争比是文献结果，本实现只是把它接到本项目的事件流上；
    我们自己的贡献只能是"在该基准上实测这条规则的闭环效用"，不能把文献界算成自己的。
    """

    name = 'online_knapsack'

    def __init__(self, density_min: float = 1.55, density_max: float = 9.52,
                 scale: float = 1.0):
        import math
        self.L = float(density_min)
        self.U = float(density_max)
        self.scale = float(scale)
        self._inv_e = 1.0 / math.e

    def threshold(self, z: float) -> float:
        z = min(max(float(z), 0.0), 1.0)
        return self.scale * (self.L * self._inv_e) * (self.U / self.L) ** z

    def decide(self, order: OrderView, clock: float, state) -> Decision:
        b_rem = float(state.budget_remaining)
        b0 = max(float(self.initial_budget), 1e-9)
        z = 1.0 - b_rem / b0
        phi = self.threshold(z)
        e = max(float(order.e_hat), 1e-9)
        d = float(order.revenue) / e
        if e > b_rem:
            return self._reject('over_remaining_budget', order, clock, state, lam=phi)
        ok = d >= phi
        return Decision(accept=ok, reason=('admit' if ok else 'below_density_threshold'),
                        policy=self.name, clock=float(clock), lam=float(phi),
                        e_hat=float(order.e_hat), revenue=float(order.revenue),
                        budget_remaining=b_rem,
                        extra=dict(density=d, used_frac=z, phi=phi))


class DPThreshold(Policy):
    """状态依赖阈值（DP 值表）：接受 ⟺ ``net + V[t-1](b-e) ≥ V[t-1](b)``。

    值表来自 `scripts/evaluation/run_causal_dp.py --save-v`（单资源因果最优的 DP）。
    `t` 用 **TRAIN 的期望每日订单数** 减已见单数（因果代理；不用当日真实的剩余单数）。
    """

    name = 'dp_threshold'

    def __init__(self, npz_path, n_expected: float = 193.0):
        z = __import__('numpy').load(npz_path)
        self.V = z['V'].astype('float64')          # (n_steps+1, nb)
        self.step = float(z['step'])
        self.budget = float(z['budget'])
        self.n_steps = int(self.V.shape[0] - 1)
        self.n_expected = float(n_expected)
        self.seen = 0

    def reset(self, state, *, horizon: float, budget: float) -> None:
        super().reset(state, horizon=horizon, budget=budget)
        self.seen = 0

    def decide(self, order: OrderView, clock: float, state) -> Decision:
        import math
        b_rem = float(state.budget_remaining)
        nb = self.V.shape[1]
        bi = int(min(max(math.floor(b_rem / self.step), 0), nb - 1))
        t = int(min(max(round(self.n_expected - self.seen), 1), self.n_steps))
        w = int(max(round(order.e_hat / self.step), 1))
        self.seen += 1
        if w > bi:
            return self._reject('over_remaining_budget', order, clock, state)
        v_rej = self.V[t - 1][bi]
        v_acc = order.revenue + self.V[t - 1][bi - w]
        lam = (v_acc - v_rej) / max(order.e_hat, 1e-9)   # 等价影子价格（仅记录）
        ok = v_acc >= v_rej
        return Decision(accept=ok, reason=('admit' if ok else 'below_shadow_price'),
                        policy=self.name, clock=float(clock), lam=float(lam),
                        e_hat=float(order.e_hat), revenue=float(order.revenue),
                        budget_remaining=b_rem,
                        extra=dict(dp_t=t, dp_bucket=bi, dp_w=w))

