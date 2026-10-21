"""
冷链数据加载器 — 扩展 CVRPTWDataloader 增加 temp_class。
输出: features (batch, nodes, 6), target (batch, pad_len), timestep (batch,)
"""

import numpy as np
from typing import Mapping


class ColdChainDataloader:
    def __init__(
        self, datasets: Mapping[str, np.ndarray],
        batch_size: int, capacity: int | None = None,
        tw_max: float | None = None,
        target_disruption=None, need_current=False,
        data_augment=0, num_workers=2,
        need_edge_feat=False,
    ):
        datasets = dict(datasets)
        required = {'coords', 'demands', 'tw_start', 'tw_end', 'temp_class', 'routes'}
        missing = required - set(datasets.keys())
        if missing:
            raise KeyError(f"Missing: {missing}")

        self.coords = datasets['coords'].astype(np.float32)
        self.opt_routes = datasets['routes']
        cap = capacity if capacity is not None else datasets.get('capacity', 50)
        self.demands_norm = datasets['demands'].astype(np.float32) / cap

        if tw_max is None:
            tw_max = float(datasets['tw_end'].max())
        self.tw_start_norm = datasets['tw_start'].astype(np.float32) / tw_max
        self.tw_end_norm = datasets['tw_end'].astype(np.float32) / tw_max
        self.temp_class = datasets['temp_class'].astype(np.float32) / 2.0  # normalize to [0,1]

        self.service_time = datasets.get('service_time',
            np.zeros_like(datasets['demands'], dtype=np.float32))
        self.has_quality_loss = 'quality_loss' in datasets
        if self.has_quality_loss:
            self.quality_loss = datasets['quality_loss'].astype(np.float32)
        self.has_energy_mat = 'energy_mat' in datasets
        if self.has_energy_mat:
            self.energy_mat = datasets['energy_mat'].astype(np.float32)

        self.batch_size = batch_size
        self.num_instances = self.coords.shape[0]
        self.steps_per_epoch = self.num_instances // batch_size
        self.target_disruption = target_disruption
        self.need_current = need_current
        self.num_workers = num_workers
        self.need_edge_feat = need_edge_feat

    def __iter__(self):
        # 修复 2026-08-26：用全局 np.random（受 np.random.seed 控制），
        # 原 np.random.default_rng() 是独立随机源，不受训练入口的 seed 控制。
        while True:
            indices = np.random.permutation(self.num_instances)
            for start in range(0, self.num_instances - self.batch_size + 1, self.batch_size):
                idx = indices[start:start + self.batch_size]
                # 6D or 7D: [x, y, demand, tw_start, tw_end, temp_class, ?reveal_time]
                feat_list = [
                    self.coords[idx],
                    self.demands_norm[idx][..., None],
                    self.tw_start_norm[idx][..., None],
                    self.tw_end_norm[idx][..., None],
                    self.temp_class[idx][..., None],
                ]
                features = np.concatenate(feat_list, axis=-1).astype(np.float32)

                timestep = np.random.uniform(0., 1., size=(self.batch_size,)).astype(np.float32)
                routes_b = self.opt_routes[idx]

                edge_mat_b = (self.energy_mat[idx] if (self.need_edge_feat and self.has_energy_mat)
                              else None)
                if self.need_current:
                    current = np.array([np.random.permutation(routes_b.shape[1])
                                         for _ in range(self.batch_size)])
                    yield features, routes_b, current, timestep
                elif self.need_edge_feat:
                    yield features, routes_b, timestep, edge_mat_b
                else:
                    yield features, routes_b, timestep
