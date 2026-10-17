# 参考文献索引（62 篇 PDF）

> PDF 正文都在 `C-VRP_Cold-chainVehicleRoutingProblem/docs/论文参考/`（**不搬家、不复制**），本文件提供按主题的清单与用途标注。
> 新增论文：PDF 放入对应子目录 → 在本文件对应表里加一行（`文件名 | 用途 | 一句话结论`）→ 若被方法/参数引用，同时在引用处标注路径。

## 1. 上游方法（4 篇）

目录：[`../../C-VRP_Cold-chainVehicleRoutingProblem/docs/论文参考/00_MASKCO/`](../../C-VRP_Cold-chainVehicleRoutingProblem/docs/论文参考/00_MASKCO/)

| 文件 | 用途 |
|---|---|
| `MASKCO.pdf` / `MASKCO_pdf.pdf` | ICLR 2026 原文（掩码生成范式、mask-and-reconstruct 推理） |
| `MASKCO的全文翻译.pdf` | 全文中文翻译（速读用，引用页码请回原文） |
| `MASKCO动态冷链论文计划.pdf` | 本项目的选题/计划底稿 |

配套阅读笔记：[`模型框架.md`](../../C-VRP_Cold-chainVehicleRoutingProblem/docs/论文参考/00_MASKCO/模型框架.md)、[`复现代码架构设计.md`](../../C-VRP_Cold-chainVehicleRoutingProblem/docs/论文参考/00_MASKCO/复现代码架构设计.md)。

## 2. 冷链车辆路径规划（7 篇）

目录：[`.../论文参考/优化/01_冷链车辆路径规划/`](../../C-VRP_Cold-chainVehicleRoutingProblem/docs/论文参考/优化/01_冷链车辆路径规划/)

主题：易腐品/生鲜的 VRPTW、时变路网、双目标（客户优先级 + 定制时间窗）、可逆车辆路径、节能路径、遗传算法。

| 文件 |
|---|
| `不确定需求下应急易腐物资多周期车辆路径问题.pdf` |
| `电动车易腐品配送路径规划（变速与软时间窗）.pdf` |
| `基于客户价值的生鲜农产品时变车辆路径问题.pdf` |
| `冷链物流转型：易腐品可逆车辆路径方法.pdf` |
| `生鲜电商农产品供应链节能车辆路径优化.pdf` |
| `时间窗与品质约束下易腐品车辆路径的遗传算法优化.pdf` |
| `易腐品配送双目标车辆路径规划（客户优先级与定制时间窗）.pdf` |

## 3. 神经组合优化（4 篇）

目录：[`.../论文参考/优化/02_神经组合优化/`](../../C-VRP_Cold-chainVehicleRoutingProblem/docs/论文参考/优化/02_神经组合优化/)

| 文件 | 与本项目的关系 |
|---|---|
| `URS：跨问题零样本泛化的统一神经路由求解器.pdf` | “统一神经求解器”对照 |
| `SPACE：对称与非对称路由问题的统一通用神经求解器.pdf` | 同上 |
| `Vehicle-as-Prompt：异构车队车辆路径的统一深度强化学习框架.pdf` | 异构车队 / prompt 条件化 |
| `大语言模型驱动的车辆路径问题统一框架.pdf` | LLM + VRP 的替代路线 |

## 4. 冷链品质模型（3 篇）

目录：[`.../论文参考/优化/03_冷链品质模型/`](../../C-VRP_Cold-chainVehicleRoutingProblem/docs/论文参考/优化/03_冷链品质模型/)

用途：C0 品质合同的**文献依据**（零阶/一阶动力学、货架期、阈值）。

| 文件 |
|---|
| `食品冷链时间-温度管理：近期进展综述.pdf` |
| `易腐食品供应链品质保证的温度管理.pdf` |
| `基于机器学习的易腐品安全与品质最优温度管理模型.pdf` |

## 5. 冷藏车热力学（8 篇）

目录：[`.../论文参考/优化/04_冷藏车热力学/`](../../C-VRP_Cold-chainVehicleRoutingProblem/docs/论文参考/优化/04_冷藏车热力学/)

用途：开门热侵入（door-opening）、制冷功率/COP、相变蓄冷、双温区控制的物理依据（C0 `coldchain_state.py` 的参数来源）。

| 文件 |
|---|
| `开门过程中相变材料温控与能耗分析.pdf` |
| `冷藏车开门时空气热空气动力学数值分析.pdf` |
| `冷藏柜开关门湿空气传递及其热负荷研究.pdf` |
| `电制冷拖车的热与功耗模型.pdf` |
| `实际工况下冷藏车热与流动分析.pdf` |
| `低温相变蓄冷材料中型冷藏车数值模拟.pdf` |
| `流动导向相变蓄冷材料冷藏车温度分布数值研究.pdf` |
| `冷链物流车双温区控制实验研究.pdf` |

## 6. 标准与法规（2 篇）

目录：[`.../论文参考/优化/05_标准/`](../../C-VRP_Cold-chainVehicleRoutingProblem/docs/论文参考/优化/05_标准/)

| 文件 |
|---|
| `GB 31605-2020 食品安全国家标准 食品冷链物流卫生规范.pdf` |
| `GBT 28843-2024 食品冷链物流追溯管理要求.pdf` |

## 7. 经典 VRP 方法（1 篇）

目录：[`.../论文参考/优化/06_经典VRP方法/`](../../C-VRP_Cold-chainVehicleRoutingProblem/docs/论文参考/优化/06_经典VRP方法/)

`遗传算法求解车辆路径问题的组合目标优化.pdf`

## 8. 对比方法（30 篇）

目录：[`.../论文参考/对比方法/`](../../C-VRP_Cold-chainVehicleRoutingProblem/docs/论文参考/对比方法/)（三处，按纳入时间分）

| 子目录 | 篇数 | 内容 |
|---|---|---|
| `CC_Compare/` | 9 | arXiv 编号命名（`1912.05784` … `2406.15007`）：POMO/AM、多任务、DPDP 等**已复现基线**的原论文 |
| `对比方法/` | 18 | 新近工作（`2405.01029`、`2503.16159`、`2511.17435`、NeurIPS-2024 复杂约束、AAAI24、MDPI/Elsevier 多篇）+ 时间依赖电动取送货冷链 DRL |
| `历史版本/` | 3 | AM（Kool 2019）、POMO（NeurIPS 2020）、DPDP（Kool 2022）——**历史对照，结论以新版总表为准** |

阅读笔记：[`对比方法总表.md`](../../C-VRP_Cold-chainVehicleRoutingProblem/docs/论文参考/对比方法/对比方法总表.md)（22 KB，先读）、[`改进清单.md`](../../C-VRP_Cold-chainVehicleRoutingProblem/docs/论文参考/对比方法/改进清单.md)、[`历史版本/*.md`](../../C-VRP_Cold-chainVehicleRoutingProblem/docs/论文参考/对比方法/历史版本/)。

## 9. 参数校准（3 篇）

目录：[`.../论文参考/校准参数/`](../../C-VRP_Cold-chainVehicleRoutingProblem/docs/论文参考/校准参数/)

| 文件 | 用途 |
|---|---|
| `Analysis of Nutrients and Volatile Compounds in Cherry Tomatoes Stored at Different Temperatures.pdf` | 番茄（18 °C）品质速率依据 |
| `fishes-09-00480-v2.pdf` | 鱼类（4 °C / −18 °C）感官评分与货架期 |
| `foods-09-01893-v2.pdf` | 同上补充（品质动力学） |

参数落地位置：`C-VRP_Cold-chainVehicleRoutingProblem/scripts/coldchain/coldchain_contract.py`（`QualityConfigV2` 的 `rate_per_hour` 等，逐项注明文献或仿真推导）。

## 10. 引用与登记规范

1. **正文引用**：在方法/参数文档里写 `文件名（年份/期刊）` + 相对路径，不写“某论文提出……”这类无法定位的说法。
2. **参数依据**：每个物理/品质参数必须能追到“文献值 / 仿真推导 / 实测”三者之一；改参数 ⇒ 重新冻结 `contract_hash`。
3. **不追认**：文献支持的是“参数取值合理”，不构成本项目方法的证据；不要把文献结论直接写成实验结果。
4. **版权与公开范围**：这些 PDF **目前是被 git 跟踪的**（随仓库一起分发，历史即如此）。若本仓库要转为公开，需先评估第三方 PDF 的分发风险——建议在公开前把 `docs/论文参考/` 移出仓库（改为本地/网盘挂载），并保留本索引的“文件名 + 出处”即可检索。
