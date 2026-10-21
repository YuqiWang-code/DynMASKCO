# MaskCO 静态冷链 VRP

本仓库当前只维护**静态冷链车辆路径问题（静态冷链 VRP）**：所有订单在路线规划前一次性可见，模型同时考虑容量、时间窗、温度类别和冷链质量/能耗成本。

## 代码入口

当前代码统一位于 [`models/`](models/)：

- `models/models/`：MaskCO 的 TSP/CVRP/MIS 模型实现；
- `models/static/`：静态冷链模型、CVRPTW 数据与静态路线冷链回放评估；
- `models/coldchain/`：冷链物理状态、单位和目标函数契约；
- `models/baselines/`：静态实验所需的基线实现；
- `models/data/`、`models/decoding/`、`models/training/`、`models/modules/`：数据、解码、训练和网络公共组件；
- `models/tests/`：静态代码测试。

`MASKCO_code/`、`C-VRP_Cold-chainVehicleRoutingProblem/scripts/` 和 `CC_Compare/` 不再是当前代码入口。动态在线接单、事件揭示、滚动时域和外部对比方法复现不属于当前研究范围。

## 静态问题口径

- 订单在规划开始前全部可见，不使用未来订单揭示、在线接拒或滚动重规划；
- 路线必须满足车辆容量、客户时间窗和冷链温区约束；
- 冷链评估使用 `models/coldchain/coldchain_contract.py` 与 `models/coldchain/coldchain_state.py` 的统一物理口径；
- `models/static/coldchain_evaluator.py` 提供静态路线回放和距离、能耗、质量损失、热违规及可行性统计。

## 环境

建议使用 Python 3.11，并安装项目所需的 JAX、Flax、NumPy；若运行 OR-Tools 或 PyVRP 基线，再安装对应可选依赖。上游 MaskCO 的编译扩展位于 `models/lib/`，只有运行使用该扩展的解码/优化入口时才需要编译。

```bash
python -m compileall -q models
python -m unittest discover -s models/tests -p 'test*.py'
```

## 开发约定

1. 新代码只放入 `models/`，不要恢复平行的根级模型副本。
2. 一个能力只保留一个当前实现；实验草稿和动态在线实现不纳入活动入口。
3. 静态实验需记录数据版本、模型配置、随机种子和冷链契约版本。
4. 研究说明和复现记录放入 `docs/`；根目录只保留本 README。

## 文档

静态问题定义、冷链口径、数据与复现说明位于 [`docs/`](docs/)。历史动态研究记录仍可在子目录中追溯，但不代表当前代码或研究方向。
