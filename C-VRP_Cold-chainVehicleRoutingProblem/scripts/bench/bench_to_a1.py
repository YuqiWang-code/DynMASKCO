#!/usr/bin/env python
"""把 `cc_dvrp3t_gen` 的数据集适配成 `StrictOnlineEnv` 需要的 A-v1 格式。

为什么需要它（G1 环境层 L8 的前置）
----------------------------------
两套格式不兼容：

* `cc_dvrp3t_gen` 产出 `instances.npz`（coords/demands/tw_start/tw_end/service_time/
  reveal_time/temp_class），**没有** `initial_quality`；
* `StrictOnlineEnv` 吃 A-v1（`run_exp_reserve.generate_dataset` 的产物），并且需要
  `add_v2_initial_quality(dataset, contract)` 补上 `initial_quality`（v2 语义：鱼初始 9、
  番茄初始 1；缺了会被默认填 1，导致鱼被判到可售线以下）。

本模块只做**格式搬运**，不改任何数值；`--check` 做结构自检，可在不启环境的情况下验证。

诚实边界
--------
* 适配器**不**保证 bench 集与 A-v1 集同分布（那是数据集设计问题，不是搬运问题）；
  要谈"重放结论可信"，必须另外验证同分布，见 `docs/04` 的 G1 现状记录。
* 适配器**不**做 L6 预算修复；`budget` 需由调用方显式给出（来自 CAL）。

用法::

    python scripts/bench/bench_to_a1.py --npz data/bench/R1_GATE/instances.npz --check
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np


def to_a1(bench_ds: dict) -> dict:
    """bench 数据集 → A-v1 字典（逐位搬运，不做任何数值变换）。"""
    need = ('coords', 'demands', 'tw_start', 'tw_end', 'service_time',
            'reveal_time', 'temp_class')
    miss = [k for k in need if k not in bench_ds]
    if miss:
        raise KeyError('bench 数据集缺少字段: %s' % miss)
    out = {k: np.asarray(bench_ds[k]) for k in need}
    # env 用 float64/float32 都能吃，但要求 demands 为正表示"有单"
    out['demands'] = out['demands'].astype(np.float32)
    out['temp_class'] = out['temp_class'].astype(np.int64)
    for k in ('coords', 'tw_start', 'tw_end', 'service_time', 'reveal_time'):
        out[k] = out[k].astype(np.float32)
    return out


def add_initial_quality(a1_ds: dict, contract) -> dict:
    """复用仓库既有实现，避免两套 v2 语义。"""
    from coldchain_evaluator_a1 import add_v2_initial_quality
    return add_v2_initial_quality(dict(a1_ds), contract)


def check(a1_ds: dict) -> list[str]:
    """结构自检：形状一致、demand 非负、depot 行为零、initial_quality 合法。"""
    errs = []
    days = a1_ds['coords'].shape[0]
    for k in ('demands', 'tw_start', 'tw_end', 'service_time', 'reveal_time', 'temp_class'):
        if a1_ds[k].shape[0] != days:
            errs.append('%s 天数 %d != coords 天数 %d' % (k, a1_ds[k].shape[0], days))
    if (a1_ds['demands'][:, 0] != 0).any():
        errs.append('depot 的 demand 不为 0')
    if (a1_ds['demands'] < 0).any():
        errs.append('存在负 demand')
    rt = a1_ds['reveal_time']
    inner = rt[:, 1:][a1_ds['demands'][:, 1:] > 0]
    if (inner <= 0).any():
        errs.append('存在 reveal_time <= 0 的订单（会被 visibility 检查抓到）')
    if 'initial_quality' in a1_ds:
        iq = np.asarray(a1_ds['initial_quality'])
        if iq.shape != a1_ds['demands'].shape:
            errs.append('initial_quality 形状与 demands 不一致')
        if not np.isfinite(iq).all():
            errs.append('initial_quality 含非有限值')
        if (iq < 0).any():
            errs.append('initial_quality 含负值')
    else:
        errs.append('缺 initial_quality（需先跑 add_initial_quality）')
    return errs


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--npz', required=True, help='bench instances.npz 路径')
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args(argv)

    _S = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for _p in (_S, os.path.join(_S, 'coldchain'), os.path.join(_S, 'evaluation')):
        if _p not in sys.path:
            sys.path.insert(0, _p)
    from coldchain_contract import ColdChainContractV2

    bench = dict(np.load(args.npz))
    a1 = to_a1(bench)
    contract = ColdChainContractV2()
    a1 = add_initial_quality(a1, contract)
    print('days=%d orders=%d' % (a1['coords'].shape[0], int((a1['demands'] > 0).sum())))
    if args.check:
        errs = check(a1)
        print('check errors:', errs if errs else 'none')
        return 0 if not errs else 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
