# CC_Compare 基线清单与来源（PROVENANCE）

> 依据总纲 §6.4 采购检查清单：`HEAD / LICENSE / 环境 / checkpoint / smoke`。
> 更新时间：2026-10-18 ｜ 记录口径：**只记录已实测的事实**；没测的写 `NOT_RUN`。

## 1. 已存在的基线目录

| 目录 | 类型 | 适配层 | LICENSE 文件 | 版本/身份 | smoke |
|---|---|---|---|---|---|
| `PyVRP/` | 非学习（HGS） | `dcc_vrp/`（**PyVRP-RH-D 已冻结**） | `LICENSE.md` ✅ | 服务器 `MASKCO_env` 内 `pyvrp==0.11.3`；**冻结链原本用 `cc_pyvrp`(py3.12, pyvrp 0.14.0)，本机不可用** ⇒ 只能做 import smoke，不能复跑冻结数值 | `import pyvrp` **OK**；`dcc_vrp/` 冻结入口 `NOT_RUN`（env 不匹配） |
| `OR-Tools/` | 非学习（工程基线） | `dcc_vrp/` + 冻结证据包（`FREEZE_SEAL.json` / `SOURCE_MANIFEST.json`） | 软件包许可（pip 安装，目录内无 LICENSE 文件） | pip `ortools==9.8.3296` | `import ortools.constraint_solver.pywrapcp` **OK** |
| `RRNCO/` | 学习（ICLR 2026） | `dcc_vrp/{dcc_data,dcc_env,run_dcc}.py` | `LICENSE` ✅ | 目录为 vendored 副本（无 `.git`），历史 SHA 未记录 | 适配层入口待跑 |
| `CaDA/` | 学习（ICML 2025） | `dcc_vrp/{dcc_data,dcc_env,run_dcc}.py` + `_torchrl_compat.py` | `LICENSE` ✅ | 同上 | 适配层入口待跑 |
| `POMO/`、`AttentionModel/`、`Sym-NCO/`、`RouteFinder/`、`Omni-VRP/`、`MVMoE/`、`DeepACO/`、`SGBS/`、`Learning-to-Delegate/`、`CO-enriched-ML/`、`Learn-Improvement-Heuristics/` | 学习 | — | 各自目录内 README | 复现状态见 `docs/A-v1对比方法总表.md` | `NOT_RUN`（本轮未触碰） |
| `PIP-constraint/` | 学习（单车辆 TSPTW） | `dcc_vrp/` | 有 | 只可部分适配（缺容量+多车辆） | `NOT_RUN` |
| `MAPT/`、`MAPT_code` | 多车动态取送货 | — | — | 无源码；`MAPT_code` 是**幽灵 gitlink**（永不 bump） | `NOT_RUN` |
| `tools/`、`common/`、`internal/`、`audit/`、`a1_accept_common/` | 公共适配/工具/审计 | — | — | — | — |

## 2. 运行环境（实测）

| 项 | 值 |
|---|---|
| Python | 3.10.19（conda `MASKCO_env`） |
| 关键包 | `pyvrp 0.11.3`、`ortools 9.8.3296`、`vrplib 1.5.1`、`networkx 3.4.2` |
| GPU | 2 × RTX 5090（共享）；CPU 96 核 |
| 复现命令 | `bash tools/gpu/queue_run.sh "<cmd>" <name>`（有卡即跑，无卡入队） |

## 3. 尚未完成（D2 的剩余部分）

1. **clone 缺失的非学习基线**：`vidalt/HGS-CVRP`（MIT）、LKH-3（学术用途）、`acco93/filo2`、`ortec/euro-neurips-vrp-2022-quickstart`。clone 后必须补 `HEAD SHA / LICENSE / 环境 / smoke 日志` 到本文件。
2. **每个基线的 smoke 实例**：同一实例、同一预算、同一 fallback，跑通一次并归档日志。
3. **rolling regret-2 与 LNS 自建基线**：落在 `CC_Compare/rolling_regret2/`、`CC_Compare/lns/`（总纲 §6.2）。

## 4. 红线（沿用总纲 §6）

- 只改各方法的 `dcc_vrp/` 适配层，**绝不动原始实现**。
- LKH-3 为学术研究用途；GPL 类实现（FILO）不得假设可再分发。
- vendored 副本缺少 git 历史 ⇒ 引用这些基线时必须写"版本未知/vendored"，不得伪造 SHA。
