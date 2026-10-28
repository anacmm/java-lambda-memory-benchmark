#!/usr/bin/env python3
"""Run sequential Lambda trials using AWS CLI; no third-party Python packages."""
import argparse
import base64
import csv
import hashlib
import json
import math
import os
import signal
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MEMORIES = [256, 512, 1024, 1536, 2048, 3072, 4096]
SUPPORTED_MEMORIES = [256, 512, 1024, 1536, 1769, 2048, 3072, 4096, 6144, 8192, 10240]
MEASUREMENT_METRICS = {
    'durationMs': 'AWS REPORT Duration; primary AWS summary metric, not Java handlerMs',
    'handlerMs': 'Java handler elapsed time; excludes initialization, framework decoding/serialization and log emission',
    's3Ms': 'Java elapsed time for full SDK GET, buffering and Content-Length validation',
    'jsonMs': 'Java dataset JSON deserialization; null for io',
    'cpuMs': 'Java elapsed calculation time for cpu or CRC32 time for io; not CPU utilization',
    'billedMs': 'AWS REPORT Billed Duration; includes applicable initialization and rounding',
    'callerMs': 'Python elapsed time including AWS CLI process, invocation and local response/log processing',
}


MAX_INVOCATIONS = 1000
MAX_CONSECUTIVE_ERRORS = 5


class BenchmarkStopped(RuntimeError):
    pass


class AwsError(RuntimeError):
    pass


class Safety:
    def __init__(self, seconds):
        self.deadline = time.monotonic() + seconds
        self.invocations = 0
        self.errors = 0
        self.restoring = False

    def check(self):
        if self.restoring:
            return
        if time.monotonic() >= self.deadline:
            raise BenchmarkStopped('Maximum benchmark duration reached')
        if self.errors >= MAX_CONSECUTIVE_ERRORS:
            raise BenchmarkStopped('5 consecutive AWS API/invocation errors')

    def invoke(self):
        self.check()
        if self.invocations >= MAX_INVOCATIONS:
            raise BenchmarkStopped('Maximum of 1,000 invocations reached')
        self.invocations += 1  # Count attempts before sending, including failures.


def aws(args, *command):
    safety = args.safety
    safety.check()
    invoking = command[:2] == ('lambda', 'invoke')
    if invoking:
        safety.invoke()
    timeout = None if safety.restoring else max(.001, safety.deadline - time.monotonic())
    try:
        result = subprocess.run(['aws', '--region', args.region, *command],
                                capture_output=True, text=True, timeout=timeout,
                                env={**os.environ, 'AWS_MAX_ATTEMPTS': '1'})
        if result.returncode:
            raise AwsError(result.stderr.strip() or result.stdout.strip())
        response = json.loads(result.stdout) if result.stdout.strip() else {}
    except subprocess.TimeoutExpired as error:
        raise BenchmarkStopped('Maximum benchmark duration reached during AWS call') from error
    except (OSError, ValueError) as error:
        safety.errors += 1
        raise AwsError(str(error)) from error
    except AwsError:
        safety.errors += 1
        raise
    if not invoking:
        safety.errors = 0
    return response


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def measurements(log):
    events = [json.loads(line) for line in log.splitlines()
              if line.startswith('{') and 'benchmark_invocation' in line]
    if len(events) != 1:
        raise ValueError('Expected exactly one application measurement in log tail')
    event = events[0]
    report = re.search(r'REPORT RequestId:\s*(\S+)\s+Duration:\s*([\d.]+) ms\s+Billed Duration:\s*(\d+) ms', log)
    if not report or report[1] != event['requestId']:
        raise ValueError('Missing or mismatched AWS execution report')
    event.update(durationMs=float(report[2]), billedMs=int(report[3]))
    event['billedGBSeconds'] = event['memoryMb'] / 1024 * event['billedMs'] / 1000
    return event


def summarize(rows):
    groups = {}
    for row in rows:
        if row.get('status') == 'OK' and not row.get('runnerError'):
            key = (row['memoryMb'], row['workload'], row['coldStart'], row['phase'])
            groups.setdefault(key, []).append(row)
    output = []
    for (memory, workload, cold, phase), values in sorted(groups.items()):
        durations = sorted(v['durationMs'] for v in values)
        def percentile(p):
            import math
            return durations[max(0, math.ceil(p * len(durations)) - 1)]
        handlers = sorted(v['handlerMs'] for v in values if v.get('handlerMs') is not None)
        def handler_percentile(p):
            return handlers[max(0, math.ceil(p * len(handlers)) - 1)] if handlers else None
        output.append(dict(memoryMb=memory, workload=workload, coldStart=cold,
                           phase=phase, samples=len(values),
                           meanDurationMs=sum(durations) / len(values),
                           p50Ms=percentile(.5), p95Ms=percentile(.95), p99Ms=percentile(.99),
                           meanBilledGBSeconds=sum(v['billedGBSeconds'] for v in values) / len(values),
                           primaryMetric='durationMs', handlerSamples=len(handlers),
                           meanHandlerMs=sum(handlers) / len(handlers) if handlers else None,
                           p50HandlerMs=handler_percentile(.5), p95HandlerMs=handler_percentile(.95),
                           p99HandlerMs=handler_percentile(.99)))
    return output


def summarize_repetitions(rows):
    return [dict(group, repetition=repetition)
            for repetition in sorted({r['repetition'] for r in rows})
            for group in summarize([r for r in rows if r['repetition'] == repetition])]


MIN_WARM_SAMPLES = 55


def configuration_counts(rows, memories):
    """Warm/cold count valid collected calls; failures include either phase."""
    counts = []
    for memory in sorted(set(memories)):
        for workload in ('cpu', 'io'):
            values = [r for r in rows if r['memoryMb'] == memory and r['workload'] == workload]
            collected = [r for r in values if r['phase'] == 'sample']
            valid = [r for r in collected if r.get('outcome') == 'valid']
            warm = sum(r.get('coldStart') is False for r in valid)
            counts.append(dict(
                memoryMb=memory, workload=workload,
                collected=len(collected), warm=warm,
                cold=sum(r.get('coldStart') is True for r in valid),
                warmup=sum(r['phase'] == 'warmup' for r in values),
                failed=sum(r.get('outcome') == 'failed' for r in values),
                invalid=sum(r.get('outcome') == 'invalid' for r in values),
                collectedFailed=sum(r.get('outcome') == 'failed' for r in collected),
                collectedInvalid=sum(r.get('outcome') == 'invalid' for r in collected),
                warmSampleWarning=warm < MIN_WARM_SAMPLES))
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--region', default='eu-west-2')
    parser.add_argument('--max-duration', type=float, default=1800, help='Maximum benchmark seconds (default: 1800)')
    parser.add_argument('--yes', action='store_true', help='Confirm benchmark without prompting')
    parser.add_argument('--outputs', type=Path, default=ROOT / 'infra/outputs.json')
    parser.add_argument('--samples', type=int, default=30, help='Collected calls per workload/memory/repetition')
    parser.add_argument('--warmups', type=int, default=3)
    parser.add_argument('--repetitions', type=int, default=2, help='Alternate workload and memory batch order')
    parser.add_argument('--interval', type=float, default=0, help='Seconds between sequential calls')
    parser.add_argument('--memories', type=int, nargs='+', default=MEMORIES, choices=SUPPORTED_MEMORIES)
    parser.add_argument('--key', default='dataset.json')
    parser.add_argument('--gb-second-price', type=float, help='Regional ARM64 USD per GB-second')
    parser.add_argument('--request-price', type=float, default=0.0000002, help='USD per request, excluding free tier')
    parser.add_argument('--results', type=Path)
    args = parser.parse_args()
    if args.samples < 1 or args.warmups < 0 or args.repetitions < 1 or args.interval < 0:
        parser.error('samples/repetitions must be positive; warmups/interval nonnegative')
    if not math.isfinite(args.max_duration) or args.max_duration <= 0 or not math.isfinite(args.interval):
        parser.error('max-duration must be finite and positive; interval must be finite')
    expected = len(args.memories) * 2 * args.repetitions * (args.warmups + args.samples)
    if expected > MAX_INVOCATIONS:
        parser.error(f'Expected {expected} invocations exceeds the 1,000 invocation limit')
    resources = json.loads(args.outputs.read_text())['JavaBenchmarkStack']
    function, bucket = resources['FunctionName'], resources['BucketName']
    print(f'Region: {args.region}\nFunction: {function}\nMemory configurations: {args.memories}\n'
          f'Workloads: cpu, io\nExpected invocations: {expected}\n'
          f'Safety limits: {MAX_INVOCATIONS} invocation attempts, {args.max_duration:g} seconds, '
          f'{MAX_CONSECUTIVE_ERRORS} consecutive AWS API/invocation errors', flush=True)
    print('Metrics: primary durationMs = AWS REPORT Duration; handlerMs = Java handler elapsed time', flush=True)
    if not args.yes:
        try:
            confirmed = input('Type yes to start: ').strip().lower() == 'yes'
        except (KeyboardInterrupt, EOFError):
            confirmed = False
        if not confirmed:
            print('Benchmark cancelled before starting.')
            return
    args.safety = Safety(args.max_duration)
    destination = args.results or ROOT / 'benchmark-runs' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    destination.mkdir(parents=True, exist_ok=False)
    artifact, dataset = ROOT / 'lambda/target/function.zip', ROOT / 'sample/dataset.json'
    identities = {str(p.relative_to(ROOT)): digest(p) for p in (artifact, dataset)}
    config = aws(args, 'lambda', 'get-function-configuration', '--function-name', function)
    if config['FunctionArn'].split(':')[3] != args.region:
        raise RuntimeError('Deployed function region does not match requested region')
    if base64.b64encode(hashlib.sha256(artifact.read_bytes()).digest()).decode() != config['CodeSha256']:
        raise RuntimeError('Local ZIP does not match deployed Lambda code')
    if config['Runtime'] != 'provided.al2023' or config.get('Architectures') != ['arm64']:
        raise RuntimeError('Expected ARM64 provided.al2023 function')
    metadata = dict({k: v for k, v in vars(args).items() if k != 'safety'}, function=function, bucket=bucket, identities=identities,
                    measurementMetrics=MEASUREMENT_METRICS,
                    originalConfiguration=config, identity=aws(args, 'sts', 'get-caller-identity'))
    (destination / 'metadata.json').write_text(json.dumps(metadata, default=str, indent=2))
    # The local fixture is uploaded once; each invocation still performs a fresh GET.
    rows = []
    changed = False
    def set_memory(memory):
        aws(args, 'lambda', 'update-function-configuration', '--function-name', function, '--memory-size', str(memory))
        aws(args, 'lambda', 'wait', 'function-updated-v2', '--function-name', function)
        current = aws(args, 'lambda', 'get-function-configuration', '--function-name', function)
        if current['MemorySize'] != memory or current['LastUpdateStatus'] != 'Successful' or current['CodeSha256'] != config['CodeSha256']:
            raise RuntimeError('Function configuration or code identity changed unexpectedly')
    stop_reason = 'Completed'
    restoration_error = None
    try:
        aws(args, 's3', 'cp', str(dataset), f's3://{bucket}/{args.key}', '--content-type', 'application/json', '--only-show-errors')
        for repetition in range(args.repetitions):
            memories = args.memories if repetition % 2 == 0 else list(reversed(args.memories))
            workloads = ['cpu', 'io'] if repetition % 2 == 0 else ['io', 'cpu']
            for memory in memories:
                if any(digest(ROOT / path) != sha for path, sha in identities.items()):
                    raise RuntimeError('Local artifact or dataset changed')
                args.safety.check()
                changed = True
                set_memory(memory)
                for workload in workloads:
                    for index in range(args.warmups + args.samples):
                        args.safety.check()
                        phase = 'warmup' if index < args.warmups else 'sample'
                        stem = f'r{repetition + 1}-{memory}-{workload}-{index + 1:04d}'
                        row = dict(repetition=repetition + 1, memoryMb=memory, workload=workload, phase=phase)
                        started = time.monotonic()
                        try:
                            result = aws(args, 'lambda', 'invoke', '--function-name', function,
                                         '--invocation-type', 'RequestResponse', '--cli-binary-format', 'raw-in-base64-out',
                                         '--payload', json.dumps(dict(workload=workload, bucket=bucket, key=args.key)),
                                         '--log-type', 'Tail', str(destination / f'{stem}.response.json'))
                            (destination / f'{stem}.invoke.json').write_text(json.dumps(result, indent=2))
                            log = base64.b64decode(result.get('LogResult', '')).decode('utf-8')
                            (destination / f'{stem}.log.txt').write_text(log)
                            if result.get('FunctionError'):
                                args.safety.errors += 1
                                raise AwsError('Lambda FunctionError: ' + result['FunctionError'])
                            args.safety.errors = 0
                            measurement = measurements(log)
                            if measurement.get('memoryMb') != memory or measurement.get('workload') != workload or type(measurement.get('coldStart')) is not bool:
                                raise ValueError('Unexpected configuration or missing coldStart classification')
                            row.update(measurement)
                            response = json.loads((destination / f'{stem}.response.json').read_text())
                            expected = dict(recordsProcessed=4000, checksum='b1e029a3d2d7974c', status='OK') if workload == 'cpu' else dict(objectBytes=191961, checksum='crc32:1c396adb', status='OK')
                            if response != expected or row['memoryMb'] != memory or row['workload'] != workload or row['status'] != 'OK':
                                raise ValueError('Unexpected response or measurement')
                            row['outcome'] = 'valid'
                        except BenchmarkStopped as error:
                            row.update(outcome='failed', runnerError=str(error))
                            stop_reason = str(error)
                        except KeyboardInterrupt:
                            row.update(outcome='failed', runnerError='Cancelled by Ctrl+C')
                            stop_reason = 'Cancelled by Ctrl+C'
                        except AwsError as error:
                            row.update(outcome='failed', runnerError=str(error))
                        except (ValueError, KeyError, TypeError, OSError) as error:
                            row.update(outcome='invalid', runnerError=str(error))
                        # Attribute invalid measurements to the requested configuration.
                        row.update(memoryMb=memory, workload=workload)
                        row['callerMs'] = (time.monotonic() - started) * 1000
                        rows.append(row)
                        with (destination / 'invocations.jsonl').open('a') as stream:
                            stream.write(json.dumps(row) + '\n')
                        print(f'{stem}: {row.get("runnerError", row.get("status"))}', flush=True)
                        if stop_reason != 'Completed':
                            raise BenchmarkStopped(stop_reason)
                        args.safety.check()
                        time.sleep(min(args.interval, max(0, args.safety.deadline - time.monotonic())))
    except KeyboardInterrupt:
        stop_reason = 'Cancelled by Ctrl+C'
    except (BenchmarkStopped, RuntimeError, OSError, ValueError, KeyError) as error:
        stop_reason = str(error)
    finally:
        # Restore before reporting: even a disk/summary error must not skip cleanup.
        if changed:
            args.safety.restoring = True
            previous_handler = signal.signal(signal.SIGINT, signal.SIG_IGN)
            try:
                print(f'Restoring original memory: {config["MemorySize"]} MB', flush=True)
                set_memory(config['MemorySize'])
            except Exception as error:
                restoration_error = str(error)
                print('RESTORATION FAILED: ' + restoration_error, flush=True)
            finally:
                signal.signal(signal.SIGINT, previous_handler)
        print('Benchmark stopped: ' + stop_reason, flush=True)
        counts = configuration_counts(rows, args.memories)
        warnings = [f'{c["memoryMb"]} MB {c["workload"]}: only {c["warm"]} valid warm collected samples (minimum {MIN_WARM_SAMPLES})'
                    for c in counts if c['warmSampleWarning']]
        final = dict(stopReason=stop_reason, invocationAttempts=args.safety.invocations,
                     restorationError=restoration_error, minimumWarmCollectedSamples=MIN_WARM_SAMPLES, configurations=counts, warnings=warnings,
                     measurementMetrics=MEASUREMENT_METRICS, repetitionSummaryFile='summary-by-repetition.json')
        (destination / 'final-summary.json').write_text(json.dumps(final, indent=2))
        with (destination / 'configuration-counts.csv').open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(counts[0]))
            writer.writeheader()
            writer.writerows(counts)
        print('Final counts: collected / warm / cold / warmup / failed / invalid', flush=True)
        for c in counts:
            print(f'{c["memoryMb"]} MB {c["workload"]}: ' + ' / '.join(str(c[k]) for k in ('collected', 'warm', 'cold', 'warmup', 'failed', 'invalid')), flush=True)
        for warning in warnings:
            print('WARNING: ' + warning, flush=True)
        summary = summarize(rows)
        repetitions = summarize_repetitions(rows)
        if args.gb_second_price is not None:
            for group in summary + repetitions:
                group['estimatedLambdaUSDPer1000'] = 1000 * (group['meanBilledGBSeconds'] * args.gb_second_price + args.request_price)
        (destination / 'summary.json').write_text(json.dumps(summary, indent=2))
        (destination / 'summary-by-repetition.json').write_text(json.dumps(repetitions, indent=2))
        if repetitions:
            with (destination / 'summary-by-repetition.csv').open('w', newline='') as stream:
                writer = csv.DictWriter(stream, fieldnames=list(repetitions[0]))
                writer.writeheader()
                writer.writerows(repetitions)
        if summary:
            with (destination / 'summary.csv').open('w', newline='') as stream:
                writer = csv.DictWriter(stream, fieldnames=list(summary[0]))
                writer.writeheader()
                writer.writerows(summary)
        print(f'Results: {destination}', flush=True)
    return 1 if stop_reason != 'Completed' or restoration_error else 0



if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print('Benchmark stopped: Cancelled by Ctrl+C', flush=True)
        sys.exit(130)
    except (RuntimeError, OSError, ValueError, KeyError) as error:
        print(f'Benchmark stopped: {error}', flush=True)
        sys.exit(1)
