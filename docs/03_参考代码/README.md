# 参考代码索引

> 三块代码：**上游 MaskCO**（只读基线）、**扩展研发代码**（本项目主体）、**`CC_Compare/` 基线复现**（对照方法）。
> 本文件只做地图与约定，具体实现以代码为准。

## 1. 上游 MaskCO（`MASKCO_code/`，**永不修改**）

TSP / CVRP / MIS 的官方 JAX+Flax 实现（ICLR 2026）。主要入口：

| 路径 | 作用 |
|---|---|
| `MASKCO_code/models/{TSPModel,CVRPModel,MISModel}.py` | 编码器-解码器 Transformer；`*ModelConfig.get_config(name)` 预设 + `construct_model()` |
| `MASKCO_code/modules/` | `TransformerEncoder` / `TransformerLayer` / `MultiHeadAttention`（cuDNN FA 或 Triton 内核）/ `TimestepEmbedder` / `SwiGLU` |
| `MASKCO_code/modules/functional/attention/triton/` | 支持 softcap + bias 的自定义 Flash Attention |
| `MASKCO_code/training/train_{tsp,cvrp,mis}.py` | 训练入口（`python -m MASKCO_code.training.train_tsp`） |
| `MASKCO_code/decoding/{tsp,cvrp,mis}.py` | 推理：generation → mask-and-reconstruct 循环 → C++ 2-opt |
| `MASKCO_code/lib/` | pybind11 C++ 扩展：`tsp_two_opt` / `cvrp_two_opt` / `*PartialInsertion` / `argsort` / `*_eval_cost` |
| `MASKCO_code/{tsp,cvrp,mis}_scripts/{train,eval}/` | 训练/评估脚本（TSP100/500/1000、CVRP100/500/1000、MIS ER/RB） |
| `MASKCO_code/data/` | 数据加载器 + 格式转换（`tsp_convert_fmt.py` / `mis_convert_fmt.py`） |

## 2. 扩展研发代码（`C-VRP_Cold-chainVehicleRoutingProblem/`，本项目主体）

| 路径 | 作用 |
|---|---|
| `scripts/project_paths.py` | 工作区路径契约（`WORKSPACE_ROOT` / `MASKCO_ROOT` / 扩展根）；**所有入口都该用它** |
| `scripts/models/` | `TSPModel → CVRPModel → CVRPTWModel → ColdChainModel → DynamicColdChainModel` + M1（`dynmaskco_cc*.py`）+ `mpre*.py` |
| `scripts/coldchain/` | `coldchain_contract.py`（版本化物理/目标合同、`QualityConfigV2`）、`coldchain_state.py`（唯一状态转移） |
| `scripts/data/` | 各类生成器（`generate_coldchain_data.py` / `generate_o0cc_split.py` / `generate_m0_teacher_split.py`）+ 可见特征提取 |
| `scripts/training/` | `train_cvrptw/coldchain/dynamic_cc` + M0/M1 探针 + `train_state_2x2` / `train_event_plan` / `train_mpre_reinforce` |
| `scripts/decoding/` | `cvrptw.py`（主解码器）、`resource_beam.py`（K-beam 资源态）、`maskco_dynamic.py`（D1–D6）、`thermal_state.py` |
| `scripts/simulation/` | 事件驱动滚动仿真、JF1-H-F 基线、各类 replanner、`visible_state.py` |
| `scripts/evaluation/` | 153 个脚本：形式门、oracle、A-v1 评价、各类诊断（D1–D7）、gate |
| `scripts/expert/` | 教师数据导出（候选/插入步标签） |
| `scripts/tests/` | 208 个测试：控制链、合同、C0、无泄漏、分区、JIT 等价… |
| `scripts/lib/` | C++ 扩展：`cvrptw_ops`（EDD repair / TW-aware 2-opt / quality 2-opt） |
| `negative_result_paper/` | 负结果论文独立复现包（脚本 + 文档 + 结果） |

## 3. `CC_Compare/` 基线复现（对照方法）

约定：**只改各方法下的 `dcc_vrp/` 适配层，绝不动原始仓库代码**。适配层三件套：`dcc_data.py`（数据转换 + 时间尺度 + 可见性）、`dcc_env.py`（非预知门控）、`run_dcc.py`（评估 harness，报告距离/TW 可行性/容量可行性/complete/gap）。

| 目录 | 方法（来源） | `dcc_vrp/` | 备注 |
|---|---|---|---|
| `CaDA/` | Constraint-Aware Dual-Attention（ICML 2025） | ✅ | VRPTW 变体，可适配 |
| `RRNCO/` | Real-World NCO（ICLR 2026） | ✅ | 已跑（clairvoyant + non-anticipatory）；结果见 `CC_Compare/docs/A-v1对比方法总表.md` |
| `PyVRP/` | PyVRP（HGS） | ✅ | 求解器可用；0.11 在部分大实例上返回异常，历史结论以 OR-Tools 为准 |
| `OR-Tools/` | Google OR-Tools | ✅ | 强基线：clairvoyant + rolling-horizon（非预知） |
| `PIP-constraint/` | 复杂约束 Lagrangian（NeurIPS 2024） | ✅ | 单车辆 TSPTW，缺容量+多车辆 ⇒ 只能部分适配 |
| `POMO/` | POMO（NeurIPS 2020） | — | 构造式基线，原论文 PDF 在 `docs/论文参考/对比方法/历史版本/` |
| `AttentionModel/` | Attention Model（Kool 2019） | — | 同上 |
| `Sym-NCO/` | Sym-NCO | — | 仓库体量大（含 vendored 依赖，1.8 万 py） |
| `RouteFinder/`、`RRNCO` 系同名条目见上 | — | — | — |
| `Omni-VRP/`、`MVMoE/`、`SGBS/`、`DeepACO/`、`Learning-to-Delegate/`、`CO-enriched-ML/`、`Learn-Improvement-Heuristics/` | 各 NCO 基线 | — | 复现状态见 [`../../CC_Compare/docs/a1_development_comparison/A-v1对比方法总表.md`](../../CC_Compare/docs/a1_development_comparison/A-v1对比方法总表.md) |
| `MAPT/`、`MAPT_code` | 多车动态取送货（AAAI 2026） | — | 无源码（`MAPT_code` 是幽灵 gitlink，**永不 bump**） |
| `a1_accept_common/`、`common/`、`internal/`、`tools/`、`audit/` | 公共适配层 / 工具 / 审计 | — | 不属于任何单一方法 |

- 对照表与读表限定：[`../../CC_Compare/docs/`](../../CC_Compare/docs/)（尤其 `读表注意与已知限定.md`）。
- 环境：`CC_Compare` 基线用 `cc_compare` conda 环境（RTX 5090 需 torch ≥ 2.7）；本服务器**当前未建该环境**，需要时按 `CC_Compare/setup_envs.sh` 另建（勿动 `MASKCO_env`）。

## 4. 外部参考实现（不随仓库分发）

- 上游官方仓库：<https://github.com/GoodThing001/DynMaskCO>（= 本副本 `upstream`）
- MaskCO 原始实现与数据：见 `README.md` 附录 A §Setup 与 <https://huggingface.co/datasets/Rick242420/MaskCO>
- 对比方法各自上游仓库：见各目录内 `README.md` 与论文链接（**不要**在本仓库内改它们的原始代码）

## 5. 新增参考代码的规则

1. 新基线放 `CC_Compare/<方法名>/`，原始代码保持不动，适配只写 `dcc_vrp/`。
2. 在 `CC_Compare/docs/A-v1对比方法总表.md` 与 `对比方法总表.md` 各加一行（来源、许可、能否适配、证据等级）。
3. 若基线需要独立环境，写进该目录 `README.md`，不要污染 `MASKCO_env`。
