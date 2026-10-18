# 起点④落地：**burst × canonical 协议**在面板里跑通（1 天冒烟 + 5 天面板已启动）

- 日期：2026-10-18（继续迭代，第 87 轮）
- 类型：**能力落地 + 冒烟实验**
- 代码：`scripts/evaluation/run_admission_panel.py`（新增 `--burst-rate/--burst-slot/--canonical-ties`）
- 上游：[G1 达成 8/8](2026-10-18_G1达成_8of8.md)（canonical 协议）、
  [L8 环境层 FAIL](2026-10-18_G1L8_环境层FAIL.md)（修法四处）

## 1. 做了什么

此前 canonical 协议（L8 修法）只在**独立测试脚本**里验证过，面板本身还不支持；
而 bench 生成器产出的 burst 数据也不能直接喂给面板（面板用的是 A-v1 格式）。
本轮把两者接上：

1. **`--canonical-ties`**：透传到 `StrictOnlineEnv(canonical_tie_order=...)` **并**设置
   `rp.canonical_ids = True`（缺一不可，见 [L8 记录](2026-10-18_G1L8_环境层FAIL.md) §7–§8）；
2. **`--burst-rate / --burst-slot`**：在面板切片后把一部分 `reveal_time` 按
   `frac < rate` 对齐到 slot 网格（与生成器 `cc_dvrp3t_gen.py` **同一规则**：
   `max(round(t/slot)*slot, 0.5*slot)`，保证 `reveal_time > 0`）。

## 2. 1 天冒烟（GATE day 0，burst 0.30 / slot 0.25，canonical 开）

```
[burst] rate=0.30 slot=0.25 -> 64 slots aligned
failures: []
utility 1772.67  revenue 1820.0  km 473.3  served 92  feasible True  energy 708.0
```

- **无任何失败标签**（`hard_feasible=True`、能耗 708.0 ≤ 710.65、承诺/去重均无问题）；
- 64 个槽位被对齐 ⇒ 并列到达真实发生（此前六集并列数为 0）；
- 与同日**无 burst** 的控制臂（1793.89 / 461.1 km / 94 单）相比：`burst` 使 utility **−21.2**、
  里程 +12.2 km、服务 −2 单 —— 方向合理（并列到达压缩了调度自由度）。

## 3. 5 天面板已启动

`burst5_control` 与 `burst5_static`（各 5 天，burst 0.30 + canonical）已开跑，
用于给出**burst regime 下的基线**（此前所有面板都是"无并列"数据）。

## 4. 这解决了什么、没解决什么

**解决**：
- canonical 协议从"独立测试"变成"面板可用"，且**默认关闭**（旧结果逐位可复现）；
- burst 数据可以进了，且与生成器同规则 ⇒ 两套数据源（bench 与 A-v1）在 burst 语义上一致。

**没解决**：
- 5 天结果还没出，因此**不能**说 burst regime 下哪个臂更好；
- L8 在 **A-v1 + burst** 上的重放**尚未做**（现有 L8 测试用的是 bench 格式）；
  这是下一步该补的（把 `test_no_future_l8_env.py` 的数据源换成面板同款 A-v1）。

## 5. 这不能证明什么

- 单日数字（burst 控制臂 1772.67）**不是**结论：单日波动可达 ±80；
- 不证明 burst 让问题更难或更易——只说明它**改变了**结果；
- 不证明 canonical 协议对非并列数据无影响：理论上它只重排并列组，但尚未在无 burst 数据上做 A/B 对照
  （下一步：跑 1 天 `--canonical-ties` 但 `burst=0`，与控制臂对比，应**逐位相同**）。
