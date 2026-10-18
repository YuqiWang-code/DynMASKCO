# G2 外部基线（OR-Tools 作路线求解器）：**BLOCKED** —— 7 次迭代未通过可行性

- 日期：2026-10-18（继续迭代，第 84 轮）
- 类型：**BLOCKED 记录**（诚实登记；不把"跑出数字"当"通过"）
- 代码：`scripts/admission/panel_replanner.py::ORToolsSaaReplanner`、`scripts/baselines/ortools_rolling_horizon.py`
- 目标：把 OR-Tools 作为**外部非学习强基线**接进严格在线面板（G2 基线半边）

## 1. 现在它能跑，但**不可行**

最新一次冒烟（`results/admission_panel/smoke_ortools6`，1 天，97.9 s）：

| 量 | 值 |
|---|---:|
| utility | **2339.17** |
| 收入 | 2390.0 |
| 里程 | 508.3 km |
| 服务单 | 104 |
| **能耗** | **1186.8**（预算 **710.65**） |
| `hard_feasible` | **False** |
| failure tags | `accepted_not_delivered`, `budget_violation`, `commitment_violation`, `served_not_accepted` |

**注意这个 2339.17 是无效数字**：它违反了能耗预算（超 67%）、承诺一致性、以及接单-送达一致性。
把它写进排行榜会直接污染 SOTA 对照。

## 2. 七次迭代的过程（每一层都是真问题）

| # | 现象 | 根因 | 处置 |
|---|---|---|---|
| 1 | `TypeError: missing num_vehicles` | 面板只传了部分 kwarg | 显式传 `capacity/num_vehicles` |
| 2 | `execution_crash` | ORToolsReplanner 是旧接口（缺 `on_reveal/restore_state`） | 改为**组合**：继承 SAA 拿接口，`plan` 委托给 OR |
| 3 | `'float' object cannot be interpreted as an integer` | `capacity` 传 float | 取整 |
| 4 | 同上（start_loads） | 初始载重是 float | 取整 |
| 5 | `pickup exceeds shared vehicle capacity` | `demands.astype(int)` **截断**需求（2.7→2），OR 低估载重 | 需求 ×100 + `ceil`，容量/载重同步放大 |
| 6 | `budget_violation` + `served_not_accepted` | 只继承 `SaaReplanner` 时**没有接拒层**，`_accepted` 为空、不做预算控制 | 在 `_saa_decide` 内**内联**登记静态价判据 + 预算跟踪 |
| 7 | `TypeError: NoneType not iterable` | `lambda_grid` 未传入（价格标定缺参数） | 面板补传 `lambda_grid/clock_grid/g_table/objective` |

修完 7 层后**能跑**，但暴露了结构性冲突（见 §3）。

## 3. 为什么仍然不可行（结构性原因，不是再修两层就能好）

- 面板的能耗**约束**是环境在**派车/执行**时按冷链路网累计的**真实制冷能耗**（本例 1186.8）；
- 而接单层能被策略看到的只是**预冷能耗代理** `e_lower = 0.15·q·ΔT`；
- 静态 λ 臂之所以能守住 707，是因为它的**路线由 SAA 生成**，而 SAA 内部同时维护预算记账；
- 一旦把**路线**交给外部求解器（OR-Tools 直接写 `mutable_suffix`），这条记账链就被绕开
  ⇒ 能量约束只能事后被发现（`budget_violation`），策略侧无法阻止。

⇒ **结论**：在当前架构里，"外部求解器**替换路线**"与"能耗预算约束"不能同时成立，
除非重写环境的预算记账（超出 G2 基线接入的范围）。

## 4. 因此的裁决

1. **`OR-Tools 作路线求解器` = `BLOCKED(structural)`**，不进入排行榜；
2. 上面那个 2339.17 **不得**被引用为"OR-Tools 很强"——它是**不可行解**；
3. 替代路径（下一步）：让外部求解器只做**同集合重优化**（不改 served 集合、只重排每辆车的 suffix），
   这样预算与承诺语义仍由 SAA 维护；可行性仍由环境逐单检查。
   这条路与我已有的 `route_reopt_pyvrp.py`（离线预知上界）是同一条技术路线，只是搬进闭环。

## 5. 已修复且**保留**的成果（不是白做）

- `ortools_rolling_horizon.py` 的**需求截断 bug**（`astype(int)` 低估载重）已修：×100 + `ceil`；
  这是一个真实缺陷，任何后续用该基线的人都会踩；
- 面板新增 `MASKCO_TRACEBACK=1` 可选打印，用于后续接入任何外部基线时快速定位；
- `per_day` 现在带上 `failures` 与 `error` 字段（此前失败原因不可见，导致我多花了两轮）。

## 6. 这不能证明什么

- **不证明** OR-Tools 在严格在线协议下弱：它根本没被合法评测过；
- **不证明**"接拒层必须由 SAA 维护"是唯一设计：只是当前环境的记账方式如此；
- 也不改变排行榜任何数字（本轮未产生任何合法的新数字）。
