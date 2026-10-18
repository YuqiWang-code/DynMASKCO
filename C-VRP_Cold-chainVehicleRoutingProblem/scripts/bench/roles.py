"""seed 角色划分（总纲 §8.1 / 仓库既有数据纪律）。

角色互不相交，且跨 regime 也不相交（`regime_offset`）。任何用某个角色训练/调参的产物，
不得在另一角色上做最终判定。
"""
from __future__ import annotations

ROLE_BASE = {
    'CAL': 777,      # 校准 / 臂统计
    'PROTO': 7781,   # 原型 / 调试
    'GATE': 7782,    # 门禁面板（5 天）
    'VAL': 78128,    # 验证 128
    'TEST': 79999,   # 封存测试（未触碰）
}
REGIME_OFFSET = {'R1': 0, 'R1c': 1000, 'R3': 2000}
ROLE_ORDER = ['CAL', 'PROTO', 'GATE', 'VAL', 'TEST']


def role_seed(role: str, regime: str = 'R1') -> int:
    if role not in ROLE_BASE:
        raise ValueError('unknown role %r' % role)
    if regime not in REGIME_OFFSET:
        raise ValueError('unknown regime %r' % regime)
    return int(ROLE_BASE[role] + REGIME_OFFSET[regime])


def all_seeds() -> dict[str, dict[str, int]]:
    return {r: {role: role_seed(role, r) for role in ROLE_ORDER} for r in REGIME_OFFSET}


def role_of(seed: int) -> tuple[str, str] | None:
    """反查 (regime, role)；找不到返回 None。"""
    n = int(seed)
    for regime, off in REGIME_OFFSET.items():
        for role, base in ROLE_BASE.items():
            if n == base + off:
                return regime, role
    return None


def assert_disjoint() -> dict:
    """所有 (regime, role) 的 seed 两两不同，且没有跨 regime 撞车。"""
    seen: dict[int, str] = {}
    for regime, roles in all_seeds().items():
        for role, seed in roles.items():
            tag = '%s/%s' % (regime, role)
            if seed in seen:
                raise AssertionError('seed %d 冲突: %s vs %s' % (seed, seen[seed], tag))
            seen[seed] = tag
    return dict(n=len(seen), seeds=sorted(seen))


if __name__ == '__main__':
    import json
    print(json.dumps(dict(seeds=all_seeds(), disjoint=assert_disjoint()['n']),
                     indent=2, ensure_ascii=False))
