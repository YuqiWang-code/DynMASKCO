# models/ 目录整理报告（2026-10-21）

依据：朋友整理的《静态多车冷链MASKCO：训练策略与参数》README + 项目根 README（当前研究=静态冷链 VRP，`models/` 为唯一代码入口，动态在线/滚动时域/外部方法复现不在范围）+ 全量 import 依赖分析。

整理方式：**移动而非物理删除**。所有被移除文件保留相对路径存放于 `docs/temporary/removed_20261021/models/`，确认无误后可彻底删除该目录。

## 一、保留内容（当前研究所需，共 59 个文件）

| 目录 | 内容 | 作用 |
|---|---|---|
| `models/models/` | TSPModel、CVRPModel（+`__init__`） | 骨干模型（CVRPModel 继承 TSPModel） |
| `models/modules/` | TransformerEncoder/Layer、MultiHeadAttention、MLPBlock、SwiGLU、TimestepEmbedder、Linear、get_activation、functional/coord_transform | 网络公共组件 |
| `models/static/` | ColdChainModel、CVRPTWModel、两个 Dataloader、coldchain_evaluator、cvrptw_utils、两个数据生成器 | 静态冷链模型与评估（当前研究核心） |
| `models/coldchain/` | coldchain_contract、coldchain_state | 冷链物理/单位/目标契约与状态机 |
| `models/training/` | train_cvrp、TrainConfig、Logger、ckpt_utils、convert_ckpt、init_optimizer、optimizers/muon | CVRP 训练与检查点 |
| `models/decoding/` | cvrp.py、utils.py | CVRP 神经解码与搜索 |
| `models/data/` | CVRPDataloader | CVRP 数据读取 |
| `models/helpers/` | coord_transform、solution_transform、tsp_transform、maybe_eval、parse_bool、with_invalid_kwargs_filtered | 公共工具 |
| `models/lib/` | C++ 编译扩展（tsp/cvrp/mis/mcl 接口一体编译） | 2-opt、插入、代价评估 |
| `models/cvrp_scripts/` | train/eval shell 脚本 | CVRP 训练/评估入口 |
| `models/workspace_assets/`、`install.sh` | 用户工具与环境依赖 | 非算法代码 |

## 二、移除内容（28 项，备份于 `docs/temporary/removed_20261021/models/`）

### A 档：无法运行 / 未被使用 / 旧动态研究遗留（8 项）
| 路径 | 原因 |
|---|---|
| `baselines/`（4 个 .py） | 引用本地不存在的模块（`strict_online_env`、`authoritative_evaluator`、`ortools_rolling_horizon`、`service_first`）或属 DynMaskCO 动态基线 |
| `tests/test_a1_evaluator.py` | 引用本地不存在的 `coldchain_evaluator_a1`、`strict_online_env`，无法运行 |
| `tools/_run_step5.sh`、`tools/_tmp_3080_summary.py` | 引用旧服务器路径 `/home/hzeng/project/MASKCO-Main/...` 与旧结果目录 `results/a1_ext_formal2` |
| `common/`（array_view.py、jax_triton.py） | 仅被未被任何业务代码引用的 Triton 注意力包装器使用 |
| `modules/functional/attention/`（Triton 注意力） | 全仓库无引用（当前 MultiHeadAttention 用纯 JAX einsum 实现） |
| `modules/MultiHeadAttention.py.bak_triton` | 旧版备份文件 |

### B 档：独立子问题 / 上游复现，与当前静态冷链研究无关（20 项）
| 路径 | 原因 |
|---|---|
| `models/MISModel.py`、`data/MISDataloader.py`、`data/mis_convert_fmt.py`、`decoding/mis.py`、`training/train_mis.py`、`helpers/mis_transform.py`、`mis_scripts/` | MIS（最大独立集）独立子问题全套 |
| `data/TSPDataloader.py`、`data/generate_tsp_with_multirun_2opt.py`、`data/solve_tsp_with_multirun_2opt.py`、`decoding/tsp.py`、`decoding/tsp_strict_ar.py`、`decoding/tsp_strict_ar_uni.py`、`decoding/extra/`、`decoding/gpu_heuristics/`、`training/train_tsp.py`、`tsp_scripts/` | TSP 独立子问题的训练/解码/数据/脚本（TSPModel 类本身保留，因 CVRPModel 继承它） |
| `plot_experiment_trends.py`、`docs/figures/`、`decoding.png`、`overview.jpg` | 上游 TSP/CVRP/MIS 复现图表 |

## 三、同步调整

- `models/__init__.py`：移除 `MISModel`、`MISModelConfig` 导出
- `models/models/__init__.py`：移除 MIS 导出
- `models/data/__init__.py`：移除 `TSPDataloader`、`MISDataloader` 导出

## 四、缓存清理

- 删除 `__pycache__` 目录 20 个（models 与备份目录内），全仓库无残留。

## 五、验证结果

| 检查 | 结果 |
|---|---|
| `python -m compileall -q models` | 全部保留文件语法通过 |
| 残留引用扫描（MIS/TSP 独立子问题、baselines、common、triton 注意力等关键词） | 0 匹配 |
| 关键 import 链核对（train_cvrp → models/modules/training/data/helpers；decoding/cvrp → models/helpers/training/lib/decoding.utils；CVRPDataloader → lib；CVRPModel → TSPModel → modules；static → models+coldchain） | 全部闭合 |

## 六、已知缺口与后续建议

1. **运行时验证未做**：本地 Python 3.14 无 JAX/Flax，未做 import/训练冒烟；建议下次同步服务器（MASKCO_env）后跑一次 `python -m compileall -q models` 与 `python -c "import models"`。
2. **项目根 README 待更新**：其中 `models/baselines/`、`models/tests/` 两行描述与实际结构已不一致（baselines 已归档、tests 已空），如需我更新请告知。
3. **恢复方法**：任何被移除文件可从 `docs/temporary/removed_20261021/models/` 按相对路径移回 `models/`；确认不需要后，可整体删除该备份目录。
