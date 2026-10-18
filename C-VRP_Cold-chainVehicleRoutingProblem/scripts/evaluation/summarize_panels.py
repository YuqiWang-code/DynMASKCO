#!/usr/bin/env python
"""把 ``results/admission_panel/*/panel.json`` 汇总成一张可读对照表。

用法::

    python scripts/evaluation/summarize_panels.py                 # 扫默认目录
    python scripts/evaluation/summarize_panels.py --root results/admission_panel
    python scripts/evaluation/summarize_panels.py --json out.json

设计要点
--------
1. **一个目录 = 一个臂的一次运行**（面板按臂分目录跑，见 run_admission_panel.py）。
2. 输出两列口径：``utility``（冻结 a1：revenue − 0.1·distance − reject_loss）与它的分解量；
   逐日序列一并给出（总纲 §8.4：禁止用均值掩盖逐日）。
3. 同时给出三温区 ``service_rate``（若该次运行记录了这一列）。
4. 只读，不写回任何结果目录。
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys


def load_runs(root: str):
    runs = []
    for p in sorted(glob.glob(os.path.join(root, '*', 'panel.json'))):
        try:
            d = json.load(open(p, encoding='utf-8'))
        except Exception as exc:  # noqa: BLE001
            print('[warn] cannot read %s: %r' % (p, exc), file=sys.stderr)
            continue
        name = os.path.basename(os.path.dirname(p))
        cfg = d.get('config') or {}
        per = d.get('per_day') or []
        arms = {}
        for row in per:
            for arm, v in row.items():
                if arm == 'day' or not isinstance(v, dict):
                    continue
                arms.setdefault(arm, []).append(v)
        for arm, rows in arms.items():
            runs.append(dict(dir=name, arm=arm, config=cfg, rows=rows, path=p))
    return runs


def _mean(rows, key):
    vals = [r.get(key) for r in rows if r.get(key) is not None]
    return (sum(vals) / len(vals)) if vals else None


def _fmt(v, spec='%.2f'):
    return 'n/a' if v is None else (spec % v)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default='results/admission_panel')
    ap.add_argument('--json', default=None, help='把汇总写成 JSON')
    ap.add_argument('--min-days', type=int, default=1)
    args = ap.parse_args(argv)

    runs = [r for r in load_runs(args.root) if len(r['rows']) >= args.min_days]
    if not runs:
        print('no panel.json under %r' % args.root)
        return 1

    hdr = ('%-22s %-22s %4s %9s %9s %8s %8s %8s %7s %7s' %
           ('dir', 'arm', 'n', 'utility', 'revenue', 'dist_km', 'energy', 'served',
            'fuel_w', 'qual_w'))
    print(hdr)
    print('-' * len(hdr))
    out = []
    for r in sorted(runs, key=lambda x: (x['dir'], x['arm'])):
        rows, cfg = r['rows'], r['config']
        rec = dict(dir=r['dir'], arm=r['arm'], n=len(rows),
                   utility=_mean(rows, 'utility'), revenue=_mean(rows, 'revenue'),
                   distance_km=_mean(rows, 'distance_km'),
                   energy_kwh=_mean(rows, 'energy_kwh'),
                   n_served=_mean(rows, 'n_served'),
                   fuel_weight=cfg.get('fuel_weight'),
                   quality_weight=cfg.get('quality_weight'),
                   days=cfg.get('days'), dataset=cfg.get('dataset'),
                   per_day=[r0.get('utility') for r0 in rows],
                   service_rate=[r0.get('service_rate') for r0 in rows])
        out.append(rec)
        print('%-22s %-22s %4d %9s %9s %8s %8s %8s %7s %7s' % (
            rec['dir'], rec['arm'], rec['n'],
            _fmt(rec['utility']), _fmt(rec['revenue'], '%.1f'),
            _fmt(rec['distance_km'], '%.1f'), _fmt(rec['energy_kwh'], '%.1f'),
            _fmt(rec['n_served'], '%.1f'),
            'n/a' if rec['fuel_weight'] is None else '%.1f' % rec['fuel_weight'],
            'n/a' if rec['quality_weight'] is None else '%.1f' % rec['quality_weight']))
        print('%-22s %-22s      per-day utility: %s' % (
            '', '', [None if v is None else round(v, 1) for v in rec['per_day']]))

    # 三温区服务率（只对记录了该列的运行）
    with_sr = [r for r in out if any(x is not None for x in r['service_rate'])]
    if with_sr:
        print()
        print('per-class service rate (mean over days):')
        for r in with_sr:
            acc = {}
            for sr in r['service_rate']:
                if not isinstance(sr, dict):
                    continue
                for k, v in sr.items():
                    if v is not None:
                        acc.setdefault(k, []).append(v)
            parts = ['%s:%.3f' % (k, sum(v) / len(v)) for k, v in sorted(acc.items())]
            print('  %-22s %-18s %s' % (r['dir'], r['arm'], '  '.join(parts)))

    if args.json:
        with open(args.json, 'w', encoding='utf-8') as fh:
            json.dump(out, fh, indent=2, ensure_ascii=False)
        print('\nwrote %s' % args.json)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
