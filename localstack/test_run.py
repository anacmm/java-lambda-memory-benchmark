import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import run


class LocalExperimentTests(unittest.TestCase):
    def event(self, workload='io', cold=False):
        return dict(event='benchmark_invocation', workload=workload, status='OK',
                    checksum=run.EXPECTED[workload]['checksum'], objectBytes=191961,
                    memoryMb=1024, coldStart=cold, s3Ms=3.0, cpuMs=.1, handlerMs=3.1)

    def test_real_credentials_and_profile_cannot_reach_cli(self):
        with patch.dict(os.environ, {'AWS_PROFILE': 'production', 'AWS_ACCESS_KEY_ID': 'real',
                                     'AWS_SESSION_TOKEN': 'real', 'AWS_ENDPOINT_URL_S3': 'https://s3.amazonaws.com',
                                     'AWS_CONTAINER_CREDENTIALS_FULL_URI': 'https://example.com',
                                     'AWS_CONFIG_FILE': '/real/config', 'LOCALSTACK_AUTH_TOKEN': 'secret',
                                     'http_proxy': 'http://external.example', 'HTTPS_PROXY': 'http://external.example'}):
            env = run.local_env()
        self.assertEqual(env['AWS_ACCESS_KEY_ID'], 'test')
        self.assertEqual(env['AWS_CONFIG_FILE'], os.devnull)
        for key in ('AWS_PROFILE', 'AWS_SESSION_TOKEN', 'AWS_ENDPOINT_URL_S3',
                    'AWS_CONTAINER_CREDENTIALS_FULL_URI'):
            self.assertNotIn(key, env)
        for key in ('http_proxy', 'HTTPS_PROXY', 'LOCALSTACK_AUTH_TOKEN'):
            self.assertNotIn(key, env)
        command = run.aws_command('lambda', 'invoke')
        self.assertEqual(command[command.index('--endpoint-url') + 1], 'http://127.0.0.1:4566')

    def test_health_redirect_is_blocked(self):
        with self.assertRaises(RuntimeError):
            run.NoRedirect().redirect_request(None, None, 302, 'Found', {}, 'https://lambda.amazonaws.com')

    def test_defaults_match_aws_per_configuration(self):
        args = run.parse_args([])
        self.assertEqual((args.samples, args.warmups, args.repetitions), (30, 3, 2))
        self.assertEqual(args.memories, run.MEMORIES)
        self.assertEqual(2 * args.repetitions * (args.samples + args.warmups), 132)

    def test_memory_selection_and_matrix_limit(self):
        self.assertEqual(run.parse_args(['--memory', '1769']).memories, [1769])
        self.assertEqual(run.parse_args(['--memories', '256', '512', '256']).memories, [256, 512])
        with patch('sys.stderr'), self.assertRaises(SystemExit):
            run.parse_args(['--samples', '100'])

    def test_matrix_runs_in_order_and_stops_after_failure(self):
        for failure in (False, True):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as directory:
                calls = []
                def single(args, destination):
                    calls.append(args.memory)
                    destination.mkdir(parents=True)
                    (destination / 'summary.json').write_text(json.dumps(dict(stopReason='failed' if failure else 'Completed')))
                    return int(failure)
                with patch.object(run, 'ROOT', Path(directory)), patch.object(run, 'run_single', side_effect=single), patch('sys.argv', ['local', '--memories', '256', '512']), patch('builtins.print'):
                    self.assertEqual(run.main(), int(failure))
                self.assertEqual(calls, [256] if failure else [256, 512])
                summary = json.loads(next(Path(directory).rglob('matrix-summary.json')).read_text())
                self.assertEqual(summary['expectedInvocations'], 264)
                self.assertEqual(len(summary['configurations']), len(calls))

    def test_repetition_statistics_do_not_mix_batches(self):
        rows = [dict(self.event(), phase='sample', outcome='valid', callerMs=value,
                     handlerMs=value, repetition=i) for i, value in [(1, 10), (2, 90)]]
        self.assertEqual(run.summarize(rows)[1]['handlerMs']['mean'], 50)
        separate = run.summarize_repetitions(rows, 3)
        self.assertEqual(separate[0]['workloads'][1]['handlerMs']['mean'], 10)
        self.assertEqual(separate[1]['workloads'][1]['handlerMs']['mean'], 90)
        self.assertEqual(separate[2]['workloads'][1]['warmCollected'], 0)

    def test_unavailable_docker_is_explicit_and_nonfatal(self):
        with patch.object(run, 'docker_read', side_effect=OSError('unavailable')):
            metadata = run.docker_metadata()
            run.capture_lambda_containers(metadata, 'our-function', 1, 'cpu')
        self.assertIsNone(metadata['version'])
        self.assertIsNone(metadata['daemonResources'])
        self.assertEqual(len(metadata['collectionWarnings']), 3)
        self.assertIn('unavailableReason', metadata['lambdaContainerSnapshots'][0])

    def test_docker_metadata_and_exact_function_association(self):
        responses = [json.dumps(dict(client='1', server='2')),
                     json.dumps(dict(cpus=6, memoryBytes=8000000000)), 'emulator',
                     json.dumps(dict(id='emulator', imageId='sha256:image', limits={})),
                     json.dumps(dict(repoDigests=['localstack@sha256:digest'])),
                     'emulator\nlambda\nother',
                     json.dumps(dict(functionName='', limits={})),
                     json.dumps(dict(functionName='our-function', limits=dict(nanoCpus=500000000, memoryBytes=1073741824))),
                     json.dumps(dict(functionName='other-function', limits={}))]
        with patch.object(run, 'docker_read', side_effect=responses) as docker:
            metadata = run.docker_metadata()
            run.capture_lambda_containers(metadata, 'our-function', 2, 'io')
        self.assertEqual(metadata['daemonResources']['cpus'], 6)
        self.assertEqual(metadata['localstackContainers'][0]['image']['repoDigests'], ['localstack@sha256:digest'])
        containers = metadata['lambdaContainerSnapshots'][0]['containers']
        self.assertEqual(len(containers), 1)
        self.assertEqual(containers[0]['limits']['memoryBytes'], 1073741824)
        # No full inspect JSON or full environment is requested.
        inspect_formats = [call.args[2] for call in docker.call_args_list if call.args[0] == 'inspect']
        self.assertTrue(all(fmt == run.CONTAINER_FORMAT for fmt in inspect_formats))
        self.assertNotIn('{{json .Config.Env}}', run.CONTAINER_FORMAT)

    def test_http_200_with_function_error_is_rejected(self):
        with self.assertRaises(ValueError):
            run.validate('io', dict(StatusCode=200, FunctionError='Unhandled'),
                         run.EXPECTED['io'], json.dumps(self.event()), 1024)

    def test_checksum_and_response_shape_are_exact(self):
        for response in (dict(run.EXPECTED['io'], checksum='wrong'),
                         dict(run.EXPECTED['io'], recordsProcessed=4000)):
            with self.assertRaises(ValueError):
                run.validate('io', dict(StatusCode=200), response, json.dumps(self.event()), 1024)

    def test_cpu_and_io_accept_prefixed_logs_without_aws_report(self):
        for workload in ('cpu', 'io'):
            event = self.event(workload)
            self.assertEqual(run.validate(workload, dict(StatusCode=200), run.EXPECTED[workload],
                                          'local log prefix ' + json.dumps(event), 1024), event)

    def test_missing_duplicate_mismatched_or_bad_timings_are_rejected(self):
        event = self.event()
        logs = ['', json.dumps(event) + '\n' + json.dumps(event),
                json.dumps(dict(event, memoryMb=512)), json.dumps(dict(event, workload='cpu')),
                json.dumps(dict(event, handlerMs=None)), json.dumps(dict(event, s3Ms=float('nan')))]
        for log in logs:
            with self.subTest(log=log), self.assertRaises(ValueError):
                run.validate('io', dict(StatusCode=200), run.EXPECTED['io'], log, 1024)

    def test_summary_excludes_warmups_cold_calls_and_errors(self):
        rows = [dict(self.event(), phase='sample', outcome='valid', callerMs=4),
                dict(self.event(cold=True), phase='sample', outcome='valid', callerMs=400),
                dict(self.event(), phase='warmup', outcome='valid', callerMs=400),
                dict(workload='io', phase='sample', outcome='failed')]
        summary = run.summarize(rows)[1]
        self.assertEqual(summary['warmCollected'], 1)
        self.assertEqual(summary['coldCollected'], 1)
        self.assertEqual(summary['callerMs']['mean'], 4)

    def test_jvm_and_x86_artifacts_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            artifact = Path(folder) / 'function.zip'
            for header in (b'not ELF', b'\x7fELF\x02\x01' + b'\0' * 12 + b'\x3e\0'):
                with zipfile.ZipFile(artifact, 'w') as archive:
                    for name, data in [('bootstrap', b''), ('cacerts', b''), ('runner', header)]:
                        archive.writestr(name, data)
                with self.assertRaises(ValueError):
                    run.check_artifact(artifact)


if __name__ == '__main__':
    unittest.main()
