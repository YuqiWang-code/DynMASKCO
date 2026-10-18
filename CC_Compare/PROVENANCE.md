# CC_Compare 基线清单与来源（PROVENANCE）

> 依据总纲 §6.4 采购检查清单：`HEAD / LICENSE / 环境 / checkpoint / smoke`。
> 更新时间：2026-10-18 ｜ 记录口径：**只记录已实测的事实**；没测的写 `NOT_RUN`。

## 0. 服务器 vendor 克隆（`CC_Compare/_vendor/`，**gitignored，不入库**）

| 仓库 | HEAD | 提交日期 | LICENSE | 体积 | 状态 |
|---|---|---|---|---|---|
| `vidalt/HGS-CVRP` | `1a92795` | 2025-03-26 | `LICENSE`（MIT） | 2.2 MB（+build） | ✅ **cmake 编译成功**，`build/hgs` 可执行 |
| `acco93/filo2` | `17b8f84` | 2026-08-29 | `LICENSE` | 2.5 GB | ✅ 已 clone（未编译） |
| `ortec/euro-neurips-vrp-2022-quickstart` | `77a1a24` | 2023-02-23 | `LICENSE` | 336 MB | ✅ 已 clone（未构建） |

## 1. 统一 smoke（同一实例 CMT1，50 客户，10 s 预算，整数化距离）

| 基线 | 版本/身份 | 目标值（cost） | 可行 | 备注 |
|---|---|---|---|---|
| **HGS-CVRP** | HEAD `1a92795`，本地编译 | **521** | ✅ | `-it 5000 -seed 42 -t 10`；解文件自带 `Cost 521` |
| **PyVRP** | pip `0.11.3` | **521.00** | ✅ | `Model.from_data(read(..., round_func="round"))` + `MaxRuntime(10)`，1199 iter |
| **OR-Tools** | pip `9.8.3296` | **555** | ✅ | Guided Local Search，10 s；明显弱于 HGS（符合预期） |

> 说明：CMT1 的公开 BKS 是 524.61（**实数距离**）；这里三方都用**四舍五入整数距离**，
> 因此 521 是"整数距离下的最优"，HGS 与 PyVRP 在同口径下**一致**，说明两者都正确跑起来了。
> OR-Tools 只用了 10 s，不作为质量结论。

## 2. 已存在的 vendored 基线目录

| 目录 | 类型 | 适配层 | LICENSE 文件 | 版本/身份 | smoke |
|---|---|---|---|---|---|
| `PyVRP/` | 非学习（HGS） | `dcc_vrp/`（**PyVRP-RH-D 已冻结**） | `LICENSE.md` ✅ | 服务器 `MASKCO_env` 内 `pyvrp==0.11.3`；**冻结链原本用 `cc_pyvrp`(py3.12, pyvrp 0.14.0)，本机不可用** ⇒ 只能做静态 CVRP smoke，不能复跑冻结数值 | 静态 smoke ✅（cost 521）；`dcc_vrp/` 冻结入口 `NOT_RUN`（env 不匹配） |
| `OR-Tools/` | 非学习（工程基线） | `dcc_vrp/` + 冻结证据包（`FREEZE_SEAL.json` / `SOURCE_MANIFEST.json`） | 软件包许可（pip 安装，目录内无 LICENSE 文件） | pip `ortools==9.8.3296` | 静态 smoke ✅（cost 555） |
| `RRNCO/` | 学习（ICLR 2026） | `dcc_vrp/{dcc_data,dcc_env,run_dcc}.py` | `LICENSE` ✅ | 目录为 vendored 副本（无 `.git`），历史 SHA 未记录 | `NOT_RUN` |
| `CaDA/` | 学习（ICML 2025） | `dcc_vrp/{dcc_data,dcc_env,run_dcc}.py` + `_torchrl_compat.py` | `LICENSE` ✅ | 同上 | `NOT_RUN` |
| `POMO/`、`AttentionModel/`、`Sym-NCO/`、`RouteFinder/`、`Omni-VRP/`、`MVMoE/`、`DeepACO/`、`SGBS/`、`Learning-to-Delegate/`、`CO-enriched-ML/`、`Learn-Improvement-Heuristics/` | 学习 | — | 各自目录内 README | 复现状态见 `docs/A-v1对比方法总表.md` | `NOT_RUN` |
| `PIP-constraint/` | 学习（单车辆 TSPTW） | `dcc_vrp/` | 有 | 只可部分适配（缺容量+多车辆） | `NOT_RUN` |
| `MAPT/`、`MAPT_code` | 多车动态取送货 | — | — | 无源码；`MAPT_code` 是**幽灵 gitlink**（永不 bump） | `NOT_RUN` |
| `tools/`、`common/`、`internal/`、`audit/`、`a1_accept_common/` | 公共适配/工具/审计 | — | — | — | — |

## 3. 运行环境（实测）

| 项 | 值 |
|---|---|
| Python | 3.10.19（conda `MASKCO_env`） |
| 关键包 | `pyvrp 0.11.3`、`ortools 9.8.3296`、`vrplib 1.5.1`、`networkx 3.4.2` |
| 编译 | cmake + g++（HGS-CVRP 编译通过） |
| GPU | 2 × RTX 5090（共享）；CPU 96 核 |
| 复现命令 | `bash tools/gpu/queue_run.sh "<cmd>" <name>`（有卡即跑，无卡入队） |

## 4. 尚未完成

1. **LKH-3**：无官方 GitHub 仓库（作者页面分发），需人工获取并确认学术用途许可。
2. **动态协议 smoke**：以上都是静态 CVRP smoke；把它们接到 `dcc_vrp/` 的 strict-online 适配层并跑一次动态面板，尚未做。
3. **rolling regret-2 与 LNS 自建基线**：落在 `CC_Compare/rolling_regret2/`、`CC_Compare/lns/`（总纲 §6.2）。
4. **checkpoint sha256**：未记录。

## 5. 红线（沿用总纲 §6）

- 只改各方法的 `dcc_vrp/` 适配层，**绝不动原始实现**。
- LKH-3 为学术研究用途；GPL 类实现（FILO）不得假设可再分发。
- vendored 副本缺少 git 历史 ⇒ 引用这些基线时必须写"版本未知/vendored"，不得伪造 SHA。
