# 实施与结果记录（`docs/04_实施与结果/`）

> 这里放**本轮工作的可读记录**：跑了什么、数字是多少、判据是什么、诚实边界是什么。
> 机器原生产物仍在 `C-VRP_Cold-chainVehicleRoutingProblem/results/<run>/`（gitignore，不入库）；
> 这里的记录是"给人看、给引用"的那一份，**数字一旦写入不放宽**，只追加更正。

## 记录规则（与项目既有纪律一致）

1. **先冻结后实施**：正式实验先写预登记（判据、分母、预算、止损、分组方案），再跑；开发诊断必须显式标注 `DEVELOPMENT_DIAGNOSTIC`。
2. **三列口径分列**：`candidate`（候选质量）/ `accepted`（接受后）/ `closed_loop`（闭环终局）；不得把 candidate 叫"部署"。
3. **失败不改写**：`FAIL` / `BLOCKED` / `NO-GO` 只追加，不就地改成 PASS。
4. **写明"未主张"**：每份记录必须有"这不能证明什么"一节。
5. **可复现**：记录命令、配置、随机种子、数据身份；产物路径写清楚。

## 记录清单

| 日期 | 记录 | 类型 | 结论 |
|---|---|---|---|
| 2026-10-17 | [接拒层离线对照（dev v1）](2026-10-17_接拒层离线对照_dev_v1.md) | 开发诊断（表级） | H1 在接拒层**成立**：动态 λ 相对静态 λ 逐日差 `[+20,+110,+30,+30,0]`，均值 **+38.00**，0 天为负；机制是静态规则预算利用率只有 93–99%，动态用满。**未主张**：不等于日效用增益（不含距离/品质/TW） |

## 相关代码与入口

| 用途 | 路径 |
|---|---|
| 接拒控制器（纯函数层） | `C-VRP_Cold-chainVehicleRoutingProblem/scripts/admission/controller.py` |
| 策略集合（静态 λ / 固定阈值 / BwK 对偶 / 预算曲线） | `…/scripts/admission/policies.py` |
| 单测（7 项，含与登记实现逐条对拍） | `…/scripts/tests/test_admission_controller.py` |
| 接拒层离线对照 | `…/scripts/evaluation/run_admission_offline_regret.py` |
| 登记面板（静态规则的原件） | `research/review_3080_20261010/pickup/a1_budget_reserving_admission_root_v4/` |
| 方案三件套 | [`docs/01_调研/2026-10-17_方案三件套/`](../01_调研/2026-10-17_方案三件套/) |
| 文献与实现调研 | [`docs/02_参考文献/BwK与保形_文献与实现_2026-10-17.md`](../02_参考文献/BwK与保形_文献与实现_2026-10-17.md) |
