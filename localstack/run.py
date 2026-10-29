#!/usr/bin/env python3
"""Separate LocalStack functional experiment. Never invokes the AWS runner."""
import argparse
import base64
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
import time
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENDPOINT = 'http://127.0.0.1:4566'
REGION = 'eu-west-2'
MEMORIES = [256, 512, 1024, 1536, 1769, 2048, 3072, 4096, 6144, 8192, 10240]
DOCKER_NETWORK = 'java-benchmark-local'
MEASUREMENT_METRICS = {
    'handlerMs': 'Java handler elapsed time; primary local metric; excludes initialization, framework decoding/serialization and log emission',
    's3Ms': 'Java elapsed time for full SDK GET, buffering and Content-Length validation',
    'jsonMs': 'Java dataset JSON deserialization; null for io',
    'cpuMs': 'Java elapsed calculation time for cpu or CRC32 time for io; not CPU utilization',
    'callerMs': 'Python elapsed time including AWS CLI process, invocation and local request/response/log processing',
    'durationMs': 'Not summarized locally; LocalStack REPORT Duration is not AWS REPORT Duration',
}
DATASET_SHA256 = '2939695c8e099f3d73ea84e17069dc7cbae9304be72972d0be0f5f1b698fa10e'
EXPECTED = {
    'cpu': dict(recordsProcessed=4000, checksum='b1e029a3d2d7974c', status='OK'),
    'io': dict(objectBytes=191961, checksum='crc32:1c396adb', status='OK'),
}


def local_env():
    # Discard real AWS profiles, credentials, endpoints and container credential hooks.
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(('AWS_', 'QUARKUS_', 'LOCALSTACK_'))
           and k.lower() not in ('http_proxy', 'https_proxy', 'all_proxy', 'no_proxy')}
    env.update(AWS_ACCESS_KEY_ID='test', AWS_SECRET_ACCESS_KEY='test',
               AWS_REGION=REGION, AWS_DEFAULT_REGION=REGION,
               AWS_EC2_METADATA_DISABLED='true', AWS_MAX_ATTEMPTS='1',
               AWS_CONFIG_FILE=os.devnull, AWS_SHARED_CREDENTIALS_FILE=os.devnull,
               AWS_PAGER='', NO_PROXY='127.0.0.1,localhost')
    return env


def aws_command(*command):
    # Endpoint is fixed, not user configurable. Every service operation is local.
    return ['aws', '--endpoint-url', ENDPOINT, '--region', REGION,
            '--no-cli-pager', '--output', 'json', *command]


def aws(*command):
    result = subprocess.run(aws_command(*command), env=local_env(),
                            capture_output=True, text=True, timeout=90)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return json.loads(result.stdout) if result.stdout.strip() else {}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_artifact(artifact):
    with zipfile.ZipFile(artifact) as archive:
        if not {'bootstrap', 'runner', 'cacerts'} <= set(archive.namelist()):
            raise ValueError('Expected native ZIP containing bootstrap, runner and cacerts')
        with archive.open('runner') as binary:
            header = binary.read(20)
        if (len(header) != 20 or header[:6] != b'\x7fELF\x02\x01'
                or header[18:20] != b'\xb7\x00'):
            raise ValueError('Expected Linux ARM64 ELF executable; do not rebuild the AWS artifact')
    return digest(artifact)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError('Refusing redirect from the fixed LocalStack endpoint')


def health():
    # Ignore system HTTP proxies for the loopback request.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    with opener.open(ENDPOINT + '/_localstack/health', timeout=5) as response:
        result = json.load(response)
    for service in ('s3', 'lambda'):
        if result.get('services', {}).get(service) not in ('available', 'running'):
            raise RuntimeError(f'LocalStack {service} is unavailable; check activation and container logs')
    return result


def docker_read(*command):
    """Read-only Docker queries; callers request whitelisted fields, never Config.Env."""
    result = subprocess.run(['docker', *command], capture_output=True, text=True, timeout=10)
    if result.returncode:
        # Do not archive stderr, which may contain host configuration or credentials.
        raise RuntimeError(f'Docker {command[0]} metadata unavailable (exit {result.returncode})')
    return result.stdout.strip()


# Extract only the function-name environment variable for container association.
# Full inspect output would expose the LocalStack activation token and credentials.
CONTAINER_FORMAT = (
    '{{$function := ""}}{{range .Config.Env}}{{$parts := split . "="}}'
    '{{if eq (index $parts 0) "AWS_LAMBDA_FUNCTION_NAME"}}'
    '{{$function = index $parts 1}}{{end}}{{end}}'
    '{"id":{{json .Id}},"name":{{json .Name}},"functionName":{{json $function}},'
    '"imageId":{{json .Image}},"imageReference":{{json .Config.Image}},'
    '"limits":{"nanoCpus":{{json .HostConfig.NanoCpus}},'
    '"cpuQuota":{{json .HostConfig.CpuQuota}},"cpuPeriod":{{json .HostConfig.CpuPeriod}},'
    '"cpuShares":{{json .HostConfig.CpuShares}},"cpusetCpus":{{json .HostConfig.CpusetCpus}},'
    '"memoryBytes":{{json .HostConfig.Memory}},"memoryReservationBytes":{{json .HostConfig.MemoryReservation}},'
    '"memorySwapBytes":{{json .HostConfig.MemorySwap}}}}'
)


def container_metadata(container_id):
    return json.loads(docker_read('inspect', '--format', CONTAINER_FORMAT, container_id))


def docker_metadata():
    data = dict(version=None, daemonResources=None, localstackContainers=[],
                lambdaContainerSnapshots=[], collectionWarnings=[])
    queries = {
        'version': ('version', '--format',
                    '{"client":{{json .Client.Version}},"server":{{json .Server.Version}}}'),
        'daemonResources': ('info', '--format',
                            '{"cpus":{{json .NCPU}},"memoryBytes":{{json .MemTotal}},'
                            '"architecture":{{json .Architecture}},"osType":{{json .OSType}},'
                            '"operatingSystem":{{json .OperatingSystem}}}'),
    }
    for key, command in queries.items():
        try:
            data[key] = json.loads(docker_read(*command))
        except (RuntimeError, OSError, ValueError, subprocess.TimeoutExpired) as error:
            data['collectionWarnings'].append(f'{key}: {type(error).__name__}; unavailable')
    try:
        ids = docker_read('ps', '--filter', 'label=com.docker.compose.project=java-benchmark-local',
                          '--filter', 'label=com.docker.compose.service=localstack', '--format', '{{.ID}}')
        for container_id in ids.splitlines():
            container = container_metadata(container_id)
            container['image'] = json.loads(docker_read('image', 'inspect', '--format',
                '{"id":{{json .Id}},"repoDigests":{{json .RepoDigests}},'
                '"architecture":{{json .Architecture}}}', container['imageId']))
            data['localstackContainers'].append(container)
        if not data['localstackContainers']:
            data['collectionWarnings'].append('Compose LocalStack container not found; image digest unavailable')
    except (RuntimeError, OSError, ValueError, subprocess.TimeoutExpired) as error:
        data['collectionWarnings'].append(f'localstackContainers: {type(error).__name__}; unavailable')
    return data


def capture_lambda_containers(data, function, repetition, workload):
    snapshot = dict(repetition=repetition, workload=workload,
                    observedAt=datetime.now(timezone.utc).isoformat(), containers=[])
    try:
        ids = docker_read('ps', '--filter', 'network=' + DOCKER_NETWORK, '--format', '{{.ID}}')
        for container_id in ids.splitlines():
            container = container_metadata(container_id)
            if container['functionName'] == function:
                snapshot['containers'].append(container)
        if not snapshot['containers']:
            snapshot['unavailableReason'] = 'No running container matched AWS_LAMBDA_FUNCTION_NAME'
    except (RuntimeError, OSError, ValueError, subprocess.TimeoutExpired) as error:
        snapshot['unavailableReason'] = f'{type(error).__name__}; Docker metadata unavailable'
    data['lambdaContainerSnapshots'].append(snapshot)


def wait_active(function):
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        config = aws('lambda', 'get-function-configuration', '--function-name', function)
        if config.get('State') == 'Failed' or config.get('LastUpdateStatus') == 'Failed':
            raise RuntimeError('Local Lambda startup failed: ' + str(config.get('StateReason',
                               config.get('LastUpdateStatusReason'))))
        if config.get('State') == 'Active' and config.get('LastUpdateStatus', 'Successful') == 'Successful':
            return config
        time.sleep(1)
    raise RuntimeError('Local Lambda did not become active within 180 seconds')


def validate(workload, result, response, log, memory):
    if result.get('FunctionError') or result.get('StatusCode') != 200:
        raise ValueError('Lambda invocation failed: ' + json.dumps(response))
    if response != EXPECTED[workload]:
        raise ValueError('Unexpected response: ' + json.dumps(response))
    events = []
    for line in log.splitlines():
        # Allow LocalStack's log prefixes; do not depend on its emulated REPORT format.
        index = line.find('{')
        if index < 0:
            continue
        try:
            event = json.loads(line[index:])
        except ValueError:
            continue
        if event.get('event') == 'benchmark_invocation':
            events.append(event)
    if len(events) != 1:
        raise ValueError('Expected exactly one application measurement in log tail')
    event = events[0]
    if (event.get('workload') != workload or event.get('status') != 'OK'
            or event.get('checksum') != EXPECTED[workload]['checksum']
            or event.get('objectBytes') != 191961 or event.get('memoryMb') != memory
            or type(event.get('coldStart')) is not bool):
        raise ValueError('Application log does not match the requested workload/configuration')
    for key in ('s3Ms', 'cpuMs', 'handlerMs'):
        value = event.get(key)
        if type(value) not in (float, int) or not math.isfinite(value) or value < 0:
            raise ValueError('Missing or invalid handler timing: ' + key)
    return event


def summarize(rows):
    output = []
    for workload in ('cpu', 'io'):
        warm = [r for r in rows if r['workload'] == workload and r['phase'] == 'sample'
                and r.get('outcome') == 'valid' and r.get('coldStart') is False]
        group = dict(workload=workload, warmCollected=len(warm),
                     coldCollected=sum(r['workload'] == workload and r['phase'] == 'sample'
                                       and r.get('outcome') == 'valid' and r.get('coldStart') is True
                                       for r in rows))
        if warm:
            for key in ('s3Ms', 'cpuMs', 'handlerMs', 'callerMs'):
                values = sorted(r[key] for r in warm)
                group[key] = dict(mean=sum(values) / len(values),
                                  p50=values[math.ceil(.5 * len(values)) - 1],
                                  p95=values[math.ceil(.95 * len(values)) - 1])
        output.append(group)
    return output


def summarize_repetitions(rows, repetitions):
    return [dict(repetition=i, workloads=summarize([r for r in rows if r['repetition'] == i]))
            for i in range(1, repetitions + 1)]


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--samples', type=int, default=30, help='Collected calls per workload/repetition (default: 30)')
    parser.add_argument('--warmups', type=int, default=3)
    parser.add_argument('--repetitions', type=int, default=2)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument('--memories', type=int, nargs='+', choices=MEMORIES,
                           help='Sequential memory matrix (default: all 11 sizes)')
    selection.add_argument('--memory', type=int, choices=MEMORIES,
                        help='Local configured memory, not AWS-equivalent compute allocation')
    args = parser.parse_args(argv)
    attempts = 2 * args.repetitions * (args.samples + args.warmups)
    if args.samples < 1 or args.warmups < 0 or args.repetitions < 1 or attempts > 1000:
        parser.error('Use positive samples/repetitions, nonnegative warmups, and at most 1000 calls')
    args.memories = list(dict.fromkeys(args.memories or ([args.memory] if args.memory else MEMORIES)))
    if attempts * len(args.memories) > 1500:
        parser.error('Memory matrix exceeds 1,500 calls')
    return args


def main():
    args = parse_args()
    if args.memory is not None:
        return run_single(args)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    destination = ROOT / 'localstack/results' / (stamp + '-full-matrix')
    destination.mkdir(parents=True, exist_ok=False)
    summary = dict(environment='localstack', memories=args.memories,
                   expectedInvocations=len(args.memories) * 2 * args.repetitions * (args.samples + args.warmups),
                   configurations=[], stopReason='Running')
    print(f'LocalStack sequential matrix: {args.memories}\nResults: {destination}', flush=True)
    code = 1
    try:
        for memory in args.memories:
            print(f'Starting {memory} MB', flush=True)
            single = argparse.Namespace(**{**vars(args), 'memory': memory})
            result_path = destination / str(memory)
            code = run_single(single, result_path)
            summary['configurations'].append(dict(memoryMb=memory, results=str(result_path),
                                                 **json.loads((result_path / 'summary.json').read_text())))
            (destination / 'matrix-summary.json').write_text(json.dumps(summary, indent=2))
            if code:
                break
        summary['stopReason'] = 'Completed' if code == 0 else 'Configuration failed'
    except KeyboardInterrupt:
        summary['stopReason'] = 'Cancelled'
        code = 1
    except (RuntimeError, ValueError, OSError, subprocess.TimeoutExpired) as error:
        summary['stopReason'] = str(error)
        code = 1
    finally:
        (destination / 'matrix-summary.json').write_text(json.dumps(summary, indent=2))
        print(f'Matrix {summary["stopReason"]}: {destination}', flush=True)
    return code


def run_single(args, destination=None):
    attempts = 2 * args.repetitions * (args.samples + args.warmups)
    artifact = ROOT / 'lambda/target/function.zip'
    dataset = ROOT / 'sample/dataset.json'
    artifact_hash = check_artifact(artifact)
    if digest(dataset) != DATASET_SHA256:
        raise ValueError('Dataset hash changed; expected the original AWS fixture')
    local_health = health()
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    destination = destination or ROOT / 'localstack/results' / stamp
    destination.mkdir(parents=True, exist_ok=False)
    function = 'java-benchmark-local-' + stamp.lower()
    bucket = 'java-benchmark-local-' + stamp.lower()
    metadata = dict(environment='localstack', endpoint=ENDPOINT, region=REGION,
                    function=function, bucket=bucket, artifactSHA256=artifact_hash,
                    datasetSHA256=DATASET_SHA256, host=platform.platform(),
                    hostDetails=dict(architecture=platform.machine(), os=platform.system(),
                                     osRelease=platform.release(), osVersion=platform.version()),
                    docker=docker_metadata(), measurementMetrics=MEASUREMENT_METRICS,
                    localstackHealth=local_health, arguments=vars(args),
                    interpretation='Local integration/timings only; not AWS memory sizing or billing')
    (destination / 'metadata.json').write_text(json.dumps(metadata, indent=2))
    rows, stopped = [], 'Completed'
    created = False
    cleanup_errors = []
    print(f'LocalStack only: {ENDPOINT}\nCalls: {attempts}\nResults: {destination}', flush=True)
    print('Metrics: primary handlerMs = Java handler elapsed time; local REPORT is not AWS durationMs', flush=True)
    try:
        aws('s3api', 'create-bucket', '--bucket', bucket,
            '--create-bucket-configuration', 'LocationConstraint=' + REGION)
        aws('s3api', 'put-object', '--bucket', bucket, '--key', 'dataset.json',
            '--body', str(dataset), '--content-type', 'application/json')
        # Verify the bytes stored in LocalStack, not only the source fixture.
        download = destination / 'downloaded-dataset.json'
        aws('s3api', 'get-object', '--bucket', bucket, '--key', 'dataset.json', str(download))
        if digest(download) != DATASET_SHA256:
            raise ValueError('Local S3 object differs from the AWS fixture')
        variables = dict(QUARKUS_S3_ENDPOINT_OVERRIDE='http://localstack:4566',
                         QUARKUS_S3_PATH_STYLE_ACCESS='true', QUARKUS_S3_AWS_REGION=REGION)
        aws('lambda', 'create-function', '--function-name', function,
            '--runtime', 'provided.al2023', '--architectures', 'arm64', '--handler', 'bootstrap',
            '--role', 'arn:aws:iam::000000000000:role/local-benchmark',
            '--memory-size', str(args.memory), '--timeout', '60',
            '--zip-file', 'fileb://' + str(artifact),
            '--environment', json.dumps(dict(Variables=variables)))
        created = True
        config = wait_active(function)
        expected_code = base64.b64encode(bytes.fromhex(artifact_hash)).decode()
        if (config.get('CodeSha256') != expected_code or config.get('Architectures') != ['arm64']
                or config.get('Runtime') != 'provided.al2023' or config.get('MemorySize') != args.memory):
            raise ValueError('Local Lambda artifact or configuration mismatch')
        # Whitelist configuration fields; never archive provider credentials.
        metadata['functionConfiguration'] = {k: config.get(k) for k in
            ('Runtime', 'Architectures', 'MemorySize', 'CodeSha256', 'State', 'Timeout')}
        (destination / 'metadata.json').write_text(json.dumps(metadata, indent=2))
        for repetition in range(1, args.repetitions + 1):
            for workload in (('cpu', 'io') if repetition % 2 else ('io', 'cpu')):
                for index in range(args.warmups + args.samples):
                    if digest(artifact) != artifact_hash or digest(dataset) != DATASET_SHA256:
                        raise ValueError('Artifact or fixture changed during the experiment')
                    stem = f'r{repetition}-{workload}-{index + 1:04d}'
                    row = dict(environment='localstack', repetition=repetition, workload=workload,
                               phase='warmup' if index < args.warmups else 'sample')
                    started = time.monotonic()
                    error = None
                    try:
                        response_file = destination / (stem + '.response.json')
                        payload = dict(workload=workload, bucket=bucket, key='dataset.json')
                        (destination / (stem + '.request.json')).write_text(json.dumps(payload))
                        result = aws('lambda', 'invoke', '--function-name', function,
                                     '--invocation-type', 'RequestResponse', '--cli-binary-format', 'raw-in-base64-out',
                                     '--payload', json.dumps(payload), '--log-type', 'Tail', str(response_file))
                        (destination / (stem + '.invoke.json')).write_text(json.dumps(result, indent=2))
                        log = base64.b64decode(result.get('LogResult', '')).decode('utf-8')
                        (destination / (stem + '.log.txt')).write_text(log)
                        row.update(validate(workload, result, json.loads(response_file.read_text()), log, args.memory))
                        row['outcome'] = 'valid'
                    except (RuntimeError, ValueError, OSError, subprocess.TimeoutExpired) as exc:
                        row.update(outcome='failed', error=str(exc))
                        error = exc
                    except KeyboardInterrupt:
                        row.update(outcome='failed', error='Cancelled')
                        raise
                    finally:
                        row['callerMs'] = (time.monotonic() - started) * 1000
                        rows.append(row)
                        with (destination / 'invocations.jsonl').open('a') as stream:
                            stream.write(json.dumps(row) + '\n')
                    print(f'{stem}: {row["outcome"]}', flush=True)
                    if error:
                        raise error
                    # Once per batch, after the first invocation creates its runtime container.
                    # Collect outside both handlerMs and callerMs, before remaining calls.
                    if index == 0:
                        capture_lambda_containers(metadata['docker'], function, repetition, workload)
                        (destination / 'metadata.json').write_text(json.dumps(metadata, indent=2))
    except (RuntimeError, ValueError, OSError, subprocess.TimeoutExpired) as error:
        stopped = str(error)
    except KeyboardInterrupt:
        stopped = 'Cancelled'
    finally:
        # Delete only unique resources belonging to this local run. Retain evidence on disk.
        commands = []
        if created:
            commands.append(('lambda', 'delete-function', '--function-name', function))
        commands += [('s3api', 'delete-object', '--bucket', bucket, '--key', 'dataset.json'),
                     ('s3api', 'delete-bucket', '--bucket', bucket)]
        for command in commands:
            try:
                aws(*command)
            except (RuntimeError, OSError, subprocess.TimeoutExpired) as error:
                cleanup_errors.append(str(error))
        final = dict(environment='localstack', stopReason=stopped, expectedInvocations=attempts,
                     recordedInvocations=len(rows), valid=sum(r['outcome'] == 'valid' for r in rows),
                     cleanupErrors=cleanup_errors, workloads=summarize(rows),
                     primaryMetric='handlerMs', measurementMetrics=MEASUREMENT_METRICS,
                     repetitions=summarize_repetitions(rows, args.repetitions))
        (destination / 'summary.json').write_text(json.dumps(final, indent=2))
        print(json.dumps(final, indent=2), flush=True)
    return 0 if stopped == 'Completed' and len(rows) == attempts and not cleanup_errors else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (RuntimeError, ValueError, OSError, subprocess.TimeoutExpired) as error:
        print(f'LocalStack experiment stopped: {error}', file=sys.stderr)
        sys.exit(1)
