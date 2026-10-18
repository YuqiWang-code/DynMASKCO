"""泄漏扫描：对生成器产物做「静态 + 运行时」双重检查（总纲 §7.3 / D1）。

八类泄漏里，与**实例生成**相关的四类在这里机械检查：

1. `future order leakage` —— 任意时刻 t 的可见集合必须恰为 `{reveal_time ≤ t}`；
2. `state leakage` —— 数据集只允许白名单字段（不允许出现 routes/costs/opt_* 等"答案"字段）；
3. `normalization leakage` —— 生成器不得写跨实例的未来统计量（字段白名单 + AST 扫描）；
4. `training/replay/energy/quality leakage` —— 由下游 dataloader/训练脚本负责，
   本脚本只检查"生成器没把未来量塞进来"，并输出需要下游检查的清单。

用法::

    python scripts/bench/verify_no_future.py --data data/bench/R1_CAL --strict
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import sys
from pathlib import Path

import numpy as np

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from bench.cc_dvrp3t_gen import dataset_sha256, visible_mask_of  # noqa: E402

ALLOWED_KEYS = {'coords', 'demands', 'tw_start', 'tw_end', 'service_time',
                'temp_class', 'reveal_time'}
FORBIDDEN_TOKENS = ('opt_cost', 'opt_tour', 'opt_routes', 'routes', 'solution',
                    'future_', 'label', 'oracle', 'bks')
GENERATOR = os.path.join(_SCRIPTS, 'bench', 'cc_dvrp3t_gen.py')


def check_manual(dataset: dict) -> list[str]:
    errs = []
    keys = set(dataset.keys())
    extra = keys - ALLOWED_KEYS
    if extra:
        errs.append('state leakage: 非白名单字段 %s' % sorted(extra))
    for k in ALLOWED_KEYS & keys:
        arr = np.asarray(dataset[k])
        if not np.all(np.isfinite(arr)):
            errs.append('non-finite 值出现在 %s' % k)
    return errs


def check_visibility(dataset: dict, n_clocks: int = 9) -> list[str]:
    errs = []
    rev = np.asarray(dataset['reveal_time'], dtype=np.float64)
    horizon = float(np.max(rev[rev < 1e5])) if np.any(rev < 1e5) else 0.0
    for clock in np.linspace(0.0, horizon, n_clocks):
        for d in range(rev.shape[0]):
            mask = visible_mask_of(rev[d], clock)          # 单日 1-D
            expect = (rev[d] <= clock).astype(np.float32)
            expect[0] = 1.0
            if not np.array_equal(mask, expect):
                errs.append('future order leakage: day %d clock %.2f' % (d, clock))
                break
        if errs:
            break
    # 每个非 depot 订单都必须有有限 reveal 且 > 0
    dem = np.asarray(dataset['demands'])
    bad = [(d, o) for d in range(rev.shape[0]) for o in range(1, rev.shape[1])
           if dem[d, o] > 0 and not (0.0 < rev[d, o] < 1e5)]
    if bad:
        errs.append('reveal_time 非法（%d 个订单，例如 %s）' % (len(bad), bad[:3]))
    return errs


def check_meta(meta: dict, dataset: dict) -> list[str]:
    errs = []
    sha = dataset_sha256(dataset)
    if meta.get('dataset_sha256') != sha:
        errs.append('meta.dataset_sha256 与数据不符（%s vs %s）'
                    % (meta.get('dataset_sha256'), sha))
    if 'seed_role' in meta and meta['seed_role'] is not None:
        from bench.roles import role_of
        got = role_of(int(meta['seed']))
        if got is None:
            errs.append('seed %s 不属于任何角色' % meta['seed'])
        elif got[1] != meta['seed_role']:
            errs.append('seed 角色不符：声明 %s 实际 %s' % (meta['seed_role'], got[1]))
    return errs


def check_event_stream(path: Path, dataset: dict) -> list[str]:
    if not path.exists():
        return ['缺少 event_stream.jsonl']
    errs = []
    rows = [json.loads(l) for l in path.read_text(encoding='utf-8').splitlines() if l.strip()]
    dem = np.asarray(dataset['demands'])
    rev = np.asarray(dataset['reveal_time'])
    expect = sum(int((dem[d] > 0).sum()) for d in range(dem.shape[0]))
    if len(rows) != expect:
        errs.append('事件流条数 %d != 订单数 %d' % (len(rows), expect))
    for r in rows[:200]:
        d, o = int(r['day']), int(r['order'])
        if abs(float(r['reveal_time']) - float(rev[d, o])) > 1e-6:
            errs.append('事件流 reveal_time 与数据集不符 day=%d order=%d' % (d, o))
            break
    if any(r.get('reveal_time', 0) > 1e5 for r in rows):
        errs.append('事件流里出现未来订单')
    return errs


def check_generator_ast() -> list[str]:
    """生成器源码不得出现"答案/未来"字段名。"""
    errs = []
    src = Path(GENERATOR).read_text(encoding='utf-8')
    tree = ast.parse(src)
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            names.add(node.value)
    hits = [t for t in FORBIDDEN_TOKENS if any(t in n for n in names)]
    if hits:
        errs.append('AST 扫描命中可疑标识: %s' % hits)
    return errs


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', required=True, help='生成器输出目录')
    ap.add_argument('--strict', action='store_true', help='任一项失败即非零退出')
    ap.add_argument('--out', default=None, help='把报告写到该 JSON 路径')
    args = ap.parse_args(argv)

    root = Path(args.data)
    dataset = dict(np.load(root / 'instances.npz'))
    meta = json.loads((root / 'meta.json').read_text(encoding='utf-8'))

    checks = {}
    checks['state_whitelist'] = check_manual(dataset)
    checks['visibility'] = check_visibility(dataset)
    checks['meta_identity'] = check_meta(meta, dataset)
    checks['event_stream'] = check_event_stream(root / 'event_stream.jsonl', dataset)
    checks['generator_ast'] = check_generator_ast()

    downstream = ['training_roles_disjoint', 'replay_truncation', 'energy_state_prefix',
                  'quality_state_prefix']
    failed = {k: v for k, v in checks.items() if v}
    report = dict(stage='verify_no_future', data=str(root),
                  n_days=int(dataset['coords'].shape[0]),
                  n_orders=int((dataset['demands'] > 0).sum()),
                  checks=checks, failed=failed,
                  n_failed=len(failed), verdict=('PASS' if not failed else 'FAIL'),
                  downstream_pending=downstream)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(report, indent=2, ensure_ascii=False),
                                  encoding='utf-8')
    return 0 if not failed else (1 if args.strict else 0)


if __name__ == '__main__':
    raise SystemExit(main())
