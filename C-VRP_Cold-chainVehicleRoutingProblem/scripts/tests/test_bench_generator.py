"""CC-DVRP-3T 生成器与泄漏扫描的单元测试。

    python scripts/tests/test_bench_generator.py

T1 确定性：同 (regime, n, days, role) 两次生成 → 同一个 dataset_sha256
T2 角色 seed 两两不相交、可反查
T3 可见性：任意 clock 的可见集合恰为 {reveal_time ≤ clock}（无未来订单泄漏）
T4 事件流：条数 == 订单数、reveal_time 与数据集一致
T5 泄漏扫描：正常产物 PASS；注入一个"答案字段"后必须 FAIL
T6 预算：B = (1−rho) × 全接能耗均值，且随 rho 单调
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import numpy as np

SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from bench import cc_dvrp3t_gen as gen  # noqa: E402
from bench import roles  # noqa: E402
from bench.verify_no_future import (check_event_stream, check_meta,  # noqa: E402
                                    check_visibility, main as verify_main)


def t1_determinism():
    ds1, meta1 = gen.build('R1', 200, 2, roles.role_seed('CAL', 'R1'), 0.6)
    ds2, meta2 = gen.build('R1', 200, 2, roles.role_seed('CAL', 'R1'), 0.6)
    h1, h2 = gen.dataset_sha256(ds1), gen.dataset_sha256(ds2)
    assert h1 == h2, '同种子生成不确定: %s vs %s' % (h1, h2)
    assert abs(meta1['budget_B'] - meta2['budget_B']) < 1e-12
    print('  [PASS] T1 确定性: sha=%s… budget=%.4f' % (h1[:16], meta1['budget_B']))
    return True


def t2_roles_disjoint():
    info = roles.assert_disjoint()
    assert info['n'] == len(roles.ROLE_ORDER) * len(roles.REGIME_OFFSET)
    for regime in roles.REGIME_OFFSET:
        for role in roles.ROLE_ORDER:
            seed = roles.role_seed(role, regime)
            got = roles.role_of(seed)
            assert got == (regime, role), '反查失败 %s/%s -> %s' % (regime, role, got)
    print('  [PASS] T2 角色 seed 不相交: %d 个，全部可反查' % info['n'])
    return True


def t3_visibility():
    ds, meta = gen.build('R3', 200, 2, roles.role_seed('PROTO', 'R3'), 0.6)
    errs = check_visibility(ds, n_clocks=11)
    assert not errs, errs
    rev = ds['reveal_time']
    # 手工再验一遍：clock=H/2 时，可见订单的 reveal 必须 ≤ H/2
    clock = 8.0
    for d in range(rev.shape[0]):
        mask = gen.visible_mask_of(rev[d], clock)     # 单日 1-D
        vis = np.where(mask > 0)[0]
        vis_nz = vis[vis != 0]          # depot(0) 恒可见，不参与 reveal 断言
        assert np.all(rev[d, vis_nz] <= clock + 1e-6), '可见集合含未来订单'
        hidden = np.where(mask == 0)[0]
        if len(hidden):
            assert np.all(rev[d, hidden] > clock - 1e-6), '未可见集合含已揭示订单'
    print('  [PASS] T3 可见性: R3 2 天 × 11 个时钟点全部一致')
    return True


def t4_event_stream():
    ds, meta = gen.build('R1c', 200, 1, roles.role_seed('GATE', 'R1c'), 0.6)
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / 'run'
        meta = gen.write_out(out, ds, meta)
        errs = check_event_stream(out / 'event_stream.jsonl', ds)
        assert not errs, errs
        n_orders = int((ds['demands'] > 0).sum())
        lines = (out / 'event_stream.jsonl').read_text(encoding='utf-8').strip().splitlines()
        assert len(lines) == n_orders
    print('  [PASS] T4 事件流: %d 条 == 订单数' % n_orders)
    return True


def t5_leak_scan():
    ds, meta = gen.build('R1', 200, 1, roles.role_seed('VAL', 'R1'), 0.6)
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / 'ok'
        meta = gen.write_out(out, ds, meta)
        rc = verify_main(['--data', str(out), '--strict', '--out', str(Path(td) / 'r.json')])
        assert rc == 0, '正常产物应 PASS，rc=%d' % rc
        # 注入答案字段 -> 必须 FAIL
        bad = dict(ds)
        bad['routes'] = np.zeros((ds['coords'].shape[0], 5), dtype=np.int32)
        out2 = Path(td) / 'bad'
        out2.mkdir()
        np.savez_compressed(out2 / 'instances.npz', **bad)
        (out2 / 'meta.json').write_text(json.dumps(dict(meta, dataset_sha256='deadbeef')),
                                       encoding='utf-8')
        rc2 = verify_main(['--data', str(out2), '--strict'])
        assert rc2 != 0, '注入答案字段后应 FAIL'
    print('  [PASS] T5 泄漏扫描: 正常 PASS / 注入答案字段 FAIL')
    return True


def t6_budget():
    ds1, m1 = gen.build('R1', 100, 2, 4242, 0.6)
    ds2, m2 = gen.build('R1', 100, 2, 4242, 0.9)
    assert m1['budget_B'] > m2['budget_B'] > 0
    assert abs(m1['budget_B'] - 0.4 * m1['mean_full_energy']) < 1e-9
    assert abs(m2['budget_B'] - 0.1 * m2['mean_full_energy']) < 1e-9
    print('  [PASS] T6 预算: rho=0.6 → %.2f, rho=0.9 → %.2f' % (m1['budget_B'], m2['budget_B']))
    return True


TESTS = [('T1', t1_determinism), ('T2', t2_roles_disjoint), ('T3', t3_visibility),
         ('T4', t4_event_stream), ('T5', t5_leak_scan), ('T6', t6_budget)]


def main():
    failed = 0
    for name, fn in TESTS:
        try:
            if not fn():
                failed += 1
        except AssertionError as exc:
            failed += 1
            print('  [FAIL] %s: %s' % (name, exc))
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print('  [ERROR] %s: %r' % (name, exc))
    print('\n结果: %d/%d 通过' % (len(TESTS) - failed, len(TESTS)))
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
