#!/usr/bin/env python3
"""Plot two completed AWS/LocalStack matrices. Requires matplotlib."""
import argparse
import csv
import json
import math
from pathlib import Path
import re

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def read_json(path):
    return json.loads(path.read_text())


def aws_rows(root):
    rows = []
    for batch in sorted(root.glob('batch-*')):
        if not batch.is_dir():
            continue
        final = read_json(batch / 'final-summary.json')
        if final['stopReason'] != 'Completed' or final['restorationError']:
            raise ValueError(f'Incomplete AWS batch: {batch}')
        rows.extend(json.loads(line) for line in (batch / 'invocations.jsonl').read_text().splitlines())
    return rows


def local_rows(root):
    rows = []
    logs = sorted(root.glob('*.public.log')) or sorted(root.glob('*.log'))
    for log in logs:
        match = re.search(r'^Results: (.+)$', log.read_text(), re.M)
        if not match:
            raise ValueError(f'Missing LocalStack results path: {log}')
        result = Path(match[1])
        summary = read_json(result / 'summary.json')
        if summary['stopReason'] != 'Completed' or summary['cleanupErrors']:
            raise ValueError(f'Incomplete LocalStack run: {result}')
        metadata = result / 'metadata.public.json'
        if not metadata.exists():
            metadata = result / 'metadata.json'
        memory = read_json(metadata)['arguments']['memory']
        for line in (result / 'invocations.jsonl').read_text().splitlines():
            rows.append(dict(json.loads(line), memoryMb=memory))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--aws', nargs=2, type=Path, required=True)
    parser.add_argument('--local', nargs=2, type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    records, checks = [], []
    for environment, roots, loader in [('AWS', args.aws, aws_rows), ('LocalStack', args.local, local_rows)]:
        for run, root in enumerate(roots, 1):
            rows = loader(root)
            if len(rows) != 1452 or any(r.get('outcome') != 'valid' for r in rows):
                raise ValueError(f'Expected 1,452 valid calls: {root}')
            checks.append(dict(environment=environment, run=run, root=str(root), validCalls=len(rows)))
            for memory in sorted({r['memoryMb'] for r in rows}):
                for workload in ('cpu', 'io'):
                    warm = [r for r in rows if r['memoryMb'] == memory and r['workload'] == workload
                            and r['phase'] == 'sample' and r.get('coldStart') is False]
                    if len(warm) != 60:
                        raise ValueError(f'Expected 60 warm samples: {environment}/{run}/{memory}/{workload}')
                    for metric in ('handlerMs', 'durationMs', 'billedGBSeconds'):
                        if metric != 'handlerMs' and environment != 'AWS':
                            continue
                        values = sorted(r[metric] for r in warm)
                        records.append(dict(environment=environment, run=run, memoryMb=memory,
                                            workload=workload, metric=metric, samples=len(values),
                                            mean=sum(values)/len(values),
                                            p95=values[math.ceil(.95*len(values))-1]))
    with (args.output / 'measurements.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    (args.output / 'sources.json').write_text(json.dumps(checks, indent=2)+'\n')
    plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False})
    memories = sorted({r['memoryMb'] for r in records})
    specifications = [
        ('aws-duration', 'AWS REPORT duration', 'durationMs', ['AWS'], 'Mean warm duration (ms)'),
        ('handler-comparison', 'AWS and LocalStack handler time', 'handlerMs', ['AWS', 'LocalStack'], 'Mean warm handler time (ms)'),
        ('aws-compute', 'AWS billed compute', 'billedGBSeconds', ['AWS'], 'Mean billed GB-seconds / invocation'),
    ]
    for name, title, metric, environments, ylabel in specifications:
        fig, axes = plt.subplots(1, 2, figsize=(14, 5), layout='constrained')
        for ax, workload in zip(axes, ('cpu', 'io')):
            for environment in environments:
                for run in (1, 2):
                    selected = sorted((r for r in records if r['environment'] == environment and r['run'] == run
                                       and r['workload'] == workload and r['metric'] == metric), key=lambda r:r['memoryMb'])
                    color = {'AWS': '#1769aa', 'LocalStack': '#bb4d00'}[environment]
                    if environments == ['AWS']:
                        color = '#1769aa' if run == 1 else '#bb4d00'
                    ax.plot(range(len(memories)), [r['mean'] for r in selected],
                            marker='o' if run == 1 else 's', linestyle='-' if run == 1 else '--',
                            color=color, label=f'{environment}, run {run}', linewidth=1.8, markersize=4)
            ax.set(title='CPU workload' if workload == 'cpu' else 'S3 I/O workload',
                   xlabel='Configured memory (MB; equally spaced settings)', ylabel=ylabel)
            ax.set_xticks(range(len(memories)), memories, rotation=55)
            ax.set_ylim(bottom=0)
            ax.grid(axis='y', alpha=.2)
            ax.legend(frameon=False)
        fig.suptitle(f'28 October 2026 — {title}\nTwo runs; 60 warm samples per workload / memory / run', fontsize=13)
        for extension in ('png', 'svg'):
            fig.savefig(args.output / f'{name}.{extension}', dpi=180)
        plt.close(fig)
    lines = ['# 28 October 2026: two complete benchmark runs', '',
             'Each run contains 1,452 valid calls per environment across 11 memory settings. Each workload/memory combination has 60 warm collected samples and six warmups. AWS batches use eu-west-1. Earlier partial and default-only runs are excluded.', '',
             'The first and second runs each used two AWS batches to preserve the 1,000-call limit. Memory and workload order reverse within each batch. Calls are sequential within each environment; AWS and LocalStack matrices were launched concurrently.', '',
             'AWS REPORT duration, Java handler time and billed compute have separate graphs. LocalStack configured memory does not establish equivalent AWS CPU allocation or production performance. Billed GB-seconds exclude request, S3 and logging costs.', '']
    for name, title, *_ in specifications:
        lines.extend([f'## {title}', '', f'![{title}]({name}.png)', '', f'[SVG]({name}.svg)', ''])
    lines.extend(['[Measurements, including p95](measurements.csv) · [Source run folders](sources.json)', '',
                  'The CSV retains every plotted value. Regenerating these graphs with '
                  '`scripts/plot-benchmark-runs.py` requires the raw invocation evidence '
                  'kept locally; per-invocation files are excluded from the compact published commit.', ''])
    (args.output / 'README.md').write_text('\n'.join(lines))
    print(f'Validated {sum(c["validCalls"] for c in checks):,} calls; graphs: {args.output}')


if __name__ == '__main__':
    main()
