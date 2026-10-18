# DynMaskCO-CC 自我迭代研发总纲
## 从「稳定在线增益 = False」到「CCF-A 创新点 + 基准 SOTA」的完整执行手册

> 版本：v1.0 ｜ 日期：2026-10-18 ｜ 维护副本：`YuqiWang-code/DynMASKCO`（上游 `GoodThing001/DynMaskCO`）
> 本文档是**唯一执行入口**。它同时是：战略定位书、跨域灵感库、文献/代码采购单、代码改造单、实验设计书、服务器与抢卡规程、定时任务编排表、12 个月里程碑与止损规则。
> 与本仓库既有纪律的兼容方式：本文不改写任何已登记结论，`stable_online_gain=False` 等封存状态在本文生效期间保持不变；本文所有新增工作走**新登记线**，预登记先行。

---

## 0. 一页速览

### 0.1 现在在做什么（客观现状，2026-10-18 封存）

| 维度 | 现状 |
|---|---|
| 课题 | 把 MaskCO（掩码生成式 NCO，ICLR 2026）扩展到**动态冷链车辆路径**：pickup-to-depot 取货回仓、三温区（18℃/4℃/−18℃）、订单按 `reveal_time` 动态揭示 + EDoD、Arrhenius 品质衰减、制冷能量预算 C0、时间窗+容量+不可撤销承诺、strict-online（非预知） |
| 核心结论 | `stable_online_gain = False`。尚未建立稳定、可归因的在线正向增益 |
| 最强线索 | 取货 A-v1：5 个冻结日受控 A/B 配对差 `[0, +102.92, +24.76, 0, 0]`，均值 **+25.54**，0 天为负；机制是把能量预算从最不划算的类挪到最划算的类（类 0 服务率 0.59→0.80）。按预登记口径**只是线索** |
| 最新一轮 | 2026-10-17 Q3 第二轮（S3 执行器浮点外扩界）**NO-GO**：`EXP_ERROR_BOUND_NOT_ESTABLISHED`，两轮止损用尽 ⇒ 连续温度认证仍未建立，L1 `BLOCKED`、L2/A3 未启动、`PRODUCTION_NOT_QUALIFIED` |
| 并行新线 | 2026-10-17 起 BwK 接拒重构：解耦接拒控制器（阶段 0 完成，7/7）→ 接拒层离线对照（动态 λ 均值 **+38.00**，0 天为负）→ **全仿真阶段 1 判 DOMINATED（动态 λ − 控制 = −25.75）** → 1b 机械 LEAD +11.60 但低于静态臂 −8.52 → 1c TRAIN 标定 DOMINATED（−10.70 / −30.82）→ 学习型 λ 落在两条手写规则之间 |
| 认证资产 | 密钥暴露已处置（脱敏 + 预提交扫描）；42 条 watch 冻结身份、一次性执行凭据、独立只读审计、`git_deliver.py` 交付链路均已建成 |

### 0.2 这次要做什么（本文给出的答案）

**一句话**：把「再训一个更强的学习器」换成「**证明并量化因果信息价格，然后在余量里用可证明的预算决策机制拿到 SOTA**」。

三段式核心贡献（互相支撑，缺一不可）：

- **I-1（理论骨，CCF-A 的创新点）**：*因果冷链路由的信息价格*。把 headroom 严格分解为「未来信息部分」`L_future` 与「规则可捕获后剩余」`L_rule`；给出严格在线下的**结构不可能性**（某些到达/时间窗结构无有限竞争比）与**可检验判据**；给出规则 oracle 的最优性条件（在哪些简化设定下 EDD / quality-density 规则可证最优）。
- **I-2（引擎，SOTA 来源）**：*资源耦合影子价格场 + 集合级承诺（OCRS）*。把 λ 从标量升级为温区×空间×时间的**联合拉格朗日乘子场** λ_{k,z,t}，接拒从「逐单阈值」升级为「分数松弛 + 在线 contention resolution」；给出 BwK 型 regret 界与 **no-regret-to-rule** 保证；这是把阶段 0.5 的 +38 代理增益真正迁移到日效用的机制。
- **I-3（承载，社区影响力）**：*CC-DVRP-3T 严格因果基准 + leak unit tests*。三条 regime、12 条基线、四列 oracle（clairvoyant / causal / rule / learned）、可复现 leaderboard。

**为什么这不是「方法性论文」**：删掉网络后 I-1 仍然成立（定理与下界）；删掉定理后 I-2 仍有硬保证（budget 不变式 + fallback 到规则）；I-3 改变了社区评价方式。三者都不依赖"换个编码器跑赢 0.x%"。

### 0.3 SOTA 的明确定义（本文硬门槛）

> 社区共识（必须正视）：在标准 CVRP 上，**HGS-CVRP 在 Uchoa-100 实例、统一时间预算 `n×240/100` 秒下的平均 BKS gap 是 0.11%**，OR-Tools GLS 是 4.01%，SISR 0.19%、FILO 0.20%、LKH-3 1.00%。**"学习类全面超过 HGS/LKH3" 至今不成立**。冷链方向目前**没有统一 SOTA benchmark**，现有工作多用改造后的 Solomon/CVRPLIB，没有动态揭示 + 品质闭环同时存在的公开实例集。

因此本文把 SOTA 拆成两个可同时拿下的口径，不做偷换：

| 口径 | 定义 | 硬门槛 |
|---|---|---|
| **SOTA-1（主口径，自建基准）** | 在 CC-DVRP-3T-Bench 上，closed-loop 日效用 U 相对 12 条基线的配对改进 | 对 **≥10/12** 条基线显著为正（配对 bootstrap 95% CI 下界 > 0）；允许最多 **2 条** 例外 |
| **SOTA-2（辅口径，社区标尺）** | 静态侧 CVRP/VRPTW：对 OR-Tools GLS 显著优；对 HGS-CVRP 报告真实 gap 与同平台时间预算 | 不强制超过 HGS，但**必须同硬件、同时间预算、同可行域**报告；差距须在表中如实呈现 |
| **不可妥协项** | 服务率、品质合格率、能耗达标率不得恶化；超时率、温区违规不得上升；每决策 CPU/GPU 时间须报 | 任一恶化 ⇒ 该候选不得宣称为 SOTA |

**允许一两个超过我们**：`clairvoyant oracle`（未来信息上界，本来就该赢，它不在"被超越"名单内，只作分母）、以及最多 1 条强非学习基线（如 rolling HGS+LNS）。这是诚实的 SOTA，不是自欺的 SOTA。

### 0.4 从今天起 7 天

| 天 | 动作 | 产出 |
|---|---|---|
| D1 | 建 `CC-DVRP-3T` 生成器 v0（Solomon 分布 + 温区 + reveal + EDoD + Arrhenius + C0），冻结 seed 角色 | `scripts/bench/cc_dvrp3t_gen.py` + 100 实例 |
| D2 | 拉 6 条非学习基线（HGS-CVRP / LKH-3 / OR-Tools / PyVRP / regret-2 rolling / LNS）并跑通 1 个实例 | `CC_Compare/` 6 个子目录 + `smoke` 日志 |
| D3 | 建**决策反演测试**（树/线性模型能否复现策略决策），把它接成合入门槛 | `scripts/tests/test_rule_inversion.py` |
| D4 | 跑 clairvoyant / causal / rule 三列 oracle，出 `L_future` 与 `L_rule` 第一版分解 | `docs/04_实施与结果/2026-10-2x_信息价格分解_v1.md` |
| D5 | λ 场第一版（温区×区域×时段），接拒层离线对照复跑（含空间维度） | 对照表 |
| D6 | 抢卡脚本 + tmux 队列 + 结果回收入库（`metrics.jsonl`） | `tools/gpu/` 三件套 |
| D7 | 定时任务上线（每日 02:00 抢卡 / 08:00 README+push / 每周一评审包） | crontab + 首次自动 push |

---

## 1. 现状诊断：为什么两年都拿不到稳定增益

### 1.1 三个结构性障碍（不要再用"训练不够/模型太小"来解释）

**障碍 A：头空间几乎 100% 是未来信息。**
诊断已建立：clairvoyant（预知未来）上界远高于任何在线策略；所有被测决策（排序、温区分配、派车时机、昼夜时钟放置、预冷）要么是未来信息，要么是规则可捕获的。**预冷是唯一接近正向的结果**（myopic headroom 3.68 normalized，来自 22× 冻结 Arrhenius 速率），但它是 rule-capturable（"永远预冷"）；中心站批量预冷的组合头空间极小（路线约 2 单/车，"批量"退化为平凡）。

**障碍 B：代理指标 → 日效用的迁移断裂（这是 10-17/18 失败的确切形态）。**
接拒层离线对照：动态 λ 逐日差 `[+20,+110,+30,+30,0]`，均值 **+38.00**，0 天为负 —— 机制清晰（静态规则预算利用率只有 93–99%，动态用满）。进入全仿真阶段 1 后：**动态 λ − 控制 = −25.75**，静态 λ − 控制 = +20.12。**+38 的收入代理被距离/品质损耗吃掉**。1b、1c、学习型 λ 全部复现同一模式：代理层有效、闭环无效。

**障碍 C：学习化的收益被证明可由规则复现。**
N0-R→N1/N2（模仿 regret-2 的蒸馏）、M-pre/M-trained（REINFORCE 直接目标）、feature-local/H-only/M1 三组消融、de-index、X_state、decision-loss 2×2 —— 全部未建立正效用；其中固定状态诊断显示学习模型复现 regret-2 的**客户集合 100% / 完整计划哈希 60%，但慢 ~440×**。**当前可行结论是"recipe 失败"，不是"encoder 不可迁移""recon 有害""capacity 被排除"**（这三个说法都被明确禁止写入）。

### 1.2 由 A+B+C 推出的三条硬纪律

1. **任何候选机制必须先过"决策反演测试"**：用在线可见特征训练树/线性模型去复现该策略的接拒与排序；若 AUC > 0.98 且效用损失 < 3~5%，正式判定为**规则可捕获**，该机制降为基线，不得作为创新点。这个测试要接成 CI 门槛，不是写进文档的一句话。
2. **代理指标与日效用必须双列上报**：任何只报接拒层收入、不报闭环 U 的记录，一律标 `PROXY_ONLY`，不得进入 SOTA 判定。
3. **不再新增"换架构再跑一遍"的实验**：除非新结构能给出可解释的信息增益、跨 regime 一致增益、或新的理论表达。

### 1.3 现在的真实机会窗口

诊断说"没有头空间"，但它只否定了**被测试过的那一族机制**。没有被测过的、且结构上不可能是规则的，只剩三类：

- **联合资源耦合的拉格朗日乘子场**（不是单标量阈值）：同一单位电量在冷冻/冷藏/常温之间不可自由替换，同一空间区域在不同时刻价值不同，容量×电量×品质构成耦合资源。乘子跨越约束绑定边界时产生**非单调切换**，单阈值无法表示。
- **集合级可扩展性**（不是逐单边际）：分数松弛 + OCRS 判断的是"已接受集合是否仍能被补足成可行完整集合"，依赖尚未来到的订单的到达过程。这是在未来随机变量上的集合一致性，不是排序。
- **不可压缩的尾部风险**（不是分位阈值）：多个相关尾部量（容量紧张、品质风险、到达时间不确定、路线不可行）映射为满足**联合风险上界**的阈值函数，且随剩余预算变化。

这三类的共同点：**决策依赖未来分布的形状与耦合结构，而不仅仅是当前可见标量**。这正是障碍 A 唯一没有排除的角落。

---

## 2. 战略定位：贡献形态的取舍

### 2.1 形态评估（基于 2021–2026 已核实案例）

| 形态 | 2025–2026 接受难度 | reviewer 典型质疑 | 本项目判定 |
|---|---|---|---|
| 新架构/新模块 | 高 | "与已有架构抽象是否不同""是否刷榜" | **死路**（无结构性增益时换模块无效） |
| 新训练范式 | 中高 | "损失是否带来机制变化""冷启动可行性" | 可做，但必须超过规则**或**证明信息增益 |
| **理论保证**（regret / competitive ratio / 下界） | 理论可单独成立；难在假设正确 | "是否过度简化""能否迁移到完整设定" | **主推** |
| **新设定 + 新评测协议** | 中，需资源与生态 | "与已有变体差别是否实质""是否改变认识" | **主推**（须绑定理论） |
| 实证反思型 | 中高 | "负结果是否有普遍意义""是否只是实现缺陷" | 可做，须有 future-info 分解 |
| 混合范式（learn to configure/select/destroy） | 中 | "学习组件必要性""是否泄漏未来""OR fallback 够不够强" | 保留为第三主包，要求**可关闭** |
| 不可能性 / 结构负结果 | 很高但价值高 | "假设是否过强""下界是否可避免" | **主推**（须参数化实例族） |

**关键外部依据**：NeurIPS 2026 官方评审说明明确列出 Negative Results 贡献类型——"主要贡献在于理解一个负结果（意义与原创性门槛高）"，并明确"理论论文不必用 SOTA 实验证明自己"。这意味着**诚实不是退而求其次**，前提是把"理解"做扎实（参数化实例族 + 可检验判据），而不是写一句"我们失败了"。

### 2.2 死路清单（明确禁止立项）

1. **换编码器/新解码器再跑一遍**（GNN→Transformer→diffusion 轮换）。
2. **用 clairvoyant 训练目标或 future-visible 特征包装在线学习** —— 这是伦理与科学性双重错误，有撤稿风险。预测模块必须单独定义，并证明 safe fallback、consistency、robustness。
3. **把"学习超过 Gurobi/OR-Tools"当唯一目标** —— 公平比较要求同时间预算、同硬件、同可行域、同 warm start、同种子数、同终止条件；只报单点平均 objective 不足以说服 OR reviewer。
4. **把三温区/Arrhenius/能量预算只当损失项** —— 线性加进 reward 不算贡献；必须写进可达集、动态约束、影子价格或 quality envelope。
5. **把失败包装成方法** —— 若最终没有正增益，主稿改为 impossibility + protocol + benchmark，这仍是完整贡献，**不允许**改成"我们提出了一种新方法，虽然没有超过基线"。

### 2.3 双轨双稿（同一份材料，两种叙述）

| | 轨 A（顶会） | 轨 B（顶刊） |
|---|---|---|
| 目标 venue | NeurIPS / ICLR / ICML（或 Datasets & Benchmarks） | Transportation Science / TR-B / EJOR / INFORMS JoC |
| 标题方向 | *The Price of Information in Causal Cold-Chain Routing* / *Causal Online Routing under Refrigeration Budgets: Lower Bounds and Learning-Augmented Algorithms* | *An Exact and Learning-Augmented Framework for Dynamic Three-Temperature Cold-Chain Routing* |
| Abstract 第一句 | 信息分离、竞争比/regret、leak audit | 易腐品、三温区、Arrhenius、能耗、运营启示 |
| Introduction | 回答"为何过去学习增益可能来自未来" | 先解释食品安全、货损、能源约束，再转到算法 |
| 共享 | simulator、instance generator、证明、部分真实实验（合规前提下共享数据与公开版本边界） | 同左 |

冷链的高质量生态**确实在 OR/交通顶刊**（已核实代表：Hülagü et al., *An Exact Algorithm for the VRP with Time Windows and Perishable Products*, Transportation Science 2026，可解至 100 客户；Lin et al., *VRP in precooling logistics with dynamic temperature-dependent product quality decay*, EJOR 2025, DOI 10.1016/j.ejor.2024.09.041；Stellingwerf et al., quality-driven VRP, IJPE 2021）。所以**顶会版引言不能只在冷链**：必须把三温区、品质衰减、能量预算抽象成"资源耦合在线组合决策"这一类问题。

---

## 3. 跨域调研：16 个领域的机制迁移与联想

> 方法：每个领域给出「原始机制 → 冷链落点 → 形式化 → **是否规则可捕获**的判断」。
> 判定原则：**非规则化必须至少满足「状态依赖 / 全局耦合 / 跨尺度守恒 / 时间一致性 / 不可压缩风险」五项之一**。只进入加性权重的标量（温度、剩余电量、容量、收益、距离）通常可编码为单调阈值。

### 3.0 先把"规则可捕获"变成可证伪假设

令 `H_t` 为可见历史，`A_t` 为即时决策，`F_t` 为在线可测特征，`G_t` 为日终才可见的完整轨迹。规则壁垒 ⟺ 存在低复杂度 `π: F_t → A_t` 使效用与学习器相当。可操作化：

- **反演测试**：在 `F_t` 上训练树/线性模型拟合策略的 `A_t`；AUC > 0.98 且效用损失 < 5% ⇒ 判规则可捕获。
- **单标量消融**：把策略替换成"以某可见标量（负载率/剩余时间/λ 均值）为唯一输入的阈值函数"；若性能差 < 5% ⇒ 判规则可捕获。
- **跨日簇留一法**：按日簇 leave-one-day-out 训练，防止策略只是记住当日到达统计。

### 3.1 第一梯队（A 级，立即做）

#### ① 温区影子价格是「时刻表」而不是单标量（MPC / 收益管理 / 生态学）

**来源**：Pontryagin 极大值原理；Rawlings & Mayne, *Model Predictive Control: Theory and Design*（2009）；Littlewood (1972) 与 Belobaba (1987) 的座位库存控制；**Charnov (1976) 边际价值定理**（*Theor. Popul. Biol.* 9(2):129–136）——动物应在斑块即时收益下降到等于环境平均收益率时离开。

**联想（这是最有想象力的迁移）**：一辆冷链车在一个「斑斑 = 温区×空间区域」里采食，边际即时收益是"再取一单的净价值"，环境平均收益率是"其他车 × 其他区域 × 剩余时间"能拿到的期望。最优离开条件不是"装满"也不是"到点"，而是 **边际收益 = 全域平均收益率 + 移动机会成本**。这直接给出「温区时刻表」：车辆何时该从冷冻区切到冷藏区、何时该返仓 —— 这是**时间函数**而不是阈值。

**形式化**：令 λ_{k,z,t} 为温区 k × 区域 z × 时刻 t 的广义价格。接单条件

```
r_i − λ_{k,z_i,t} − μ_{q,i} − μ_{e,i} + E_t[ V_{t+1}(S') − V_{t+1}(S) ] ≥ 0
```

其中质量机会成本 `μ_q = ∂V/∂q_i` 沿 Arrhenius 反向传播，能量机会成本 `μ_e = ∂V/∂e` 沿 `ė = −P(u) + σ` 反向传播。滚动窗口 H 内用估计到达与温度预测解 LP / 最小成本流，窗口外用 λ 代理续值，每事件只执行首个动作。

**为何不是规则可捕获**：静态 λ 只回答"当前单位容量值多少"；λ_{k,z,t} 是**联合约束的拉格朗日乘子场**。同一单位电量在三温区之间不可自由替换、同一区域在不同时刻价值不同、容量×电量×品质耦合。典型非单调切换：晚高峰冷冻需求占满剩余能量时，18℃ 番茄反而因窗口更宽而值得保留容量 —— 这是乘子跨越约束绑定边界，固定优先级表示不了。

**最小实验**：基线 = 静态 bid price / EDD / 固定温区优先级；消融 = 仅价格 → 价格+温区 → 价格+空间+温区；每 15 分钟或每事件更新。
**成功**：闭环 ΔU ≥ 1.5% 且连续 10 个测试日中 ≥8 日为正。
**失败信号（命中任两项即止损）**：λ 变化幅度 < 10% 分位；λ 与车辆利用率相关系数 > 0.98；反演树 R² > 0.95；增益只在放宽时间窗时出现。

#### ② 紧性感知 OCRS：把「逐单接受」改成「集合承诺」（组合数学 / 机制设计）

**来源**：Edmonds (1971) 拟阵贪婪最优性；Nemhauser–Wolsey–Fisher (1978) 次模最大化 `1−1/e`；**Feldman–Svensson–Zenklusen, Online Contention Resolution Schemes**（2016）；Karp–Vazirani–Vazirani (1990) RANKING `1−1/e`。

**形式化**：先解分数松弛 `max_x E[Σ r_i x_i]`（容量、窗口、能量约束）得 `p_i = E[x_i*]`；在线 CRS 以概率 `b_i p_i` 试探接受，再在冲突图上做边/匹配/资源 CRS；OCRS 要求 `Pr[j ∈ S̃ | j ∈ S, B(S)] ≥ c`，其中 `B(S)` = "已接受集合 S 仍可扩展为可行完整集合"。

**为何不是规则可捕获**：单订单边际收益可成阈值；**集合可扩展性**依赖尚未揭示订单的到达过程、其他车辆剩余时间、能量与品质耦合 —— 这是未来随机变量上的集合一致性。

**诚实边界**：冷链的实时约束未必构成拟阵，`1−1/e` **不能**直接宣传为保证。已知对抗到达 matching RCRS 可达 0.344-selectable、随机顺序 0.474-selectable，且随机顺序 RCRS 的 selectability 不可能超过 0.5 —— 这个 0.5 上界要写进论文，不能回避。

**最小实验**：只改接拒层，其余沿用冻结 MaskCO；对照 = 静态阈值 / 分数 LP+简单舍入 / 边 CRS / 匹配 CRS / 拟阵 CRS；以 clairvoyant LP 为松弛上界。
**失败信号**：CRS 接受率与分数值相关系数 > 0.97；随机接受只增加低价值订单；复杂 CRS 与"分数阈值 + 可行性检查"无显著差异。

#### ③ 拒绝原因特定的保形风险控制（极值统计 / 保形预测）

**来源**：Vovk–Gammerman–Shafer, *Algorithmic Learning in a Random World*（2005）；Angelopoulos & Bates et al., *Learn then Test*（NeurIPS 2021, arXiv:2110.01052）。

**形式化**：不统一校准"拒单风险"，而是**为每一类拒因**构造非一致性分数：`s_1 = r_i − λ_i`（未来紧容量）、`s_2 = q_i(T_i) − q_min`（品质风险）、`s_3 = t̂_i − t_i`（到达时间不确定）、`s_4`（路线不可行）。在交换性校准集上选阈值使 `Risk̄(Ŝ) ≤ α`；阈值随 t 与剩余预算 b_t 变化，但风险约束仍是**日频强约束**。

**为何不是规则可捕获**：单个分位阈值是规则；把多个相关尾部量映射为满足**联合风险上界**的阈值函数、且随预算耗尽改变，属于分布—决策联合校准。

**诚实边界**：arrival 非 i.i.d. 时普通保形覆盖失效，须改用加权或在线 regret 控制 —— 必须先做交换性检验。
**失败信号**：交换性检验被拒；组间覆盖率差距 > 5 个百分点；阈值只随样本量而非状态变化；收益差连续两轮 < 0.1%。

### 3.2 第二梯队（B 级，第一梯队验证后再做）

#### ④ 质量—能量守恒流与 tube 鲁棒控制（非平衡热力学 / 随机 MPC）

**来源**：Lotka (1920) / Volterra 捕食者—猎物；细致平衡网络；Mayne et al. tube-based RMPC（*Automatica* 41(2):219–224, 2005；42(4):541–550, 2006）；Raković & Mayne (2005)。

**联想**：把每个温区当作一个 compartment，质量流 `q̇_i = −A_k q_i exp[−E_k/(R T_i)]` 与能量流 `ė_v = P_v − η_v ṁ_v²/2` 构成非平衡稳态；制冷做功 = 细致平衡破缺的程度，**熵产生率**是"品质—能耗"权衡的守恒量。tube 的中心轨迹由窗口 LP 给出，管截面由温度扰动、行程扰动、品质误差的鲁棒正不变集收紧。

**落点**：路线重构、能量预算、派车与回仓。
**为何可能不是规则**：固定预冷温度 + 固定回仓阈值不保留扰动传播结构；tube 显式保留"误差可能如何累积"。当电量与品质共享预算时，局部阈值的加和**不是**系统守恒量。
**风险**：鲁棒管束可能收缩到无可行解。
**失败信号**：管束收紧后可行率下降 > 20%；保守回仓次数增加但品质几乎不变；额外距离抵消全部质量收益。

#### ⑤ 到达过程的极值与换点校准（极值统计 / 大偏差）

**来源**：Leadbetter–Lindgren–Rootzén (1983)；Cramér (1938)；Pickands/Balkema–de Haan 的 GPD 尾部；Rubinstein (1997) 交叉熵方法。

**形式化**：`N_{k,z}(t)` 的尾部用 GPD 建模 `F(x) = 1 − (1 + ξ(x−u)/σ)^(−1/ξ)`；对到达强度做 CUSUM/GLR 换点检测；在预测分布上用重要性权重 `w = dP*/dP` 评估拒绝稀有高峰的机会成本。

**为何可能不是规则**：决定拒绝与否的是"**即将**发生容量紧张"的概率质量，而不是当前队列长度；极值尾部依赖跨时段依赖、温区相关性与区域聚集。
**失败信号**：尾部参数置信区间覆盖整个可行温度区间；换点只在节假日触发；动态模型连续 14 天不触发。

#### ⑥ 风险—信息权衡的受限探索（随机热力学 / 信息论）

**来源**：Seifert (2005) 积分涨落定理 ⟨e^{−Σ}⟩ = 1（*PRL* 95:040602）；Sagawa–Ueda 信息热机；Still–Sivak–Bell–Crooks, *Thermodynamics of Prediction*（*PRL* 109:120604, 2012）；Tishby–Pereira–Bialek 信息瓶颈（2000）。

**联想（较激进但形式干净）**：**热力学不确定性关系（TUR）**说"提高观测/控制精度必须付出耗散代价"。迁移到本项目：**想更准确地知道"未来是否需要这块容量"，本身要付出制冷能耗与行驶代价**。于是探索不再是"试一次看看"，而是受耗散预算约束的最优信息获取问题：

```
max_π  E[R] − β·I(A_t; S_{t+1} | H_t) − γ·Σ(a) − η·E[max(0, q_min − q)]
```

**落点**：接拒、路线探索、重构触发。
**诚实边界**：这些是连续时间热力学定理，**不是**车辆路径的性能定理，不能直接套成保证；只能作为正则项与目标设计原则。
**失败信号**：信息增益与车辆位移高度共线；额外能耗 > 增益两倍；最优探索只访问最近邻。

#### ⑦ 多时间尺度机会约束 + backpressure（排队论 / 随机网络优化）

**来源**：Tassiulas–Ephremides (1992) backpressure；Neely (2010) Lyapunov 漂移；Prékopa 机会约束。

**形式化**：把每辆车的温区承诺、剩余时间、品质、电量视为队列 `Q_{v,k}`；压力路由沿 `−∇Q_{v,k}`；出发动作使 `Σ_k Q_{v,k} Q̇_{v,k} ≤ −ε Σ_k Q_{v,k}² + B`；机会约束 `Pr(q_i(t_i) ≥ q_min) ≥ 1 − ε`。
**风险**：若压力定义成负载/时间窗，会退化成 cμ 规则。
**失败信号**：压力与剩余时间排序相关系数 > 0.97；队列持续为零。

#### ⑧ 预测残差条件化的状态表示（神经科学 / 信息论）

**来源**：Rescorla–Wagner (1972) `ΔV_i = α_i(λ − Σ_j V_j)`；Rao–Ballard (1999) 预测编码；Friston (2010) 自由能原理。

**形式化**：学 `ŝ_{t+1} = f_θ(s_t, a_t)` 与残差 `e_t`；状态扩展为 `(s_t, e_t)`；价值网络 `V(s,e) = V_0(s) + g(e)`；**只在 |e| 超过经验置信边界时触发全量重构**（省算力 + 抗噪声）。
**为何可能不是规则**：单一预测均值会制造"看起来已经知道未来"的伪头空间；残差揭示模型何时失配，且残差常有时空结构。
**失败信号**：残差加入只提高 0.1% 预测精度；门控永远关闭；残差可由单变量预测。

### 3.3 第三梯队（C 级，只做工具或对照）

| # | 机制 | 领域 | 判定 |
|---|---|---|---|
| ⑨ | 质量—时间机会约束放松 | 概率规划 | 中可能；安全边界只随温度均值变化 ⇒ 规则化 |
| ⑩ | 非马尔可夫承诺历史的信息瓶颈压缩 | 信息论 | 中低；若最优压缩 = 剩余容量+温区计数则无增益 |
| ⑪ | 状态依赖 Gittins/Whittle 索引**族** | 排队论 | **通常规则化**；索引与 `r_i/w_i` 相关系数 > 0.98 即止损 |
| ⑫ | 大偏差重要采样 + 双重稳健离线评估 | 极值统计 | **偏评估工具**，但项目正是被"代理迁移失败"困住 ⇒ 应作为基础设施 |
| ⑬ | Sinkhorn / 熵正则最优传输 | 最优传输 | 若 ε 固定则是更快的运输求解器；只有 ε 随未来到达不确定性自适应、输出可学习双势才可能突破 |
| ⑭ | 反应扩散 / 图灵斑图 / 斑块边界 | 系统化学 / 生态 | 本质仍是空间索引+容量规则；除非密度波传播速度与车辆返回时间形成非平衡稳态 |
| ⑮ | 多巴胺奖励预测误差门控重构 | 神经科学 | 与 ⑧ 高度重叠，并入 ⑧；**神经科学名字不能当性能证明** |
| ⑯ | 模拟退火 / 蚁群信息素 / Hopfield 能量 | 统计物理 / 群体智能 | **大概率退化为搜索启发式**。MaskCO 已提供掩码重构，再叠加退火/信息素不产生新信息壁垒。**只作对照，不作主创新** |

### 3.4 更"不相关"的联想池（保留，供选题枯竭时取用）

| 领域 | 原始思想 | 冷链联想 | 直觉价值 |
|---|---|---|---|
| 交通信号绿波带 | 相位对齐使车队连续通过 | **dispatch wave 的相位对齐**：让返仓/出发与订单揭示节奏共振，减少空驶等待 | 中 |
| 音乐节奏与切分 | 节拍错位制造张力 | 故意错开 epoch 边界与 reveal 高峰，把"必须立即决策"的压力平滑 | 低（难形式化） |
| 传染病 R0 阈值 | 传播阈值决定爆发 | **品质阈值传播**：一单超温是否污染同舱其他单（共载热泄漏），存在临界装载率 | 中高（可建模） |
| 通信网络拥塞控制 | AIMD 与带宽探测 | 车队"探测"需求：小步扩张服务半径，遇超时则乘性收缩 | 中 |
| 经济学最优税收 / 价格歧视 | 按弹性差别定价 | **按 EDoD 弹性差别定价**：宽松窗口的订单收低价（延迟服务），紧窗口收高价 | 中 |
| 生态最优收获 | 最大可持续产量 | 制冷预算的"可持续开采率"：不让当日能耗透支后续温区能力 | 中 |
| 免疫网络亲和力成熟 | 体细胞高频突变 + 选择 | LNS 的 destroy 集合按"亲和力"（历史改进贡献）自适应 | 中低 |
| 地貌学 / 最小能耗河流网络 | 最优输运网络自组织 | 服务区域的 Voronoi 边界随订单密度自组织（与 ⑭ 相关） | 低 |

### 3.5 整合架构：一条主链路，不是 16 个模块堆叠

```
订单揭示
  ↓  [到达过程预测 + 极值尾部]  →  Ŝ(t+H)
  ↓  [温区×空间×时间 λ 场]      →  λ_{k,z,t}   （候选 ①）
  ↓  [分数松弛 + 紧性感知 OCRS]  →  接受集合     （候选 ②）
  ↓  [拒因特定保形风险控制]      →  阈值校准     （候选 ③）
  ↓  [冻结 MaskCO 掩码重构]      →  只重构未锁定且可修改的变量
  ↓  [质量—能量 tube / 机会约束] →  温控、派车、回仓（候选 ④⑦）
  ↓  [残差门控 / 信息瓶颈]       →  何时值得重构、历史压缩（候选 ⑧⑩）
执行 → 事件日志 → 反演测试 → 判定 → README/GitHub → 下一假设
```

**防两类误判必须同时做**：
- **防止"学习器只是记住未来统计"**：禁未来特征、重放真实到达时间戳、按日簇留一法。
- **防止"学习器只是复现简单规则"**：样本外决策树反演 + 局部线性近似 + 特征消融 + **受限策略类比较**。
只做前者只能说明没作弊，不能说明突破规则。

---

## 4. 创新点提案：三个候选 + 选型决策树

### 4.1 创新点 I-1｜因果冷链路由的信息价格（理论骨，**首选**）

**Central claim**：在严格因果信息下，冷链在线路由的可获得余量可以且必须被分解为「未来信息的价格」与「规则可捕获之后的剩余余量」；在若干参数化到达/时间窗结构下，前者主导且**不存在有限竞争比**。

**最小可发表包（五件）**
1. 形式化 strict-online：事件定义、reveal/commit 时间线、特征白名单与黑名单、品质与能耗 ODE、硬约束、目标、四类 oracle（clairvoyant-OPT / clairvoyant-feasible / causal-optimal / rule）。
2. **两个参数化 impossibility 构造**：(a) 请求仅在自己时间窗起点揭示 ⇒ 无有限竞争比（类比 Chawla & Christou, *Online Time-Windows TSP with Predictions*, APPROX/RANDOM 2024，该文证明无预测时无有限 competitive ratio、有预测时可得关于网络直径的对数竞争比且常数因子内紧）；(b) 制冷预算导致不可撤销插入错误 —— 一旦错误接受某温区订单，能量预算被占用，后续任意策略都无法恢复。
3. **分解量**：`L_future = (OPT_cl − OPT_causal)/OPT_cl`，`L_rule = (OPT_causal − Rule)/OPT_causal`。只有 `L_rule` 在多个 regime 显著为正，才谈学习。
4. **规则 oracle 的最优性定理**（正面结果，与负结果配对）：在单车辆、固定路线、相同剩余时间窗、单位收益、能耗可线性化时，证明 **EDD 或 quality-density 规则最优**；再逐步加入容量、三温区、能量，并显式列出哪些假设排除了 route coupling。
5. 公开事件级评测协议 + **leak unit tests**。

**风险与对策**：最大 reviewer 风险是"下界实例太人为" ⇒ 实例族必须**参数化**并覆盖真实订单到达、温区、时间窗、车辆容量；最好用公开实例重标注或真实匿名数据。

### 4.2 创新点 I-2｜资源耦合影子价格场 + 集合承诺（引擎，**SOTA 来源**）

**Central claim**：把接拒从"逐单阈值"升级为"联合资源乘子场 + 集合级 contention resolution"，可以在不预知未来的条件下，把预算利用率缺口（实测静态规则只用到 93–99%）转化为**闭环日效用**增益，且**不会比强规则更差**（no-regret-to-rule）。

**最小可发表包（五件）**
1. 把完整问题降维成「订单接受 — 车辆匹配 — 局部插入」的 BwK / online matching 框架。
2. **一个可验证的 regret 上界**：目标形式 `Õ((md+1) log T / Δ)`（m = 候选/车辆数，d = 资源数），或分布未知时 `Õ(√T)`；由 LP 对偶间隙 + UCB 集中不等式 + 可行 oracle + budget 不变式共同完成。**不得直接照搬 Li et al. (ICML 2021) 的 BwK bound 当本项目定理**。
3. 规则 oracle 的可行性、预算不超支与性能下界。
4. 学习器在分布未知时的次线性 regret，且相对"始终用规则"具有 **no-regret-to-rule**。
5. **预测/学习模块在预测错误时不比 robust rule 差**（consistency + robustness + 平滑退化）。

**这就是把 +38 的代理增益迁移到日效用的机制**：λ 场解决"预算没用满"，OCRS 解决"逐单接受破坏集合可扩展"，拒因保形解决"阈值没控制真正的拒因风险"。三者结构互补，不是同一机制改名。

### 4.3 创新点 I-3｜CC-DVRP-3T 严格因果基准（承载，fallback 也是成果）

**最小可发表包**：≥3 类生成器/真实化订单流；2 个公开基准的重新形式化；clairvoyant / causal / rule / learned 四类策略；能耗、品质、延迟、碳排、车辆使用、超时、不可行率、尾部分位数、**per-decision CPU 时间**；泄漏扫描；可复现 leaderboard。
**风险**：会被质疑"没有方法贡献" ⇒ 必须至少提出一个 **causal evaluation metric**、**policy class separation** 或 **benchmark design principle**，而不只是代码仓库。

### 4.4 选型决策树（每周评审用）

```
跑完反演测试 + 三列 oracle 后：
├─ L_rule 显著为正（>2%）且 λ 场闭环 ΔU ≥ 1.5%（≥8/10 日）
│    └─ 主推 I-2（引擎）+ I-1（理论骨）+ I-3（承载）→ 顶会主稿 + 顶刊姊妹稿
├─ L_rule 显著为正，但 λ 场/OCRS 均未迁移到闭环
│    └─ 主推 I-1 + I-3；I-2 降级为"已排除的机制族"（这本身是有价值的负面证据）
└─ L_rule ≈ 0（规则 oracle 已逼近 causal 最优）
     └─ 主推 I-1（不可能性 + 规则最优性定理）+ I-3；
        绝不改写成方法论文
```

---

## 5. 文献采购单（必须下载并按用途归档）

> 存放位置遵守仓库规则：PDF 放 `C-VRP_Cold-chainVehicleRoutingProblem/docs/论文参考/<分类>/`，并在 `docs/02_参考文献/README.md` 登记一行（标题、年份、用途、相对路径）。
> **标注「待核实」的条目：下载前必须先用 arXiv/DOI 检索确认编号存在且标题匹配；严禁按记忆补全编号。**

### 5.1 A 组 · 理论骨架（I-1/I-2 的承重文献，优先下载）

| # | 文献 | 出处 / 编号 | 用途 |
|---|---|---|---|
| A1 | Chawla & Christou, *Online Time-Windows TSP with Predictions* | APPROX/RANDOM 2024（**编号待核实**） | **不可能性 + learning-augmented 三段式的模板**，I-1 的直接类比对象 |
| A2 | Immorlica et al. / Li et al., BwK 的 primal-dual 对数 regret | ICML 2021（BwK 奠基：Badanidiyuru et al. 2013；primal-dual：ICML 2021，**具体编号待核实**） | I-2 主定理工具箱 |
| A3 | Feldman, Svensson, Zenklusen, *Online Contention Resolution Schemes* | SIAM J. Comput. / 2016（**卷期待核实**） | OCRS 主文献 |
| A4 | Karp, Vazirani, Vazirani, *An Optimal Algorithm for On-line Bipartite Matching* | STOC 1990 | RANKING `1−1/e`，规则最优性标杆 |
| A5 | Nemhauser, Wolsey, Fisher, *An analysis of approximations for maximizing submodular set functions—I* | Math. Program. 14:265–294, 1978 | 次模 `1−1/e` |
| A6 | Edmonds, *Matroids and the greedy algorithm* | 1971 | 拟阵贪婪最优性 |
| A7 | Baligács, Disser, Mosis, Weckbecker, LAZY dial-a-ride 紧竞争比 | SIDMA 2026（一般度量 2.457 / 半直线 2.366，**编号待核实**） | "提新策略并证明紧性"是成熟路径的证据 |
| A8 | Prophet inequality / prophet secretary 系列（0.632 / 0.641 / 0.672 / 0.688） | 经典 + 近年（**逐篇核实**） | 接受—拒绝简化模型的引理 |
| A9 | Learning to Branch with Tree MDPs | NeurIPS 2022, arXiv:2205.11107 | 混合范式模板 |
| A10 | Learning LNS Policy for IP | NeurIPS 2021, arXiv:2111.03466 | 混合范式模板 |
| A11 | Adaptive Bandit Algorithms for Contextual Matching Markets | ICML 2026（**编号待核实**，目标是 stable matching regret，**不可直接套用**） | 边界参照 |

### 5.2 B 组 · 保形与风险控制（I-2 阈值校准）

| # | 文献 | 出处 | 用途 |
|---|---|---|---|
| B1 | Vovk, Gammerman, Shafer, *Algorithmic Learning in a Random World* | Springer 2005, DOI 10.1007/b106715 | 保形基础 |
| B2 | Angelopoulos, Bates et al., *Learn then Test: Calibrating Predictive Systems to Arbitrary Data-Dependent Group Losses* | NeurIPS 2021, arXiv:2110.01052 | 风险可控预测集 |
| B3 | 保形风险控制 / risk-controlling prediction sets 系列 | 2022–2025（**逐篇核实**） | 拒因特定阈值 |
| B4 | Dembo & Zeitouni, *Large Deviations Techniques and Applications* | Springer 2/e | 大偏差工具 |
| B5 | Rubinstein, *Optimization of computer simulation models with rare events* | EJOR 99(1):89–112, 1997 | 交叉熵 / 重要采样 |

### 5.3 C 组 · 冷链与多温区（领域合法性 + 参数依据）

| # | 文献 | 出处 | 用途 |
|---|---|---|---|
| C1 | Hülagü et al., *An Exact Algorithm for the VRP with Time Windows and Perishable Products* | Transportation Science 2026（**编号待核实**） | 精确算法标杆，可解 100 客户；温度/行程/停靠/载荷耦合到品质 |
| C2 | Lin et al., *Vehicle routing in precooling logistics with dynamic temperature-dependent product quality decay* | EJOR 2025, DOI 10.1016/j.ejor.2024.09.041 | 预冷 + 动态品质，QTDD-ALNS |
| C3 | Stellingwerf et al., quality-driven VRP（Arrhenius 嵌入路径模型） | IJPE 2021 | 品质应进入状态与约束的论据 |
| C4 | MC-VRP-T（路线 + 车辆目标温度联合优化） | TR-C 2026, DOI 10.1016/j.trc.2026.105822 | 温区兼容 + 车辆温度联合决策，可达 100 客户 |
| C5 | Basso et al., *Electric VRP with machine learning for energy prediction* | TR-B 2021 | 能耗方差 + 机会约束 |
| C6 | 食品动力学参数（Arrhenius A_k、E_k、鱼货感官阈值）原始文献 | 已在本仓库 `docs/02_参考文献/` 品冷车热力学 8 篇中（**先盘点再补**） | 参数校准依据 |

### 5.4 D 组 · NCO 与基线（SOTA 对照的方法论文献）

| # | 方法 | arXiv / 出处 | 用途 |
|---|---|---|---|
| D1 | MaskCO | ICLR 2026（本仓库上游 `MASKCO_code/`） | 骨架，不改 |
| D2 | POMO | arXiv:2010.16011 | 构造式基线 |
| D3 | Sym-NCO | arXiv:2205.13209 | 对称性基线 |
| D4 | LEHD | arXiv:2310.07985 | 轻量解码 / 跨规模 |
| D5 | NeuOpt | arXiv:2310.18264 | 柔性 k-opt 改进搜索 |
| D6 | DIFUSCO | arXiv:2302.08224 | 扩散 heatmap（TSP-10k gap 2.58%，**注意是 TSP 口径**） |
| D7 | RRNCO（真实路由） | ICLR 2026, arXiv:2503.16159 | 非对称距离/时长，真实基准 |
| D8 | BQ-NCO | NeurIPS 2023（**编号待核实**） | 商 MDP / 最优性保证 |
| D9 | CAMP | AAMAS 2025（**编号待核实**）, github ai4co/camp | 多画像路由 |
| D10 | Vidal, *Hybrid Genetic Search for the CVRP* | arXiv:2012.10384 | **质量标尺：0.11% BKS gap** |
| D11 | Baty et al., *CO-Enriched ML for DVRPTW* | Transportation Science 2024（竞赛第一） | 动态 VRP 混合范式标杆 |
| D12 | FrontierCO / ML4CO-Bench-101 | ICLR 2026 / NeurIPS 2025（**编号待核实**） | benchmark 设计原则 |

### 5.5 下载执行脚本（可直接跑）

```bash
# 在仓库根执行；PDF 落到 docs/论文参考/<分类>/
python tools/fetch_papers.py --manifest docs/02_参考文献/download_manifest.yaml \
    --out "C-VRP_Cold-chainVehicleRoutingProblem/docs/论文参考" \
    --verify-title            # 标题不匹配即拒绝落盘（防编号错配）
```

`download_manifest.yaml` 字段：`id / title / arxiv_or_doi / category / purpose / verified(bool)`。**`verified: false` 的条目必须先核实再下载**，脚本在 `--verify-title` 下会拒绝未核实条目。

---

## 6. 代码采购单（必须 clone 并按协议归档）

> 落点：`CC_Compare/<method>/`，只改各自的 `dcc_vrp/` 适配层；每个仓库保存 `SHA / lockfile / checksum / license` 快照。
> **许可证红线**：LKH-3 为学术研究用途（商用需授权）；部分 HGS-2012 / SISR 实现协议不明 ⇒ **不得**假设可再分发。论文实验允许 ≠ 代码允许再分发。

### 6.1 第一组：非学习强基线（**必须先跑通，否则后面所有 SOTA 说法都无效**）

| 优先级 | 仓库 / 入口 | 协议 | 回答什么 | 算力 |
|---|---|---|---|---|
| 1 | `https://github.com/vidalt/HGS-CVRP` | MIT | 中等规模静态与 rolling 质量上限（**0.11% BKS gap 的来源**） | C++ CPU，`-t` 设时间上限 |
| 2 | LKH-3（Keld Helsgaun 官方页） | 学术研究用途 | 经典 VRPTW/CVRP 高质量解、初值与重启 | CPU，单实例可调时间 |
| 3 | OR-Tools Routing（Apache-2.0） | Apache-2.0 | 工程可行性、约束扩展速度、GLS/ALNS 对照 | CPU |
| 4 | PyVRP / VRPLib 生态 | MIT | Python 内嵌 HGS，**最推荐用于自定义冷链目标** | CPU |
| 5 | SISR / FILO（`https://github.com/acco93/filo`, `filo2`） | FILO: GPL-3.0；FILO2 待核 | 与 HGS 拉开专用启发式差距（SISR 0.19% / FILO 0.20%） | CPU |
| 6 | EURO-NeurIPS 2022 quickstart（`ortec/euro-neurips-vrp-2022-quickstart`） | 待核 | 事件流、controller、评价协议；含 `hgs_vrptw` | CPU + 单 GPU 容器 |

### 6.2 第二组：动态基线（自建，无现成仓库）

| 基线 | 说明 | 落点 |
|---|---|---|
| Greedy / First-Fit / Cheapest-Insertion | 无学习 online policy 下限 | `CC_Compare/rules/` |
| **Regret-2 insertion + rolling reoptimize** | regret-2 = "立即派送 i" 与"等待并合并更优插入位置"的代价差；**本项目最关键的中间基线** | `CC_Compare/rolling_regret2/` |
| **LNS with destroy/repair（保留 accepted 前缀）** | 承诺边界下的局部搜索 | `CC_Compare/lns/` |
| **Clairvoyant HGS / LKH3** | 未来信息上界与 regret 分母 | `CC_Compare/clairvoyant/` |

### 6.3 第三组：学习基线（在第一组跑通后再引入）

| 基线 | 仓库 | 备注 |
|---|---|---|
| RL4CO / AM / POMO | `github.com/ai4co/rl4co` 等 | 构造式 vanilla；单张 24GB GPU 可训 |
| LEHD | `github.com/CIAM-Group/NCO_code` | 跨规模构造 |
| GLOP | `github.com/henry-yeh/GLOP` | Python 3.8 / PyTorch 1.13，有 checkpoint |
| NeuOpt | `github.com/debnath-d/NeuOpt` | MIT，Python 3.10 / PyTorch 1.13，需 GPU |
| DACT / BQ-NCO | `github.com/naver/bq-nco` 等 | 依赖逐版本核验 |
| RRNCO | `github.com/ai4co/real-routing-nco` | 代码/数据/权重齐全，工程优先级高 |
| DIFUSCO / T2TCO | `Edward-Sun/DIFUSCO`、`Thinklab-SJTU/T2TCO` | 需 GPU；**建议先冻结扩散器只做候选弧重排序**，不建议直接把未投影采样当结果 |

### 6.4 采购检查清单（clone 后逐项打勾）

- [ ] `git rev-parse HEAD` 记入 `CC_Compare/<method>/PROVENANCE.md`
- [ ] LICENSE 文件存在且已记录；GPL/学术用途的标红
- [ ] `requirements.txt` / `environment.yml` 存在；Python 与 PyTorch/CUDA 版本记入
- [ ] 预训练 checkpoint 可下载且 sha256 已记录
- [ ] 能跑通 1 个最小实例（`smoke` 脚本 + 日志归档）
- [ ] 与本项目 fleet executor 共用同一超时 fallback 与事件流

---

## 7. 代码改造方案

> 硬不变量不变：永不修改 `MASKCO_code/`；扩展子目录不放 `__init__.py`（走 `sys.path.insert`）；strict-online 用 `coord_normalize_visible`；`distance_cost` 恒为纯距离、冷链复合目标用 `coldchain_cost`；`COMPUTE_FILES` 15 个哈希一致才可续跑；数据角色按 seed 不相交（DEV-CAL 777 / DEV-PROTO 7781 / DEV-GATE 7782 / VAL128 / TEST）。

### 7.1 新增目录（全部在 `C-VRP_Cold-chainVehicleRoutingProblem/` 下）

```
scripts/
├── bench/                        # 【新】CC-DVRP-3T 基准
│   ├── cc_dvrp3t_gen.py          # 实例与事件流生成器
│   ├── regimes.py                # 三个 regime 的参数化定义
│   ├── roles.py                  # seed 角色划分（CAL/PROTO/GATE/VAL/TEST）
│   └── verify_no_future.py       # 泄漏扫描：AST + 运行时快照双重证明
├── admission/                    # 【已有】接拒控制器（阶段 0 已完成）
│   ├── controller.py             # 纯函数层
│   ├── policies.py               # 静态 λ / 固定阈值 / BwK 对偶 / 预算曲线
│   ├── price_field.py            # 【新】λ_{k,z,t} 影子价格场
│   ├── fractional_lp.py          # 【新】分数松弛（LP / 最小成本流）
│   ├── ocrs.py                   # 【新】紧性感知在线 contention resolution
│   └── conformal.py              # 【新】拒因特定保形风险控制
├── evaluation/
│   ├── run_rule_inversion.py     # 【新】决策反演测试（合入门槛）
│   ├── run_information_price.py  # 【新】L_future / L_rule 分解
│   ├── run_cc_dvrp3t.py          # 【新】统一评测入口（12 条基线共用）
│   └── run_admission_offline_regret.py  # 【已有】接拒层离线对照
├── fleet/
│   ├── executor.py               # 【新】统一车队执行器（所有策略共用）
│   └── fallback.py               # 【新】超时 fallback（固定，不得因策略而异）
└── tests/
    ├── test_rule_inversion.py
    ├── test_price_field.py
    ├── test_ocrs.py
    ├── test_conformal.py
    ├── test_leak_taxonomy.py     # 【新】8 类泄漏的 unit test
    └── test_budget_invariant.py  # 【新】budget 不变式
```

### 7.2 逐模块改造说明

| 模块 | 改造内容 | 验收 |
|---|---|---|
| `cc_dvrp3t_gen.py` | 客户位置抽自 Solomon 分布；服务窗口沿用标准生成；温区按先验分配；reveal_time 服从指定到达过程（含 Poisson / Hawkes / burst 三种）；品质参数取自已发表食品动力学；C0 由车型+环境温度+温区决定。**同时输出静态 oracle 实例与动态事件流** | 同 seed 重跑逐字节一致；`verify_no_future.py` 通过 |
| `price_field.py` | λ 从标量升级为 `λ[k][z][t]`；更新频率可配（每事件 / 每 15 min）；窗口 H 内 LP、窗口外续值代理；`μ_q`、`μ_e` 沿 Arrhenius 与 `ė` 反向传播 | 单元测试：退化到单温区单区域时与原静态 λ 逐位一致 |
| `fractional_lp.py` | 分数松弛 `max E[Σ r_i x_i]`，约束含容量/窗口/能量；输出 `p_i` | LP 解与 clairvoyant LP 上界的差被记录（松弛间隙） |
| `ocrs.py` | 边/匹配/资源 CRS 三档；`B(S)` 可扩展性判定；**记录 selectability 实测值并与 0.344/0.474/0.5 理论界对照** | 可行性违规率不上升；随机接受不得只增加低价值订单 |
| `conformal.py` | 四类拒因分数 `s_1..s_4`；交换性检验先行；阈值随 t 与 b_t 变化；日频风险约束 | 交换性检验通过；组间覆盖率差 < 5pp |
| `executor.py` | 所有策略共用同一执行器、同一 epoch deadline、同一 fallback。杜绝"HGS 在 epoch 内搜 10 秒、学习器只计一次前向" | 对同一事件流，任何策略的执行轨迹可完全重放 |
| `run_rule_inversion.py` | 在在线可见特征上训练树/线性模型拟合策略决策；输出 AUC + 效用损失 | **AUC > 0.98 且效用损失 < 5% ⇒ 该策略判为规则可捕获，禁止作为创新点** |
| `run_information_price.py` | 跑四类 oracle，输出 `L_future`、`L_rule`、尾部分位数、failure case | 逐 regime 分行；不得跨 regime 平均掩盖 |
| `test_leak_taxonomy.py` | 8 类泄漏：future order / oracle / state / normalization / training / replay / energy / quality。**每类一个可检测的变量或函数审计** | 8/8；失败即 `BLOCKED` |

### 7.3 泄漏分类学（必须写成可执行 unit test，不能只是文档一句话）

| 类型 | 定义 | 检测方式 |
|---|---|---|
| future order leakage | 同一 batch 内排序/索引/全部 reveal_time 泄漏 | 静态 AST + 运行时快照：决策时刻可见集合断言 |
| oracle leakage | 训练目标直接用最优解端到端学习 | 训练目标构造函数的输入白名单 |
| state leakage | 路线状态中保留未来停靠信息 | 状态张量字段白名单 |
| normalization leakage | 跨未来实例计算统计量 | 断言只用 `coord_normalize_visible` |
| training leakage | 未来 episode 进入 validation | 角色划分断言（seed 不相交） |
| replay leakage | 修复 infeasible 动作时使用完整轨迹 | replay 缓冲区截断断言 |
| energy leakage | 用最终温度反推中间决策 | 能耗状态只含截至 t 的积分 |
| quality leakage | 用最终 Arrhenius 残值预测当前决策 | 品质状态只含截至 t 的积分 |

### 7.4 与 MaskCO 的接入方式（不改上游）

- 冻结的 `DynamicColdChainModel` 编码器 + 已有 `score_fn` 保持不变。
- 新增机制只作用于三处接口：**接受集合（admission）**、**候选插入集合（insertion candidates）**、**重构触发（何时调 MaskCO）**。
- 接口契约：`admission.decide(state, candidates) -> accept_set`；`candidates.select(state, pool) -> subset`；`trigger.should_reconstruct(state, residual) -> bool`。三者都可被替换为纯规则实现（用于 ablation 与 fallback）。

### 7.5 Git 交付纪律（沿用，不得绕过）

```bash
# 每完成一件独立工作就提交；两个分支保持同步；只允许 fast-forward；行尾冻结
python tools/git_deliver.py --message-file <msg.txt>
python tools/git_deliver.py --message-file <msg.txt> --paths <p1> <p2>
python tools/git_deliver.py --check-only
```

红线：绝不 `--force`；排除幽灵子模块 `CC_Compare/MAPT_code`；预提交密钥扫描命中即 REFUSED（返回码 4），`--skip-secret-scan` 仅经复核例外；**绝不静默跳过 push**。失败尝试与旧版本逐字节留存，不得把 FAIL 改写成 PASS。

---

## 8. 实验设计

### 8.1 基准：CC-DVRP-3T-Bench

| Regime | 来源 | 规模 | 用途 |
|---|---|---|---|
| R1 合成参数化 | `cc_dvrp3t_gen.py` 全参数可控 | 客户池 100 / 250 / 500 | 精细统计与理论验证 |
| R2 公开实例重标注 | Solomon C1/R1/RC1 + Gehring–Homberger 重标注温区与品质参数 | 200–1000 | 与社区可比 |
| R3 真实化事件流 | EURO-NeurIPS ORTEC 实例改造为 pickup-to-depot | 200–900，5–9 epoch | 现实到达结构 |

**每个 regime × 5 个动态度 × 30 天 = 450 个日级 episode**（主表规模）。动态度指标同时报告：`n_d`、`n_tot`、`δ = n_d/n_tot`、`δ^e = (1/n_tot)Σ t_i/T`、带时间窗的 `δ^e_TW`、订单揭示过程熵、平均 reaction time、EDoD 分布、温区到达过程。**不要**把"出现晚"和"必须马上服务"合成一个标量。

### 8.2 四列 oracle 与三列口径

**四列 oracle**：`clairvoyant OPT`（知道完整未来）/ `clairvoyant feasible`（知道未来但受可行性约束）/ `causal optimal`（简化设定下可解的最优）/ `rule`（强规则 oracle）。

**三列口径**（沿用仓库既有纪律，缺一不可）：
- `candidate`：当前观察下的可行建议
- `accepted`：已承诺、不可撤销
- `closed_loop`：按事件与车队执行后的累计实际

**`candidate` 不得称为"部署"**；`distance_cost` 与 `coldchain_cost` 不得混用。

### 8.3 指标体系

| 指标 | 定义 | 用途 |
|---|---|---|
| Clairvoyant gap | `(J_online − J_oracle)/J_oracle` | 在线损失（oracle 非真正下界，须注明） |
| Rolling gap | `(J_online − J_rolling)/J_rolling` | 对比无学习重优化（**这是现实分母**） |
| Regret | `J_online − J_clairvoyant`（绝对/相对须注明） | 机会损失 |
| Competitive ratio | `sup J_online / J_clairvoyant` | 最坏情形（只能给一类实例的上界） |
| 日效用 U | 收入 − 燃油 − 拒单罚 − 品质罚 | **主指标** |
| 服务率 | 时窗内服务 / 承诺 | 区分 accepted 与 executed |
| 品质合格率 | 剩余品质超阈值的鱼货比例 | 冷链安全，须记录温度历程 |
| 能耗达标率 | 满足 C0 预算的路线比例 | 违规分硬/软报告 |
| 计算超时率 | 超 epoch deadline 的比例 | **因果公平性**，fallback 须固定 |
| 温区违规 | 不兼容共载 / 超温事件 | 分装载、运输、开门三类 |
| per-decision 时间 | 每决策 CPU/GPU 毫秒 | 帕累托曲线 |

### 8.4 统计口径（防止"均值掩盖"）

- 每个配置 **10–30 个随机种子**；报均值、标准差、**中位数**、IQR、**配对 bootstrap 95% CI**。
- 学习模型同时报 greedy / sampling / augmentation / search 四种模式；**不得用 128 采样搜索后宣称"推理快"**。
- 分组 bootstrap 按日簇分组（同一天的订单不独立）。
- **主判定用配对差**：同事件流、同种子下策略 A − 策略 B 的逐日差序列，报 `[d1..dn]` 全量 + 均值 + 正值天数。这是仓库既有纪律（A-v1 线就是这么报的），继续使用。

### 8.5 预登记模板（每次实验前必须先入库）

```
PREREG-<id>
1. 假设（一句话，可证伪）
2. 唯一变化因素（其余全部冻结）
3. 冻结身份（source_identity_sha256 + watch 清单）
4. 数据角色与 seed（不相交）
5. 分母（完整，不放宽；异常/超时/空池分列，永不在判定前删样本）
6. 判据（数值门槛 + 统计门槛；例如"10 日中 ≥8 日为正且均值 ≥1.5%"）
7. 预算（时间/调用次数/算力上限）
8. 止损规则（触发即终止，不追加第三轮）
9. 「不主张」清单
10. 反演测试承诺（跑完必须做，命中即降级）
```

七要素齐全后才执行；**先冻结后实施**：预登记先单独入库（commit），实施与测量后才写验收报告 ⇒ 判据不可能被结果反向调整。这是 Q3 线已经做到的事，继续保持。

### 8.6 三个否定性问题（必须同时回答，否则不宣称 SOTA）

1. MaskCO 系策略是否优于**相同 epoch 时间**的 regret-2 + HGS/LNS？
2. 质量提升是否以温区违规、品质损失或超时率为代价？
3. 在事件频率、规模、温区组成变化（分布漂移）时，是否仍优于 rolling HGS？

任一为否 ⇒ 论文定位改为「冷链动态 VRP 基准与强基线」，不写"泛化 NCO SOTA"。

### 8.7 结果表必须分成三张

1. **静态表**：CVRP/VRPTW 的 BKS gap、可行率、CPU 时间（同平台同时间预算）。
2. **动态表**：closed-loop cost、service level、超时率、品质合格率、能耗达标率。
3. **泛化表**：跨客户规模、跨城市分布、跨温区比例、跨 reveal process。

每张表都同时给 `(J − J_clairvoyant)/J_clairvoyant` 与 `(J − J_rolling)/J_rolling`，并报每单位时间计算量的帕累托曲线。**硬约束违规用屏障法或增广拉格朗日不等价于真正可行，必须另列硬违规数。**

---

## 9. 服务器、GPU 与抢卡

### 9.1 环境（沿用仓库既有配置，不另起炉灶）

| 环境 | 配置 |
|---|---|
| 本地 Windows / Python 3.12 | JAX 0.5.0 / Flax 0.10.4 (NNX) / optax；M0/M1 小 MLP 可 CPU 训；控制链与身份测试只需 NumPy |
| 服务器 Linux / Python 3.10.19 | conda `MASKCO_env`（jax 0.6.2 / flax **必须 0.10.4** / optax 0.2.6），2× RTX 5090；需 `jax-cuda12-plugin==0.6.2` + `nvidia-*-cu12` |
| 部署路径 | `/home/hzeng/project/ZH/MASKCO_v1/`（= `.vscode/sftp.json` 的 `remotePath`） |
| 远程执行 | `python tools/_srv.py "<cmd>"`（凭据从 `sftp.json` 读，**绝不**在命令行内联密码） |
| 上传/下载 | `python tools/_sftp_put.py <repo相对路径>` / `python tools/_sftp_get.py <repo相对路径>` |
| 长任务 | 用 `tmux`，**不要 `nohup`** |

**已知坑（必须遵守）**：flax 0.10.7 会让 `SwiGLU` 报 `'ArrayImpl' object has no attribute 'value'`；训练 `XLA_PYTHON_CLIENT_MEM_FRACTION=0.9`、推理 `0.5`；M0/M1 用 `CUDA_VISIBLE_DEVICES=1`（GPU 与他人共享），视情况 `XLA_PYTHON_CLIENT_PREALLOCATE=false`、`XLA_FLAGS=--xla_gpu_autotune_level=0`（小 MLP / batch-8 compact decoder 反而要 `unset XLA_FLAGS`）。

### 9.2 抢卡策略（有卡就用，没卡就排队）

原则：**永不阻塞主流程**。CPU-only 的基线（HGS/LKH3/OR-Tools/regret-2/LNS/CRS/保形/LP）永远可以跑，GPU 只是加速学习模块。

```bash
# tools/gpu/acquire.sh —— 返回一张空闲卡的编号，拿不到就返回 1 并写队列
#!/usr/bin/env bash
set -euo pipefail
LOCK=/tmp/dynmaskco_gpu.lock
MIN_FREE_MEM=${MIN_FREE_MEM:-20000}   # MB
MAX_LOAD=${MAX_LOAD:-0.30}
exec 9>"$LOCK"; flock -w 5 9 || { echo "another acquirer running"; exit 1; }
pick=$(nvidia-smi --query-gpu=index,memory.used,memory.total,utilization.gpu \
        --format=csv,noheader,nounits \
      | awk -F',' -v m=$MIN_FREE_MEM -v l=$MAX_LOAD '
        {free=$3-$2; if (free>=m && $4<=l*100) {print $1; exit}}')
if [ -z "${pick:-}" ]; then
  echo "$pick"
  echo "NO_GPU_FREE at $(TZ='CST-8' date '+%F %T')" >> logs/gpu_queue.log
  exit 1
fi
echo "$pick"
```

```bash
# tools/gpu/queue_run.sh —— 有卡即跑，无卡则入队由定时任务重试
#!/usr/bin/env bash
set -euo pipefail
JOB_CMD="$1"; JOB_NAME="${2:-job}"
GPU=$(bash tools/gpu/acquire.sh) || {
  echo "$JOB_CMD" >> queue/pending.txt
  echo "[$JOB_NAME] queued (no free GPU)"; exit 0; }
export CUDA_VISIBLE_DEVICES=$GPU
export XLA_PYTHON_CLIENT_MEM_FRACTION=0.9
tmux new-session -d -s "$JOB_NAME-$GPU" "$JOB_CMD; echo EXIT=\$? > logs/$JOB_NAME.exit"
echo "[$JOB_NAME] started on GPU $GPU"
```

**纪律**：同一时刻每卡只允许一个本项目会话；会话名带 GPU 编号便于回收；`logs/*.exit` 是唯一完成信号（不接受"tmux 还在"作为完成证据）。

### 9.3 断线重试与结果回收

```bash
# tools/gpu/collect.sh —— 扫描 tmux 会话退出码，回收产物，失败按退出码分类
python tools/_sftp_get.py "C-VRP_Cold-chainVehicleRoutingProblem/results/<run>/"
```

回收后必须校验：`metrics.json` 存在、行数 == 预期 episode 数、`ledger_ok == true`、身份 watch 起止一致。任一不满足 ⇒ 该 run 记 `INCOMPLETE`，**不进入统计，但保留在分母中**（沿用 L1 线纪律：分母永不放宽）。

---

## 10. 定时任务与自我迭代流程

> 本节给出完整编排表。**在你确认之前，我不会实际创建任何定时任务**；确认后按表逐条创建。

### 10.1 主循环（Loop）：假设 → 预登记 → 执行 → 收集 → 反演 → 判定 → 公开 → 下一假设

```
[1 生成] 假设池（第 3 章 16 个机制 + 3.4 联想池）按优先级取队首
   ↓
[2 预登记] 写 PREREG-<id>，七要素齐全，单独 commit 入库
   ↓
[3 执行]   CPU 部分立即跑；GPU 部分 tools/gpu/queue_run.sh 入队
   ↓
[4 收集]   结果写 metrics.jsonl（逐 episode 一行），回收校验
   ↓
[5 反演]   决策反演测试 + 单标量消融（合入门槛，不过即降级）
   ↓
[6 判定]   按预登记判据出 PASS / DOMINATED / NO-GO / INCOMPLETE
   ↓
[7 公开]   docs/04_实施与结果/ 追加记录 → README 表更新 → git_deliver 推送
   ↓
[8 复盘]   更新假设池优先级；触发止损则关闭该机制
   ↓ 回到 [1]
```

### 10.2 定时任务表

| ID | 频率 | 时间 | 动作 | 产出 |
|---|---|---|---|---|
| **T1** | 每 30 分钟 | `*/30 * * * *` | 扫描 `queue/pending.txt`，有卡即出队启动 | 队列不饥饿 |
| **T2** | 每 2 小时 | `0 */2 * * *` | 结果回收 + 校验 + 写 `metrics.jsonl` | 数据入库 |
| **T3** | 每日 | `05 02 * * *` | **抢卡高峰填充**：夜间填充次日 GPU 队列 | 队列预满 |
| **T4** | 每日 | `30 03 * * *` | 跑决策反演测试（对所有已入库策略回归） | `rule_inversion_daily.json` |
| **T5** | 每日 | `00 08 * * *` | 生成指标卡 → 更新 `README.md` 结果表 → `git_deliver` 推送 | GitHub 每日可见进展 |
| **T6** | 每日 | `30 08 * * *` | 推送日报（新增记录、PASS/DOMINATED 计数、卡时消耗、队列长度） | 日报 |
| **T7** | 每周一 | `00 09 * * 1` | 周度评审包：`L_future`/`L_rule` 曲线、12 条基线对比、止损命中清单、下周假设队列 | 周报 + 决策点 |
| **T8** | 每周日 | `00 23 * * 0` | 全量回归 + 泄漏扫描 + 密钥扫描 + 身份一致性校验 | 健康体检报告 |
| **T9** | 每月 1 日 | `00 10 1 * *` | 里程碑 Gate 评审（G1–G6），决定是否进入下一阶段 | Gate 决议 |
| **T10** | 事件驱动 | — | 新基线接入 / 新论文入库 / 反例发现 | 追加登记 |

### 10.3 各任务的契约（给调度层/Harness 的输入输出定义）

> 无论当前编排层用哪一套（DeepSeek Harness 或任何其他 harness），下表是**任务契约**，可被任何调度器驱动。每个任务只认输入、只写约定输出、只返回约定状态码。

| 任务 | 输入 | 输出 | 状态码 |
|---|---|---|---|
| `gen_instances` | regime + seed 角色 | `instances/*.yaml`, `event_stream/*.jsonl` | 0 ok / 3 校验失败 |
| `run_baseline` | 实例集 + 基线名 + 时间预算 | `results/<run>/metrics.json` | 0 / 1 超时 / 2 不可行 / 3 校验失败 |
| `run_policy` | 实例集 + 策略配置 + 冻结身份 SHA | 同上 + `identity.json` | 0 / 4 身份漂移 / 5 预算越限 |
| `invert_test` | 策略决策日志 + 可见特征 | `rule_inversion.json`（AUC、效用损失） | 0 / 6 判为规则可捕获 |
| `score_board` | 所有 `metrics.json` | `scoreboard.csv` + `README` 表格片段 | 0 / 7 数据不完整 |
| `deliver` | 变更文件列表 | commit SHA + push 结果 | 0 / 8 推送失败（必须记录确切原因） |

### 10.4 自动化红线（自动化可以做与不可以做）

**可以做**：跑实验、回收结果、算统计量、生成表格、更新 README 的结果表、推送、跑回归测试、生成日报周报、填充队列、抢卡。

**不可以做（必须留人工决策点）**：
1. **修改预登记判据**（判据先入库后执行，禁止事后放宽）。
2. **放宽分母**（异常/超时样本永不删除）。
3. **把 FAIL / NO-GO / DOMINATED 改写成 PASS**。
4. **人工批准字段代填**（`approved_by` 必须有明确的用户决策来源）。
5. **force push / 重写历史**。
6. **在未经用户确认的情况下"再给一轮机会"**（止损触发即终止）。
7. **把 `PROXY_ONLY` 的代理指标写进 SOTA 判定**。

### 10.5 状态板字段（每日自动更新到 README）

```
日期 | 当前假设 | 阶段 | 判据 | 结果(PASS/DOMINATED/NO-GO/INCOMPLETE)
L_future | L_rule | 闭环 ΔU(均值/正值天数/配对CI)
12 条基线对比（逐条：Δ / CI / 是否显著）
GPU 卡时消耗 | 队列长度 | 失败任务数
止损命中 | 下一步
```

---

## 11. 里程碑与止损

### 11.1 12 个月路线

| 月份 | 目标 | Gate | 中间可发表成果 |
|---|---|---|---|
| M1 | 冻结问题语义：写"信息合同"（事件定义、reveal/commit 时间线、特征白/黑名单、品质能耗 ODE、硬约束、目标、四类 oracle）；建 causal event bus / replay / 快照序列化 / leak audit | **G1**：8 类泄漏测试 8/8；同 seed 重放逐字节一致 | 4 页 technical report：*Strict-Online Protocol for Cold-Chain DVRP*（workshop，不投主会） |
| M2–M3 | 跑通 12 条基线（先非学习 6 条，再动态 3 条，再学习 3 条）；出 `L_future` / `L_rule` 第一版分解 | **G2**：12 条基线全部 smoke 通过；三 regime × 30 天数据齐全 | lower-bound note |
| M4–M5 | 构造参数化 impossibility 实例族（时间窗起点揭示 / 制冷预算导致不可撤销插入错误）；证明第一个定理 | **G3**：至少一个定理或可验证的竞争比上界；证明经独立复核 | theory working paper |
| M6–M7 | λ 场 + OCRS + 拒因保形 的最小对照（逐项过反演测试） | **G4**：闭环 ΔU ≥ 1.5% 且 ≥8/10 日为正，或明确记录失败并降级 | 机制对照记录 |
| M8–M9 | 只在有理论依据的模块上加入学习（accept threshold 参数化 / destroy 集合选择 / 能耗与品质预测器），每个模块独立 ablation | **G5**：no-regret-to-rule 成立；关闭学习模块后仍是合法可复现的 OR 基线 | leaderboard + baseline zoo |
| M10 | 大规模、跨分布、鲁棒性：分布漂移、arrival burst、车辆故障、温区不兼容、能耗预测误差、长尾实例 | **G6**：SOTA-1 门槛达成（≥10/12 显著为正） | 主稿实验章节 |
| M11 | 可复现资产（simulator、generator、protocol tests、Docker、leaderboard JSON、raw traces）与分轨写作 | — | 顶会稿 + 顶刊稿 |
| M12 | 投稿 | — | 保留两条延续线：预测质量驱动的 learning-augmented bounds；扩展到异构车队与碳约束 |

### 11.2 止损规则（触发即终止，不追加轮次）

| 层级 | 触发条件 | 动作 |
|---|---|---|
| 单机制 | 反演测试 AUC > 0.98 且效用损失 < 5% | 降为基线，关闭该机制 |
| 单机制 | 命中该机制的 ≥2 条失败信号（见第 3 章各条目） | 关闭，记录为"已排除的机制族" |
| 单机制 | 连续两轮 DOMINATED | 关闭，不追加第三轮（沿用 Q3 两轮止损纪律） |
| 单实验 | 分母不完整 / 身份漂移 / 预算越限 | `BLOCKED`，**永不升为 PASS** |
| 战略级 | M5 结束仍无任何定理 | 放弃 I-1 主推地位，主稿改投 I-3（Datasets & Benchmarks） |
| 战略级 | M9 结束仍无任何机制迁移到闭环 | 主稿改为 impossibility + protocol + benchmark；**明确禁止**改写成方法论文 |

### 11.3 单机制止损计数板（每次评审必须更新）

```
机制① λ场          轮次 0/2  DOMINATED 0  失败信号 0/5   状态 ACTIVE
机制② OCRS         轮次 0/2  DOMINATED 0  失败信号 0/4   状态 ACTIVE
机制③ 拒因保形      轮次 0/2  DOMINATED 0  失败信号 0/4   状态 ACTIVE
机制④ tube         轮次 0/2  DOMINATED 0  失败信号 0/3   状态 QUEUED
...
```

---

## 12. 风险、诚实边界与质量红线

### 12.1 必须写在每一份记录里的「不主张」清单

- 所有结果均为**自测的工程/机制证据**，不是论文级结论（除非通过预登记 + 独立复核 + 完整分母）。
- `candidate` / `accepted` / `closed_loop` 三列不可混用；`candidate` 不得称"部署"。
- `distance_cost` 恒为纯距离；冷链复合目标另用 `coldchain_cost`；两者不得互相替代。
- `PROXY_ONLY` 的接拒层数字不得进入 SOTA 判定。
- 过期的 `项目当前状态.md` 顶部旧条目按**时间快照**理解。
- **不得**写"整套历史测试通过"：既有失败（`test_q3_door_interval_thresholds.py` 的 ERR-12、`test_m1b_q2_certification.py` 的 `omega10_initialization`）必须如实列为 `PRE_EXISTING_FAILURE_UNCHANGED`。
- **不得**写"encoder 不可迁移""recon 有害""capacity 已被排除"—— 现有证据只支持"current recipe 失败"。

### 12.2 SOTA 相关红线

1. **不得偷换对照**：只报"优于 AM/POMO"不算 SOTA；必须报与 regret-2 + HGS/LNS 的同 epoch 时间对照。
2. **不得偷换时间**：HGS 在 epoch 内搜 10 秒、学习器只计一次前向 —— 这是不公平对照，必须同 deadline。
3. **不得偷换分母**：clairvoyant 是上界不是"被超越对象"；rolling baseline 才是现实分母。
4. **允许失败**：若最终 12 条中只有 9 条显著为正，就写 9 条；**不要**为了凑 10 条去改判据。
5. **允许一两个超过我们**：这是正常科学结果，写进论文反而增强可信度。

### 12.3 关于"方法性论文"的最终判断标准

三条朴素判据，写稿前逐条自问：

- **删掉神经网络后论文仍成立吗？** 成立 ⇒ 不要伪装成学习方法论文。
- **删掉定理后只剩实例结果吗？** 是 ⇒ 不要声称理论贡献。
- **删掉未来信息后学习失效吗？** 是 ⇒ **这不是缺陷，这是最重要的被证明事实**。

只有当学习在 causal policy、强规则、分布漂移、预测误差四重压力下**稳定改进**，并且能关闭成纯 OR fallback，才值得把 learning 放进标题。

### 12.4 若最终没有任何正增益

主稿 = **不可能性 + 协议 + 基准**。这是完整贡献，不是退而求其次。NeurIPS 2026 官方评审说明明确允许以"理解一个负结果"为主要贡献（意义与原创性门槛高）；理论论文不必用 SOTA 实验证明自己。前提是：**下界实例必须参数化且覆盖真实结构**，且**必须给出替代方案**（协议 + 基准 + 可检验判据）。

---

## 附录 A · 立即执行清单（今天起 7 天，可直接复制）

```bash
# D1 生成器
mkdir -p "C-VRP_Cold-chainVehicleRoutingProblem/scripts/bench"
# 实现 cc_dvrp3t_gen.py / regimes.py / roles.py / verify_no_future.py
python scripts/bench/cc_dvrp3t_gen.py --regime R1 --n 100 --days 30 --seed-role DEV-CAL
python scripts/bench/verify_no_future.py --strict        # 必须 0 违规

# D2 拉基线（只 clone，先不动代码）
cd CC_Compare
git clone https://github.com/vidalt/HGS-CVRP hgs_cvrp
git clone https://github.com/acco93/filo2 filo2
git clone https://github.com/ortec/euro-neurips-vrp-2022-quickstart euro_neurips
git clone https://github.com/CIAM-Group/NCO_code lehd
git clone https://github.com/ai4co/rl4co rl4co
# 每个仓库补 PROVENANCE.md：HEAD SHA / LICENSE / 环境 / checkpoint sha256 / smoke 日志

# D3 反演测试（合入门槛）
python scripts/evaluation/run_rule_inversion.py --policy admission.dynamic_lambda --out rule_inv.json
# 判据：AUC > 0.98 且效用损失 < 5% ⇒ 判规则可捕获

# D4 信息价格分解
python scripts/evaluation/run_information_price.py --regime R1 --out info_price.json
# 输出 L_future / L_rule / 尾部分位 / failure case

# D5 λ 场
python scripts/evaluation/run_admission_offline_regret.py --price-field zone_space --ablation all

# D6 抢卡与回收
bash tools/gpu/acquire.sh && bash tools/gpu/queue_run.sh "<cmd>" <name>
bash tools/gpu/collect.sh

# D7 定时任务上线（确认后创建）
crontab -l > /tmp/cron.bak
cat >> /tmp/cron.bak <<'EOF'
*/30 * * * * cd /home/hzeng/project/ZH/MASKCO_v1 && bash tools/gpu/dispatch.sh >> logs/t1.log 2>&1
0 */2 * * * cd /home/hzeng/project/ZH/MASKCO_v1 && bash tools/gpu/collect.sh >> logs/t2.log 2>&1
5  2 * * * cd /home/hzeng/project/ZH/MASKCO_v1 && bash tools/gpu/fill_queue.sh >> logs/t3.log 2>&1
30 3 * * * cd /home/hzeng/project/ZH/MASKCO_v1 && python scripts/evaluation/run_rule_inversion.py --all >> logs/t4.log 2>&1
0  8 * * * cd /home/hzeng/project/ZH/MASKCO_v1 && python tools/scoreboard.py --update-readme >> logs/t5.log 2>&1
30 8 * * * cd /home/hzeng/project/ZH/MASKCO_v1 && python tools/daily_report.py >> logs/t6.log 2>&1
0  9 * * 1 cd /home/hzeng/project/ZH/MASKCO_v1 && python tools/weekly_review.py >> logs/t7.log 2>&1
0 23 * * 0 cd /home/hzeng/project/ZH/MASKCO_v1 && python tools/health_check.py >> logs/t8.log 2>&1
EOF
crontab /tmp/cron.bak
```

## 附录 B · README 结果表模板（T5 自动填充）

```markdown
### CC-DVRP-3T-Bench 主表（更新：YYYY-MM-DD ｜ regime：R1/R2/R3 ｜ 30 天 × 5 动态度）

| 策略 | 类别 | closed-loop U↑ | Δ vs rolling-HGS | 配对 95% CI | 正值天数 | 服务率 | 品质合格率 | 能耗达标率 | 超时率 | per-decision |
|---|---|---|---|---|---|---|---|---|---|---|
| Clairvoyant OPT | oracle（上界，不参与超越判定） | — | — | — | — | — | — | — | — | — |
| Rolling HGS + LNS | 非学习强基线 | | 0（分母） | — | — | | | | | |
| Regret-2 rolling | 非学习中间基线 | | | | | | | | | |
| OR-Tools GLS | 非学习 | | | | | | | | | |
| LKH-3 / HGS 静态 | 非学习 | | | | | | | | | |
| POMO / LEHD / NeuOpt | 学习 | | | | | | | | | |
| **Ours（λ场 + OCRS + 保形）** | 学习+理论 | | | | | | | | | |

口径：Δ 为同事件流同种子的**配对逐日差**；CI 为按日簇分组 bootstrap；
`candidate`/`accepted`/`closed_loop` 三列分列，本表为 `closed_loop`；
`distance_cost` 与 `coldchain_cost` 不混用；`PROXY_ONLY` 数字不进本表。
```

## 附录 C · 假设池初始优先级（供 Loop 取用）

```
P0  ① λ场（温区×空间×时间）        —— 解释"预算只用到 93–99%"
P0  ② OCRS 集合承诺                —— 解释"逐单接受破坏可扩展性"
P0  ③ 拒因特定保形                 —— 解释"阈值没控制真正拒因"
P1  ④ 质量—能量 tube               —— 解释"局部省电导致后续不可行"
P1  ⑤ 到达极值/换点                —— 解释"容量紧张的概率质量"
P1  ⑦ backpressure + 机会约束      —— 解释"跨温区压力差"
P2  ⑥ 风险—信息权衡探索            —— 基础设施（探索成本）
P2  ⑧ 残差门控重构触发             —— 基础设施（算力分配）
P2  ⑩ 承诺历史信息瓶颈             —— 基础设施（状态压缩）
P2  ⑫ 大偏差双重稳健评估           —— 基础设施（极端日可信评估）
P3  ⑨⑪⑬⑭⑮ —— 仅作对照/工具
X   ⑯ 退火/蚁群/Hopfield —— 仅作对照，不作创新
```

## 附录 D · 三份配套调研报告（素材来源）

| 文件 | 内容 |
|---|---|
| `xdomain_mechanisms.md` | 16 个跨域机制调研：来源、形式化、落点、规则可捕获判断、最小实验、失败信号、12 个月路线 |
| `sota_baselines.md` | NCO / 非学习强基线 / 冷链多温区 / 动态评测协议 / 2025–2026 顶会趋势 / 12 条基线推荐 |
| `ccfa_contribution.md` | 贡献形态分类学、突围先例、理论可行路径（BwK / OCRS / prophet / dial-a-ride）、leak taxonomy、双轨双稿、12 个月路线 |
