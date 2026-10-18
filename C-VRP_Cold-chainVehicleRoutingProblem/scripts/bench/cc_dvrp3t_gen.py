"""CC-DVRP-3T 实例与事件流生成器（总纲 §7.1 / D1）。

三温区取货回仓（pickup-to-depot）动态冷链实例：

* 客户位于单位方形（R1 随机 / R1c 聚类 / R3 爆发到达）；
* 每单有温区 `temp_class ∈ {0:18℃, 1:4℃, 2:−18℃}`、需求、时间窗；
* `reveal_time` 决定何时对策略可见（严格在线：t 时刻只能看到 reveal_time ≤ t 的订单）；
* 出厂品质按 v2 合同（fish 9 / tomato 1）、Arrhenius 参数取登记值；
* 每日能量预算 B 由"全接"轨迹推得（与登记口径一致，见 `--budget-rho`）。

产物（`--out` 下）::

    meta.json                 # regime / role / seeds / hash / 预算
    instances.npz             # coords, demands, tw_start, tw_end, service_time,
                              # temp_class, reveal_time, visible_mask
    event_stream.jsonl        # 每个订单一行：day, order, reveal_time, class, demand

**确定性**：同 (regime, n, days, role, seed) 重跑逐字节一致（见 `--hash-only`）。

用法::

    python scripts/bench/cc_dvrp3t_gen.py --regime R1 --n 100 --days 5 \
        --seed-role CAL --out data/bench/R1_CAL
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from pathlib import Path

import numpy as np

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

# ---- 登记常量（与 run_exp_reserve / coldchain_contract 一致） --------------
REV = {0: 10.0, 1: 20.0, 2: 30.0}
TARGET_C = {0: 18.0, 1: 4.0, 2: -18.0}
AMBIENT_C = 25.0
PRECOOL_K = 0.15          # kWh per unit-demand per K
HORIZON_H = 16.0
SERVICE_H = 0.05
SPEED_KMH = 30.0
KM_PER_UNIT = 20.0
# 品质 v2（v1 合同里的零阶/一阶速率，登记来源见 docs/02_参考文献）
K_EFF = {0: 2.23e-5, 1: 1.3e-3, 2: 2.23e-5}


def _softmax(w):
    w = np.asarray(w, dtype=np.float64)
    w = w - w.max()
    e = np.exp(w)
    return e / e.sum()


def regime_params(regime: str) -> dict:
    """三个 regime 的参数化定义（总纲 §8.1）。"""
    base = dict(clusters=False, burst=False, n_orders=200, jitter=0.12,
                class_probs=[[0.1, 0.3, 0.6], [0.3, 0.5, 0.2], [0.6, 0.3, 0.1]])
    if regime == 'R1':
        return dict(base, name='R1_uniform', clusters=False, burst=False)
    if regime == 'R1c':
        return dict(base, name='R1_clustered', clusters=True, burst=False)
    if regime == 'R3':
        return dict(base, name='R3_burst', clusters=False, burst=True, n_orders=200)
    raise ValueError('unknown regime %r (expect R1 / R1c / R3)' % regime)


def generate_day(rng: np.random.Generator, params: dict, n_orders: int,
                 capacity: float = 50.0) -> dict:
    """生成一天：返回与登记 dataloader 同构的数组。"""
    n = int(n_orders)
    # --- 到达（揭示时刻）：均匀 or 爆发（Hawkes-lite：泊松 + 一个高斯峰） ---
    if params['burst']:
        n_peak = int(rng.poisson(n * 0.3))
        peak_center = float(rng.uniform(6.0, 11.0))
        t_peak = np.clip(rng.normal(peak_center, 0.8, n_peak), 0.0, HORIZON_H)
        t_bg = rng.uniform(0.0, HORIZON_H, n - n_peak) if n > n_peak else np.empty(0)
        times = np.concatenate([t_peak, t_bg])
    else:
        times = rng.uniform(0.0, HORIZON_H, n)
    times = np.sort(times)[:n]

    # --- 空间：均匀 or 三个高斯簇 ---
    if params['clusters']:
        centers = np.array([[0.25, 0.25], [0.75, 0.25], [0.5, 0.75]])
        spot = rng.choice(3, size=n, p=[0.35, 0.35, 0.30])
        coords = centers[spot] + rng.normal(0.0, params['jitter'], size=(n, 2))
    else:
        coords = rng.uniform(0.0, 1.0, size=(n, 2))
    coords = np.clip(coords, 0.0, 1.0)

    # --- 温区：按空间簇的相关先验 ---
    if params['clusters']:
        spot = rng.choice(3, size=n, p=[0.35, 0.35, 0.30])
        cp = np.asarray(params['class_probs'], dtype=np.float64)
        cls = np.array([rng.choice(3, p=cp[s]) for s in spot], dtype=np.int64)
    else:
        cls = rng.choice(3, size=n, p=[0.5, 0.3, 0.2]).astype(np.int64)

    demand = rng.uniform(1.0, 3.0, n)

    # --- 时间窗：终点 = 揭示后 2–4 h；仓库截止 22:00 ---
    tw_end = np.minimum(times + rng.uniform(2.0, 4.0, n), HORIZON_H + 6.0)
    tw_start = np.zeros(n)

    # --- 组装成 (N+1) 的 depot-first 形式 ---
    coords_all = np.zeros((n + 1, 2), dtype=np.float32)
    coords_all[0] = [0.5, 0.5]
    coords_all[1:] = coords.astype(np.float32)
    demands_all = np.zeros(n + 1, dtype=np.float32)
    demands_all[1:] = demand.astype(np.float32)
    tw_start_all = np.zeros(n + 1, dtype=np.float32)
    tw_end_all = np.full(n + 1, HORIZON_H + 6.0, dtype=np.float32)
    tw_end_all[1:] = tw_end.astype(np.float32)
    service_all = np.full(n + 1, SERVICE_H, dtype=np.float32)
    service_all[0] = 0.0
    # --- burst 通道（总纲 M10 的 arrival burst 维度；也是 G1-L8 的前置）---
    # 默认关闭：BURST_RATE 未设置（或为 0）时，本段**不改变任何输出**，
    # 既有六个数据集的 dataset_sha256 逐位不变（已实测：见
    # docs/04_实施与结果/2026-10-18_G1缺口_泄漏检查5到8.md 的并列组数全 0）。
    # 打开后把一部分订单的 reveal_time 对齐到 BURST_SLOT 网格，制造"同时刻多单到达"，
    # 从而让 L8（并列到达的排列不变性）与 burst 鲁棒性测试**可判别**。
    # 注意：这是**能力桩**，尚未接 CLI / meta 身份（下一步），因此不得据此生成正式数据集。
    _burst_rate = float(globals().get('BURST_RATE', 0.0))
    if _burst_rate > 0.0:
        _slot = float(globals().get('BURST_SLOT', 0.25))
        # **不消耗 rng**：用 times 自身的小数位置做确定性挑选，
        # 这样打开 burst 不会改变 coords / demands / 其它任何抽样（已实测验证）。
        _frac = times / _slot - np.floor(times / _slot)
        _mask = _frac < _burst_rate
        times = times.copy()
        times[_mask] = np.round(times[_mask] / _slot) * _slot
    reveal_all = np.full(n + 1, 1e6, dtype=np.float32)
    reveal_all[1:] = times.astype(np.float32)
    cls_all = np.zeros(n + 1, dtype=np.int32)
    cls_all[1:] = cls
    return dict(coords=coords_all, demands=demands_all,
                tw_start=tw_start_all, tw_end=tw_end_all,
                service_time=service_all, reveal_time=reveal_all,
                temp_class=cls_all)


def visible_mask_of(reveal_time: np.ndarray, clock: float) -> np.ndarray:
    """t 时刻的可见性：1 = 已揭示（depot 恒可见）。"""
    mask = (reveal_time <= float(clock)).astype(np.float32)
    mask[0] = 1.0
    return mask


def instance_energy(dataset, day: int) -> float:
    """全接轨迹的预冷能耗（用于预算）。"""
    cls = dataset['temp_class'][day]
    q = dataset['demands'][day]
    idx = np.where(q > 0)[0]
    total = 0.0
    for o in idx:
        delta = max(0.0, AMBIENT_C - TARGET_C[int(cls[o])])
        total += float(q[o]) * PRECOOL_K * delta
    return total


def build(regime: str, n_orders: int, days: int, seed: int, rho: float = 0.6) -> tuple[dict, dict]:
    params = regime_params(regime)
    rng = np.random.default_rng(seed)
    per_day = [generate_day(rng, params, n_orders) for _ in range(days)]
    keys = ['coords', 'demands', 'tw_start', 'tw_end', 'service_time',
            'reveal_time', 'temp_class']
    dataset = {k: np.stack([d[k] for d in per_day], axis=0) for k in keys}
    energies = [instance_energy(dataset, d) for d in range(days)]
    budget = (1.0 - float(rho)) * float(np.mean(energies))
    meta = dict(regime=regime, regime_name=params['name'], days=int(days),
                n_orders=int(n_orders), seed=int(seed), rho=float(rho),
                budget_B=float(budget),
                mean_full_energy=float(np.mean(energies)),
                horizon_h=HORIZON_H, ambient_c=AMBIENT_C,
                target_c=[TARGET_C[k] for k in (0, 1, 2)],
                precool_energy_per_unit_per_c=PRECOOL_K,
                km_per_unit=KM_PER_UNIT, speed_kmh=SPEED_KMH,
                service_time_h=SERVICE_H)
    return dataset, meta


def dataset_sha256(dataset: dict) -> str:
    h = hashlib.sha256()
    for k in sorted(dataset):
        h.update(k.encode())
        h.update(np.ascontiguousarray(dataset[k]).tobytes())
    return h.hexdigest()


def write_out(out: Path, dataset: dict, meta: dict, event_stream: bool = True) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    sha = dataset_sha256(dataset)
    meta = dict(meta, dataset_sha256=sha)
    np.savez_compressed(out / 'instances.npz', **dataset)
    (out / 'meta.json').write_text(json.dumps(meta, indent=2, ensure_ascii=False),
                                   encoding='utf-8')
    if event_stream:
        lines = []
        for d in range(dataset['coords'].shape[0]):
            rt = dataset['reveal_time'][d]
            cls = dataset['temp_class'][d]
            dem = dataset['demands'][d]
            for o in range(1, rt.shape[0]):
                if dem[o] <= 0:
                    continue
                lines.append(json.dumps(dict(day=int(d), order=int(o),
                                             reveal_time=float(rt[o]),
                                             temp_class=int(cls[o]),
                                             demand=float(dem[o])))
                             )
        (out / 'event_stream.jsonl').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return meta


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--regime', default='R1', choices=['R1', 'R1c', 'R3'])
    ap.add_argument('--n', type=int, default=100, help='day 数（instances）')
    ap.add_argument('--days', type=int, default=5)
    ap.add_argument('--n-orders', type=int, default=200)
    ap.add_argument('--seed', type=int, default=None)
    ap.add_argument('--seed-role', default=None,
                    choices=['CAL', 'PROTO', 'GATE', 'VAL', 'TEST'])
    ap.add_argument('--rho', type=float, default=0.6)
    ap.add_argument('--out', required=True)
    ap.add_argument('--hash-only', action='store_true')
    args = ap.parse_args(argv)

    if args.seed_role is not None:
        from bench.roles import role_seed
        seed = role_seed(args.seed_role, args.regime)
    else:
        seed = int(args.seed if args.seed is not None else 0)

    days = int(args.days) if args.n <= 0 else int(args.n)
    dataset, meta = build(args.regime, args.n_orders, days, seed, args.rho)
    meta['seed_role'] = args.seed_role
    if args.hash_only:
        print(json.dumps({'dataset_sha256': dataset_sha256(dataset),
                          'budget_B': meta['budget_B']}, indent=2))
        return 0
    meta = write_out(Path(args.out), dataset, meta)
    print(json.dumps({'out': str(args.out), 'days': meta['days'],
                      'budget_B': round(meta['budget_B'], 6),
                      'dataset_sha256': meta['dataset_sha256']}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
