# 文档中心（`docs/`）

> 本目录是**只做索引与规范**的根级文档入口：项目原有文档（含 200+ 篇计划/审计文档、62 篇论文 PDF、20+ 参考代码库）继续留在原位，此处提供分类导航、阅读顺序与写作规范，**不复制正文、不搬动已登记工件**。
>
> 更新：2026-10-17 ｜ 维护入口：随手更新本目录下的索引文件；正文更新仍写回各正文位置。

## 四个分类

| 分类 | 放什么 | 入口 |
|---|---|---|
| **指导性文档** | 接手阅读路线、服务器使用、文档规范、**自我迭代研发总纲（2026-10-18）**、工程不变式与验收口径导航 | [`00_指导/`](00_指导/) |
| **调研文档** | 对比方法调研、动态冷链/神经组合优化文献调研、机制诊断与负结果调研；含 2026-10-17 方案三件套（BwK 接拒 / 外部数学 / 几何可行性） | [`01_调研/README.md`](01_调研/README.md) |
| **参考文献** | 论文 PDF（MaskCO 原文、冷链路网/品质/热力学/标准、对比方法、参数校准）+ 新方向的文献与实现调研笔记 | [`02_参考文献/README.md`](02_参考文献/README.md) |
| **参考代码** | 上游 MaskCO 代码地图、`CC_Compare/` 20+ 基线实现与 `dcc_vrp/` 适配约定 | [`03_参考代码/README.md`](03_参考代码/README.md) |
| **实施与结果** | 每轮工作的可读记录：跑了什么、数字、判据、诚实边界（原生产物仍在 `results/`） | [`04_实施与结果/README.md`](04_实施与结果/README.md) |

## 权威状态入口（不在本目录，别在这里找答案）

| 想知道 | 打开 |
|---|---|
| 项目当前状态（唯一权威） | [`../C-VRP_Cold-chainVehicleRoutingProblem/项目当前状态.md`](../C-VRP_Cold-chainVehicleRoutingProblem/项目当前状态.md) |
| 阶段 / Gate / 下一动作 | [`../C-VRP_Cold-chainVehicleRoutingProblem/docs/当前规划/结果与进度/执行进度表.md`](../C-VRP_Cold-chainVehicleRoutingProblem/docs/当前规划/结果与进度/执行进度表.md) |
| 三条研究线入口 | [`../C-VRP_Cold-chainVehicleRoutingProblem/00_项目导航.md`](../C-VRP_Cold-chainVehicleRoutingProblem/00_项目导航.md) |
| 仓库总览与工程指引 | [`../README.md`](../README.md)（附录 A 为原 `CLAUDE.md` 全文） |

## 放置规则（与 `00_项目导航.md` 一致，勿另立第二份正文）

1. **单一正文**：某个课题的正文只写一处；本目录新增文件只允许是**索引、规范、阅读路线**这三类，不允许复制既有正文。
2. **按方向归属**：单方向的可编辑文档写进 `C-VRP_Cold-chainVehicleRoutingProblem/{01_取货线,02_配送线,03_负结果线}/文档/`；跨方向的计划、状态、进度写进 `C-VRP_Cold-chainVehicleRoutingProblem/docs/当前规划/`。
3. **不搬动已登记工件**：`research/` 下的登记 / 审计 / 回执、`results/` 下的运行目录、冻结的数据快照与字节容器**原地不动**（哈希与路径都被登记过）。
4. **新论文**：PDF 存 `C-VRP_Cold-chainVehicleRoutingProblem/docs/论文参考/<分类>/`，并在 [`02_参考文献/README.md`](02_参考文献/README.md) 的对应表里登记一行（标题、年份、用途、相对路径）。
5. **失败不改写**：文档中的 FAIL / BLOCKED / NO-GO 记录只能追加新版本或勘误条目，不得就地改写成 PASS。
6. **口径三列**：任何数字必须注明是 `candidate` / `accepted` / `closed_loop` 中的哪一列；`distance_cost` 与 `coldchain_cost` 不得混用。

## 目录现状（供安心：正文都在，只是不搬家）

| 位置 | 内容 |
|---|---|
| `C-VRP_Cold-chainVehicleRoutingProblem/docs/当前规划/` | 202 篇 md：`决策与审计`、`结果与进度`、`工程实现`、`研究设计`、`实验与评估`、`文献调研`、`历史已收束`、`历史快照` |
| `C-VRP_Cold-chainVehicleRoutingProblem/docs/实验记录/` | 3 篇：阶段实验记录 |
| `C-VRP_Cold-chainVehicleRoutingProblem/docs/论文参考/` | 62 篇 PDF + 8 篇阅读笔记/总表 |
| `C-VRP_Cold-chainVehicleRoutingProblem/negative_result_paper/` | 负结果论文独立复现包（脚本 + 文档 + 结果） |
| `CC_Compare/` | 20+ 基线实现；`CC_Compare/docs/` 为 A-v1 对比总表与读表限定 |
| `research/` | 研发证据树（登记 / 独立审计 / RESULT / 回执） |
| `C-VRP.../scripts/admission/` | **新增（2026-10-17）**：接拒控制器纯函数层（`controller.py`）+ 策略集合（`policies.py`），见 [`04_实施与结果/`](04_实施与结果/README.md) |
