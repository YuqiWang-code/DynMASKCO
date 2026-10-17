# DynMaskCO — MaskCO 向动态冷链车辆路径的因果掩码生成扩展

> 本仓库是**组合工作区**，不是单一代码包：上游 MaskCO（ICLR 2026）源码 + **DynMaskCO-CC 动态冷链扩展研发** + **CC_Compare 对比方法复现** + **研发证据树（登记 / 独立审计 / 回执）**。
>
> 仓库地址：<https://github.com/YuqiWang-code/DynMASKCO>（本人维护副本，来源 <https://github.com/GoodThing001/DynMaskCO>）
>
> 本文档由原根目录的 `README.md` / `CLAUDE.md` / `AGENTS.md` / `工作区导航.md` / `EVIDENCE_MANIFEST.md` 合并而成（四份原文作为附录 A–D **逐字保留**，未做删改），因此单一入口即可查到布局规则、工程不变式、常用命令、架构说明与原始证据清单。

## 想了解这个仓库 / Start here

| 想了解 | 直接打开 |
|---|---|
| **当前权威状态（唯一入口，先看这个）** | [`C-VRP_Cold-chainVehicleRoutingProblem/项目当前状态.md`](C-VRP_Cold-chainVehicleRoutingProblem/项目当前状态.md) |
| 总体阶段与 Gate | [`docs/当前规划/结果与进度/执行进度表.md`](C-VRP_Cold-chainVehicleRoutingProblem/docs/当前规划/结果与进度/执行进度表.md) |
| 工作区目录地图与规则 | 本文 §工作区布局（原 `工作区导航.md`，见附录 C） |
| 最新研究记录（第 1 轮：A-v1 效用上界） | [`取货A-v1预算可达上界与选择缺口_2026-10-13.md`](C-VRP_Cold-chainVehicleRoutingProblem/docs/当前规划/决策与审计/取货A-v1预算可达上界与选择缺口_2026-10-13.md) |
| 最新研究记录（第 2 轮：预算保留接拒面板） | [`取货A-v1预算保留接拒面板_2026-10-13.md`](C-VRP_Cold-chainVehicleRoutingProblem/docs/当前规划/决策与审计/取货A-v1预算保留接拒面板_2026-10-13.md) |
| 双线工程记录（评分头泛化 / 惰性复用） | [`双线第六轮_评分头泛化与全场景惰性复用_2026-10-13.md`](C-VRP_Cold-chainVehicleRoutingProblem/docs/当前规划/决策与审计/双线第六轮_评分头泛化与全场景惰性复用_2026-10-13.md) |
| 扩展代码 | [`C-VRP_Cold-chainVehicleRoutingProblem/scripts/`](C-VRP_Cold-chainVehicleRoutingProblem/scripts/) |
| 研发证据树（登记 / 审计 / RESULT / 回执） | [`research/review_3080_20261010/`](research/review_3080_20261010/) |
| **原始证据归档**（≥1 MiB 的原始转储，约 5.3 GB → 压缩 406 MiB） | 上游 Release：<https://github.com/GoodThing001/DynMaskCO/releases/tag/evidence-2026-10-13>（本仓库**不转载**该附件）；清单见附录 D |

## 一句话现状（截至 2026-10-17，取自 `项目当前状态.md` 置顶）

**尚未建立稳定、可归因的 MaskCO 核心在线正向增益（`stable_online_gain = False`）。**

- 取货 A-v1 线首次出现**预登记、受控、独立核查的正向线索**：5 个冻结日受控 A/B 配对差 `[0, +102.92, +24.76, 0, 0]`，均值 **+25.54**，0 天为负；机制是把能量预算从最不划算的类补回最划算的类（类 0 服务率 0.59→0.80）。按项目自己的预登记口径，这**只是线索**，需另登记并执行 40 天阶段才能称为增益。
- 最新一轮（2026-10-17，Q3 第二轮 S3 执行器浮点外扩界）判定 **NO-GO**：`EXP_ERROR_BOUND_NOT_ESTABLISHED`，两轮止损用尽 ⇒ 连续温度认证仍未建立，L1 `BLOCKED`、L2/A3 未启动、`PRODUCTION_NOT_QUALIFIED`。
- 配送线需主干训练（对 8 GiB 内存门槛敏感）；负结果线（`negative_result_paper/`）已具备独立复现包。

## 诚实边界（务必阅读后再引用任何数字）

- 所有结果均为作者自测的**工程 / 机制证据**，不是论文级结论。
- 过期的 `项目当前状态.md` 顶部旧条目按**时间快照**理解，以最新条目与上表记录为准。
- 三列口径不可混用：`candidate`（候选质量）/ `accepted`（接受后质量）/ `closed_loop`（闭环终局）；`candidate` 不得称“部署”。
- `distance_cost` 恒为纯行驶距离；冷链复合目标另用 `coldchain_cost`，两者不得互相替代。

## 仓库边界

为满足 GitHub 单文件上限并避免 15 倍膨胀，本仓库**不跟踪 ≥1 MiB 的原始审计转储**（`STATES.jsonl` / `*FULLRAW.json` / `REQUEST_*.json` / `downloaded/` 等，共 474 个文件、约 5.3 GB；完整清单见附录 D 与 `.gitignore` 的 generated 块）。这些文件**未被删除**，打包在上游 Release 附件中。**全部源码、文档、登记 / 审计 / 回执与 <1 MiB 工件都在库内。**

## 工作区布局

| 区域 | 职责 | 整理规则 |
|---|---|---|
| [`MASKCO_code/`](MASKCO_code/) | TSP / CVRP / MIS 上游实现（ICLR 2026 MaskCO） | **保持源码不变**，扩展侧只通过路径接入 |
| [`C-VRP_Cold-chainVehicleRoutingProblem/`](C-VRP_Cold-chainVehicleRoutingProblem/) | DynMaskCO 主研发工作区（取货线 / 配送线 / 负结果线） | 当前主要工作区域 |
| [`CC_Compare/`](CC_Compare/) | learned baselines 复现与适配 | 只修改各方法的 `dcc_vrp/` 适配层 |
| [`research/`](research/) | 研发证据树（登记 / 独立审计 / RESULT / 回执） | 只追加，不改写历史 |
| `tools/` | 本地-服务器与交付工具（`_srv.py` / `_sftp_*.py` / `git_deliver.py` …） | 均为辅助脚本 |
| `MASKCO_code/workspace_assets/` | 下载归档与非源码辅助文件 | 不参与训练与评估 |

DynMaskCO 的唯一当前状态入口是 [`C-VRP_Cold-chainVehicleRoutingProblem/项目当前状态.md`](C-VRP_Cold-chainVehicleRoutingProblem/项目当前状态.md)。当前论文主线固定为：**基于 MaskCO 的掩码生成与迭代重构范式，构建面向动态冷链物流的在线优化方法**；主实验采用 dynamic cold-chain **pickup-to-depot**（车辆空载出发、`service_finish` 入舱、`return_arrival` 卸货关闭），而非 depot-to-customer 配送。Cost-aware preference 仅是内部效用对齐模块。

## 快速开始

```bash
# 1) 上游 MaskCO 环境（从仓库根目录）
cd MASKCO_code
sh install.sh
cd lib && make
cd ../..

# 2) 冷链/动态扩展的 C++ 扩展（EDD repair + TW-aware 2-opt）
pip install pybind11
cd "C-VRP_Cold-chainVehicleRoutingProblem/scripts/lib" && make && cd ../..
```

- 训练：`XLA_PYTHON_CLIENT_MEM_FRACTION=0.9`；推理：`0.5`。默认 GPU 0。
- 定位：`scripts/project_paths.py` 解析 `WORKSPACE_ROOT` / `MASKCO_ROOT` / 扩展根，优先使用它而不是硬编码路径。
- 上游训练 / 评估脚本：`MASKCO_code/{tsp,cvrp,mis}_scripts/{train,eval}/`；扩展入口见附录 A §Common Commands。

## 硬不变量（摘录，全文见附录 A §Hard Invariants）

1. **永不修改 `MASKCO_code/`**；所有扩展代码与路径适配放在 `C-VRP_Cold-chainVehicleRoutingProblem/`。
2. 扩展子目录**不放 `__init__.py`**，导入走 `sys.path.insert`。
3. **strict-online / causal**：非预知；用 `coord_normalize_visible`（绝不用泄漏未来的 `coord_normalize`）；已执行前缀冻结、承诺不变、订单恰好服务一次。
4. **成本语义**：`distance_cost` 恒为纯距离；冷链复合目标用独立的 `coldchain_cost`。
5. **版本分离**：`COMPUTE_FILES`（15 个，决定 oracle/eval/env/contract）哈希必须一致才能续跑；`CONTROL_FILES` / `ANALYSIS_FILES` 可独立演进。
6. **Runner 自哈希**：`run_action_oracle.py` 在进程**启动时**哈希自身源码并写入实例记录与 manifest（不得在结束时重读磁盘）。
7. **数据角色按 seed 不相交**：DEV-CAL(777) / DEV-PROTO(7781) / DEV-GATE(7782) / VAL128 / TEST；CAL-PHYS 拟合不得读取其他角色的方法效应。
8. **所有权分区**（M0/M1 在线接受/认证）：校验 `committed ⊎ planned suffix ⊎ explicit deferred` 的完整划分，用 `validate_full_partition`。
9. **输入一致性**：训练 / 在线重规划 / 诊断三条路径对同一 state+action 必须产出**逐字段相同**的张量。
10. **教师采样**：默认 `--context-sampling earliest` 会在首个事件截断（t=0 陷阱），真实 TRAIN/DEV 导出用 `--context-sampling spread`。

## 环境

- **本地（Windows, Python 3.12）**：JAX 0.5.0 / Flax 0.10.4 (NNX) / optax 已装，M0/M1 小 MLP 头可在 CPU 上训练；控制链 / 身份测试套件只需 NumPy。
- **服务器（Linux, Python 3.10.19）**：`/home/hzeng/project/MASKCO-Main/`（凭据在 `.vscode/sftp.json`），conda `MASKCO_env`（jax 0.6.2 / flax 0.10.4 / optax 0.2.4），2× RTX 5090。GPU 需 `jax-cuda12-plugin==0.6.2` + `nvidia-*-cu12`，且 **flax 必须保持 0.10.4**（0.10.7 会让 `SwiGLU` 报 `'ArrayImpl' object has no attribute 'value'`）。
- 远程命令：`python tools/_srv.py "<cmd>"`（凭据从 `sftp.json` 读，**绝不**在命令行内联密码）；上传/下载：`python tools/_sftp_put.py <repo相对路径>` / `python tools/_sftp_get.py <repo相对路径>`（远程根取 `remotePath`）。>5 分钟的任务用 `tmux`，不要 `nohup`。
- GPU 与他人共享：M0/M1 用 `CUDA_VISIBLE_DEVICES=1`，并视情况 `XLA_PYTHON_CLIENT_PREALLOCATE=false`、`XLA_FLAGS=--xla_gpu_autotune_level=0`（小 MLP / batch-8 compact decoder 反而要 `unset XLA_FLAGS`）。

## Git 交付约定（2026-10-14 起，长期有效）

**每完成一件独立工作就提交并推送，不要积攒成一次大 push。** 机械入口：

```bash
python tools/git_deliver.py --message-file <msg.txt>          # 全部改动
python tools/git_deliver.py --message-file <msg.txt> --paths <p1> <p2>
python tools/git_deliver.py --check-only                      # 只报告
```

它强制执行本仓库已被咬过的规则：① 两个分支（`codex/o0cc-cal-phys` 与 `main`）保持同步，推送后校验 `origin/<branch> == HEAD`；② **只允许 fast-forward**，绝不 `--force`；③ 排除幽灵子模块 `CC_Compare/MAPT_code`（gitlink 无 `.gitmodules`）；④ **行尾冻结**：对已登记原始 sha256 的字节容器根做 `git add --renormalize`（`core.autocrlf=true` 且无根 `.gitattributes` 时会把 LF 变 CRLF，破坏所有已登记哈希）；⑤ 并发写保护（90 秒内若有其他进程写入则拒绝，`--allow-concurrent` 仅在线索核实后使用）；⑥ **绝不静默跳过 push**，失败必须记录确切原因。

原始字节证据保持：失败尝试与旧版本逐字节留存并向前滚动为新版本，**不得把 FAIL 改写成 PASS**。

> 本副本的上游为 <https://github.com/GoodThing001/DynMaskCO>，本人维护副本为 <https://github.com/YuqiWang-code/DynMASKCO>；`tools/git_deliver.py` 中的远端若需指向本人仓库，改 `origin` 即可（`git remote set-url origin https://github.com/YuqiWang-code/DynMASKCO.git`）。

## 文档地图

| 附录 | 原文件 | 内容 |
|---|---|---|
| A | `CLAUDE.md` | 工程指引全文：当前状态快照、硬不变量、常用命令（测试 / 形式门 / oracle / M0-M1 / de-index / feature-local / 诊断）、架构（形式门控制链、身份冻结、冷链层、A-v1、M0/M1、event_plan_v2、CC-LNS、M-pre/M-trained）、环境 |
| B | `AGENTS.md` | Codex 侧指引全文：历史状态与推进记录、CC_Compare 复现约定、训练 / 评估 / 数据生成命令、解码器旗标、关键发现与失效清单、Phase 2–4 记录 |
| C | `工作区导航.md` | 工作区职责表、论文主线定位、目录迁移与整理记录指针 |
| D | `EVIDENCE_MANIFEST.md` | 原始证据归档清单（474 个 ≥1 MiB 文件，含校验与大小） |

---

# 附录 A — 工程指引（原 `CLAUDE.md`，逐字保留）

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**MaskCO** is the official ICLR 2026 implementation of a Neural Combinatorial Optimization (NCO) framework using masked generation (TSP / CVRP / MIS). The unmodified upstream implementation lives in `MASKCO_code/`.

**DynMaskCO-CC** is an isolated extension in `C-VRP_Cold-chainVehicleRoutingProblem/` that extends MaskCO to dynamic cold-chain vehicle routing: CVRPTW (time windows) → Cold-Chain (temperature classes) → Dynamic (reveal_time + EDoD). It is a **pickup-to-depot** problem (vehicles leave empty, pick up cold-chain orders, return to depot), not depot-to-customer delivery.

This is a combined workspace, not a single package:

| Area | Purpose |
|---|---|
| `MASKCO_code/` | Upstream TSP/CVRP/MIS source (never modify) |
| `C-VRP_Cold-chainVehicleRoutingProblem/` | DynMaskCO main research workspace (the active area) |
| `CC_Compare/` | Learned-baseline reproduction; only the `dcc_vrp/` adapter layers are edited |

## ⚠️ Current Status

> **Only authoritative status entry:** `C-VRP_Cold-chainVehicleRoutingProblem/项目当前状态.md` + `docs/当前规划/结果与进度/执行进度表.md`. When research status conflicts with anything in this file, those win.

**2026-09-24 — A-v0 收束，A-v1 重定位为「MaskCO 事件掩码重构」.** 方向 A 从「动态承诺 + 掩码条件场景生成」进一步收敛。A-v0 的「冻结 encoder → k-NN 前瞻匹配」假设**已收束**（结果 C：frozen-H ≈ count ≈ random，表征无增量；结果 E：条件匹配 = −4.27 vs 无条件动态门槛，即「按当天早期计数选邻居」这一步**略有害**，最强非学习策略是 `uncond_dynamic`，甚至超过贪心 clairvoyant）。**保留的假设是真正的 MaskCO 核心**：每次揭示事件后，MaskCO 只重构「尚未执行、允许修改的接受/车辆—路线决策」（已执行前缀 + 已接受承诺锁定），在可行性层（时间窗/容量/C0 能耗预算/承诺兑现/鱼可售）内检验是否比强对照有可重复决策收益。**2026-09-24 锁定的决策**：保留**全温区待命制冷**（`active_zone_mask=(True,)*3`，不改 C0 物理）；拒绝惩罚 `p_c=(5,10,15)`（假设合同损失=收入 50%，报告 `p_c=0`/`(10,20,30)` 敏感性）；**C0 品质合同 v2**（`QualityConfigV2` + `ColdChainContractV2`，版本化，v1 hash 不变）；番茄（18°C）= 连续品质指标（无可售阈值，`salable=None` 不评价），鱼（4°C/−18°C）= 零阶感官评分 + 绝对阈值 5；A-v1 效用 = 收入 − 燃油 − 拒绝损失（**品质不货币化**）。**Active code**：`scripts/evaluation/run_exp_a1_compare.py`（三臂 uncond_dynamic/rolling/clairvoyant 框架，MaskCO 占位）、`rolling_optimizer.py`（`RollingOptimizeReplanner`：枚举接单 + 贪心插入 + relocate/swap 局部搜索 + `certify_plan` 硬预算）、`coldchain_evaluator_a1.py`（`add_v2_initial_quality` + `evaluate_trace_a1`）、`run_exp_rule_control.py`（fixed_threshold/class_priority/uncond_dynamic 强规则对照）。Key doc：`docs/当前规划/结果与进度/四步清理阶段性审计记录_2026-09-24.md`（结果 A–E + A-v1 决策 + 文献核查）。**Open risk：MaskCO 掩码重构尚未实现/验证；三臂口径刚闭环（rolling 的接受决策 value/e 排序 vs 枚举贪心仍待定）。**

**2026-09-23 research conclusion (superseded by the A pivot; describes the OLD setting):** a no-training diagnostic campaign (headroom localization D1–D7 + causal headroom + value-predictability + diurnal-energy + precooling) established that **MaskCO has no causally-capturable headroom in the old dynamic cold-chain pickup-to-depot setting**. The terminal headroom is ~100% **future-information** (clairvoyant reveals); every cold-chain decision tested — ordering, zone-assignment, dispatch-timing, diurnal clock-placement, precooling treatment — is either future-info or **rule-capturable** (a simple threshold/ordering rule captures it). ~10 structural contract changes all failed. The **precooling** direction (field vs no-precool) is the closest positive result — a material *myopic* headroom (3.68 normalized) from the 22× frozen Arrhenius rate — but it is rule-capturable ("always precool"), and the central-station batch-precooling combinatorial headroom is tiny (routes are ~2 orders/vehicle, so the "batch" is trivial). The negative-result evidence is fully reproduced in `C-VRP_Cold-chainVehicleRoutingProblem/negative_result_paper/` (scripts + docs + results + README, see §Headroom-localization diagnostics). The bullet points below are the 09-19 historical status.

- **DEV-GATE v4 = GO** (9×128=1152 instances, run_id `20260908-054550`): nine-cell equal-weight Δ = **−0.2771**, grouped-bootstrap 95% CI [−0.2848, −0.2696]. Output: `results/o0cc/dev_gate_v4_official/`. Pilot oracle result, **not** a learned-method claim.
- **路线 B** (M0/M1 direct, no CAL-PHYS→VAL gate). CAL-PHYS is a literature-supported simulator setting; ORACLE-VAL is optional.
- **M0/M1 layer implemented and run on server** on **m0_scale**: TRAIN-64 (root_seed 9701) / CAL-16 (9702) / DEV-CHECK-16 (9703), 50-node R1 EDoD=0.5. (Earlier m0dev 8/4 is superseded.)
- **De-index ablation done**: ID-sensitivity is real and strong — renumbering non-depot nodes flips scores (max |Δ| ≈ 0.008–0.027). `--deindex` masks `ACTION_ID_CHANNELS=(0,2,4,5)` (customer/slot_anchor/predecessor/successor) + `FLEET_ID_CHANNELS=(0,4)` (vehicle_node/committed_next) and removes the sensitivity — but does **not** improve utility.
- **Three-group (feature-local / H-only / M1) and A/B/C/D compact ablation, 3 seeds each**: none establish positive utility. A (explicit-only) is best (net ≈ −0.0016, Spearman .33); B/C/D degrade (Spearman .33→.13→.02→.07). **B/C/D fit poorly in a short budget (30-step loss 31–59 vs A's 0.30)** → A→B degradation is an optimization/budget confound, **not** "encoder has no info". Defensible claim: "current recipe (Huber + mutable-edge recon, 2000-step budget) fails". Do **not** write "encoder untransferable" / "recon harmful" / "capacity ruled out".
- **X_state (candidate-vehicle-cargo state) wired + tested**: `extract_vehicle_cargo_state` + `resolve_target_vid` (in `coldchain_visible_features.py`) resolve target vehicle and read per-zone cargo quality. 2×2 (F_H/F_R/S_H/S_R) shows state has **no increment** — legal candidates with cargo ≈58–67% (not the padding-diluted "17%"), yet S−F diff ≈0 even in the has-cargo subset.
- **Decision-loss 2×2 + soft label done; branch closed**: KEEP-ranking gives exploratory τ=0 improvement (2/3 seeds) but no positive net at CAL-selected τ\*; three-way decomposition shows pick_loss (wrong candidate) and accept_loss (accept/reject) both ≈0.010–0.017. Soft label (`F_soft`) lowers margin error (0.035→0.023) but is insufficient to improve actual net gain (magnitude conflict is not the sole confirmed bottleneck). Per stop rule: **no further loss-branch extension, no encoder, no state expansion; recorded as negative (recipe closed, not "MaskCO infeasible"); current DEV is not a held-out test.**
- Frozen scale profile: `o0cc-pilot-devmean-equal-v2` (`results/o0cc/scale_v2/objective_profile.json`), contract hash `0f00af5d…`.
- Frozen encoder for M0/M1: `ckpts/r1_5_baseline/typed_v1_edge/phase3c/seed42/step50000.ckpt` (loads as `DynamicColdChainModel`, 7D input, `edge_feat=None`).
- Current source identity: `compute_sha256 = f83ad3c485327d8c…` (15 files), control `3c77ecf5…`, analysis `a56f4e55…`.
- **④ interface and ⑤ closed-loop/attribution results recorded** — frozen feature-local models have not established positive utility. FULL−ONE and FULL−EVENT-ONE show additional degradation for F_R_s42; the corresponding F_H intervals cross zero. EVENT-ONE itself has not established a gain. Reported reveal-tail invalidation explains checked cases, not all zero-gain actions; equal next dispatch does not imply equivalent future execution. Do not reinstate the unsupported “baseline undo → repeated reapplication” mechanism. See the results table §1.5d–f and D-050–D-052.
- **EP-v1.2 closed under the effort limit (D-056)** — local summaries confirm A/B/proxy select infinity and DEV has no interventions; distance delta is +0.041983. B has no detected conflicting-input groups in these samples, which does not prove a lossless representation or rule out representation as a major bottleneck. CAL seed43 favors B over A, the other two do not. Source review found WAIT not advanced to H, committed load double-counted in projection summaries, and training/generation seeds coupled. Record these limits without automatically fixing and rerunning the closed recipe. Numerical reproduction is reported; server byte identity was not independently verified. Preserve assets as requiring validation before reuse. See `C-VRP_Cold-chainVehicleRoutingProblem/docs/当前规划/历史已收束/决策与审计/event_plan两轮收束与后续决策.md`.
- **N0-R → N1/N2 (cold-chain search reference + MaskCO conditional reconstruction; concluded negative, no learning increment)** — N0-R (forbid LNS from using JF1-H-F's reserved idle vehicle, `--guard`) reached the exploratory N1 entry (R: CAL ΔJ −0.0686, DEV −0.0232, service 16/16). N1/N2 trained a MaskCO conditional joint-repairer (frozen `DynamicColdChainModel` encoder + trainable `MaskCODecoder` + insertion head, cross-entropy on teacher insertion steps) and closed the loop: MaskCO does **not** beat regret-2 R (mixed vs baseline, R better on both splits). Diagnostics (evidence bounds corrected 2026-09-20): (a) train/deploy padding mismatch — s42 first 20 training records' first-step choice flips 6/20 (pad length = total nodes; whether it equals training `Nv_max` still to cross-check); (b) fixed-state — learned model reproduces regret-2's **customer set** 100% / full-plan hash 60%, ~440× slower (compile/steady not separated, learner timing excludes encoder); **no `J_vis` computed, so fixed-state quality is unjudged**. Conclusion: closed-loop has no learning increment; the diagnostics do **not** prove "the student can only copy R". The follow-up no-training enhanced-repair validation (interleaved two-customer cross-vehicle swap after R's full repair, full certification + full `J_vis`) also concluded negative — fixed-state clustered-bootstrap mean Δ(J_S−J_R)=+0.0058 (CI>0) and closed-loop swap_effect>0 on CAL/DEV; this does **not** prove "R is the deployable upper bound" nor "no better local repair exists" (228 states improved; S's candidate set doesn't contain R's). Stop the imitate-regret-2 distillation route, **not** turning to a non-learning paper; next = MaskCO direct-objective-training limited prototype (reuse pretrained decoder, policy-gradient on full-repair reward). Server GPU now needs `jax-cuda12-plugin` + `nvidia-*-cu12` + `flax==0.10.4` (encoder's `SwiGLU` breaks on 0.10.7).
- **MaskCO direct-objective-training (M-pre / M-trained) — concluded negative on clean protocol (2026-09-22)** — reuse the **pretrained CVRP decoder** (`MASKCO_code/ckpts/cvrp100.ckpt`, 512-dim; NOT the extension's 256-dim encoder-only `step50000.ckpt`) + a cold-chain adapter `C` + a directed insertion head `δ` (both zero-init last layer), train via REINFORCE on full-repair reward `r=(J_vis(P0)−J_vis(P))/s_TRAIN`. Two collector bugs (live `vehicles`/`served_mask` references; global `max_states` → 4-instance concentration) were fixed; a **clean retrain** ran (seed42/1000 updates/8×4, same network/reward/lr; checkpoint `mpre_reinforce_s42_clean`, SHA `f5acf83f…`). Clean-protocol results: fixed-state M-trained **>** M-pre (Δ≈−0.05, ~61–66% of the M-pre↔R gap) but **<** R; closed-loop (4s) gain did **not** transfer (M-trained vs M-pre inconsistent, vs R worse); sampling diagnostic: best-of-8 ≈ R. SGBS layer-by-layer beam (mask pool unified via `mask_candidate_pool`/`validate_mask_scope`) lifted M-trained SGBS to ≈ R but it stayed **dominated by distance-heuristic + SGBS** (+0.017/+0.008). Exit: **收束搜索增强路线 + 直接目标训练分支** — transfer-finetune works (beats M-pre) but has no deployment increment over cheap distance/regret-2 heuristics. See `docs/当前规划/历史已收束/结果与进度/MaskCO直接目标训练_搜索增强验证与收束.md`.
- **Work ownership** — the user decides direction and may delegate implementation+execution to the assistant; the assistant implements code, runs experiments (locally and on the server via `python tools/_srv.py`, credentials read from `.vscode/sftp.json`), and writes result docs; the user reviews and corrects docs. Routine implementation choices within the recorded protocol do not need repeated method approval.

## Git delivery convention (standing, 2026-10-14)

**After every completed piece of work, commit and push to https://github.com/GoodThing001/DynMaskCO.**
A "completed piece of work" = a deliverable unit finished, an engineering stage closed, or a
diagnostic/experiment has produced a result. Do not batch several units into one later push.

Mechanical entry point — use it instead of hand-rolled `git` sequences:

```bash
python tools/git_deliver.py --message-file <msg.txt>          # all changes
python tools/git_deliver.py --message-file <msg.txt> --paths <p1> <p2>
python tools/git_deliver.py --check-only                      # report only
```

It enforces the rules that have already bitten this repository:

1. **Both branches stay in sync**: push `HEAD` to `codex/o0cc-cal-phys` **and** `main`;
   `origin/<branch>` must equal local `HEAD` afterwards (verified, not assumed).
2. **Fast-forward only.** If `origin/main` is not an ancestor of `HEAD` it refuses — never
   `--force`, never rewrite published history.
3. **Exclude the phantom submodule** `CC_Compare/MAPT_code` (a gitlink with no `.gitmodules`
   mapping; its inner tree is dirty as a pre-existing state). Never bump it as a side effect.
4. **Line-ending freeze**: `git add --renormalize` the byte-container roots whose raw sha256
   have been registered, so `blob == worktree bytes` survives a fresh checkout
   (`core.autocrlf=true` and no root `.gitattributes` would otherwise turn LF into CRLF and
   break every registered hash). New byte containers get their own `.gitattributes`.
5. **Concurrent-writer guard**: if another process (e.g. the `maskco` heartbeat) wrote files
   in the last 90 s, it refuses by default, because `git add -A` can otherwise capture a
   half-written tree. `--allow-concurrent` overrides only after verifying the writes are
   complete and additive. `__pycache__`/`.pyc` are ignored as build noise.
6. **Never silently skip the push.** On failure, or when a concurrent writer or a
   non-fast-forward blocks it, record the exact reason and report it.

Raw-byte evidence is preserved: failed attempts and prior versions stay byte-intact and move
forward as new versions; do not rewrite a FAIL into a PASS.

## Hard Invariants

1. **Never modify `MASKCO_code/`.** All extension code and path adapters live in `C-VRP_Cold-chainVehicleRoutingProblem/`.
2. **No `__init__.py`** in CVRPTW subdirectories — imports are done via `sys.path.insert` to avoid shadowing parent packages.
3. **strict-online / causal**: non-anticipatory; use `coord_normalize_visible` (never `coord_normalize`, which leaks future nodes); frozen executed prefix; committed invariance; exact-once order service.
4. **Cost semantics**: `distance_cost` is always pure travel distance; the cold-chain composite objective uses a **separate** `coldchain_cost` field. Never mix or substitute them.
5. **Version separation** (established after the DEV-GATE drift incident):
   - `COMPUTE_FILES` (15 files, in `formal_gate_contract.py`) = files that decide oracle/eval/env/contract behavior. Resume requires identical hash; changing any one means re-running 1152 instances.
   - `CONTROL_FILES` = driver / instance validation / summary rebuild — evolve independently.
   - `ANALYSIS_FILES` = aggregator — evolve independently.
6. **Runner self-hash**: `run_action_oracle.py` hashes its own source at process **startup** and writes that into instance records + manifest. Never re-read disk at the end (that was the drift bug).
7. **Data roles** are disjoint by seed: DEV-CAL(777) / DEV-PROTO(7781) / DEV-GATE(7782) / VAL128 / TEST. CAL-PHYS fitting must not read DEV-GATE/VAL/TEST method effects.
8. **Ownership partition** (M0/M1 online accept/certify): validate the full state partition `committed ⊎ planned suffix ⊎ explicit deferred` — not just "suffix covers universe". `validate_full_partition` in `dynmaskco_cc_context.py` is the reference. Never use `validate_ownership` with a universe that includes committed/deferred customers (they are legitimately outside the suffix and would be falsely flagged "missing").
9. **Input consistency** (M0/M1): the training, online-replanner, and diagnosis paths must produce **identical** input tensors for the same state+action (DEFER/KEEP included). Do not hand-construct action/coldchain features in one path and use `extract_action_features`/`cc_state_dict` in another. Verify per-field equality when adding features.
10. **Teacher sampling**: default `--context-sampling earliest` truncates at the first event (all contexts at t=0), which starves the model of committed-leg/deferred/late-reveal states. Use `--context-sampling spread` for real TRAIN/DEV export.

## Common Commands

All paths below are relative to `C-VRP_Cold-chainVehicleRoutingProblem/` (run from there — several tests use `results/…`-relative paths resolved against the extension root).

### Tests (pure NumPy, no GPU/JAX needed locally)

```bash
# Control-chain / identity suites (run from the extension root)
python scripts/tests/test_formal_gate_contract.py      # roles/manifest/seed/hash/registry/stat-plan
python scripts/tests/test_contract_manifest.py          # cold-chain contract serialize/round-trip
python scripts/tests/test_dev_gate_control.py           # instance validation / cell summary / aggregator identity
python scripts/tests/test_control_chain.py              # DEV-GATE driver end-to-end (resume + drift negatives)
python scripts/tests/test_aggregate_cross_cell.py       # aggregator 9-cell negatives
python scripts/tests/test_val_control_chain.py          # VAL archive end-to-end + startup-lock negatives

# Compute-layer regression
python scripts/tests/test_coldchain_contract.py         # C0 functional gate (20/20)
python scripts/tests/test_sequential_oracle.py          # sequential oracle synthetic (6/6)

# A-v1 layer (accept/reject + C0 energy budget + quality v2)
python scripts/tests/test_quality_v2.py                 # v2 品质：v1 回归 + 零阶/一阶手算 + 阈值两侧
python scripts/tests/test_a1_evaluator.py               # A-v1 评价链：initial_quality + 端到端 + 合法拒单 + 负例
python scripts/tests/test_rolling_optimizer.py          # 滚动优化器：接受/拒绝 + 硬预算 + 在途重复计数
```

Run a single test function: `python -c "import sys; sys.path.insert(0,'scripts/tests'); import test_contract_manifest as t; sys.exit(0 if t.test_file_roundtrip() else 1)"`.

### Formal gate (DEV-GATE / O0-CC VAL)

```bash
# Generic driver (dev_gate; --role val is blocked — VAL is archive-only)
python scripts/evaluation/run_formal_gate.py --role dev_gate \
    --manifest <exact manifest> --profile <profile.json> --workers 8 --out <fresh dir>

# DEV-GATE thin entry (legacy CLI)
python scripts/evaluation/run_dev_gate.py \
    --data-dir data/baseline/50_node/dev_gate \
    --profile results/o0cc/scale_v2/objective_profile.json --workers 8 --out results/o0cc/dev_gate

# VAL entry — ONLY from a sealed archive (self-contained, verified)
python scripts/evaluation/run_o0cc_val.py \
    --archive <sealed archive> --expected-bundle-sha256 <64-hex> --workers 8 --out <fresh dir>
```

### Freeze / verify the source archive

```bash
python scripts/evaluation/freeze_source_archive.py \
    --role val --manifest <VAL_MANIFEST.json> --profile <profile.json> \
    --split-registry <registry.json> --contract <contract.json> \
    --statistical-plan <plan.json> --out <archive dir>

python -B scripts/evaluation/verify_source_archive.py --archive <archive dir>
```

### Oracle runner (single cell/shard, internal `--role regression`)

```bash
python scripts/evaluation/run_action_oracle.py \
    --data <npz> --capacity 50 --num_vehicles 25 --objective coldchain \
    --objective-profile <profile.json> --coldchain-contract <contract.json> \
    --local --role regression --workers 8 --out <dir>
```

### Data split generation

```bash
python scripts/data/generate_o0cc_split.py \
    --split-role val --seed <root_seed> --num-instances 128 \
    --profile <profile.json> --disjoint-manifest <other_manifest> --out <dir>
```

### M0/M1 data & model (server GPU; JAX/Flax needed)

```bash
# Fresh M0 TRAIN/DEV base instances (root seeds 9601/9602, R1 EDoD=0.5)
python scripts/data/generate_m0_teacher_split.py --train-instances 8 --dev-instances 4 --out data/m0dev

# Teacher candidate export (spread across events; default 'earliest' is the t=0 trap)
python scripts/expert/export_coldchain_teacher.py \
    --data data/m0dev/dcc_50_r1_edod05_train_teacher.npz --dataset-role train_teacher \
    --objective coldchain --objective-profile results/o0cc/scale_v2/objective_profile.json \
    --num-vehicles 25 --capacity 50 --max-instances 8 --max-contexts-per-instance 12 \
    --context-sampling spread --manifest data/m0dev/M0_TEACHER_MANIFEST.json \
    --out results/m0dev/train_spread

# Feature-only utility probe (train + eval) — the M0 representation probe
python scripts/training/train_coldchain_utility_probe.py \
    --teacher-dir results/m0dev/train --data data/m0dev/dcc_50_r1_edod05_train_teacher.npz \
    --num-steps 2000 --batch-size 8 --seed 42 --out results/m0dev/probe_feature_only
python scripts/training/run_coldchain_utility_probe.py \
    --ckpt results/m0dev/probe_feature_only/probe.ckpt \
    --teacher-dir results/m0dev/dev --data data/m0dev/dcc_50_r1_edod05_dev_teacher.npz \
    --out results/m0dev/eval_feature_only

# M1 (DynMaskCO-CC) joint training: frozen encoder + masked decoder + utility head
python scripts/training/train_dynmaskco_cc.py \
    --teacher-dir results/m0dev/train --data data/m0dev/dcc_50_r1_edod05_train_teacher.npz \
    --ckpt ckpts/r1_5_baseline/typed_v1_edge/phase3c/seed42/step50000.ckpt \
    --num-steps 2000 --batch-size 8 --seed 42 --out results/m0dev/m1_2000

# M1 / feature-only online gate (baseline vs method on the strict-online trajectory)
python scripts/evaluation/run_dynmaskco_cc_gate.py \
    --data data/m0dev/dcc_50_r1_edod05_dev_teacher.npz --capacity 50 --num_vehicles 25 \
    --objective coldchain --objective-profile results/o0cc/scale_v2/objective_profile.json \
    --max-instances 4 --K 1 --m1-ckpt results/m0dev/m1_2000/m1.ckpt \
    --encoder-ckpt ckpts/r1_5_baseline/typed_v1_edge/phase3c/seed42/step50000.ckpt \
    --out results/m0dev/gate_m1k1

# Offline utility diagnosis (g_pred vs counterfactual g_true) + input-consistency check
python scripts/evaluation/run_utility_diagnosis.py \
    --data data/m0dev/dcc_50_r1_edod05_dev_teacher.npz \
    --feature-only-ckpt results/m0dev/probe_feature_only/probe.ckpt \
    --objective coldchain --objective-profile results/o0cc/scale_v2/objective_profile.json \
    --max-contexts 12 --out results/m0dev/diag_fo
python scripts/evaluation/run_input_consistency.py \
    --teacher-dir results/m0dev/train --data data/m0dev/dcc_50_r1_edod05_train_teacher.npz \
    --max-contexts 4 --out results/m0dev/input_consistency
```

M0/M1 tests (JAX + NumPy; run locally — JAX is installed):
`test_coldchain_reader_features.py`, `test_coldchain_teacher_dataset.py`, `test_coldchain_utility_probe.py`, `test_dynmaskco_cc.py` (no-op parity), `test_dynmaskco_cc_accept.py` (deterministic accept), `test_m1_partition_fix.py` (ownership partition), `test_m1_jit_equiv.py` (real-checkpoint JIT vs non-JIT), `test_deindex_features.py` (de-index + renumbering invariance), `test_pre_prepare_collector.py` (pre-prepare context collector cache/拒绝语义).

### De-index ablation + compact A/B/C/D (m0_scale, the current active data)

Active data is now `data/m0_scale/` (`generate_m0_teacher_split.py --train-instances 64 --cal-instances 16 --dev-check-instances 16`), **not** the older m0dev 8/4. The newer scripts (all take `--deindex`):

- `scripts/training/train_feature_only_local.py` — feature-only-local (70-dim: context 25 + action 16 + local 29); `--deindex` masks the ID channels.
- `scripts/training/train_m1_compact.py` — compact A/B/C/D ablation (`--group A|B|C|D`; A=explicit, B=+compact H endpoint, C=+compact Z recon=0, D=+recon); `--fit-check` overfits a subset to separate wiring vs optimization.
- `scripts/training/train_coldchain_utility_probe.py` — `--context-mode encoder_real` (H-only) + `--train-all` (use all TRAIN-64, no internal dev split).
- `scripts/evaluation/run_threeway_eval.py` — unified offline eval (`--model feature_local|encoder_real|m1|compact|state_2x2`): margin scan (instance-equal net gain, CAL-locked τ\*, regret, harmful ratio) + Spearman/MAE. Reads the model's `s` from the checkpoint (never re-estimates).
- `scripts/evaluation/run_id_sensitivity.py` — renumbering invariance check (fix depot, permute other nodes, compare scores/winner/KEEP).
- `scripts/evaluation/run_candidate_gain_space.py` — hindsight `g* = max(0, max_a[J_keep − J_a])` + 4-category candidate coverage.
- `scripts/evaluation/run_margin_scan.py` — fixed CAL selection rule (argmax over CAL instance-equal net gain, restricted to `service_feasible` & `label_complete` & finite; tie-break smaller τ). `τ=∞` = "keep baseline", not a gain.

- `scripts/training/train_state_2x2.py` — the decision-loss 2×2 trainer (small MLP over the 70/83-dim explicit features, no encoder): `--use-state` (append the 13-dim X_state), `--use-rank` (hard-sign KEEP ranking), `--soft-rank` (soft-label ranking `softplus(m/T)−σ(y/T)(m/T)`); `--fit-n` overfits a subset; writes full config to `manifest.json`. `s` = std(δ) over **full TRAIN** supervision (computed before any `--fit-n` slice).
- `scripts/evaluation/diag_v2.py` / `diag_v3.py` / `agg_fsoft.py` — offline diagnostics (instance-equal selection outcomes, τ\* weighted decomposition + identity check, has-cargo stratification, three-way gain decomposition full/fixed/actual → pick_loss/accept_loss, margin error). No training; reuse the checkpoints' predictions.

Key new extractors in `scripts/data/coldchain_visible_features.py`: `extract_vehicle_cargo_state(snapshot, vid, plan, …)` (13-dim target-vehicle state: anchor_time/remaining-capacity from the **plan** (not snapshot's ready/load), per-zone temp/zone-load/remaining-quality, `state_valid` + `has_cargo` separate) + `resolve_target_vid(action, plans, allowed_vehicle_ids)` (NEW_ROUTE → `_match_new_route`, DEFER → None). Wired into `train_state_2x2.py`'s `build_x_state` (not yet into the online replanner).

### feature-local 70-dim adapter + ⑤ attribution (m0_scale, 2026-09-18)

The frozen 70-dim `ScoringMLP` scorer (`train_state_2x2.py` `model.ckpt`, no encoder) is deployed online via `feature_local_replanner.py` with a `PrePrepareContextCollector` for the pre-prepare context. All these take `--deindex` (required, read from training `manifest.json`):

```bash
# ④ interface reconciliation (feature/score/writeback/causality — all PASS)
python scripts/evaluation/run_feature_local_reconcile.py \
    --teacher-dir results/m0_scale/dev_check \
    --data data/m0_scale/dcc_50_r1_edod05_dev_check_teacher.npz \
    --max-contexts 8 --deindex --out results/m0_scale/iface_reconcile
python scripts/evaluation/run_feature_local_score_check.py \
    --ckpt results/m0_scale/state2x2_full_v1/F_H_s42/model.ckpt \
    --teacher-dir results/m0_scale/dev_check \
    --data data/m0_scale/dcc_50_r1_edod05_dev_check_teacher.npz \
    --max-contexts 4 --deindex --out results/m0_scale/iface_score
python scripts/evaluation/run_feature_local_writeback_check.py \
    --teacher-dir results/m0_scale/dev_check \
    --data data/m0_scale/dcc_50_r1_edod05_dev_check_teacher.npz \
    --max-contexts 2 --deindex --out results/m0_scale/iface_writeback

# ⑤ K=1 closed-loop (baseline vs FeatureLocalReplanner; --tau inf = no-op control, must == baseline)
python scripts/evaluation/run_feature_local_gate.py \
    --ckpt results/m0_scale/state2x2_full_v1/F_H_s42/model.ckpt \
    --data data/m0_scale/dcc_50_r1_edod05_dev_check_teacher.npz \
    --capacity 50 --num-vehicles 25 --objective coldchain \
    --objective-profile results/o0cc/scale_v2/objective_profile.json \
    --deindex --K 1 --tau 0.005 --max-instances 16 --out results/m0_scale/gate_fl

# ⑤ attribution: B/ONE/FULL (ONE = max_total_accepts=1, first accept then baseline)
python scripts/evaluation/run_feature_local_onefull.py \
    --ckpt results/m0_scale/state2x2_full_v1/F_H_s42/model.ckpt \
    --data data/m0_scale/dcc_50_r1_edod05_dev_check_teacher.npz \
    --capacity 50 --num-vehicles 25 --objective coldchain \
    --objective-profile results/o0cc/scale_v2/objective_profile.json \
    --deindex --tau 0.005 --max-instances 16 --out results/m0_scale/onefull_F_H_s42

# ⑤ attribution: ĝ vs g_B counterfactual (samples 1st/5th/10th accepts, ≤24 decision points)
python scripts/evaluation/run_feature_local_gB.py \
    --ckpt results/m0_scale/state2x2_full_v1/F_H_s42/model.ckpt \
    --data data/m0_scale/dcc_50_r1_edod05_dev_check_teacher.npz \
    --capacity 50 --num-vehicles 25 --objective coldchain \
    --objective-profile results/o0cc/scale_v2/objective_profile.json \
    --deindex --tau 0.005 --max-instances 4 --out results/m0_scale/gB_F_H_s42

# ⑤ behavior summary (aggregates onefull instances/*.json decision logs)
python scripts/evaluation/run_behavior_summary.py \
    --gate-dir results/m0_scale/onefull_F_H_s42 --out results/m0_scale/onefull_F_H_s42/behavior_summary.json
```

Key facts that bite: the 70-dim model is a plain MLP over `ctx25 + action16 + local29`, **no encoder/mask**. The online context must be **pre-prepare** (via `PrePrepareContextCollector` registered to `env.snapshot_hook`), never reconstructed from post-`prepare_decision_point` vehicles — `prepare_decision_point` bumps `ready_time` (idle→clock, ready→max) and the pre-bump value is unrecoverable. `deindex` is a required constructor arg (no default). The `ĝ vs g_B` diagnostic must install `P_before`/`P_after` explicitly via `_snapshot_with_force` (never `rollout_baseline` from the original snapshot, which rebuilds the pre-modification incumbent).

## Headroom-localization diagnostics (D1–D7; concluded negative, 2026-09-23)

A family of **no-training, pure-NumPy** diagnostics that established *why* MaskCO has no headroom (the "big picture" above). They reuse the frozen JF1-H-F baseline + the C0 cold-chain physics; none load a model or need a GPU. All run from `C-VRP_Cold-chainVehicleRoutingProblem/` with `--data data/m0_scale/dcc_50_r1_edod05_{train,cal,dev_check}_teacher.npz --objective-profile results/o0cc/scale_v2/objective_profile.json`.

- `scripts/evaluation/analyze_complementarity.py` — is the learned model's candidate set disjoint from distance-search's? (`J_union = min(dist, model)` per state; result ≈0.)
- `scripts/evaluation/run_headroom_census.py` (D1/D2) — exhaustive mask=2 repair oracle (D1) + single-step correction census (D2), myopic J_vis.
- `scripts/evaluation/run_terminal_headroom.py` (D3) — the decisive one: does the myopic repair headroom survive **terminal** rollout (future reveals)? Result: no.
- `scripts/evaluation/run_causal_headroom.py` (D5) — myopic sequential oracle vs clairvoyant; quantifies the future-information share.
- `scripts/evaluation/run_value_predictability.py` (D6) — is terminal gain predictable from visible state? (linear probe Spearman ≈ −0.04 → no.)
- `scripts/evaluation/run_perishability_headroom.py` (D7-a) + `run_terminal_perishability.py` / `run_terminal_commit.py` / `run_perishability_oracle.py` (D7-b/b'/c) — perishability-ordering headroom.
- `scripts/evaluation/run_diurnal_sensitivity.py` + `run_dispatch_delay_sweep.py` — diurnal (time-of-day) ambient-temperature energy headroom (phase spread material, but causal dispatch-delay ≈0).
- `scripts/evaluation/run_precool_gate.py` / `run_precool_threshold.py` / `run_precool_station.py` / `run_station_routing.py` — precooling (field vs no-precool) + central-station batch-precooling headroom.

**`negative_result_paper/`** is the standalone reproduction folder for the methodology/negative-result paper: `README.md` (the full evidence chain + exact commands + dependencies), `scripts/` (copies of the entry-point diagnostics), `docs/` (result/decision docs), `results/` (summary.json + per_state.json). If the "change the contract/task" route ever fails, this one folder reproduces the entire negative chain.

**Three-column evaluation** (the clarification that bites): fixed-state methods are scored at three distinct levels — `candidate` (候选质量, fail→J0), `accepted` (接受后质量, online accept rule `min(J0,J)`), `closed-loop` (闭环终局, `run_step5_gate` ΔJ). ⚠️ The frozen `MaskCO直接目标训练_干净协议冻结/README.md` "部署均值" numbers are **candidate**, not accepted — do not call candidate "deployment".

**Mechanism experiments (②a/②b, in `negative_result_paper/scripts/`)**: `run_execution_trace.py` (action tracing — the mask customer's final vehicle assignment rarely persists; strict-online commits only the first suffix element per vehicle) and `run_future_sampling_oracle.py` (future-info vs evaluation-horizon — the finite-sample future-sampling score does not recover the clairvoyant score's gain; the paired difference `clairvoyant − sampling` has CI>0). Results in `negative_result_paper/results/06_机制实验/`.



## Architecture

### Formal gate control chain (DEV-GATE / VAL share one core)

- `scripts/evaluation/formal_gate_contract.py` — the single shared contract: roles, manifest validation (9 cells R1/C1/RC1 × EDoD 0.2/0.5/0.8, 128 instances, shared seeds), hash helpers, frozen-compute plan + resume validation, cross-split disjointness, split registry, statistical-plan validation, and sealed-archive verification (`verify_archive` / `verify_active_code`).
- `scripts/evaluation/run_formal_gate.py` — the generic driver (`run()`): validate manifest/profile/contract/registry → write `pre_run_manifest.json` (first run requires empty dir; resume requires identical frozen identity) → per-cell run `run_action_oracle.py --role regression` (resume only missing instances, hard-fail on error/protocol/service-fail) → rebuild canonical cell summary → aggregate.
- `scripts/evaluation/run_dev_gate.py` / `run_o0cc_val.py` — thin entries fixing `role=dev_gate` / `role=val`. VAL entry verifies the archive (bundle + active-code hash) before running.
- `scripts/evaluation/aggregate_cross_cell.py` — nine-cell equal-weight grouped bootstrap (by internal seed group, not 1152 independent rows), with `regression`/`dev_gate`/`val` modes and formal blocking checks.
- `scripts/evaluation/instance_validation.py` + `cell_summary.py` — shared strict instance acceptance and canonical cell summary rebuild (atomic publish + `canonical.COMPLETE` marker).

### Identity / freeze model

- A run's frozen identity = `compute/control/analysis` hashes + `data_sha256` (per-cell NPZ) + `profile_hash` + (VAL) `val_identity` (manifest hash / root_seed / scene ids / contract / profile / registry / stat-plan hashes) + (explicit contract) `contract_identity` (raw + effective contract hash + contract/profile file hashes).
- `freeze_source_archive.py` builds a self-contained archive: 15+6+1 source files, profile, manifest, and — for VAL — the 9 NPZ, `contract.json`, `statistical_analysis_plan.json`, and a normalized bundle-relative `split_registry.json` + `registered_splits/`. It writes `ARCHIVE_SEALED` + a seal manifest with a `bundle_sha256`.
- `verify_source_archive.py` / `formal_gate_contract.verify_archive` check exact file set + per-file SHA-256 + bundle recompute + seal↔源码冻结清单 cross-validation + ARCHIVE_SEALED.

### Cold-chain layer

- `scripts/coldchain/coldchain_contract.py` — versioned physical + objective contract (`ColdChainContract`), `ObjectiveProfile` (named scale/λ), `from_manifest` / `load_coldchain_contract` / `validate_contract_manifest` (strict schema + hash re-check). Calibrated contracts are loaded explicitly via `--coldchain-contract`; the implicit `default_pilot_contract()` remains the legacy pilot default.
- `scripts/coldchain/coldchain_state.py` — the single pure state transition (`transition_segment`; pickup enters cargo, return unloads). `ThermalConfig` carries **research-extension** fields added 2026-09-23 for the headroom-localization studies: `diurnal_amplitude_c`/`diurnal_phase_hour`/`dispatch_delay_hour` (time-of-day ambient → clock-dependent refrigeration energy, `_time_weighted_hours`) and `precool_energy_per_unit_per_c`/`precooled`/`precool_min_temp_class`/`precool_station_discount`/`use_station` (field-vs-central-station precooling; `CargoLotState.precooled` makes decay rate depend on effective temperature). These are diagnostics, not the frozen production contract — they change `contract_hash`, so re-freeze the identity if any become production.
- `scripts/evaluation/hard_gate.py` — shared service/hard gate (`hard_vector_from_outcome` / `service_ok` / `outcome_protocol_error` / `select_improving`).
- `scripts/simulation/jf1h_repair.py` — **JF1-H-F** hard-feasible baseline (`make_continuation()` factory + `export_state`/`restore_state` + urgent-defer).

### A-v1 layer (accept/reject + C0 energy budget + quality v2) — the active line (2026-09-24)

Problem: orders reveal over a day → **accept/reject commitment** (accepted ⇒ served exactly once, non-cancellable) → **green energy budget** (C0 refrigeration ≤ B) → **A-v1 utility = revenue − fuel − reject-loss** (quality NOT monetized; fish salability is a hard constraint). All under the strict-online causal protocol. The hypothesis being tested is the **true MaskCO core**: after each reveal, reconstruct the *unexecuted, modifiable* accept/route decisions (frozen executed prefix + committed accepts locked).

- `scripts/coldchain/coldchain_contract.py` — **`QualityConfigV2`** (per-zone `dynamics_order` zero/first, `metric_name`, `initial_value` (fish 9 / tomato 1), `rate_per_hour`, `threshold_type` none/absolute, `threshold` (fish 5)) + **`ColdChainContractV2`** (versioned; v1 unchanged). Literature rates: tomato TA 18°C first-order ≈0.00184/h; mullet sensory 4°C zero-order 0.452 pt/day ≈0.01883/h; sea-bass −18°C zero-order ≈0.000278/h (from 580–623-day shelf life).
- `scripts/coldchain/coldchain_state.py` — `transition_segment` branches on `isinstance(contract.quality, QualityConfigV2)`: zero-order (`score -= k·dt`) vs first-order (`q *= exp(-k·dt)`), absolute (`score>=5`) vs none (`salable=None`) delivery; `active_quality_loss` returns 0 for v2.
- `scripts/evaluation/coldchain_evaluator_a1.py` — `add_v2_initial_quality` (fish 9 / tomato 1) + `evaluate_trace_a1` (accepted⊆served, fish salable, TW/capacity/budget; all revealed orders exactly accepted∪rejected; accepted must have delivered records).
- `scripts/evaluation/rolling_optimizer.py` — `RollingOptimizeReplanner(C0ReserveReplanner)`: enumerate accept/reject → greedy insert → relocate+swap local search → `certify_plan`, within `time_limit`.
- `scripts/evaluation/run_exp_a1_compare.py` — 3-arm framework (uncond_dynamic / rolling / clairvoyant-ref; MaskCO placeholder).
- `scripts/evaluation/run_exp_rule_control.py` — strong rules: `fixed_threshold`, `class_priority`, `UncondDynamicReplanner` (the strongest non-learning arm).

**Key facts that bite:**
- **WAIT fix**: `plan()` sets `mutable_suffix = route` (NOT `route + [0]`). The old `+[0]` hardcoded "return" into the suffix → vehicle returned right after its route's last order and missed future reveals. Applied in `run_exp_reserve.py` + `run_exp_energy_c0.py`; **this changes all prior reserve/capacity/energy numbers** (re-run).
- **In-transit double count**: exclude `committed_next` from the remaining route in `_plan_start_states`/`certify_plan` (it's already in the in-transit load), else "an order can be picked exactly once".
- **est = `c0_marginal_energy(c, q, cooling_share, contract)` = `cooling_share + door/COP + precool`**; `cooling_share` = all-zone standby refrigeration amortized per order, NOT the old single-zone `cooling_power_kw[c]×mean_dwell[c]`. Energy split ≈ 72% precool + 28% cooling + 0.3% dispatch.
- **Hard budget = `certify_plan`** (`c0_completion_energy` simulates route + **WAIT to booking_end** + return from the current state; checks ≤ B). `cooling_share` is auxiliary only.
- Reject penalty `p_c=(5,10,15)`; report `p_c=0` as the main signal (p_c>0 makes reject-loss dominate when budget covers only ~30–40% of a 200-order day).

### Oracle (O0-D / O0-CC)

`scripts/evaluation/run_action_oracle.py` compares baseline (JF1-H-F) vs a greedy **sequential** action-space oracle on the same strict-online protocol, plus a **local** single-customer baseline-state oracle. Instance-level multiprocessing (`--workers`), per-instance non-degeneration + `PROTOCOL_ERROR` checks.

### M0/M1 data & model layer (DynMaskCO-CC)

The active research area. The pipeline is: **teacher data → utility learning (M0 probe) → masked reconstruction + utility (M1) → online replanner → offline diagnosis**.

- **Teacher data** — `scripts/expert/export_coldchain_teacher.py` runs the JF1-H-F baseline, collects decision-point snapshots, and for each (snapshot × customer) enumerates all candidate actions + counterfactual rollouts, writing a versioned dataset (`contexts.jsonl` + `candidates.jsonl` + `manifest.json`, fail-closed). `scripts/data/coldchain_teacher_dataset.py` reads it (groups candidates by `context_id`, separates `legal_mask` from `supervision_mask`); `scripts/data/coldchain_visible_features.py` builds the visible-order/fleet/action features and candidate-local features (info-boundary aware — unrevealed orders are masked).
- **M0 feature-only probe** — `scripts/models/coldchain_utility_head.py` (`UtilityHead`, masked-mean order/fleet context + action). `scripts/training/train_coldchain_utility_probe.py` trains Huber regression `y = -(J_a − J_keep)/s` (s estimated on TRAIN only); `run_coldchain_utility_probe.py` is the eval entry (MAE / Spearman / top1-agreement). This is a representation probe, **not** the final method.
- **M1 model** — `scripts/models/dynmaskco_cc.py` (`DynMaskCOModel`: frozen `DynamicColdChainModel` encoder + trainable `MaskCODecoder` + `ScoringMLP`; `M1Scorer` wraps decode→gather→head in one persistent `jax.jit`). `scripts/models/dynmaskco_cc_graph.py` builds the visible-node index, symmetric plan adjacency, event mask `M = ⋁(A_a ≠ A_0)` + `A_in`, timestep, and endpoint resolution. `scripts/simulation/dynmaskco_cc_context.py` holds the shared state-restore / incumbent / full-partition validation used by training, online, and diagnosis.
- **Online replanners** — `scripts/simulation/dynmaskco_cc_replanner.py` (M1: JF1-H-F incumbent → K rounds of event-mask/reconstruct/score/certify/write-back) and `feature_only_replanner.py` (the same flow with the M0 head). Both subclass `JF1HRepairReplanner`; `model=None`/`scorer=None` = no-op == baseline.
- **70-dim feature-local adapter (④⑤, `feature_local_replanner.py`)** — `FeatureLocalReplanner` (JF1HRepairReplanner subclass) scores `ScoringMLP(70)` over `ctx25+action16+local29`; `PrePrepareContextCollector` (registered to `env.snapshot_hook`) saves the pre-prepare 25-dim context keyed by `(inst, event, clock)` — missing key raises, never falls back to post-prepare. Accept rule `g = s·(f(a)−f(KEEP/DEFER)) > τ`; `max_total_accepts=1` = the ONE strategy. Per-decision logging records `P_before`/`P_after` (full plans) for the ĝ-vs-g_B counterfactual. Empty-plan write-back uses `env.has_future_reveal` (`[]` WAIT vs `[0]` return), matching teacher/JF1-H-F. `plan_to_dict`/`plan_distance` are module-level helpers for the decision log.
- **Gate + diagnosis** — `scripts/evaluation/run_dynmaskco_cc_gate.py` runs baseline vs method on 4 DEV instances (per-instance JSON + online stats + split timing). `run_utility_diagnosis.py` pairs model-predicted improvement `g_pred = s·[f(a)−f(KEEP)]` against counterfactual `g_true = J_KEEP − J_a`; `run_input_consistency.py` verifies train/online/diagnosis tensors are identical.

Key wiring facts that bite if forgotten: the M1 masked decoder's adjacency is a **soft 0/1 attention bias** (not a hard mask), and `edge_feat=None` (no edge input) in this dev stage. Node padding: `train_dynmaskco_cc.py` pads nodes **globally** (fixed JIT shape); the compact `dynmaskco_cc_compact.py` masks padded nodes via a `node_valid` bias (−1e9) + zeroed output. The older `dynmaskco_cc.py` decoder does **not** mask padded nodes, so its scores shift under padding (verified max |Δ| ≈ 0.008–0.027) — don't trust its per-context numbers as padding-invariant.

### event_plan_v2 (event-level complete-plan evaluation — concluded, kept as assets)

Event-level plan evaluation supersedes the per-modification 70-dim scorer: from one decision-point incumbent P0, generate ≤8 full-fleet candidate plans (G_simple_r1, 7 deterministic requests) and score each candidate's counterfactual terminal gain `g_B = J(P0→B) − J(P→B)` under a common JF1-H-F continuation. Pipeline: **export (labels+features) → train `PlanEvalMLP` → online replanner → fixed-state selection + CAL→DEV closed loop**. Core modules (all under `scripts/`):

- `simulation/event_plan_candidate.py` — `generate_simple_candidates_r1` (request/plan-bound, KEEP-deduped) + `plan_distance` (includes depot-return leg; distinguishes WAIT vs RETURN).
- `simulation/event_plan_projection.py` — visible execution-consequence projection: advances the **currently-known** plan via C0 `transition_segment` to a D/Q/E/J proxy (`project_plan`/`proxy_cost`), no future reveals. Physical engine behind the B representation and the non-learned S_proxy control.
- `simulation/event_plan_features.py` — `extract_plan_delta` (A, 100-dim structural summary) vs `extract_plan_consequence` (B, 529-dim consequence).
- `simulation/event_plan_replanner.py` — `EventPlanReplanner` (`mode=distance|proxy|learned`, `representation=A|B`).
- `training/train_event_plan.py` — `PlanEvalMLP` over `[context25 + plan_feature]`, Huber on `(f(P)−f(P0)) − g_B/s`, instance→event→candidate balanced sampling.
- `evaluation/run_event_plan_export.py` (TRAIN/CAL data: g_B + both features + hard vectors + real deferred) / `run_event_plan_select.py` (fixed-state selection table) / `run_event_plan_closed_loop.py` (CAL threshold grid {0,0.005,0.02,∞} → service-first lock τ → DEV) / `run_event_plan_gate.py` (single mode/tau).

Result is a concluded negative (see Current Status); the modules are research assets, not an active recipe.

### CC-LNS-RH + reserved protection + MaskCO conditional reconstruction (N0 → N1/N2, concluded negative)

The current research line: a **non-learning cold-chain LNS reference (CC-LNS-RH)** proves the framework target, then **MaskCO learns to generate joint-repair candidates** against it. The pipeline, in dependency order (all under `scripts/`):

- `simulation/visible_state.py` — read-only cold-chain view `VisibleState` (order-level cargo manifest + per-vehicle temps/zone_load) + the visible-scenario evaluator `evaluate_visible_plan` (no-new-orders completion via C0 `transition_segment`, returns `J_vis`). Unused idle vehicles are NOT dispatched (no phantom pre-cooling).
- `simulation/cc_lns_replanner.py` — `CCLNSReplanner`: JF1-H-F incumbent → remove mask → regret-2 reconstruct → `J_vis` accept. `guard_reserved=True` (N0-R) forbids LNS from using the highest-id idle vehicle that JF1-H-F still reserves. `run_cc_lns_gate.py` is its closed-loop gate.
- `simulation/repair_teacher.py` + `expert/export_repair_teacher.py` — per-step insertion labels `P_before → mask → P_partial → steps → P_target` from a more-thorough regret-2 search on the guarded R trajectory (384 records).
- `training/train_dynmaskco_cc_repair.py` — conditional insertion-step training: frozen encoder + trainable `MaskCODecoder` + insertion `ScoringMLP`, softmax cross-entropy over legal insertions (NOT the old g_B regression). Reuses `models/dynmaskco_cc.py` (`MaskCODecoder`, `ScoringMLP`, `gather_endpoints`).
- `simulation/dynmaskco_cc_repair_replanner.py` — `RepairReplanner` + `greedy_reconstruct` (decode Z once per candidate, then score insertion steps); `evaluation/run_repair_gate.py` is the closed-loop gate.
- `evaluation/diag_n1_table{1,2}.py` — table-1 (padding consistency / label replay / skip counting) and table-2 (fixed-state learned-vs-regret-2) diagnostics.
- `simulation/cc_swap.py` + `evaluation/run_cc_lns_swap_{fixed_state,gate}.py` — **enhanced-repair validation (no training; the next work package after N1/N2)**: limited two-customer cross-vehicle swap after R's full repair, full certification + full `J_vis`. `cc_lns_swap_search(swap=False)` is behaviorally identical to `cc_lns_search`; `swap=True` adds swap candidates (TW pre-check + capacity via try/except). Fixed-state (Q1: does swap beat R from the same public state?) + closed-loop (Q2: does it persist online?). See `docs/当前规划/历史已收束/决策与审计/N1N2收束与增强修复验证决策.md`.

Key wiring facts: the decoder is a **soft 0/1 attention bias** over the plan adjacency, and `edge_feat=None`. The frozen encoder loads as `DynamicColdChainModel` (7D input) via `train_fleet_head.load_base_model`; server needs `jax-cuda12-plugin` + `nvidia-*-cu12` + `flax==0.10.4` (0.10.7 breaks `SwiGLU`). Train/deploy padding is a known inconsistency (see Current Status): the training pads nodes to a fixed Nv (unmasked) while the online replanner uses the actual visible Nv, flipping ~30% of insertion choices.

### M-pre / M-trained (MaskCO direct-objective-training, Steps 1–5, concluded negative)

Reuse the **pretrained CVRP decoder** (not the extension's 256-dim encoder) + cold-chain adapter + directed head, trained by REINFORCE on full-repair reward. Modules (all under `scripts/`):

- `models/mpre.py` — `load_cvrp_model`/`encode_cvrp`/`decode_edge_logits`: loads `MASKCO_code/ckpts/cvrp100.ckpt` (512-dim `CVRPModel`, 3D coord+demand input), produces **symmetric** edge logits `features@features.T`.
- `models/mpre_trained.py` — `MpreTrainedModel` = frozen CVRP encoder (`init_proj/encoder/depot_bias`) + trainable decoder (`mid_proj/timestep_embedder/decoder/final_proj/final_norm`) + `c_adapter` + `delta_head` (both **zero-init last layer** → init scores == M-pre). `partition()` splits train/frozen params via `nnx.split` path predicates; `edge_insertion_scores(L, pred, c, succ)` adds `L[pred][c]+L[c][succ]` and deletes `L[pred][succ]` **only if pred≠succ** (empty-route pred==succ==depot must NOT subtract the masked diagonal sentinel ≈−1.7e38).
- `data/repair_state.py` — `extract_repair_state_v1` (repair_state_v1 schema: F_NODE=10, F_ACTION_EXPLICIT=20 incl. target-vehicle `X_state` 13-dim + slack valid bits + order-level cargo table). **`freeze_vehicles` deep-copies the collector's vehicle list.**
- `simulation/mpre_policy.py` — `stepwise_sample`/`replay_log_prob` (sampling/replay separation; `deterministic=True` = argmax for eval), `enumerate_legal_actions`, `validate_repair_plan` (full-plan reconciliation: vehicle set/anchor/exact-once/non-mask order/protected — NOT customer-set).
- `simulation/mtrained_replanner.py` — `PolicyReplanner` + `cc_lns_policy_search` (unified softmax/argmax policy), `load_trained_model` (merges trained `train_state` into `MpreTrainedModel`).
- `training/train_mpre_reinforce.py` — REINFORCE (baseline = mean of other K−1 samples; reward `(J_vis(P0)−J_vis(P))/s_TRAIN`; functional JIT + fixed-capacity padding; `CollectProbe` with **per-instance quota + `freeze_vehicles`**).
- `evaluation/run_step5_gate.py` — 4-way B/R/M-pre/M-trained closed-loop (with JIT warm-up excluded from the online budget); `evaluation/diag_collector_state.py` — collector freeze/quota diagnostic.
- `evaluation/run_fixed_state_quality.py` — fixed-state R/M-pre/M-trained comparison (per-state `det` + 8 samples, `validate_repair_plan` full-plan cert, `mask_candidate_pool` for masks); `evaluation/analyze_fixed_state.py` — acceptance-corrected `J_accept=min(J0,J_cand)` when certified + instance-clustered paired bootstrap; `evaluation/analyze_sampling_diag.py` — greedy / best-of-1..8 / win-R / dup / fail sampling diagnostic.
- `evaluation/run_sgbs_fixed_state.py` — SGBS layer-by-layer beam (`sgbs_search`: greedy + beam=2, per-parent≤2, ≤8 completions, plan-hash dedup) with distance-proposal + independent-sampling + R controls; `evaluation/verify_sgbs_search.py` / `verify_cache_equiv.py` / `verify_cache_real.py` — search/cache acceptance tests; `evaluation/record_training_identity.py` — checkpoint/data/source SHA recorder.

**Key wiring facts that bite:**
- **Collectors must freeze mutable state** — save `freeze_vehicles(vehicles)` + `np.array(served_mask, copy=True)` at event time; the simulator mutates `VehicleState` fields in-place afterward (60.8% mismatch when not frozen).
- **Per-instance quota, not global `max_states`** — a global cap concentrates all states in the first few instances.
- **Fixed-capacity padding is NOT lossless** for deterministic argmax search: padding to Nv_max/M_max introduces ~1e-5 float32 noise (XLA reassociation) that flips argmax in near-ties and diverges the search. Use unpadded (varying shapes, per-shape JIT recompile) for exact deterministic results; padding only when approximation is acceptable.
- **Mask pool is unified** — repair masks come from `mask_candidate_pool` (= `decision_pool_from_vehicles` − protected tail) with `validate_mask_scope` assertion (⊆ decision_pool, not committed_next, not protected tail). Never use the broad `[c for c in visible_ids if not served_mask[c]]` pool — it leaks non-replan-vehicle tail customers (10.5% of training states, mask scope bug).
- **Cache H0 only, not all H** — `mpre_score_fn_cached`/`mtrained_score_fn_cached` (in `mtrained_replanner.py`) cache the frozen encoder output H0 (event-invariant `raw_3d`); `C`/decoder recompute per step via `encode_H0`/`score_from_H0`. Bit-identical to uncached (worst |Δ|=0).
- **Checkpoint dims**: pretrained CVRP decoder is **512-dim**; the extension's frozen `step50000.ckpt` is **256-dim encoder-only**. There is no adapted bridge checkpoint on the server.

## Environment

- **Local (Windows, Python 3.12)**: JAX 0.5.0 / Flax 0.10.4 (NNX) / optax are installed, so the M0/M1 training (small MLP heads) runs locally on CPU; the control-chain/identity test suites need only NumPy. The frozen `DynamicColdChainModel` encoder + real teacher data are **server-only**.
- **Server (Linux, Python 3.10.19)**: `/home/hzeng/project/MASKCO-Main/` (credentials in `.vscode/sftp.json`), conda `MASKCO_env` (jax 0.6.2 / flax 0.10.4 / optax 0.2.4), 2× RTX 5090. GPU access requires `pip install jax-cuda12-plugin==0.6.2 nvidia-*-cu12` (the default jax is CPU-only), and `flax` must stay at **0.10.4** (0.10.7 breaks `SwiGLU` → `'ArrayImpl' object has no attribute 'value'`). Run remote commands via the local helper `python tools/_srv.py "<cmd>"` (reads credentials from `sftp.json`, never inline the password — the auto-mode classifier flags plaintext credentials in the transcript). The GPUs are **shared** with other users' jobs — for M0/M1 runs use `CUDA_VISIBLE_DEVICES=1` and cut memory/compile contention with:
  ```bash
  export XLA_PYTHON_CLIENT_PREALLOCATE=false   # avoid JAX's 75% upfront allocation (else OOM under contention)
  export XLA_FLAGS=--xla_gpu_autotune_level=0  # skip slow GEMM autotuning (fine for the full 256-dim decoder)
  ```
  ⚠️ `--xla_gpu_autotune_level=0` triggers a `XlaRuntimeError: CANCELLED: Too small divisible part of the contracting dimension` on small MLPs (H-only probe) and batch-8 compact decoders — **`unset XLA_FLAGS` for those runs**.
  For any job >5 min use `tmux` (not `nohup`) — MobaXterm SSH drops kill foreground jobs. Frozen M0/M1 encoder: `ckpts/r1_5_baseline/typed_v1_edge/phase3c/seed42/step50000.ckpt`.
- **File upload/download to server**: `python tools/_sftp_put.py <local_rel>` / `python tools/_sftp_get.py <remote_rel>` (both take **repo-relative** paths; remote base `/home/hzeng/project/MASKCO-Main/` is hardcoded in the scripts). ⚠️ Git Bash converts `/home/...` CLI args to Windows paths, so **never pass absolute remote paths as args** — pass only relative local paths. `cvrp100.ckpt` (~305 MB) is **on the server** (uploaded 2026-09-20). The server conda is at `~/miniconda3` (not `~/anaconda3`): `source ~/miniconda3/etc/profile.d/conda.sh && conda activate MASKCO_env`, or use the direct interpreter `/home/hzeng/miniconda3/envs/MASKCO_env/bin/python`.

---

# 附录 B — Codex 侧指引（原 `AGENTS.md`，逐字保留）

# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Project Overview

MaskCO is the official ICLR 2026 implementation of a Neural Combinatorial Optimization (NCO) framework using masked generation. Three NP-hard problems: **TSP**, **CVRP**, **MIS**. The unmodified upstream implementation now lives in `MASKCO_code/`.

The `C-VRP_Cold-chainVehicleRoutingProblem/` subdirectory extends MaskCO from standard CVRP to **CVRPTW** (Time Windows), **Cold-Chain** (temperature), and **Dynamic Cold Chain (DCC)** (reveal_time + EDoD). This is an isolated workspace — **never modify files under `MASKCO_code/`**.

## 当前状态入口（2026-09-28）：方向 A 正向优化与全链路核查

2026-09-29 最新主线按用户固定为“基于 MaskCO 的掩码生成与迭代重构范式，构建面向动态冷链物流的在线优化方法”。当前正向仅属开发系统/条件信息观测；S3-1 稳健性未过，MaskCO 数量/联合与迭代本体未落地。最新代码缺口、结果解释和下一阶段以扩展目录 `docs/当前规划/决策与审计/方向A_S3裁决复核与MaskCO主线推进_2026-09-29.md` 和状态入口置顶为准，助手/执行端分工不变。

当前主线为 A-v1 条件未来场景生成 + 共用 SAA 的动态冷链接单；以扩展目录 `项目当前状态.md` 和 `docs/当前规划/决策与审计/方向A全链路核查与正向增益改进清单_2026-09-28.md` 为最新依据。助手维护文档与正确性审计，用户/执行端实施代码、正式实验、归档与提交。系统胜公平强对照、条件信息增益、MaskCO 独立方法增益分别验证；开发 seed=20260926/20260930/20261001 均已查看，最终 20260927/28 只测一次。不得以旧批均值、修复混合差值或不匹配的合同/数据身份裁决反超。以下 09-19 研究状态属于历史，工程禁改上游规则继续有效。

## 历史状态（2026-09-19）：event_plan两轮未建立正效用，按投入边界收束；下一步为证据归档与方法职责决策

> **唯一状态入口**：`C-VRP_Cold-chainVehicleRoutingProblem/项目当前状态.md`。本文件保留工程规则和历史背景；若研究进度或权威路径冲突，以 `项目当前状态.md` 及其链接的论文优先版进度表为准。

> **本轮分工与任务**：助手维护重要文档，用户/执行端实施代码、实验、归档与提交。event_plan两轮已有本地结果，A/B/S_proxy均锁∞，未建立正效用，按D-056收束；源码投影与运行身份仍有局限，不能据此认定表示不是主要瓶颈。下一步见扩展目录 `docs/当前规划/历史已收束/决策与审计/event_plan两轮收束与后续决策.md`：保存已有证据，重新定义学习职责、目标/信息和可部署强对照。不默认pairwise第三轮，也不因新发现缺陷自动修复后重跑。助手不代跑/提交，冻结上游/数据与评价规则仍有效。

> **目录迁移状态**：P0-M 已通过。扩展入口统一使用 `scripts/project_paths.py` 解析 `WORKSPACE_ROOT`、`MASKCO_ROOT` 和扩展根目录；路径/导入/入口/syntax 7/7 与 P0-R/S/A/U 回归通过。后续仍不得修改 `MASKCO_code/`。

> **v4 运营契约**：主实验是 dynamic cold-chain pickup-to-depot，不是 depot-to-customer 配送。车辆空载出发，`service_finish` 取货入舱并开始品质计时，`return_arrival` 卸货并关闭；同构多温舱、共享总容量、单次行程、无 reload。后续 C0 实现必须包含订单级 cargo manifest。

> **本文件以下大部分是 2026-08-19 冻结的旧叙事。2026-08-26~09-01 做了 P0 协议审计 → R1.7 归因 → B0 → JF1 → JF2（exact-vehicle No-Go）→ HFR-M0（Gate A FAIL/F3），旧数字全部作废。**

**核心证据链（R1 EDoD=0.5，strict-online）**：

| 方法 | `distance_cost` | complete |
|------|------|----------|
| OR-Tools-RH（OR-joint） | 23.04 | 100% |
| **JF1-H（heuristic joint）** | **24.50** | 100% |
| JF1-R（real logits joint） | 26.84 | 97.7% |
| model guarded (H2-G) | 27.10 | 100% |
| NN (H1) | 27.66 | 100% |
| model raw (H2) | 28.20 | 100% |
| JF1-S（shuffle joint） | 29.10 | 96.1% |
| model_shuffle (H3) | 30.19 | 100% |

**演进链**：exact-vehicle CE（JF2-M0-v2）Gate A FAIL（25.91 vs 24.50）→ 2×2 oracle 证明 partition×sequencing 交互（interaction −1.6151）→ **HFR-M0（Hierarchical Fleet–Route Masked Reconstruction）完整实现（Step 1-5），Gate A FAIL（F3）**。

**HFR-M0 训练端 Sanity Gate 全 PASS**：G 学到 partition 信号（AUROC 0.727 / AUPRC 0.667）；A_joint 优于 A_base（L_A 13.57→8.92）；real G >> shuffle G（8.92 vs 29.56，耦合 active）。

**HFR-M0 Gate A（VAL128，7 变体消融，JF1-H=24.50）**：

| 变体 | partition | insert | cost | Δ |
|------|-----------|--------|------|---|
| g_only | G | min-travel | **24.97** | +0.47 |
| min_travel（骨架） | travel | travel | 25.92 | +1.38 |
| a_only | travel | A_joint | 26.63 | +2.12 |
| full | G | A_joint | 29.95 | +5.41 |
| group_only | G | ΔA+logσ(G) | 30.19 | +5.69 |
| group_logit | G | 纯 logσ(G) | 30.07 | +5.52 |

**方向定论（F3 坐实）**：
> HFR 训练信号可学但未转化为部署效用，说明旧 structural target 与可执行动作错位；这不证明所有 route signal 无用，也不否定 MaskCO。v4 主线固定为 **DynMaskCO-CC：基于 MaskCO 的动态冷链效用对齐掩码重构**。Cost-aware preference 是内部监督机制；C0 功能/口径 20/20、pilot sensitivity 7/7 已通过，下一步 O0-D；最终 M1 必须保留 event mask、masked reconstruction 与 iterative refinement。

**权威入口**：
- `C-VRP_Cold-chainVehicleRoutingProblem/项目当前状态.md` — 当前状态与导航
- `C-VRP_Cold-chainVehicleRoutingProblem/docs/当前规划/结果与进度/执行进度表.md` — 当前阶段、Gate 与下一动作
- `C-VRP_Cold-chainVehicleRoutingProblem/docs/当前规划/` — 论文主控、执行契约与评价口径

**关键脚本（HFR-M0）**：
- `C-VRP_Cold-chainVehicleRoutingProblem/scripts/expert/build_teacher_routes.py` — HFR Step 1：OR-joint 完整 routes → G/A 监督
- `C-VRP_Cold-chainVehicleRoutingProblem/scripts/models/hierarchical_fleet_route.py` — HFR Step 2：GroupingHead + RouteResidualAdapter
- `C-VRP_Cold-chainVehicleRoutingProblem/scripts/training/train_hfr_m0.py` — HFR Step 3：frozen base + 训练
- `C-VRP_Cold-chainVehicleRoutingProblem/scripts/simulation/hfr_replanner.py` — HFR Step 4：FleetSlot + joint GA score
- `C-VRP_Cold-chainVehicleRoutingProblem/scripts/evaluation/run_hfr_gate_a.py` — HFR Step 5：Gate A eval（partition/insert 消融）
- （JF2 遗留：`joint_fleet.py` / `fleet_features.py` / `fleet_assignment_head.py` / `jf2.py` / `train_fleet_head.py` / `run_jf2_gate_a.py`）

**R1 诊断历史（2026-08-28，已被取代）**：旧 strict-online 曾发现「模型输出与 EDD 贪心逐位相同」，根因 R1-R4——经 P0 协议修复后模型 active（61% divergence）；R1.7 证明 learned preference 有独立价值；B0 证明 fleet allocation 主导；JF1 证明 joint topology −11.4% 收益；JF2/HFR-M0 证明 exact-vehicle 与 route 结构监督都无 online utility（F3）。

## 当前定位（2026-08-19 最终冻结）

**核心研究问题**：研究掩码生成范式如何从静态组合优化扩展到动态冷链车辆路径问题中的因果、可行性保持在线优化。

*"DynMaskCO investigates how masked generation can be extended from static combinatorial optimization to causal, feasibility-preserving online optimization for dynamic cold-chain vehicle routing."*

**三层贡献**（按原始课题排序）：

1. **从 Static MaskCO 到 Causal Dynamic Masked Generation**（核心）—— Visibility-Gated Attention（P0-2）+ Visible-Only Normalization（P0-3a）+ Event Masking（D1）+ Frozen Prefix（D2）+ Online Seq（Phase 3c）。核心消融（3 类型一致）：Model-only 0% feas + ~20 viol → +Resource Beam −90% viol → +EDD 100%。
2. **动态硬约束下的 Feasibility-Preserving Reconstruction** —— Hybrid NCO 架构（learned masked generation + resource-feasible search），45/45 = 100% 可行。
3. **Cold-Chain 多资源约束扩展与机制验证** —— Toy 因果翻转（weighted completion time 机制成立）+ R1 弱效应（硬 TW 主导，诚实报告）。

> ⚠️ **历史叙事（已被 2026-09-03 v4 覆盖）**：曾将冷链降为应用扩展；当前主线已重新锁定为基于 MaskCO 的动态冷链优化。

**历史入口**：`C-VRP_Cold-chainVehicleRoutingProblem/archive/docs/优化历程/v1/代码核查与修正.md`（P0 修复记录）+ `C-VRP_Cold-chainVehicleRoutingProblem/archive/docs/旧版总览/v1/完整代码归档.txt`（历史源码快照）。当前动作仍以文件顶部的唯一状态入口为准。

## 核心成果

**DynMaskCO v1 Frozen** — Phase 3c K=5 online seq + K=16 beam + TW 2opt: **100% TW feas + 0 violations, 45/45**（5 train seeds × 3 types × 3 EDoDs）。Avg cost **14.77**（全矩阵平均；R1 EDoD=0.5 单独 17.40）。Causal model（coord_normalize_visible）比 leaky model 便宜 **8.8%**。

**typed embedding + 边特征**（2026-08-18）: `temp_embed`(3)→`type_embed`(5，修复 temp_class 截断 bug) → 14.79（+0.1% 零退化）；再 + 边特征 `energy_mat` → **14.08（-4.8%）**。checkpoint 见 `ckpts/p0_fix/typed_v1{,_edge}/phase3c/`。

**核心演化消融**（2026-08-19，论文第一贡献证据）: Model-only（原始 MaskCO）feas 0% + viol 22.2 → +Resource Beam（viol 22.2→2.1，**-90%**）→ +EDD（feas 100%）→ +2opt（cost 微调）。证明「learned masked generation + resource-feasible search」hybrid 架构——模型提供路由偏好，resource-state decoding 保证硬约束。

**历史品质机制观察（C0 前口径）**：toy、R1 与 R2 数字只作为调试线索；当时热学单位、品质累计语义和执行轨迹评估器尚未闭环，不能作为当前机制结论。C0 现已闭环，但机制效果仍须由后续 O0-CC/M1 在新口径下重跑。

## 诚实报告

严格 frozen-prefix non-anticipatory 对比显示 **OR-Tools Rolling Horizon 全面优于 DynMaskCO**（R1 −16.5%, C1 −37%, RC1 −21%; 100-node 仍 feasible）。「在线 SOTA」和「可扩展性」叙事已废弃。详见 `docs/调研/GPT/v5/执行方案_v5.md`。

RRNCO（ICLR 2026 learned 基线）对比同样**交叉而非一边倒**：RRNCO clairvoyant（R1 11.88）远强于 DynMaskCO 底层（~17），naive 特征屏蔽下随 EDoD 崩坏 +60%（15.38→24.67），DynMaskCO 仅 +5%（17.12→17.95）。低动态 RRNCO 赢、高动态 DynMaskCO 赢，但这只支撑「causal 架构鲁棒性」，**不**支撑「DynMaskCO 路线更优」——给 RRNCO 正经非预知方案（rolling horizon）大概率全面优于 DynMaskCO。详见 `C-VRP_Cold-chainVehicleRoutingProblem/docs/当前规划/实验与评估/基线对比.md` §3.2。

## Setup

```bash
cd MASKCO_code
sh install.sh          # JAX 0.5.0, Flax 0.10.4, Triton 3.1.0, PyTorch CPU, NumPy 1.26.4
cd lib && make         # Upstream C++ extension (2-opt, insertion)
cd ../..

# CVRPTW C++ extension (EDD repair + TW-aware 2-opt)
pip install pybind11
cd "C-VRP_Cold-chainVehicleRoutingProblem/scripts/lib" && make
```

Set `XLA_PYTHON_CLIENT_MEM_FRACTION=0.9` (training) or `0.5` (inference). GPU 0 is default (31GB free).

## Server Environment

- **Path**: `/home/hzeng/project/MASKCO-Main/`
- **Conda**: `/home/hzeng/envs/MASKCO_env/` (Python 3.10.19)
- **GPU**: 2× RTX 5090 (32 GB), use GPU 0 (always free). `CUDA_VISIBLE_DEVICES=0` for decoding, `--gpu_id 0` for training.
- **Workflow**: Write locally → MobaXterm SFTP upload → SSH run
- **⚠️ SSH instability**: MobaXterm SSH connections drop frequently, killing foreground jobs. For any run >5min, use `tmux` (NOT `nohup`, which doesn't reliably survive the drop):
  ```bash
  tmux new-session -d -s freeze 'bash C-VRP_Cold-chainVehicleRoutingProblem/scripts/run_method_freeze.sh eval > /tmp/freeze_eval.log 2>&1'
  tmux ls                                    # verify running
  tail -f /tmp/freeze_eval.log               # view progress (no attach needed)
  tmux attach -t freeze                      # attach; detach with Ctrl+B then D
  ```

## Architecture

### Parent Project (MaskCO)

Encoder-decoder transformer (Flax NNX). Encoder → Decoder + timestep + partially-masked adjacency matrix as attention bias → edge predictions. Training: random mask edges in solutions, CE loss. Inference: iterative mask-and-reconstruct + C++ 2-opt.

### CVRPTW / Cold-Chain / DCC Extension

Model chain: `TSPModel → CVRPModel → CVRPTWModel → ColdChainModel → DynamicColdChainModel`

| File | Input | Key Features |
|------|-------|-------------|
| `models/CVRPTWModel.py` | 5D (x,y,demand,tw_start,tw_end) | +tw_bias, config: `softcap_fn` (256d), `softcap_fn_512` (512d) |
| `models/ColdChainModel.py` | 6D (+temp_class) | Inherits CVRPTWModel |
| `models/DynamicColdChainModel.py` | 7D (+reveal_time) | **type_embed（5 类：depot/常温/冷藏/冷冻/未来订单）**（2026-08-18 替代 temp_embed，修复 temp_class 截断 bug）+ **edge_weight**（`energy_mat` 边特征，`--use_edge_feat`）, **Visibility-Gated Attention (P0-2)**: `encode(raw_features, visible_mask)` → attn bias `-1e9` for future nodes |
| `models/cvrptw_utils.py` | — | **P0-3a**: `coord_normalize_visible(inputs, visible_mask)` — visible-only normalization statistics. Fixes the leak in parent `coord_normalize` (which used ALL nodes' mean/norm). |

| File | Purpose |
|------|---------|
| `data/generate_cvrptw_data.py` | Solomon CVRPTW generator (R1/C1/RC1/R2/C2/RC2) |
| `data/generate_coldchain_data.py` | Cold-chain + DCC generator. `--edod 0.5` for dynamic. `--temp_dist "0,0,1"` for 温区分布控制（全冷冻=温度驱动验证）. **P0-4**: +`quality_loss` (Arrhenius), +`energy_mat` (refrigeration) |
| `data/CVRPTWDataloader.py` | 5D loader, pure NumPy |
| `data/ColdChainDataloader.py` | 6D/7D/8D auto-detecting loader. **P0-2**: masks future order features (coords→0.5, others→0). **P0-4**: loads `quality_loss` as optional 8D. Yields `(features, routes, timestep, visible_mask)` |
| `training/train_cvrptw.py` | CVRPTW training. `--encoder_input_dim`, `--tw_loss_lambda` |
| `training/train_coldchain.py` | ColdChain training. **Must add encoder_input_dim override before construct_model**. Adapts to 4-tuple dataloader output |
| `training/train_dynamic_cc.py` | DCC training. `--masking_mode` (random/spatio_temporal/targeted/adaptive). `--online_seq_training --online_seq_steps 5` (Phase 3c K=5). `--seed` (default 42, added 2026-08-12). **P0-2**: passes `visible_mask` to `m.encode()`. **P0-3a**: uses `coord_normalize_visible`. `--spoilage_lambda` still accepted but not used (deprecated) |
| `training/auto_train.py` | Auto GPU-detect → smoke 50 steps → full training. Uses `/bin/bash` |
| `decoding/cvrptw.py` | **Main decoder**. Auto-detects C++ ops, feature dims, model types. **P0-2**: masks future order features + passes `visible_mask`. **Phase 2 (D1-D6)**: constraint-aware decoder, event-aware mask-reconstruct, frozen prefix, adaptive mask, anytime solver. **Phase 3**: `--enable_resource_decoder --beam_width 16` (K-beam). CLI flags: `--enable_event_mask`, `--enable_frozen_prefix`, `--enable_constraint_decoder`, `--enable_adaptive_mask`, `--enable_anytime` |
| `decoding/resource_beam.py` | **Phase 3a core** — K-beam resource-state decoder: `BeamState` tracks route/arrival/load/visited; `_can_go()` checks TW+capacity+round-trip+2-step lookahead. **品质感知 score**: `--enable_quality --lambda_q` → beam score -= λ_q × weighted completion time（∑K_i·t_i 边际贡献，2026-08-19 修正方向）。支持 `dist_mat` 手动传入（toy 验证用）。 |
| `decoding/resource_mask.py` | Per-edge TW+capacity feasibility mask (v1→v3). Superseded by resource_beam for decoding. |
| `decoding/thermal_state.py` | **C0 compatibility shim** — 静态路线桥接到唯一 `coldchain_state`；旧歧义单段热 API 已拒绝执行 |
| `decoding/learnable_mask.py` | **Phase 3b** — REINFORCE mask policy (Gumbel-Top-K, MaskPolicyTrainer). Honest ablation. |
| `decoding/coldchain.py` | ColdChain/DynamicColdChain decoding wrapper |
| `decoding/maskco_dynamic.py` | **Phase 2 core module** — D1-D6 unified implementation: `dynamic_mask_reconstruct()`, `compute_affected_segments()`, `compute_adaptive_keep_rate()`, `AnytimeScheduler`, `SequentialDynamicSampler`, `apply_constraint_mask()` |
| `baselines/solomon_audit.py` | **P0-2** — OR-Tools + PyVRP 三层 Solomon sanity check. Proves OR-Tools adapter correct (J*=9.1 on DCC). |
| `baselines/ortools_rolling_horizon.py` | **P0-2 强动态基线** — OR-Tools frozen-prefix rolling-horizon（non-anticipatory）。关键发现：全面优于 DynMaskCO（16-37%） |
| `baselines/euro_adapter.py` | **P0-4** — DynMaskCO → EURO Meets NeurIPS 2022 D-VRPTW competition protocol adapter. |
| `simulation/run_dynamic_sim.py` | Rolling-horizon dynamic simulation. **P0-2**: replanner masks future orders + `encode_fn` accepts `visible_mask` |
| `simulation/rolling_horizon.py` | Event-driven simulator: Order states (unknown→known→assigned→in_transit→completed), clock-based revelation |
| `analysis/recourse_regret.py` | **P0-3** — Conditional Recourse Regret 计算（clairvoyant J_e*，待接入 J_e^π） |
| `tests/test_no_future_leakage.py` | **P0-2 verification**: 3 tests (dataloader masking, gradient isolation, attention bias math) |
| `tests/test_future_cardinality.py` | **P0-3a** — future identity invariance + cardinality leakage |
| `tests/test_target_label_leakage.py` | **P0-3b** — target adjacency future-edge leakage (vis-only Δ=0) |
| `tests/test_data_qc.py` | **P0-5** — data QC (NaN/范围/重复/TW sanity) |
| `scripts/run_method_freeze.sh` | **P0-5 canonical** — 训练 + 评估一键复现（`smoke`/`phase3c`/`full`/`eval`/`env`） |
| `scripts/run_phase_e.sh` | One-click pipeline: data gen → train → eval → summary. `smoke` (1280/500) or `full` (12800/50000) |
| `lib/` | C++ extension: `cvrptw_ops.{hpp,cpp}` + `cvrptw_bindings.cpp`. EDD (0.3ms) + TW 2opt (0.27ms). **P0-4**: +`cvrptw_quality_cost`, +`cvrptw_quality_two_opt` |

Full file index: [`scripts/README.md`](C-VRP_Cold-chainVehicleRoutingProblem/scripts/README.md)

### Data Format (.npz)

```
coords:       (N, nodes, 2)  float32
demands:      (N, nodes)     int32
tw_start/end: (N, nodes)     float32
service_time: (N, nodes)     float32
temp_class:   (N, nodes)     int32     — ColdChain/DCC [0,1,2]
reveal_time:  (N, nodes)     float32   — DCC only (0=known, >0=future)
visible_mask: (N, nodes)     float32   — 1=visible at t=0, 0=future (P0-2)
quality_loss: (N, nodes)     float32   — 历史 delivery-reference 代理（仅兼容旧模型）
energy_mat:   (N, nodes, nodes) float32 — 历史 edge-energy 代理（仅兼容旧模型）
initial_quality: (N, nodes)  float32   — C0 pickup 时的初始品质
routes:       (N, pad_len)   int32     — depot=0 separators
opt_costs:    (N,)           float32
```

## CC_Compare（对比方法复现工作区）

复现「同赛道 learned 方法」并改成 DCC-VRP 协议做公平对比（对应 `C-VRP_Cold-chainVehicleRoutingProblem/docs/当前规划/实验与评估/基线对比.md` §2.3）。**一个方法一个文件夹**，位于根目录 `CC_Compare/`，是独立于 `C-VRP_Cold-chainVehicleRoutingProblem/` 的第二个工作区。

| 文件夹 | 方法 | 出处 | 状态 |
|--------|------|------|------|
| `CaDA/` | Constraint-Aware Dual-Attention | ICML 2025 | ✅ 可适配（VRPTW 变体） |
| `RRNCO/` | Real-World NCO | ICLR 2026 | ✅ 已跑（clairvoyant + non-anticip） |
| `PIP-constraint/` | 复杂约束 Lagrangian | NeurIPS 2024 | ⛔ 不可适配（单车辆 TSPTW，缺容量+多车辆） |
| `MAPT/` | 多车动态取送货 | AAAI 2026 | ❌ 无源码 |

**适配约定**（每个方法在 `dcc_vrp/` 下放一套不改原始代码的脚本）：
- `dcc_data.py` — DCC .npz → 该方法输入（时间尺度对齐 + demand 归一 + 可见性）。
- `dcc_env.py` — 环境门控（non-anticipatory：`--mask_future`）。
- `run_dcc.py` — 评估 harness（报告 cost=纯距离 / TW Feas / Cap Feas / complete / gap）。
- `README.md` — checkpoint 下载 + 运行命令。

**关键规则**：只改 `dcc_vrp/` 适配脚本，**绝不改原始仓库代码**（如 `RRNCO/rrnco/`、`CaDA/50/`）。non-anticipatory 语义 = 未来节点特征屏蔽（coords→0.5，与 DynMaskCO P0-2 一致）+ env 用 `_true_*` 真值做可行性/奖励（serve 全部 50，不早停），等价 DynMaskCO 的「causal encoder + full-service decoder」。

**RRNCO 结果**（已跑完，见 `基线对比.md` §3.2）：clairvoyant R1 11.88 / C1 6.93 / RC1 10.24（EDoD 不变）；non-anticipatory（naive 特征屏蔽）随 EDoD 崩坏 +60%（R1 15.38→24.67），与 DynMaskCO（+5%）**交叉**——低动态 RRNCO 赢、高动态 DynMaskCO 赢。⚠️ 这是「鲁棒性」对比不是「更优」对比：RRNCO 底层模型远强（clairvoyant 11.88 vs DynMaskCO ~17），给它正经 rolling-horizon 非预知方案大概率全面优于 DynMaskCO（与 OR-Tools-RH 同一逻辑）。

环境：`cc_compare` conda env（RTX 5090 需 torch≥2.7）。建环境 `bash CC_Compare/setup_envs.sh cc`（CaDA+RRNCO 共用）。CaDA 原始 pin 旧 torchrl 0.1.1，需 `_torchrl_compat.py` 补丁。

## Key Commands

### Batch Experiment Scripts

```bash
# P0 Protocol Audit (run these first)
bash "C-VRP_Cold-chainVehicleRoutingProblem/scripts/run_p0_verification.sh"        # P0-2+P0-3a+P0-3b 一键审计
bash "C-VRP_Cold-chainVehicleRoutingProblem/scripts/run_baseline_audit.sh"         # OR-Tools/PyVRP Solomon sanity

# DynMaskCO v1 Frozen Reproduction (THE canonical entry point)
bash "C-VRP_Cold-chainVehicleRoutingProblem/scripts/run_method_freeze.sh" smoke    # 冒烟 (~10min, 1 seed 2K steps)
bash "C-VRP_Cold-chainVehicleRoutingProblem/scripts/run_method_freeze.sh" phase3c  # Phase 3c only (~5h, 5 seeds)
bash "C-VRP_Cold-chainVehicleRoutingProblem/scripts/run_method_freeze.sh" full     # 完整复现 (~24h, 5 seeds)
bash "C-VRP_Cold-chainVehicleRoutingProblem/scripts/run_method_freeze.sh" eval     # 仅评估已有 ckpt
bash "C-VRP_Cold-chainVehicleRoutingProblem/scripts/run_method_freeze.sh" env      # 环境快照

# Legacy / supplemental
bash "C-VRP_Cold-chainVehicleRoutingProblem/scripts/run_phase_e.sh" full           # 全流程: 数据→训练→评估
bash "C-VRP_Cold-chainVehicleRoutingProblem/scripts/run_mixed_edod.sh" full         # 混合EDoD训练
bash "C-VRP_Cold-chainVehicleRoutingProblem/scripts/run_baselines.sh"               # ALNS vs Greedy vs MaskCO
bash "C-VRP_Cold-chainVehicleRoutingProblem/scripts/run_ablation.sh"                # P0-3 四层消融
bash "C-VRP_Cold-chainVehicleRoutingProblem/scripts/run_keep_rate_sweep.sh" smoke   # 方向C: keep_rate×EDoD sweep（greedy对照）
```

### Training

```bash
# CVRPTW 50-node
python -u "C-VRP_Cold-chainVehicleRoutingProblem/scripts/training/train_cvrptw.py" \
    --gpu_id 0 --num_nodes 50 --capacity 50 --model_config softcap_fn \
    --encoder_input_dim 5 --peak_lr 1e-3 --batch_size 64 \
    --num_steps 50000 --save_interval 5000 --data <train.npz> \
    --logdir ... --savedir ... \
    --optimizer_type adamw --weight_decay 1e-2 --target_disruption None

### DCC 7D + ST-mask (fixed GPU 0)

```bash
CUDA_VISIBLE_DEVICES=0 XLA_PYTHON_CLIENT_MEM_FRACTION=0.9 \
python -u "C-VRP_Cold-chainVehicleRoutingProblem/scripts/training/train_dynamic_cc.py" \
    --gpu_id 0 --num_nodes 50 --capacity 50 --model_config softcap_fn \
    --encoder_input_dim 7 --peak_lr 1e-3 --batch_size 64 \
    --num_steps 50000 --save_interval 5000 --data <dcc_train.npz> \
    --masking_mode spatio_temporal \
    --logdir ... --savedir ... \
    --optimizer_type adamw --weight_decay 1e-2 --target_disruption None
```

# Phase 3c K=5 online seq training (strongest model)
CUDA_VISIBLE_DEVICES=0 XLA_PYTHON_CLIENT_MEM_FRACTION=0.9 \
python -u "C-VRP_Cold-chainVehicleRoutingProblem/scripts/training/train_dynamic_cc.py" \
    --gpu_id 0 --num_nodes 50 --capacity 50 --model_config softcap_fn \
    --encoder_input_dim 7 --peak_lr 1e-3 --batch_size 64 \
    --num_steps 50000 --save_interval 5000 --data <train.npz> \
    --masking_mode spatio_temporal --online_seq_training --online_seq_steps 5 \
    --logdir ... --savedir ... \
    --optimizer_type adamw --weight_decay 1e-2 --target_disruption None

# Beam decode evaluation (Phase 3, strongest decoder)
CUDA_VISIBLE_DEVICES=0 XLA_PYTHON_CLIENT_MEM_FRACTION=0.5 \
python -u "C-VRP_Cold-chainVehicleRoutingProblem/scripts/decoding/cvrptw.py" \
    --capacity 50 --penalty 3. --data <test.npz> --ckpt <phase3c.ckpt> \
    --keep_rate 0.3 --batch_size 8 --runs 1 --cycles 1 --sampling_steps 1 \
    --two_opt_steps 4 --seed 42 --gumbel_scale_factor 0. --threads_over_batches 1 \
    --enable_resource_decoder --beam_width 16 --enable_tw_aware_2opt_py

# Auto-train (GPU detect + smoke + full)
python "C-VRP_Cold-chainVehicleRoutingProblem/scripts/training/auto_train.py" \
    --script train_dynamic_cc.py \
    --num_nodes 50 --capacity 50 --model_config softcap_fn \
    --encoder_input_dim 7 --peak_lr 1e-3 --batch_size 64 \
    --num_steps 50000 --save_interval 5000 --data <train.npz> \
    --logdir ... --savedir ... \
    --optimizer_type adamw --weight_decay 1e-2 --target_disruption None
```

### Evaluation (Best Configuration)

```bash
CUDA_VISIBLE_DEVICES=0 XLA_PYTHON_CLIENT_MEM_FRACTION=0.5 \
python -u "C-VRP_Cold-chainVehicleRoutingProblem/scripts/decoding/cvrptw.py" \
    --capacity 50 --penalty 3. --data <test.npz> --ckpt <ckpt> \
    --keep_rate 0.3 --two_opt_steps 4 --batch_size 8 --runs 8 --cycles 40 \
    --sampling_steps 2 --augment_level 0 --gumbel_scale_factor 0. --seed 42 \
    --threads_over_batches 1 \
    --enable_tw_filter --enable_tw_repair_edd --enable_tw_aware_2opt_py

# P0-4: quality-aware 2-opt (add these flags)
    --enable_quality_2opt --lambda_q 0.1 --lambda_e 0.01
```

### Self-Training Labels (方向一)

```bash
# 用最佳模型生成伪标签
CUDA_VISIBLE_DEVICES=0 XLA_PYTHON_CLIENT_MEM_FRACTION=0.5 \
python -u "C-VRP_Cold-chainVehicleRoutingProblem/scripts/data/generate_self_training_labels.py" \
    --data <train.npz> --ckpt <best_ckpt> --output <st_labels.npz> \
    --batch_size 8 --runs 8 --cycles 320
# Then fine-tune on st_labels.npz with train_dynamic_cc.py
```

### EDoD Matrix Evaluation

```bash
python -u "C-VRP_Cold-chainVehicleRoutingProblem/scripts/analysis/run_edod_matrix.py"
# Outputs 9-line summary: R1/C1/RC1 × EDoD 0.2/0.5/0.8
```

### Data Generation

```bash
# Standard CVRPTW
python -u "C-VRP_Cold-chainVehicleRoutingProblem/scripts/data/generate_cvrptw_data.py" \
    --problem_size 50 --num_instances 1280 --type R1 --capacity 50 --output <out.npz>

# ColdChain with EDoD (0.2/0.5/0.8)
python -u "C-VRP_Cold-chainVehicleRoutingProblem/scripts/data/generate_coldchain_data.py" \
    --problem_size 50 --num_instances 1280 --type R1 --capacity 50 \
    --edod 0.5 --output <out.npz>
```

### P0-2 Leakage Verification

```bash
python -u "C-VRP_Cold-chainVehicleRoutingProblem/scripts/tests/test_no_future_leakage.py" \
    --data <dcc_test.npz> --ckpt <step50000.ckpt>
# 3 tests: dataloader masking, gradient isolation, attention bias math
```

### C++ Extension

```bash
cd "C-VRP_Cold-chainVehicleRoutingProblem/scripts/lib"
make clean && make
```

## Decoding Flags

| Flag | Effect |
|------|--------|
| `--enable_tw_filter` | Filter candidate edges by TW compatibility |
| `--enable_tw_repair_edd` | EDD sort within route segments (C++ auto-detected) |
| `--enable_tw_aware_2opt_py` | TW-constrained 2-opt (C++ auto-detected) |
| `--enable_quality` | 品质感知 beam score（weighted completion time ∑K_i·t_i）: beam score -= λ_q × 品质损耗 |
| `--quality_salable_threshold` | 不可售品质损耗阈值（Num 指标，默认 0.1 对本数据偏高，用 0.02） |
| `--save_routes` | 保存最终路线到 .npz（路线分析用，`analysis/mechanism_analysis.py` 等） |
| `--tw_margin` | Phase 3a: TW 安全裕度 (default 0.05, 0=无裕度) |
| `--lambda_q` | Quality loss weight (default 0.1) |
| `--enable_event_mask` | D1: event-driven local reconstruction (only mask affected segments) |
| `--enable_frozen_prefix` | D2: freeze executed route prefix (immutable) |
| `--enable_constraint_decoder` | D3: decoder-native TW constraint (logit=-inf for illegal edges) |
| `--enable_adaptive_mask` | D4: feature-adaptive per-node mask probability |
| `--enable_anytime` | D6: time-budget-aware cycle scheduler |
| `--time_budget_ms` | D6: total time budget in ms (default 200) |
| `--frozen_prefix_len` | D2: number of prefix positions to freeze |
| `--enable_tw_attn_bias` | ⚠️ Conflicts with preserving 2opt, don't combine |
| `--enable_tw_preserving_2opt` | ⚠️ 100% revert rate, deprecated |

## Critical Rules

1. **Never modify original MaskCO files under `MASKCO_code/`** — all new code and path adapters belong in `C-VRP_Cold-chainVehicleRoutingProblem/`
2. **No `__init__.py` in CVRPTW subdirectories** — imports via `sys.path.insert` to avoid shadowing parent packages
3. **`--gpu_id` must be parsed before `import jax`** — raw `sys.argv` scan sets `CUDA_VISIBLE_DEVICES`
4. **`tw_max` auto-detected** — `tw_end.max()` in both training and decoding. Must be consistent.
5. **C++ RNG seed** — incrementing per call for diversity across cycles/threads
6. **`encoder_input_dim` must be overridden on model_config before construct_model** — `train_coldchain.py` missed this initially (fixed)
7. **`auto_train.py` uses `executable='/bin/bash'`** — `/bin/sh`=dash doesn't support `source`
8. **Dataloader yields 5-tuple, UNMASKED features** — `ColdChainDataloader` yields `(features, routes, timestep, visible_mask, reveal_time)`. Features are **unmasked**（掩码移到训练器按 vis_k 逐步做，2026-08-27 起，见 §当前状态）。All consumers must unpack 5 values.
9. **Python 3.10 f-string limitation** — f-strings cannot nest same quote type. Use `%` formatting or variables for complex format strings in shell-embedded Python.
10. **Use `coord_normalize_visible`, not `coord_normalize`** — parent project's `coord_normalize` computes statistics over ALL nodes (axis=-2), leaking future coordinates. `cvrptw_utils.coord_normalize_visible()` uses only visible nodes. All training/decoding/simulation must use the visible-aware version.
11. **cost semantics unified (跨方法指标一致性)** — all methods' reported `cost` = **pure travel distance, no penalty**. Infeasibility is reported via separate TW Feas / Cap Feas metrics, never mixed into cost. `_eval_distmat_cost` (final report) is pure distance; `_eval_single_route_cost` (2-opt internal only) has capacity soft-penalty. See `C-VRP_Cold-chainVehicleRoutingProblem/docs/当前规划/实验与评估/评估口径.md` §1.0 and `C-VRP_Cold-chainVehicleRoutingProblem/docs/当前规划/实验与评估/基线对比.md`.

## Key Findings

### What Works
- **Causal Normalization (P0-3a)**: `coord_normalize_visible` → model no longer sees future nodes' coordinate statistics. Cleaner prior → cost -8.8% vs leaky
- **历史 Quality-Aware Beam 观察**：toy/R1/R2 数字来自 C0 前的多套品质口径，只作调试线索；需由唯一 cold-chain trace evaluator 复核后才能形成机制结论。
- **Transferable Representation (支持证据)**: 纯 R1 训练 → zero-shot C1/RC1 零迁移损失（C1 差 0.2%, RC1 差 0.6%）。证明 masked representation 未只记忆单一分布，支持第一贡献（不是论文主题）。
- **C0 唯一温度/品质/能耗状态**：COP、开门热、制冷功率和 Arrhenius 品质统一由版本化 contract 与 `coldchain_state.py` 执行；参数仍为 pilot。
- **Self-Training**: feas +20pp (73→93%), largest single lever. Generate pseudo-labels with best model → fine-tune
- **EDD repair**: viol 9→2 (-77%), highest-leverage single change
- **TW-aware 2opt (C++)**: enables mask-reconstruct iteration, 30,000x speedup
- **Spatio-Temporal masking**: feas +10pp vs random (64→74%), simulates dynamic info scarcity
- **Temperature constraint**: improves TW feas (50→73%), constraint = inductive bias
- **Mixed training (R1+C1+RC1)**: C1 feas 7→63%, essential for generalization
- **Temp Embedding**: clean replacement for harmful spoilage_bias (no performance loss)
- **Visibility-Gated Attention (P0-2)**: `visible_mask` → encoder attn bias `-1e9` for future nodes. Zero parent-project changes. Oracle→Causal gap: **76.6%→51.2% (−25.4pp)** — paper's core evidence: the cost of non-anticipatory decisions.
- **Mixed EDoD Training (方向A)**: R1+C1+RC1 × 0.2+0.5+0.8 joint training → Causal feas **74.7%** (+23.5pp vs single-EDoD 51.2%). EDoD=0.8: **28.8%→99.3%** (3×).
- **8D Quality-Aware (P0-4)**: Adding `quality_loss` as encoder feature → **77.9%** (+3.2pp vs 7D). EDoD=0.5 hardest-case: **54.9%→66.7%** (+11.8pp). Quality signal helps prioritize perishable nodes at medium dynamism.
- **Quality-Aware C++ 2-opt (P0-4)**: `cvrptw_quality_two_opt` with `total = dist + λ_q×quality_loss + λ_e×energy`. Verified λ_q sweep [0,2.0] — reference sol is locally optimal (dist unchanged), enables tradeoff selection during inference.
- **历史 Temperature Trajectory Tracking (P0-4)**：`rolling_horizon.py` 的旧 TTI/energy 数字来自非 C0 代理口径，已显式标记 `legacy`，不得作为当前冷链效果证据。

### P0-2 Results: Causal Dynamic Routing (50K steps, 3 seeds) — OBSOLETE (replaced by P0-3a causal retraining)

These results used leaky `coord_normalize` (full-node statistics). See [Causal v1 Results](#p0-3a-causal-v1-results-2026-08-12) below for corrected numbers.

| Stage | Avg EDoD=0.2 | Avg EDoD=0.5 | Avg EDoD=0.8 | Overall | vs Oracle |
|-------|-------------|-------------|-------------|---------|-----------|
| Oracle (泄漏) | 76.3% | 75.0% | 78.4% | 76.6% | — |
| Single-EDoD | 57.4% | 67.4% | 28.8% | 51.2% | −25.4pp |
| **Mixed-EDoD (7D)** | **69.9%** | 54.9% | **99.3%** | 74.7% | −1.9pp |
| **8D Quality (P0-4)** | 67.5% | **66.7%** | **99.6%** | **77.9%** | **+1.3pp** |

### P0-3a Causal v1 Frozen Results (2026-08-13, 5 train seeds)

**coord_normalize_visible fix** — Phase 3c K=5 online seq + K=16 beam decoder.
5 train seeds (42/123/999/2025/2026), fixed decode seed 42, 8 runs × 40 cycles, TW 2-opt 4 steps.

| Type | EDoD=0.2 | EDoD=0.5 | EDoD=0.8 | Avg |
|------|------|------|------|:---:|
| R1 | 17.12 ± 0.06 (100%) | 17.40 ± 0.05 (100%) | 17.95 ± 0.06 (100%) | 17.49 |
| C1 | 11.51 ± 0.06 (100%) | 11.80 ± 0.06 (100%) | 12.15 ± 0.05 (100%) | 11.82 |
| RC1 | 14.67 ± 0.04 (100%) | 14.95 ± 0.06 (100%) | 15.41 ± 0.06 (100%) | 15.01 |
| **Avg** | **14.43** | **14.72** | **15.17** | **14.77** |

**45/45 = 100% feasible, 0 violations.** All std ≤ 0.06 — highly stable across training seeds.

vs OR-Tools Clairvoyant (R1 EDoD=0.5): J*=9.1 → **Clairvoyance Gap = 8.30 (91%)**.

vs old leaky model (Phase 3c beam, same decode config): 16.23 → **causal is 8.8% cheaper**.
Full-node normalization was noise, not useful signal.

**Checkpoints**: `ckpts/p0_fix/causal_v1/step50000.ckpt` (ST-mask, 814s) ·
`ckpts/p0_fix/causal_v1/phase3c/step50000.ckpt` (K=5 online seq, ~56min)
**5-seed Phase3c**: `ckpts/p0_fix/frozen_v1/phase3c/seed{42,123,999,2025,2026}/step50000.ckpt`
**Results CSV**: `logs/p0_fix/frozen_v1/results/full_matrix.csv`

### What Doesn't Work
- **spoilage_bias (Arrhenius)**: -6pp feas, replaced by Temp Embedding
- **TW attention bias**: conflicts with preserving 2opt → numerical overflow
- **TW penalty loss**: training labels already TW-feasible, CE loss implicitly covers
- **LKH3 labels**: can't find feasible solutions for narrow-TW (R1) instances
- **Predictive masking (0.65x keep)**: too aggressive, worse than ST-mask (0.8x)
- **coord_normalize (parent project)**: computes statistics over ALL nodes → leaks future coordinate distribution into visible encodings. Fixed with `cvrptw_utils.coord_normalize_visible()`.
- **PyVRP 0.11**: solver works on 3-node but fails on 25+ node in server env (`.distance()` returns garbage). OR-Tools 9.8 used instead.
- **"Causal > Oracle" claim**: was an artifact of leaky normalize comparing against itself. Retracted.

### EDoD Sensitivity (DCC, 9 groups, Causal P0-2)
- Causal feas drops 25pp vs Oracle (76.6%→51.6%) — quantifies the cost of non-anticipatory decisions
- Non-monotonic: medium dynamic (0.5) is hardest, strong dynamic (0.8) recovers partially
- C1 most robust: clustered data provides spatial prior even with masked nodes (81.0% at EDoD=0.5)
- EDoD distribution mismatch is critical: model trained at 0.5 → cross-EDoD generalization needs mixed training

## Experiment Records

`C-VRP_Cold-chainVehicleRoutingProblem/docs/实验记录/`:
- `01_决策记录.md` — D-001 through D-031 (K-beam, PyVRP, 100-node)
- `阶段二/PhaseE_P0修复.md` — Phase A→E + Phase 2/3/4 完整实验记录
- `阶段二/00_阶段二总结.md` — 方向一~四实验记录 + EDoD全矩阵

`C-VRP_Cold-chainVehicleRoutingProblem/docs/调研/GPT/`:
- `执行方案.md` — **总执行方案（汇总 + 导航）**，详细见 v3
- `v2/第二阶段详细优化方案.md` — Phase 3/4 全部完成, 36/36 feasible, W10 通过
- `v3/执行方案_v3.md` — v3 详细执行方案（协议审计 + 理论化，已完成）
- `v3/P1_理论形式化.md` — **P1 方法形式化：3 命题 + 1 定理（含证明）**
- `v3/深度研究报告.md` — v3 深度诊断报告
- `v4/执行方案_v4.md` — v4 证据链加固（发现 OR-Tools-RH 全面优于）
- `v4/竞争力诚实评估与重新定位.md` — **诚实评估 + 重新定位**
- `v5/执行方案_v5.md` — v5 重新定位（历史）：冷链多资源 + 可迁移表示（已被 8-19 三层贡献定位取代）
- `v5/冷链参数标定清单.md` — 冷链参数标定（文献/关键词，方向三+四准备）
- `v5/模型改进计划.md` — 基于 29 篇论文的模型改进方向（5 类）

`C-VRP_Cold-chainVehicleRoutingProblem/archive/docs/旧版总览/v1/`（2026-08-21 整理为 1 导航 + 5 内容）:
- `总索引.md` — 论文写作导航（文件清单 + 核心数字速查 + 复现命令 + v6 进展）
- `评估口径.md` — 评估协议（KPI 公式 + 统计规范 + §1.0 cost 语义统一声明）
- `基线对比.md` — 跨方法指标对比（obj/gap/time vs feas/cost/clairvoyance gap）
- `实验细节.md` — 完整公式 + 模型架构 + 实验配置
- `理论形式化.md` — 3 命题 + 1 定理（非预知/前缀/可行性/anytime）
- `完整代码归档.txt` — 全部源文件当前内容归档（77 文件，2026-08-19）
> 权威结果表 → `docs/实验记录/实验结果总表.md`（不在 ALL，已移除过时的 results.json/dashboard/html）

`C-VRP_Cold-chainVehicleRoutingProblem/docs/`:
- `项目当前状态.md` — 当前状态、权威入口与下一步
- `实验记录/实验结果总表.md` — **权威结果表（旧 14.77 作废，现以 strict-online VAL128 为准）**

## 历史推进记录：修监督 → JF2 → HFR-M0（F3）→ Cost-Aware Preference

> 本节是 2026-09-01 的历史快照，其中“待办”已被 2026-09-02 完成的 P0-R/P0-S/P0-A/P0-U 取代。当前下一步只看文件顶部的唯一状态入口。

**历史状态（2026-09-01）**：R0 协议修复 ✅ → R1/R1.5/R1.7/B0/JF1 ✅ → JF2（exact-vehicle CE）No-Go ✅ → HFR-M0 Gate A FAIL。严格解释是 structural signal 可学但未建立相对 JF1-H 的 downstream utility。

**顺序**：
1. **R0/R1/R1.5-M/R1.7/B0/JF1** ✅（fleet allocation 主导 + joint topology −11.4%）
2. **JF2（exact-vehicle Fleet Head）** ✅ No-Go（M0-v2 25.91 vs 24.50 FAIL）
3. **HFR-M0（Hierarchical Fleet–Route）** ✅ 实现完成 + Gate A FAIL/F3（G 有 partition 价值、route 信号有害）
4. **历史计划：Cost-Aware probe**（v4 中降为 M0 表征探针；最终方法改为 DynMaskCO-CC masked recourse）

**待办**：
- [ ] 构造 cost-aware joint-action dataset（`(state, customer, slot, insertion_pos, continuation_cost, regret)` → pairwise preference）
- [ ] 最小 Preference-M0（frozen encoder + Utility Preference Head + pairwise logistic loss），Gate：`CostAware-M0 < JF1-H`（100% service）
- [ ] 和导师决定 Go/No-Go（2026-10-01）

**Server run (P0 protocol audit)**:
```bash
# P0-2 Baseline audit (OR-Tools + PyVRP Solomon sanity)
bash "C-VRP_Cold-chainVehicleRoutingProblem/scripts/run_baseline_audit.sh" smoke   # or full

# P0-3a Cardinality / identity leakage
python -u "C-VRP_Cold-chainVehicleRoutingProblem/scripts/tests/test_future_cardinality.py" \
    --data "C-VRP_Cold-chainVehicleRoutingProblem/data/p0_fix/dcc_50_r1_edod05_test.npz" \
    --ckpt "C-VRP_Cold-chainVehicleRoutingProblem/ckpts/p0_fix/causal_v1/phase3c/step50000.ckpt"

# P0-3b Target-label leakage
python -u "C-VRP_Cold-chainVehicleRoutingProblem/scripts/tests/test_target_label_leakage.py" \
    --data "C-VRP_Cold-chainVehicleRoutingProblem/data/p0_fix/dcc_50_mixed_edod_train.npz" \
    --ckpt "C-VRP_Cold-chainVehicleRoutingProblem/ckpts/p0_fix/causal_v1/phase3c/step50000.ckpt"
```

**新实验脚本（2026-08-19 新增）**：
```bash
bash "C-VRP_Cold-chainVehicleRoutingProblem/scripts/run_core_ablation.sh" r1|c1|rc1  # 核心演化消融
bash "C-VRP_Cold-chainVehicleRoutingProblem/scripts/run_c2_sensitivity.sh"            # C2/R2 宽 TW sensitivity
bash "C-VRP_Cold-chainVehicleRoutingProblem/scripts/run_cross_scale.sh"               # 50→100-node scale transfer
bash "C-VRP_Cold-chainVehicleRoutingProblem/scripts/run_typed_retrain.sh" full        # typed embedding 5-seed 重训（USE_EDGE=1 边特征）
bash "C-VRP_Cold-chainVehicleRoutingProblem/scripts/run_lambda_q_sweep.sh"            # 品质感知权重扫描
python "C-VRP_Cold-chainVehicleRoutingProblem/scripts/analysis/toy_instance_test.py"  # ③ toy 因果验证
python "C-VRP_Cold-chainVehicleRoutingProblem/scripts/analysis/mechanism_analysis.py" # ② 机制验证
python "C-VRP_Cold-chainVehicleRoutingProblem/scripts/analysis/route_changing.py"     # ① route-changing
python "C-VRP_Cold-chainVehicleRoutingProblem/scripts/baselines/ortools_weighted_completion.py"  # ④ matched-OR
```

## Phase 2: Dynamic-Aware MaskCO (2026-08-06)

Six directions in `decoding/maskco_dynamic.py` (now superseded by Phase 3 beam decoder):

| # | Direction | Status |
|:---:|------|:---:|
| D1 | Event-aware Masking | ✅ |
| D2 | Frozen Prefix | ✅ |
| D3 | Constraint-aware Decoder | ✅ (superseded by resource beam) |
| D4 | Adaptive Mask Ratio | ✅ |
| D5 | Online Seq Training | ✅ (= Phase 3c) |
| D6 | Anytime Solver | ✅ |

Paper positioning: **"Adaptive Masked Generation for Online Vehicle Routing"** — Cold Chain as application, not title.

## Phase 3: K-Beam Resource-State Decoder (2026-08-07, Complete)

Milestone: **model_only 0% → K-beam 100% feasible** (first time a neural solver hits 100% on narrow-TW). Evolution:

- **3a** K-beam resource-state decoder (each beam tracks time+load+visited; first model_only >0%)
- **3b** REINFORCE mask policy (honest ablation, zero signal)
- **3c** K=5 online seq training (only method that reduces beam cost, −3.8%)
- **3d** Endogenous thermal physics (Newton cooling + refrigeration + door shock + Arrhenius)

**100-node scale**: 9/9 feasible, sub-linear cost growth (+89% for 2× nodes). C1 maintains best cost.

⚠️ The 50-node "16.23" figure from this phase was the **leaky model** — superseded by causal v1 (14.77, see Key Findings §P0-3a).

## Phase 4: Four-Direction Polish (2026-08-08~09, Complete)

| Direction | Result |
|:---:|------|
| 1 Thermal-beam | Dist −29%, Viol −68% |
| 2 Beam+2opt | 100% feas, cost −0.3% (beam already near-optimal) |
| 3 100-node scale | 9/9 feasible (R1 39.37, C1 21.93, RC1 32.01) |
| 4 Baseline audit | ⚠️ PyVRP "0% feasible" was a server env bug (P0-2); OR-Tools solves J*=9.1 |

---

# 附录 C — 工作区导航（原 `工作区导航.md`，逐字保留）

# MASKCO-Main 工作区导航

> 最后更新：2026-09-03

本目录是一个组合工作区，而不是单一代码包：

| 区域 | 职责 | 整理规则 |
|---|---|---|
| [`MASKCO_code/`](MASKCO_code/) | TSP/CVRP/MIS 上游实现 | 保持源码不变；扩展侧只通过路径接入 |
| [`C-VRP_Cold-chainVehicleRoutingProblem/`](C-VRP_Cold-chainVehicleRoutingProblem/) | DynMaskCO 主研发工作区 | 当前主要工作区域 |
| [`CC_Compare/`](CC_Compare/) | learned baselines 复现与适配 | 只修改各方法的 `dcc_vrp/` 适配层 |
| `MASKCO_code/workspace_assets/` | 下载归档和非源码辅助文件 | 不参与训练与评估 |

DynMaskCO 的唯一当前状态入口是 [`C-VRP_Cold-chainVehicleRoutingProblem/项目当前状态.md`](C-VRP_Cold-chainVehicleRoutingProblem/项目当前状态.md)。

当前论文主线固定为：**基于 MaskCO 的掩码生成与迭代重构范式，构建面向动态冷链物流的在线优化方法**。Cost-aware preference 仅是内部效用对齐模块；主实验采用 dynamic cold-chain pickup-to-depot。

P0-M 目录迁移兼容门与 C0 cargo manifest/冷链状态/trace evaluator 闭环均已完成。当前按计划进入 O0-D 距离 oracle sanity，随后再做 O0-CC；所有扩展入口继续统一使用 `scripts/project_paths.py`。

目录整理清单保存在 `C-VRP_Cold-chainVehicleRoutingProblem/archive/目录整理记录/2026-09-02/`；论文主线修正记录保存在 [论文主线修正报告.md](C-VRP_Cold-chainVehicleRoutingProblem/archive/目录整理记录/2026-09-03/论文主线修正报告.md)。

---

# 附录 D — 原始证据归档清单（原 `EVIDENCE_MANIFEST.md`，逐字保留）

# Raw evidence archive

| item | value |
|---|---|
| download | https://github.com/GoodThing001/DynMaskCO/releases/download/evidence-2026-10-13/DynMaskCO_raw_evidence.tar.gz |
| release page | https://github.com/GoodThing001/DynMaskCO/releases/tag/evidence-2026-10-13 |
| size | 405.9 MiB (425648120 bytes) |
| raw before compression | 5319.7 MiB |
| sha256 | `e994bab551884ed3e65b1f744e0874f53b3ffd7f993b751a4dca4f4a45836e05` |
| files | 474 |

## Contents

| path | MB |
|---|---|
| `research/review_3080_20261010/delivery/action_head_execution_chain_preparation_root_v1/INPUTS.json` | 2.01 |
| `research/review_3080_20261010/delivery/action_head_independent_replay_preparation_root_v1/INPUTS.json` | 2.01 |
| `research/review_3080_20261010/delivery/action_tensor_binding_root_v2/INDEPENDENT_ACTION_TENSOR_BINDING.json` | 1.22 |
| `research/review_3080_20261010/delivery/actual_action_head_execution_root_v1/INPUTS.json` | 2.01 |
| `research/review_3080_20261010/delivery/actual_action_head_execution_root_v1/downloaded/AUDIT_SOURCE_END.json` | 1.56 |
| `research/review_3080_20261010/delivery/actual_action_head_execution_root_v1/downloaded/AUDIT_SOURCE_START.json` | 1.56 |
| `research/review_3080_20261010/delivery/actual_action_head_execution_root_v1/downloaded/INDEPENDENT_ACTION_HEAD_AUDIT.json` | 5.21 |
| `research/review_3080_20261010/delivery/actual_action_head_execution_root_v1/downloaded/INPUTS.json` | 2.01 |
| `research/review_3080_20261010/delivery/actual_action_head_execution_root_v1/downloaded/SOURCE_END.json` | 1.55 |
| `research/review_3080_20261010/delivery/actual_action_head_execution_root_v1/downloaded/SOURCE_START.json` | 1.55 |
| `research/review_3080_20261010/delivery/actual_score_chain_execution_root_v1/downloaded/AUDIT_SOURCE_END.json` | 1.57 |
| `research/review_3080_20261010/delivery/actual_score_chain_execution_root_v1/downloaded/AUDIT_SOURCE_START.json` | 1.57 |
| `research/review_3080_20261010/delivery/actual_score_chain_execution_root_v1/downloaded/INDEPENDENT_SCORE_CHAIN_AUDIT.json` | 1.56 |
| `research/review_3080_20261010/delivery/actual_score_chain_execution_root_v1/downloaded/SOURCE_END.json` | 1.55 |
| `research/review_3080_20261010/delivery/actual_score_chain_execution_root_v1/downloaded/SOURCE_START.json` | 1.55 |
| `research/review_3080_20261010/delivery/compiled_head_identity_root_v1/COMPACT_INSPECTION_20261013T020553063648Z.json` | 1.40 |
| `research/review_3080_20261010/delivery/compiled_head_identity_root_v1/DOWNLOAD_PREFLIGHT_20261013T020607303297Z.json` | 1.40 |
| `research/review_3080_20261010/delivery/compiled_head_identity_root_v1/downloaded/INDEPENDENT_TIMED_REQUEST_AUDIT.json` | 1.40 |
| `research/review_3080_20261010/delivery/compiled_head_identity_root_v1/downloaded/SOURCE_END.json` | 1.54 |
| `research/review_3080_20261010/delivery/compiled_head_identity_root_v1/downloaded/SOURCE_START.json` | 1.54 |
| `research/review_3080_20261010/delivery/compiled_head_identity_root_v1/downloaded/TIMED_AUDIT_SOURCE_END.json` | 1.53 |
| `research/review_3080_20261010/delivery/compiled_head_identity_root_v1/downloaded/TIMED_AUDIT_SOURCE_START.json` | 1.47 |
| `research/review_3080_20261010/delivery/directed_action_chain_root_v1/ACTION_CHAINS.jsonl` | 21.27 |
| `research/review_3080_20261010/delivery/family2_orientation_action_diagnosis_root_v1/OBSERVED_PAIRS.json` | 1.43 |
| `research/review_3080_20261010/delivery/family2_remaining_action_diagnosis_root_v1/OBSERVED_ACTION_RECORDS.json` | 4.63 |
| `research/review_3080_20261010/delivery/finite_training_preparation_v1/ENGINEERING_TEACHER_QA_v1/TEACHER_STATES.jsonl` | 1.23 |
| `research/review_3080_20261010/delivery/head_intermediate_arithmetic_root_v1/DOWNLOAD_PREFLIGHT_20261013T022558641250Z.json` | 1.51 |
| `research/review_3080_20261010/delivery/head_intermediate_arithmetic_root_v1/INSPECTION_20261013T022527063776Z.json` | 1.51 |
| `research/review_3080_20261010/delivery/head_intermediate_arithmetic_root_v1/downloaded/AUDIT_SOURCE_END.json` | 1.50 |
| `research/review_3080_20261010/delivery/head_intermediate_arithmetic_root_v1/downloaded/AUDIT_SOURCE_START.json` | 1.50 |
| `research/review_3080_20261010/delivery/head_intermediate_arithmetic_root_v1/downloaded/INDEPENDENT_ARITHMETIC_AUDIT.json` | 1.57 |
| `research/review_3080_20261010/delivery/head_intermediate_arithmetic_root_v1/downloaded/SOURCE_END.json` | 1.53 |
| `research/review_3080_20261010/delivery/head_intermediate_arithmetic_root_v1/downloaded/SOURCE_START.json` | 1.53 |
| `research/review_3080_20261010/delivery/insertable_teacher_engineering_root_v3/RESULT.json` | 41.86 |
| `research/review_3080_20261010/delivery/loaded_identity_guard_boundary_root_v1/DOWNLOAD_PREFLIGHT_20261013T054457112620Z.json` | 19.04 |
| `research/review_3080_20261010/delivery/loaded_identity_guard_boundary_root_v1/INSPECTION_20261013T054421665681Z.json` | 19.04 |
| `research/review_3080_20261010/delivery/loaded_identity_guard_boundary_root_v1/downloaded/01_normal.json` | 2.31 |
| `research/review_3080_20261010/delivery/loaded_identity_guard_boundary_root_v1/downloaded/02_new_presealed_module.json` | 2.31 |
| `research/review_3080_20261010/delivery/loaded_identity_guard_boundary_root_v1/downloaded/03_origin_rebound.json` | 2.31 |
| `research/review_3080_20261010/delivery/loaded_identity_guard_boundary_root_v1/downloaded/04_parameter_rebound.json` | 2.31 |
| `research/review_3080_20261010/delivery/loaded_identity_guard_boundary_root_v1/downloaded/05_unsealed_module.json` | 2.31 |
| `research/review_3080_20261010/delivery/loaded_identity_guard_boundary_root_v1/downloaded/06_loaded_byte_changed.json` | 2.31 |
| `research/review_3080_20261010/delivery/loaded_identity_guard_boundary_root_v1/downloaded/07_unloaded_tree_changed.json` | 2.31 |
| `research/review_3080_20261010/delivery/loaded_identity_guard_boundary_root_v1/downloaded/08_actual_native_load.json` | 2.31 |
| `research/review_3080_20261010/delivery/loaded_identity_guard_boundary_root_v1/downloaded/AUDIT_SOURCE_END.json` | 1.55 |
| `research/review_3080_20261010/delivery/loaded_identity_guard_boundary_root_v1/downloaded/AUDIT_SOURCE_START.json` | 1.55 |
| `research/review_3080_20261010/delivery/loaded_identity_guard_boundary_root_v1/downloaded/INDEPENDENT_LOADED_GUARD_AUDIT.json` | 19.36 |
| `research/review_3080_20261010/delivery/loaded_identity_guard_boundary_root_v1/downloaded/SOURCE_END.json` | 1.55 |
| `research/review_3080_20261010/delivery/loaded_identity_guard_boundary_root_v1/downloaded/SOURCE_START.json` | 1.55 |
| `research/review_3080_20261010/delivery/multistep_full_gradient_audit_root_v1/downloaded/INDEPENDENT_FULL_GRADIENT_ADJUDICATION.json` | 2.91 |
| `research/review_3080_20261010/delivery/multistep_full_gradient_root_v2/STATES.jsonl` | 44.11 |
| `research/review_3080_20261010/delivery/multistep_full_gradient_root_v2/downloaded/FULL_SOURCE_END.json` | 1.44 |
| `research/review_3080_20261010/delivery/multistep_full_gradient_root_v2/downloaded/FULL_SOURCE_START.json` | 1.49 |
| `research/review_3080_20261010/delivery/multistep_full_gradient_root_v2/downloaded/MATCHED_TENSORS.json` | 3.04 |
| `research/review_3080_20261010/delivery/multistep_insertable_family2_data_audit_root_v1/downloaded/AUDIT_SOURCE_START.json` | 1.42 |
| `research/review_3080_20261010/delivery/multistep_insertable_family2_data_audit_root_v2/inspection_20261011T111137553714Z/AUDIT_SOURCE_END.json` | 1.42 |
| `research/review_3080_20261010/delivery/multistep_insertable_family2_data_audit_root_v2/inspection_20261011T111137553714Z/AUDIT_SOURCE_START.json` | 1.42 |
| `research/review_3080_20261010/delivery/multistep_insertable_family2_data_audit_root_v2/inspection_20261011T111137553714Z/INDEPENDENT_FAMILY2_DATA_ACCEPTANCE.json` | 9.69 |
| `research/review_3080_20261010/delivery/multistep_insertable_family2_root_v1/QUALIFIED_SERVER_REFERENCE.json` | 1.42 |
| `research/review_3080_20261010/delivery/multistep_insertable_family2_root_v1/downloaded/QUALIFIED_SERVER_REFERENCE.json` | 1.42 |
| `research/review_3080_20261010/delivery/multistep_insertable_family2_root_v1/downloaded/REQUESTS_STARTED.jsonl` | 1.01 |
| `research/review_3080_20261010/delivery/multistep_insertable_family2_root_v1/downloaded/RESULT.json` | 1.49 |
| `research/review_3080_20261010/delivery/multistep_insertable_family2_root_v1/downloaded/SOURCE_END.json` | 1.42 |
| `research/review_3080_20261010/delivery/multistep_insertable_family2_root_v1/downloaded/SOURCE_START.json` | 1.42 |
| `research/review_3080_20261010/delivery/multistep_insertable_family2_root_v1/downloaded/STATES.jsonl` | 1190.12 |
| `research/review_3080_20261010/delivery/multistep_insertable_family2_root_v1/inspection_20261011T104503732008Z/SOURCE_START.json` | 1.42 |
| `research/review_3080_20261010/delivery/multistep_insertable_family2_root_v1/inspection_20261011T105259376215Z/SOURCE_START.json` | 1.42 |
| `research/review_3080_20261010/delivery/multistep_insertable_family2_root_v1/inspection_20261011T105627776426Z/SOURCE_START.json` | 1.42 |
| `research/review_3080_20261010/delivery/multistep_insertable_family2_root_v1/inspection_20261011T105835079417Z/RESULT.json` | 1.49 |
| `research/review_3080_20261010/delivery/multistep_insertable_family2_root_v1/inspection_20261011T105835079417Z/SOURCE_END.json` | 1.42 |
| `research/review_3080_20261010/delivery/multistep_insertable_family2_root_v1/inspection_20261011T105835079417Z/SOURCE_START.json` | 1.42 |
| `research/review_3080_20261010/delivery/multistep_insertable_teacher_engineering_root_v1/STATES.jsonl` | 43.29 |
| `research/review_3080_20261010/delivery/multistep_insertable_teacher_engineering_root_v2/STATES.jsonl` | 44.11 |
| `research/review_3080_20261010/delivery/multistep_optimizer_audit_root_v2/downloaded/AUDIT_SOURCE_END.json` | 1.44 |
| `research/review_3080_20261010/delivery/multistep_optimizer_audit_root_v2/downloaded/AUDIT_SOURCE_START.json` | 1.44 |
| `research/review_3080_20261010/delivery/multistep_optimizer_audit_root_v2/downloaded/INDEPENDENT_OPTIMIZER_ADJUDICATION.json` | 3.55 |
| `research/review_3080_20261010/delivery/multistep_optimizer_root_v1/downloaded/TRAINING_SOURCE_END.json` | 1.44 |
| `research/review_3080_20261010/delivery/multistep_optimizer_root_v1/downloaded/TRAINING_SOURCE_START.json` | 1.44 |
| `research/review_3080_20261010/delivery/parallel_identity_collection_root_v1/DOWNLOAD_PREFLIGHT_20261013T051911581410Z.json` | 4.19 |
| `research/review_3080_20261010/delivery/parallel_identity_collection_root_v1/INSPECTION_20261013T051855645441Z.json` | 4.19 |
| `research/review_3080_20261010/delivery/parallel_identity_collection_root_v1/downloaded/AUDIT_SOURCE_END.json` | 1.55 |
| `research/review_3080_20261010/delivery/parallel_identity_collection_root_v1/downloaded/AUDIT_SOURCE_START.json` | 1.55 |
| `research/review_3080_20261010/delivery/parallel_identity_collection_root_v1/downloaded/INDEPENDENT_IDENTITY_AUDIT.json` | 4.27 |
| `research/review_3080_20261010/delivery/parallel_identity_collection_root_v1/downloaded/PARALLEL_SOURCE_COLLECTION.json` | 1.55 |
| `research/review_3080_20261010/delivery/parallel_identity_collection_root_v1/downloaded/SEQUENTIAL_REFERENCE_COLLECTION.json` | 1.55 |
| `research/review_3080_20261010/delivery/parallel_identity_collection_root_v1/downloaded/SOURCE_END.json` | 1.55 |
| `research/review_3080_20261010/delivery/parallel_identity_collection_root_v1/downloaded/SOURCE_START.json` | 1.55 |
| `research/review_3080_20261010/delivery/phase_timed_model_execution_root_v1/downloaded/TIMED_AUDIT_SOURCE_END.json` | 1.57 |
| `research/review_3080_20261010/delivery/phase_timed_model_execution_root_v1/downloaded/TIMED_AUDIT_SOURCE_START.json` | 1.57 |
| `research/review_3080_20261010/delivery/phase_timed_model_execution_root_v1/downloaded/pretrained_initial_fault0_worker/SOURCE_START.json` | 1.55 |
| `research/review_3080_20261010/delivery/phase_timed_model_execution_root_v1/downloaded/random888_initial_fault0_worker/SOURCE_START.json` | 1.55 |
| `research/review_3080_20261010/delivery/primitive_schedule_semantics_root_v1/DOWNLOAD_PREFLIGHT_20261013T024822347255Z.json` | 1.40 |
| `research/review_3080_20261010/delivery/primitive_schedule_semantics_root_v1/INSPECTION_20261013T024808228632Z.json` | 1.40 |
| `research/review_3080_20261010/delivery/primitive_schedule_semantics_root_v1/downloaded/AUDIT_SOURCE_END.json` | 1.53 |
| `research/review_3080_20261010/delivery/primitive_schedule_semantics_root_v1/downloaded/AUDIT_SOURCE_START.json` | 1.53 |
| `research/review_3080_20261010/delivery/primitive_schedule_semantics_root_v1/downloaded/INDEPENDENT_SEMANTICS_AUDIT.json` | 1.41 |
| `research/review_3080_20261010/delivery/primitive_schedule_semantics_root_v1/downloaded/SOURCE_END.json` | 1.53 |
| `research/review_3080_20261010/delivery/primitive_schedule_semantics_root_v1/downloaded/SOURCE_START.json` | 1.53 |
| `research/review_3080_20261010/delivery/remote_final_model_budget_bundle_root_v2/downloaded/RESULT.json` | 14.33 |
| `research/review_3080_20261010/delivery/remote_final_model_budget_bundle_root_v2/downloaded/discard_900000.json` | 1.04 |
| `research/review_3080_20261010/delivery/remote_final_model_budget_bundle_root_v2/downloaded/discard_900001.json` | 1.04 |
| `research/review_3080_20261010/delivery/remote_final_model_budget_bundle_root_v2/downloaded/nonlearning_900000.json` | 1.04 |
| `research/review_3080_20261010/delivery/remote_final_model_budget_bundle_root_v2/downloaded/nonlearning_900001.json` | 1.04 |
| `research/review_3080_20261010/delivery/remote_final_model_budget_bundle_root_v2/downloaded/paired_objective_900000.json` | 1.03 |
| `research/review_3080_20261010/delivery/remote_final_model_budget_bundle_root_v2/downloaded/paired_objective_900001.json` | 1.05 |
| `research/review_3080_20261010/delivery/remote_final_model_budget_bundle_root_v2/downloaded/pretrained_900000.json` | 1.04 |
| `research/review_3080_20261010/delivery/remote_final_model_budget_bundle_root_v2/downloaded/pretrained_900001.json` | 1.04 |
| `research/review_3080_20261010/delivery/remote_final_model_budget_bundle_root_v2/downloaded/random_900000.json` | 1.03 |
| `research/review_3080_20261010/delivery/remote_final_model_budget_bundle_root_v2/downloaded/random_900001.json` | 1.04 |
| `research/review_3080_20261010/delivery/remote_final_model_budget_bundle_root_v2/downloaded/reconstruction_control_900000.json` | 1.03 |
| `research/review_3080_20261010/delivery/remote_final_model_budget_bundle_root_v2/downloaded/reconstruction_control_900001.json` | 1.05 |
| `research/review_3080_20261010/delivery/remote_final_model_budget_bundle_root_v3/downloaded/RESULT.json` | 14.34 |
| `research/review_3080_20261010/delivery/remote_final_model_budget_bundle_root_v3/downloaded/discard_900000.json` | 1.04 |
| `research/review_3080_20261010/delivery/remote_final_model_budget_bundle_root_v3/downloaded/discard_900001.json` | 1.04 |
| `research/review_3080_20261010/delivery/remote_final_model_budget_bundle_root_v3/downloaded/nonlearning_900000.json` | 1.04 |
| `research/review_3080_20261010/delivery/remote_final_model_budget_bundle_root_v3/downloaded/nonlearning_900001.json` | 1.04 |
| `research/review_3080_20261010/delivery/remote_final_model_budget_bundle_root_v3/downloaded/paired_objective_900000.json` | 1.03 |
| `research/review_3080_20261010/delivery/remote_final_model_budget_bundle_root_v3/downloaded/paired_objective_900001.json` | 1.05 |
| `research/review_3080_20261010/delivery/remote_final_model_budget_bundle_root_v3/downloaded/pretrained_900000.json` | 1.04 |
| `research/review_3080_20261010/delivery/remote_final_model_budget_bundle_root_v3/downloaded/pretrained_900001.json` | 1.04 |
| `research/review_3080_20261010/delivery/remote_final_model_budget_bundle_root_v3/downloaded/random_900000.json` | 1.03 |
| `research/review_3080_20261010/delivery/remote_final_model_budget_bundle_root_v3/downloaded/random_900001.json` | 1.04 |
| `research/review_3080_20261010/delivery/remote_final_model_budget_bundle_root_v3/downloaded/reconstruction_control_900000.json` | 1.03 |
| `research/review_3080_20261010/delivery/remote_final_model_budget_bundle_root_v3/downloaded/reconstruction_control_900001.json` | 1.05 |
| `research/review_3080_20261010/delivery/remote_finite_research_root_v2/teacher_downloaded/TEACHER_STATES.jsonl` | 39.46 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/RESULT.json` | 107.59 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/nonlearning_0.json` | 1.18 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/nonlearning_1.json` | 1.15 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/nonlearning_10.json` | 1.12 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/nonlearning_11.json` | 1.14 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/nonlearning_12.json` | 1.15 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/nonlearning_13.json` | 1.15 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/nonlearning_14.json` | 1.17 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/nonlearning_15.json` | 1.16 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/nonlearning_2.json` | 1.13 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/nonlearning_3.json` | 1.18 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/nonlearning_4.json` | 1.16 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/nonlearning_5.json` | 1.15 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/nonlearning_6.json` | 1.15 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/nonlearning_7.json` | 1.14 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/nonlearning_8.json` | 1.14 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/nonlearning_9.json` | 1.14 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/paired_objective_0.json` | 1.14 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/paired_objective_1.json` | 1.12 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/paired_objective_10.json` | 1.17 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/paired_objective_11.json` | 1.16 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/paired_objective_12.json` | 1.16 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/paired_objective_13.json` | 1.14 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/paired_objective_14.json` | 1.15 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/paired_objective_15.json` | 1.14 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/paired_objective_2.json` | 1.14 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/paired_objective_3.json` | 1.18 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/paired_objective_4.json` | 1.19 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/paired_objective_5.json` | 1.15 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/paired_objective_6.json` | 1.15 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/paired_objective_7.json` | 1.15 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/paired_objective_8.json` | 1.11 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/paired_objective_9.json` | 1.17 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/pretrained_0.json` | 1.16 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/pretrained_1.json` | 1.16 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/pretrained_10.json` | 1.14 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/pretrained_11.json` | 1.16 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/pretrained_12.json` | 1.12 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/pretrained_13.json` | 1.12 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/pretrained_14.json` | 1.14 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/pretrained_15.json` | 1.17 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/pretrained_2.json` | 1.16 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/pretrained_3.json` | 1.18 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/pretrained_4.json` | 1.15 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/pretrained_5.json` | 1.16 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/pretrained_6.json` | 1.14 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/pretrained_7.json` | 1.14 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/pretrained_8.json` | 1.14 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/pretrained_9.json` | 1.14 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/random_0.json` | 1.12 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/random_1.json` | 1.14 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/random_10.json` | 1.14 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/random_11.json` | 1.14 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/random_12.json` | 1.15 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/random_13.json` | 1.14 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/random_14.json` | 1.17 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/random_15.json` | 1.17 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/random_2.json` | 1.15 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/random_3.json` | 1.18 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/random_4.json` | 1.16 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/random_5.json` | 1.15 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/random_6.json` | 1.14 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/random_7.json` | 1.14 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/random_8.json` | 1.12 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/random_9.json` | 1.14 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/reconstruction_control_0.json` | 1.16 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/reconstruction_control_1.json` | 1.15 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/reconstruction_control_10.json` | 1.14 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/reconstruction_control_11.json` | 1.15 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/reconstruction_control_12.json` | 1.15 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/reconstruction_control_13.json` | 1.14 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/reconstruction_control_14.json` | 1.14 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/reconstruction_control_15.json` | 1.14 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/reconstruction_control_2.json` | 1.12 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/reconstruction_control_3.json` | 1.16 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/reconstruction_control_4.json` | 1.16 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/reconstruction_control_5.json` | 1.14 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/reconstruction_control_6.json` | 1.17 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/reconstruction_control_7.json` | 1.13 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/reconstruction_control_8.json` | 1.14 |
| `research/review_3080_20261010/delivery/remote_fresh_development_root_v1/downloaded/reconstruction_control_9.json` | 1.11 |
| `research/review_3080_20261010/delivery/remote_model_budget_bundle_root_v1/downloaded/RESULT.json` | 14.33 |
| `research/review_3080_20261010/delivery/remote_model_budget_bundle_root_v1/downloaded/discard_900000.json` | 1.04 |
| `research/review_3080_20261010/delivery/remote_model_budget_bundle_root_v1/downloaded/discard_900001.json` | 1.04 |
| `research/review_3080_20261010/delivery/remote_model_budget_bundle_root_v1/downloaded/nonlearning_900000.json` | 1.04 |
| `research/review_3080_20261010/delivery/remote_model_budget_bundle_root_v1/downloaded/nonlearning_900001.json` | 1.04 |
| `research/review_3080_20261010/delivery/remote_model_budget_bundle_root_v1/downloaded/paired_objective_900000.json` | 1.04 |
| `research/review_3080_20261010/delivery/remote_model_budget_bundle_root_v1/downloaded/paired_objective_900001.json` | 1.04 |
| `research/review_3080_20261010/delivery/remote_model_budget_bundle_root_v1/downloaded/pretrained_900000.json` | 1.04 |
| `research/review_3080_20261010/delivery/remote_model_budget_bundle_root_v1/downloaded/pretrained_900001.json` | 1.04 |
| `research/review_3080_20261010/delivery/remote_model_budget_bundle_root_v1/downloaded/random_900000.json` | 1.03 |
| `research/review_3080_20261010/delivery/remote_model_budget_bundle_root_v1/downloaded/random_900001.json` | 1.04 |
| `research/review_3080_20261010/delivery/remote_model_budget_bundle_root_v1/downloaded/reconstruction_control_900000.json` | 1.04 |
| `research/review_3080_20261010/delivery/remote_model_budget_bundle_root_v1/downloaded/reconstruction_control_900001.json` | 1.04 |
| `research/review_3080_20261010/delivery/retained_edge_teacher_engineering_root_v2/RESULT.json` | 36.92 |
| `research/review_3080_20261010/delivery/score_split_timed_execution_root_v1/downloaded/TIMED_AUDIT_SOURCE_END.json` | 1.57 |
| `research/review_3080_20261010/delivery/score_split_timed_execution_root_v1/downloaded/TIMED_AUDIT_SOURCE_START.json` | 1.57 |
| `research/review_3080_20261010/delivery/score_split_timed_execution_root_v1/downloaded/pretrained_initial_fault0_worker/SOURCE_START.json` | 1.55 |
| `research/review_3080_20261010/delivery/score_split_timed_execution_root_v1/downloaded/random888_initial_fault0_worker/SOURCE_START.json` | 1.55 |
| `research/review_3080_20261010/delivery/server_teacher_boundary_audit_root_v1/downloaded/AUDIT_SOURCE_END.json` | 1.42 |
| `research/review_3080_20261010/delivery/server_teacher_boundary_audit_root_v1/downloaded/AUDIT_SOURCE_START.json` | 1.42 |
| `research/review_3080_20261010/delivery/server_teacher_boundary_audit_root_v1/downloaded/INDEPENDENT_SERVER_TEACHER_BOUNDARY.json` | 3.30 |
| `research/review_3080_20261010/delivery/server_teacher_boundary_root_v1/downloaded/ANSWERS.jsonl` | 13.83 |
| `research/review_3080_20261010/delivery/server_teacher_boundary_root_v1/downloaded/SOURCE_END.json` | 1.45 |
| `research/review_3080_20261010/delivery/server_teacher_boundary_root_v1/downloaded/SOURCE_START.json` | 1.38 |
| `research/review_3080_20261010/delivery/server_teacher_boundary_root_v2/downloaded/ANSWERS.jsonl` | 13.86 |
| `research/review_3080_20261010/delivery/server_teacher_boundary_root_v2/downloaded/SOURCE_END.json` | 1.45 |
| `research/review_3080_20261010/delivery/server_teacher_boundary_root_v2/downloaded/SOURCE_START.json` | 1.38 |
| `research/review_3080_20261010/delivery/server_teacher_boundary_root_v3/downloaded/ANSWERS.jsonl` | 13.81 |
| `research/review_3080_20261010/delivery/server_teacher_boundary_root_v3/downloaded/SOURCE_END.json` | 1.42 |
| `research/review_3080_20261010/delivery/server_teacher_boundary_root_v3/downloaded/SOURCE_START.json` | 1.42 |
| `research/review_3080_20261010/delivery/split_final_timed_execution_root_v1/downloaded/TIMED_AUDIT_SOURCE_END.json` | 1.58 |
| `research/review_3080_20261010/delivery/split_final_timed_execution_root_v1/downloaded/TIMED_AUDIT_SOURCE_START.json` | 1.58 |
| `research/review_3080_20261010/delivery/split_final_timed_execution_root_v1/downloaded/pretrained_initial_fault0_worker/SOURCE_START.json` | 1.55 |
| `research/review_3080_20261010/delivery/split_final_timed_execution_root_v1/downloaded/random888_initial_fault0_worker/SOURCE_START.json` | 1.55 |
| `research/review_3080_20261010/delivery/timed_actual_request_execution_root_v1/downloaded/TIMED_AUDIT_CHECKS.jsonl` | 3.08 |
| `research/review_3080_20261010/delivery/timed_actual_request_execution_root_v1/downloaded/TIMED_AUDIT_SOURCE_END.json` | 1.62 |
| `research/review_3080_20261010/delivery/timed_actual_request_execution_root_v1/downloaded/TIMED_AUDIT_SOURCE_START.json` | 1.62 |
| `research/review_3080_20261010/delivery/timed_actual_request_execution_root_v1/downloaded/pretrained_initial_fault0_worker/SOURCE_START.json` | 1.55 |
| `research/review_3080_20261010/delivery/timed_actual_request_execution_root_v1/downloaded/pretrained_initial_fault1_worker/FAULT_SOURCE_AT_ENTRY.json` | 1.55 |
| `research/review_3080_20261010/delivery/timed_actual_request_execution_root_v1/downloaded/pretrained_initial_fault1_worker/SOURCE_START.json` | 1.55 |
| `research/review_3080_20261010/delivery/timed_actual_request_execution_root_v1/downloaded/pretrained_initial_fault2_worker/FAULT_SOURCE_AT_ENTRY.json` | 1.55 |
| `research/review_3080_20261010/delivery/timed_actual_request_execution_root_v1/downloaded/pretrained_initial_fault2_worker/SOURCE_START.json` | 1.55 |
| `research/review_3080_20261010/delivery/timed_actual_request_execution_root_v1/downloaded/pretrained_initial_fault3_worker/SOURCE_START.json` | 1.55 |
| `research/review_3080_20261010/delivery/timed_actual_request_execution_root_v1/downloaded/pretrained_initial_fault4_worker/SOURCE_START.json` | 1.55 |
| `research/review_3080_20261010/delivery/timed_actual_request_execution_root_v1/downloaded/pretrained_initial_fault5_worker/SOURCE_START.json` | 1.55 |
| `research/review_3080_20261010/delivery/timed_actual_request_execution_root_v1/downloaded/pretrained_initial_fault6_worker/SOURCE_START.json` | 1.55 |
| `research/review_3080_20261010/delivery/timed_actual_request_execution_root_v1/downloaded/pretrained_initial_fault7_worker/SOURCE_START.json` | 1.55 |
| `research/review_3080_20261010/delivery/timed_actual_request_execution_root_v1/downloaded/pretrained_initial_fault8_worker/SOURCE_START.json` | 1.55 |
| `research/review_3080_20261010/delivery/timed_actual_request_execution_root_v1/downloaded/random888_initial_fault0_worker/SOURCE_START.json` | 1.55 |
| `research/review_3080_20261010/delivery/training_runtime_preflight_root_v4/INDEPENDENT_REMOTE_CAPTURE.json` | 1.33 |
| `research/review_3080_20261010/delivery/training_runtime_preflight_root_v4/INDEPENDENT_RUNTIME_ADJUDICATION.json` | 1.09 |
| `research/review_3080_20261010/delivery/training_runtime_preflight_root_v4/REMOTE_CAPTURE.json` | 2.66 |
| `research/review_3080_20261010/delivery/training_runtime_preflight_root_v4/RESULT.json` | 2.42 |
| `research/review_3080_20261010/pickup/actual_common_candidate_root_v1/RESULT.json` | 2.87 |
| `research/review_3080_20261010/pickup/actual_common_candidate_root_v1/own_incumbent_RAW.json` | 1.13 |
| `research/review_3080_20261010/pickup/actual_common_candidate_root_v1/strong_rolling_RAW.json` | 1.13 |
| `research/review_3080_20261010/pickup/actual_common_candidate_root_v2/RESULT.json` | 10.98 |
| `research/review_3080_20261010/pickup/actual_common_candidate_root_v2/discard_RAW.json` | 2.34 |
| `research/review_3080_20261010/pickup/actual_common_candidate_root_v2/own_incumbent_RAW.json` | 1.04 |
| `research/review_3080_20261010/pickup/actual_common_candidate_root_v2/pretrained_RAW.json` | 2.34 |
| `research/review_3080_20261010/pickup/actual_common_candidate_root_v2/random_RAW.json` | 2.34 |
| `research/review_3080_20261010/pickup/actual_common_candidate_root_v2/strong_rolling_RAW.json` | 1.05 |
| `research/review_3080_20261010/pickup/actual_masked_fleet_followup_v1/actual_cond_hist_root_v1/FULLRAW.json` | 46.21 |
| `research/review_3080_20261010/pickup/actual_masked_fleet_followup_v1/full_day_qa_v1/cond_report_fullraw.json` | 87.60 |
| `research/review_3080_20261010/pickup/actual_masked_fleet_followup_v1/full_day_qa_v1/own_pretrained_fullraw.json` | 91.10 |
| `research/review_3080_20261010/pickup/actual_masked_fleet_followup_v1/full_day_qa_v1/own_uncond_dynamic_fullraw.json` | 89.47 |
| `research/review_3080_20261010/pickup/actual_masked_fleet_followup_v1/full_day_qa_v1/strong_rolling_fullraw.json` | 89.01 |
| `research/review_3080_20261010/pickup/checkpoint_ack_root_v1/INDEPENDENT_CHECKPOINT_ACK.json` | 1.47 |
| `research/review_3080_20261010/pickup/checkpoint_resume_cancel_root_v1/ATTEMPT_3.json` | 4.40 |
| `research/review_3080_20261010/pickup/checkpoint_resume_cancel_root_v1/ATTEMPT_4.json` | 4.55 |
| `research/review_3080_20261010/pickup/checkpoint_resume_cancel_root_v1/OWNER_STATE_3.json` | 6.97 |
| `research/review_3080_20261010/pickup/checkpoint_resume_cancel_root_v1/OWNER_STATE_4.json` | 13.13 |
| `research/review_3080_20261010/pickup/checkpoint_resume_cancel_root_v1/REQUEST_3.json` | 4.74 |
| `research/review_3080_20261010/pickup/checkpoint_resume_cancel_root_v1/REQUEST_4.json` | 4.90 |
| `research/review_3080_20261010/pickup/complete_history_energy_qa_root_v1/complete_ledger/FULLRAW.json` | 30.03 |
| `research/review_3080_20261010/pickup/complete_history_energy_qa_root_v1/original_ledger/FULLRAW.json` | 30.03 |
| `research/review_3080_20261010/pickup/continuous_checkpoint_root_v2/ATTEMPT_1.json` | 3.68 |
| `research/review_3080_20261010/pickup/continuous_checkpoint_root_v2/ATTEMPT_2.json` | 4.06 |
| `research/review_3080_20261010/pickup/continuous_checkpoint_root_v2/OWNER_STATE_1.json` | 5.73 |
| `research/review_3080_20261010/pickup/continuous_checkpoint_root_v2/OWNER_STATE_2.json` | 11.78 |
| `research/review_3080_20261010/pickup/continuous_checkpoint_root_v2/REQUEST_1.json` | 3.91 |
| `research/review_3080_20261010/pickup/continuous_checkpoint_root_v2/REQUEST_2.json` | 4.34 |
| `research/review_3080_20261010/pickup/endogenous_owner_transaction_root_v2/CANDIDATE_RESULT_0.json` | 2.71 |
| `research/review_3080_20261010/pickup/endogenous_owner_transaction_root_v2/CANDIDATE_RESULT_1.json` | 2.71 |
| `research/review_3080_20261010/pickup/endogenous_owner_transaction_root_v2/OWNER_RESULT_0.json` | 2.85 |
| `research/review_3080_20261010/pickup/endogenous_owner_transaction_root_v2/RESPONSE_ATTEMPT_0.json` | 2.02 |
| `research/review_3080_20261010/pickup/endogenous_owner_transaction_root_v2/RESPONSE_ATTEMPT_1.json` | 2.02 |
| `research/review_3080_20261010/pickup/event_loss_resume_root_v1/ATTEMPT_11.json` | 6.02 |
| `research/review_3080_20261010/pickup/event_loss_resume_root_v1/ATTEMPT_12.json` | 6.38 |
| `research/review_3080_20261010/pickup/event_loss_resume_root_v1/OWNER_STATE_11.json` | 9.14 |
| `research/review_3080_20261010/pickup/event_loss_resume_root_v1/OWNER_STATE_12.json` | 18.38 |
| `research/review_3080_20261010/pickup/event_loss_resume_root_v1/REQUEST_11.json` | 6.50 |
| `research/review_3080_20261010/pickup/event_loss_resume_root_v1/REQUEST_12.json` | 6.90 |
| `research/review_3080_20261010/pickup/full_census_diagnostic_v1/full_day_all_fleet_trace.jsonl` | 11.02 |
| `research/review_3080_20261010/pickup/full_census_diagnostic_v1/per_event_vehicle.json` | 7.34 |
| `research/review_3080_20261010/pickup/inactive_slot_cancel_root_v1/ATTEMPT_7.json` | 5.47 |
| `research/review_3080_20261010/pickup/inactive_slot_cancel_root_v1/ATTEMPT_8.json` | 5.52 |
| `research/review_3080_20261010/pickup/inactive_slot_cancel_root_v1/OWNER_STATE_7.json` | 8.34 |
| `research/review_3080_20261010/pickup/inactive_slot_cancel_root_v1/OWNER_STATE_8.json` | 15.85 |
| `research/review_3080_20261010/pickup/inactive_slot_cancel_root_v1/REQUEST_7.json` | 5.91 |
| `research/review_3080_20261010/pickup/inactive_slot_cancel_root_v1/REQUEST_8.json` | 5.96 |
| `research/review_3080_20261010/pickup/joint_policy_rejection_root_v1/RESULT.json` | 4.79 |
| `research/review_3080_20261010/pickup/joint_policy_transaction_root_v2/RESULT.json` | 10.83 |
| `research/review_3080_20261010/pickup/joint_policy_transaction_root_v3/RESULT.json` | 10.83 |
| `research/review_3080_20261010/pickup/lazy_base_distance_full_scenario_root_v2/RESULT.json` | 8.68 |
| `research/review_3080_20261010/pickup/learned_after_strong_recovery_execution_root_v2/RESULT.json` | 2.58 |
| `research/review_3080_20261010/pickup/lineage_header_cancel_root_v1/ATTEMPT_13.json` | 6.73 |
| `research/review_3080_20261010/pickup/lineage_header_cancel_root_v1/ATTEMPT_14.json` | 7.75 |
| `research/review_3080_20261010/pickup/lineage_header_cancel_root_v1/OWNER_STATE_13.json` | 10.30 |
| `research/review_3080_20261010/pickup/lineage_header_cancel_root_v1/OWNER_STATE_14.json` | 23.87 |
| `research/review_3080_20261010/pickup/lineage_header_cancel_root_v1/REQUEST_13.json` | 7.29 |
| `research/review_3080_20261010/pickup/lineage_header_cancel_root_v1/REQUEST_14.json` | 8.46 |
| `research/review_3080_20261010/pickup/live_event_prefix_root_v1/PREPARED_RESPONSES.jsonl` | 7.66 |
| `research/review_3080_20261010/pickup/live_event_prefix_root_v1/RESULT.json` | 31.13 |
| `research/review_3080_20261010/pickup/live_resume_saa_cancel_root_v1/ATTEMPT_6.json` | 5.16 |
| `research/review_3080_20261010/pickup/live_resume_saa_cancel_root_v1/OWNER_STATE_6.json` | 7.83 |
| `research/review_3080_20261010/pickup/live_resume_saa_cancel_root_v1/REQUEST_6.json` | 5.56 |
| `research/review_3080_20261010/pickup/live_resume_saa_cancel_root_v1/SAA_CANCEL_WITNESS.json` | 6.50 |
| `research/review_3080_20261010/pickup/observed_day_extension_root_v1/PREPARED_RESPONSES.jsonl` | 98.47 |
| `research/review_3080_20261010/pickup/observed_day_extension_root_v1/REQUESTS_STARTED.jsonl` | 19.34 |
| `research/review_3080_20261010/pickup/observed_day_extension_root_v1/RESULT.json` | 866.09 |
| `research/review_3080_20261010/pickup/pending_admission_transaction_root_v1/RESULT.json` | 10.98 |
| `research/review_3080_20261010/pickup/prepared_slot_cancel_root_v1/ATTEMPT_8.json` | 5.52 |
| `research/review_3080_20261010/pickup/prepared_slot_cancel_root_v1/ATTEMPT_9.json` | 5.61 |
| `research/review_3080_20261010/pickup/prepared_slot_cancel_root_v1/OWNER_STATE_8.json` | 7.95 |
| `research/review_3080_20261010/pickup/prepared_slot_cancel_root_v1/OWNER_STATE_9.json` | 15.56 |
| `research/review_3080_20261010/pickup/prepared_slot_cancel_root_v1/REQUEST_8.json` | 5.96 |
| `research/review_3080_20261010/pickup/prepared_slot_cancel_root_v1/REQUEST_9.json` | 6.05 |
| `research/review_3080_20261010/pickup/private_joint_integration_root_v1/RESULT.json` | 6.19 |
| `research/review_3080_20261010/pickup/private_public_transport_root_v1/RESULT.json` | 1.06 |
| `research/review_3080_20261010/pickup/private_public_transport_root_v2/RESULT.json` | 1.06 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/ATTEMPT_14.json` | 7.75 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/ATTEMPT_15.json` | 7.81 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/ATTEMPT_16.json` | 7.87 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/ATTEMPT_17.json` | 8.05 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/ATTEMPT_18.json` | 8.08 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/ATTEMPT_19.json` | 8.09 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/ATTEMPT_20.json` | 8.11 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/ATTEMPT_21.json` | 8.24 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/ATTEMPT_22.json` | 8.27 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/ATTEMPT_23.json` | 8.50 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/ATTEMPT_24.json` | 8.64 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/ATTEMPT_25.json` | 8.70 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/ATTEMPT_26.json` | 8.76 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/ATTEMPT_27.json` | 8.73 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/ATTEMPT_28.json` | 8.79 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/ATTEMPT_29.json` | 9.01 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/ATTEMPT_30.json` | 9.02 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/ATTEMPT_31.json` | 9.19 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/ATTEMPT_32.json` | 9.40 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/ATTEMPT_33.json` | 9.49 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/ATTEMPT_34.json` | 9.56 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/ATTEMPT_35.json` | 9.76 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/ATTEMPT_36.json` | 10.04 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/ATTEMPT_37.json` | 10.22 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/ATTEMPT_38.json` | 10.45 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/ATTEMPT_39.json` | 10.72 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/ATTEMPT_40.json` | 10.77 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/ATTEMPT_41.json` | 10.87 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/ATTEMPT_42.json` | 11.16 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/ATTEMPT_43.json` | 11.93 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/ATTEMPT_44.json` | 12.23 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/ATTEMPT_45.json` | 12.61 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/ATTEMPT_46.json` | 12.64 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/ATTEMPT_47.json` | 12.75 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/ATTEMPT_48.json` | 12.82 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/ATTEMPT_49.json` | 12.88 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/ATTEMPT_50.json` | 12.91 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/ATTEMPT_51.json` | 12.98 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/ATTEMPT_52.json` | 13.29 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/ATTEMPT_53.json` | 13.46 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/ATTEMPT_54.json` | 13.50 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/ATTEMPT_55.json` | 13.58 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/ATTEMPT_56.json` | 14.87 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/ATTEMPT_57.json` | 14.91 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/ATTEMPT_58.json` | 15.35 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/ATTEMPT_59.json` | 15.61 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/ATTEMPT_60.json` | 15.60 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/ATTEMPT_61.json` | 15.69 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/ATTEMPT_62.json` | 16.02 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/ATTEMPT_63.json` | 16.23 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/REQUEST_14.json` | 8.46 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/REQUEST_15.json` | 8.53 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/REQUEST_16.json` | 8.59 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/REQUEST_17.json` | 8.78 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/REQUEST_18.json` | 8.81 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/REQUEST_19.json` | 8.82 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/REQUEST_20.json` | 8.84 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/REQUEST_21.json` | 8.97 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/REQUEST_22.json` | 9.04 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/REQUEST_23.json` | 9.27 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/REQUEST_24.json` | 9.44 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/REQUEST_25.json` | 9.49 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/REQUEST_26.json` | 9.56 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/REQUEST_27.json` | 9.53 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/REQUEST_28.json` | 9.59 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/REQUEST_29.json` | 9.82 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/REQUEST_30.json` | 9.83 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/REQUEST_31.json` | 10.02 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/REQUEST_32.json` | 10.26 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/REQUEST_33.json` | 10.34 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/REQUEST_34.json` | 10.41 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/REQUEST_35.json` | 10.64 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/REQUEST_36.json` | 10.94 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/REQUEST_37.json` | 11.15 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/REQUEST_38.json` | 11.41 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/REQUEST_39.json` | 11.71 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/REQUEST_40.json` | 11.76 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/REQUEST_41.json` | 11.88 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/REQUEST_42.json` | 12.20 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/REQUEST_43.json` | 13.07 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/REQUEST_44.json` | 13.41 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/REQUEST_45.json` | 13.84 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/REQUEST_46.json` | 13.87 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/REQUEST_47.json` | 14.00 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/REQUEST_48.json` | 14.07 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/REQUEST_49.json` | 14.12 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/REQUEST_50.json` | 14.15 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/REQUEST_51.json` | 14.22 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/REQUEST_52.json` | 14.58 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/REQUEST_53.json` | 14.76 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/REQUEST_54.json` | 14.80 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/REQUEST_55.json` | 14.88 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/REQUEST_56.json` | 16.35 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/REQUEST_57.json` | 16.39 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/REQUEST_58.json` | 16.88 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/REQUEST_59.json` | 17.16 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/REQUEST_60.json` | 17.16 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/REQUEST_61.json` | 17.27 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/REQUEST_62.json` | 17.63 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/REQUEST_63.json` | 17.86 |
| `research/review_3080_20261010/pickup/resident_day_tail_root_v1/TERMINAL.json` | 1.94 |
| `research/review_3080_20261010/pickup/resident_tail_stream_audit_root_v3/CHECKS.jsonl` | 3.34 |
| `research/review_3080_20261010/pickup/resident_tail_stream_audit_root_v3/INDEPENDENT_RESIDENT_TAIL_STREAM_R3.json` | 4.11 |
| `research/review_3080_20261010/pickup/resident_two_events_root_v1/ACK_1.json` | 2.94 |
| `research/review_3080_20261010/pickup/resident_two_events_root_v1/ACK_2.json` | 3.04 |
| `research/review_3080_20261010/pickup/resident_two_events_root_v1/ATTEMPT_1.json` | 2.80 |
| `research/review_3080_20261010/pickup/resident_two_events_root_v1/ATTEMPT_2.json` | 2.90 |
| `research/review_3080_20261010/pickup/resident_two_events_root_v1/REQUEST_1.json` | 2.94 |
| `research/review_3080_20261010/pickup/resident_two_events_root_v1/REQUEST_2.json` | 3.04 |
| `research/review_3080_20261010/pickup/resident_two_events_root_v1/RESIDENT_RESULT.json` | 7.55 |
| `research/review_3080_20261010/pickup/restore_compute_cancel_root_v1/CASE_2/ATTEMPT_6.json` | 5.16 |
| `research/review_3080_20261010/pickup/restore_compute_cancel_root_v1/CASE_2/FAULT_WITNESS.json` | 7.10 |
| `research/review_3080_20261010/pickup/selector_event_loss_root_v1/ATTEMPT_10.json` | 5.76 |
| `research/review_3080_20261010/pickup/selector_event_loss_root_v1/ATTEMPT_9.json` | 5.61 |
| `research/review_3080_20261010/pickup/selector_event_loss_root_v1/OWNER_STATE_10.json` | 15.84 |
| `research/review_3080_20261010/pickup/selector_event_loss_root_v1/OWNER_STATE_9.json` | 8.05 |
| `research/review_3080_20261010/pickup/selector_event_loss_root_v1/REQUEST_10.json` | 6.20 |
| `research/review_3080_20261010/pickup/selector_event_loss_root_v1/REQUEST_9.json` | 6.05 |
| `research/review_3080_20261010/pickup/strong_independent_owner_fault3_root_v1/CANDIDATE_RESULT_0.json` | 2.95 |
| `research/review_3080_20261010/pickup/strong_independent_owner_fault3_root_v1/RESPONSE_ATTEMPT_0.json` | 2.18 |
| `research/review_3080_20261010/pickup/strong_independent_owner_next_root_v2/CANDIDATE_RESULT_0.json` | 2.94 |
| `research/review_3080_20261010/pickup/strong_independent_owner_next_root_v2/OWNER_RESULT_0.json` | 3.08 |
| `research/review_3080_20261010/pickup/strong_independent_owner_next_root_v2/RESPONSE_ATTEMPT_0.json` | 2.17 |
| `research/review_3080_20261010/pickup/strong_independent_owner_root_v3/CANDIDATE_RESULT_0.json` | 2.72 |
| `research/review_3080_20261010/pickup/strong_independent_owner_root_v3/OWNER_RESULT_0.json` | 2.85 |
| `research/review_3080_20261010/pickup/strong_independent_owner_root_v3/RESPONSE_ATTEMPT_0.json` | 2.02 |
| `research/review_3080_20261010/pickup/terminal_restore_root_v2/RESTORE_IN_REQUEST.json` | 1.62 |
| `research/review_3080_20261010/pickup/terminal_restore_root_v2/TERMINAL.json` | 1.94 |
| `research/review_3080_20261010/pickup/terminal_restore_root_v2/TERMINAL_EVENTS.json` | 17.18 |
| `research/review_3080_20261010/pickup/timed_restore_live_root_v1/ATTEMPT_4.json` | 4.55 |
| `research/review_3080_20261010/pickup/timed_restore_live_root_v1/ATTEMPT_5.json` | 4.87 |
| `research/review_3080_20261010/pickup/timed_restore_live_root_v1/OWNER_STATE_4.json` | 6.50 |
| `research/review_3080_20261010/pickup/timed_restore_live_root_v1/OWNER_STATE_5.json` | 13.52 |
| `research/review_3080_20261010/pickup/timed_restore_live_root_v1/REQUEST_4.json` | 4.90 |
| `research/review_3080_20261010/pickup/timed_restore_live_root_v1/REQUEST_5.json` | 5.25 |
| `research/review_3080_20261010/pickup/undecided_public_input_root_v1/FAILURE.json` | 1.02 |
| `research/review_3080_20261010/pickup/undecided_public_input_root_v2/RESULT.json` | 1.19 |

## How this archive is built (reproducible)

The exclusion list is generated from the working tree by `tools/_git_exclude_big_evidence.py`
(it appends every `*.json`/`*.jsonl` staged file of at least 1 MiB to the `.gitignore`
generated block). To rebuild the archive from a machine that still has the files:

```bash
# 1. extract the excluded paths from .gitignore
sed -n '/BEGIN generated/,/END generated/p' .gitignore | grep '^/' | sed 's|^/||' > evidence_list.txt
# 2. archive them (paths are relative to the repository root)
tar -czf DynMaskCO_raw_evidence.tar.gz -T evidence_list.txt
# 3. verify
sha256sum DynMaskCO_raw_evidence.tar.gz
```

To unpack: `tar -xzf DynMaskCO_raw_evidence.tar.gz -C <repo-root>` restores every path
to the location the repository references.

## Why these files are not in git

A naive `git add -A` staged 5,571.7 MiB, including a 1,190.1 MiB `STATES.jsonl` and an 866.1 MiB
`RESULT.json`. GitHub rejects any single file over 100 MiB, and the existing tracked tree is 383 MiB,
so committing everything was neither possible nor desirable. All source (`.py`), documentation (`.md`)
and every artifact below 1 MiB stay tracked; only oversized raw dumps are externalised here.
