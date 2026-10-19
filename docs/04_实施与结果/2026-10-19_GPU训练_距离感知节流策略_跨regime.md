# GPU 训练的「距离感知 + 节流」接单策略：**跨 regime 零样本打败"在评测集上调过的"静态族**

> 类型：**GPU 训练 + 跨 regime 零样本评测**（新方向第一枪）· 第 162 轮 · 2026-10-19
> 脚本：`scripts/train/gpu_policy_search.py`（新建）；产物 `results/train/policy_r1.json`
> **GPU 取证**：`jax.devices() = [cuda:0, cuda:1]`；运行期 `nvidia-smi --query-compute-apps` 捕获到本作业
> **pid 875872**（cuda:0 **24612 MiB** + cuda:1 **508 MiB**），上一次同脚本运行为 pid **874168**（同量）。
> 同机另有他人进程（849675 等 29 GB），已区分。

## 1. 为什么换这个方向（调研结论，不是拍脑袋）

第 99–158 轮把**只按 ``revenue / e_lower`` 密度**做门槛的接单族在万天级 GPU 仿真上榨干了
（静态 ρ 扫荡 +0.27%，分时段阈值 +0.48%）。而**登记静态 λ 本身正是这一族**——它**看不见距离**，
可效用是 ``revenue − 0.1·distance_km``。也就是说：**这一族的天花板，是它自己把自己限制住了。**

跨领域调研给出的三条可用线索：

| 线索 | 出处 | 我们怎么用 |
|---|---|---|
| **GPU 批量仿真器是这类问题的第一生产力**（Mahjax 在 8×A100 上跑到 200 万步/秒） | [Mahjax (arXiv 2605.20577)](https://arxiv.org/html/2605.20577v1) | 把"日"当 batch 维，用 `lax.scan` 逐单推进、`vmap` 扫参数 → 参数搜索从 CPU 天级降到 GPU 秒级 |
| **长时序/长流程任务的序列建模**（Decision Transformer 把轨迹当序列） | [Long-Horizon Decision Making via Latent Planning](https://www.sciencedirect.com/science/article/pii/S0893608026012189)、[DT 综述](https://www.leewayhertz.com/decision-transformer/) | 把一天看成"沿揭示时间的序列"，门槛是**时间的函数**而不是常数 |
| **阈值型在线背包有竞争比理论**（Ma 等的 randomized threshold 最优） | [The Competitive Ratio of Threshold Policies for Online Unit-Density Knapsack (arXiv 1907.08735)](https://arxiv.org/html/1907.08735v3) | 门槛随时间/剩余预算变化不是"调参"，而是**有理论根据的结构** |
| **LLM/智能体用于组合优化正在爆发**（FM4CO 清单、RL+LLM agent for VRP） | [awesome-fm4co](https://github.com/ai4co/awesome-fm4co)、[RL-Enhanced LLM Agents for VRP (arXiv 2609.00859)](https://arxiv.org/html/2609.00859v1) | 下一步：把"接单+派车"做成**工具调用式 agent**（求解器即工具），先在本轮把"策略结构"这层吃干 |

## 2. 策略（4 个可训练量 → 只留 3 个，避免过参数化）

```
v_i   = rev_i − 0.1 · dist_km_i,   dist_km_i = 2·‖x_i − depot‖ · 20      （每单往返近似，km）
t̂     = clock / 16,   r = 1 − e_used / B_eff,   B_eff = 0.685·B（扣 32% 固定开销）
ρ_eff = max(0.25, ρ0 · exp(a_t·(t̂ − 0.5) + a_b·(r − 1)))
接受  ⇔  v_i / e_i ≥ ρ_eff  且  e_used + e_i ≤ B_eff
```

θ = (ρ0, a_t, a_b) 用 **ES（无梯度）在 GPU 上训**，训练集 **R1_CAL（30 天）**，训完**参数冻结**，
零样本换 regime 评测（**不重训、不重标定**）。

## 3. 结果（ES 80 代 × 群体 32，全程 GPU）

训练（R1_CAL 30 天）：

```
static(rev/e) ρ*=3.55 → utility 1086.558
ES θ = (1.738, −0.9849, −0.9706) → utility 1120.997   (+3.17%)
```

**零样本跨 regime**（5 天 GATE）：

| 评测集 | ES 策略 | 静态密度族（**在该评测集上网格最优 = 作弊上界**） | ES 增益 | 把 train-ρ 直接搬过去 |
|---|---:|---:|---:|---:|
| R1c_GATE | **1430.68** | 1419.12 | **+0.81%** | 902.25（−36.4%） |
| R3_GATE | **1143.19** | 1104.19 | **+3.53%** | 677.37（−38.7%） |
| R1_GATE | **1158.73** | 1123.25 | **+3.16%** | 709.88（−38.7%） |

两个要点：

1. **ES 打败的是"在评测集上自己调过的静态族"**——不是打败一个弱基线。这是本仓库**第一次**
   出现"新策略族 > 距离盲阈值族"的正面结果。
2. **跨 regime 不崩**：R1 训出来的 θ 直接用在 R3（另一套到达/预算口径）仍有 +3.53%；
   而"把 ρ 常数搬过去"会崩到 −38% ⇒ **真正可迁移的是"结构"（随时间下降 + 随预算收紧），不是常数**。

## 4. 边界（写死，不许含糊）

* 这是**仿真筛选器**，不是闭环结论：距离用"每单往返"近似、不建模拼趟与时间窗可行性；
  能耗只按 32% 固定开销压预算。**最终判定必须在真实闭环面板里做**（预登记见下）。
* 仿真里的"静态族"是**密度阈值**；真实环境的最强基线是**预算保留式 λ（含 reserve）**，两者不同源，
  **不能拿仿真增益换算真实增益**。
* 训练集是 R1_CAL 30 天，评测 5 天/regime：**样本小**，只能作方向性证据。

## 5. 下一步（已预登记，同一轮启动）

把 θ **冻结**后接进真实闭环，作为 `pd` 臂（`PacedDistanceReplanner`），与 control / 登记静态 λ 配对：

* 文件：`2026-10-19_预登记_GPU训练策略进闭环.md`
* 判据：`PD-LEAD` 需 `≥ static λ × 1.015` **且** ≥8/10 日为正 **且** 无 `budget_violation`/协议违规
* 预言（可被推翻）：**真实闭环会缩水到 +0.3%~+1.5%**

## 6. 未主张

不主张 SOTA（闭环未验）、不主张"GPU 仿真可替代闭环"、不主张跨 regime 结论已成立（5 天样本）、
不主张任何定理。
