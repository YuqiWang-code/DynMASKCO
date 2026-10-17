# 调研文档索引

> 本文件只做**索引与读法**，正文全部留在原位。新增调研正文请写进
> `C-VRP_Cold-chainVehicleRoutingProblem/docs/当前规划/文献调研/` 或 `CC_Compare/docs/`，然后在这里补一行。

## 0. 最新：2026-10-17 方案三件套（当前主线依据）★

| 文档 | 内容 |
|---|---|
| [`2026-10-17_方案三件套/README.md`](2026-10-17_方案三件套/README.md) | 三份方案的总索引 + 落地状态表（阶段 0/0.5 已完成，阶段 1/2 待跑） |
| [`改进方案_在线预算接拒与遗憾界_2026-10-17.md`](2026-10-17_方案三件套/改进方案_在线预算接拒与遗憾界_2026-10-17.md) | 把在线接拒重构成 BwK：动态影子价格 λ_t、阶段 0–3、预登记与止损、几何取舍 |
| [`外部数学方法调研_BwK与保形_2026-10-17.md`](2026-10-17_方案三件套/外部数学方法调研_BwK与保形_2026-10-17.md) | 四方向排序：BwK ＞ 保形/CRC ＞ 随机占优/Pareto ＞ Wasserstein DRO/Sinkhorn |
| [`几何方法可行性调研_2026-10-17.md`](2026-10-17_方案三件套/几何方法可行性调研_2026-10-17.md) | 几何方向适配度：对称性 5/5、次模-拟阵 5/5；**不做**双曲/信息几何/扩散为主方法 |

配套的文献与实现清单见 [`../02_参考文献/BwK与保形_文献与实现_2026-10-17.md`](../02_参考文献/BwK与保形_文献与实现_2026-10-17.md)；
第一轮实验结果见 [`../04_实施与结果/2026-10-17_接拒层离线对照_dev_v1.md`](../04_实施与结果/2026-10-17_接拒层离线对照_dev_v1.md)。

## 1. 对比方法调研（哪个 baseline 能改、改了以后还敢不敢比）

| 文档 | 内容 | 说明 |
|---|---|---|
| [`../../C-VRP_Cold-chainVehicleRoutingProblem/docs/论文参考/对比方法/对比方法总表.md`](../../C-VRP_Cold-chainVehicleRoutingProblem/docs/论文参考/对比方法/对比方法总表.md) | 22 KB：候选 learned 基线逐一评估（可适配性、VRPTW 支持、开源情况） | **先读这份**再决定复现哪个方法 |
| [`改进清单.md`](../../C-VRP_Cold-chainVehicleRoutingProblem/docs/论文参考/对比方法/改进清单.md) | 13 KB：如何把各方法改到 DCC-VRP 协议 | 与 `dcc_vrp/` 适配层对照读 |
| [`CC_Compare/README.md`](../../C-VRP_Cold-chainVehicleRoutingProblem/docs/论文参考/对比方法/CC_Compare/README.md) | 复现工作区说明 | 入口 |
| [`历史版本/对比方法调研_神经组合优化.md`](../../C-VRP_Cold-chainVehicleRoutingProblem/docs/论文参考/对比方法/历史版本/对比方法调研_神经组合优化.md) | NCO 方向综述式调研 | 历史版本，结论可能已被总表覆盖 |
| [`历史版本/对比方法调研_动态冷链专用.md`](../../C-VRP_Cold-chainVehicleRoutingProblem/docs/论文参考/对比方法/历史版本/对比方法调研_动态冷链专用.md) | 动态冷链专用方法调研 | 同上 |
| [`历史版本/对比方法_开源与不开源_总表.md`](../../C-VRP_Cold-chainVehicleRoutingProblem/docs/论文参考/对比方法/历史版本/对比方法_开源与不开源_总表.md) | 开源可用性总表 | 同上 |

## 2. A-v1 对比结果总表（带资格分层，引用数字必读）

| 文档 | 内容 |
|---|---|
| [`../../CC_Compare/docs/a1_development_comparison/A-v1对比方法总表.md`](../../CC_Compare/docs/a1_development_comparison/A-v1对比方法总表.md) | 78 KB：各方法在 A-v1 口径下的对照与产出 |
| [`A-v1对比方法总表_v2_资格分层.md`](../../CC_Compare/docs/a1_development_comparison/A-v1对比方法总表_v2_资格分层.md) | 17 KB：按“资格”分层后哪些数字可用于论文 |
| [`读表注意与已知限定.md`](../../CC_Compare/docs/a1_development_comparison/读表注意与已知限定.md) | 28 KB：**读表前必看**——哪些列不可比、哪些是工程证据 |
| [`ARCHIVE_NOTES.md`](../../CC_Compare/docs/a1_development_comparison/ARCHIVE_NOTES.md) | 归档说明 |

## 3. 文献调研（选题依据）

| 文档 | 内容 |
|---|---|
| [`../../C-VRP_Cold-chainVehicleRoutingProblem/docs/当前规划/文献调研/四杠杆文献调研_动态冷链接单_2026-09-26.md`](../../C-VRP_Cold-chainVehicleRoutingProblem/docs/当前规划/文献调研/四杠杆文献调研_动态冷链接单_2026-09-26.md) | 动态冷链接单的四个可利用杠杆：文献依据 + 实际核查 |
| [`../../C-VRP_Cold-chainVehicleRoutingProblem/docs/论文参考/00_MASKCO/模型框架.md`](../../C-VRP_Cold-chainVehicleRoutingProblem/docs/论文参考/00_MASKCO/模型框架.md) | 上游 MaskCO 方法拆解 |
| [`复现代码架构设计.md`](../../C-VRP_Cold-chainVehicleRoutingProblem/docs/论文参考/00_MASKCO/复现代码架构设计.md) | 上游代码架构与复现要点 |

## 4. 机制诊断与负结果（“为什么没增益”的调研）

| 文档 | 内容 |
|---|---|
| [`../../C-VRP_Cold-chainVehicleRoutingProblem/negative_result_paper/README.md`](../../C-VRP_Cold-chainVehicleRoutingProblem/negative_result_paper/README.md) | 负结果论文的完整证据链 + 复现命令 |
| `../../README.md` 附录 A §Headroom-localization diagnostics | D1–D7 头空间定位诊断的清单与结论 |
| [`../../C-VRP_Cold-chainVehicleRoutingProblem/03_负结果线/`](../../C-VRP_Cold-chainVehicleRoutingProblem/03_负结果线/) | 负结果线正文（迁移边界、机制、论文工作稿） |

## 5. 最新一轮的调研/裁决（时效最强，按日期找）

```bash
ls -t C-VRP_Cold-chainVehicleRoutingProblem/docs/当前规划/决策与审计/ | head -20
```

每篇文件名自带主题与日期（`<主题>_<动作>_<YYYY-MM-DD>.md`）。**引用其中的数字前**，先确认它标注的是 `candidate` / `accepted` / `closed_loop` 哪一列，以及是否有对应的独立审计。

## 6. 新增调研的登记方式

1. 正文写进上面的对应目录（不要写进本目录）。
2. 在本文件对应小节加一行：标题 / 一句话内容 / 链接。
3. 若引用了新论文 PDF，同时在 [`../02_参考文献/README.md`](../02_参考文献/README.md) 登记。
