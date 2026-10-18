#!/usr/bin/env python
"""L8（种子/顺序级）的**接拒层**重放测试：并列到达重排后决策必须按订单 id 不变。

范围（必须写清）
----------------
本测试只覆盖**接拒层**：`AdmissionController` + 一个确定性策略，按 reveal 顺序喂订单。
它**不**覆盖完整环境的派车/插入路径（那需要 `StrictOnlineEnv` 重放，尚未实现）。
因此本测试通过 ≠ L8 通过；G1 仍保持 7/8，直到环境级重放也做出来。

判定
----
1. 造一天订单：其中若干组 `reveal_time` 完全相同（并列到达）；
2. 按 reveal_time 排序（并列组内按 id）喂一遍，记录 `{order_id: accept}`；
3. 把**并列组内部**的到达顺序反转，其余不变，再喂一遍；
4. 断言两次的 `{order_id: accept}` **完全相同**。

若失败 ⇒ 策略依赖了组内位置（等价于偷看了一个协议没承诺的"隐含优先级"），即 L8 泄漏。

用法::

    python scripts/tests/test_no_future_l8.py
"""
from __future__ import annotations

import os
import sys

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_SCRIPTS, os.path.join(_SCRIPTS, 'admission')):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _make_orders(n=12, tie_size=3):
    """造一天订单：每 tie_size 单同一 reveal_time；收入/能耗按温区取登记口径。"""
    from admission.controller import OrderView
    from admission.policies import e_lower_of

    objective = dict(ambient_c=25.0, target_c=[18.0, 4.0, -18.0],
                     precool_energy_per_unit_per_c=0.15)
    rev = {0: 10.0, 1: 20.0, 2: 30.0}
    orders = []
    for i in range(n):
        cls = i % 3
        q = 2.0
        e = e_lower_of(cls, q, objective)
        clock = 1.0 * (i // tie_size)            # 每 tie_size 单同一时钟
        orders.append((i, OrderView.build(i, cls, q, e, reveal_time=clock,
                                          revenue=rev[cls]), clock))
    return orders


def _run_sequence(orders, budget=200.0, horizon=16.0):
    """按给定到达顺序喂一遍接拒控制器，返回 {order_id: accept}。"""
    from admission.controller import AdmissionController
    from admission.policies import FixedThreshold

    # 用无参的确定性策略，避免引入 λ 网格标定（那是标定问题，不是顺序问题）
    ctrl = AdmissionController(FixedThreshold(theta=3.0), budget=budget)
    ctrl.begin_day([], horizon=horizon, day_index=0)
    out = {}
    for oid, view, clock in orders:
        dec = ctrl.decide(view, clock)
        out[int(oid)] = bool(dec.accept)
    return out


def _reverse_within_tie_groups(orders):
    """把并列组（同一 clock）内部顺序反转，组间顺序不变。"""
    groups = []
    for item in orders:
        if groups and groups[-1][0] == item[2]:
            groups[-1][1].append(item)
        else:
            groups.append((item[2], [item]))
    flat = []
    for clock, items in groups:
        flat.extend(reversed(items))
    return flat


def main() -> int:
    orders = _make_orders()
    clocks = sorted({c for _, _, c in orders})
    print('orders=%d  tie groups=%d  group size=%d'
          % (len(orders), len(clocks), len([1 for _, _, c in orders if c == clocks[0]])))

    base = _run_sequence(orders)
    perm = _run_sequence(_reverse_within_tie_groups(orders))

    diff = {k: (base[k], perm[k]) for k in base if base[k] != perm[k]}
    # 自检：若全部接受或全部拒绝，本测试**无判别力**，必须报失败而不是通过
    n_acc = sum(base.values())
    discriminating = 0 < n_acc < len(base)
    ok = (not diff) and discriminating
    print('base accepts:', sum(base.values()), '/', len(base))
    print('perm accepts:', sum(perm.values()), '/', len(perm))
    print('mismatched orders:', len(diff), (list(diff.items())[:5] if diff else ''))
    if not discriminating:
        print('verdict: VACUOUS (all accept or all reject) - NOT a pass')
    else:
        print('verdict:', 'PASS_ADMISSION_LAYER_ORDER_INVARIANT' if not diff
              else 'FAIL_ORDER_DEPENDENT')
    print('scope: admission layer only; env-level (dispatch/insertion) replay NOT covered')
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
