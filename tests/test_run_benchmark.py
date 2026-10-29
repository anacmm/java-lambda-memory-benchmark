import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('runner', Path(__file__).resolve().parents[1] / 'scripts/run-benchmark.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class SafetyTests(unittest.TestCase):
    def test_report_and_handler_metrics_stay_distinct_by_repetition(self):
        rows = [dict(memoryMb=1024, workload='cpu', coldStart=False, phase='sample',
                     status='OK', repetition=i, durationMs=duration, handlerMs=handler,
                     billedGBSeconds=.1) for i, duration, handler in [(1, 120, 100), (2, 220, 200)]]
        combined = runner.summarize(rows)[0]
        self.assertEqual(combined['meanDurationMs'], 170)
        self.assertEqual(combined['meanHandlerMs'], 150)
        self.assertEqual(combined['primaryMetric'], 'durationMs')
        separate = runner.summarize_repetitions(rows)
        self.assertEqual([g['meanDurationMs'] for g in separate], [120, 220])
        self.assertEqual([g['meanHandlerMs'] for g in separate], [100, 200])
        self.assertEqual([g['repetition'] for g in separate], [1, 2])

    def test_handler_statistics_are_additive_for_older_measurements(self):
        row = dict(memoryMb=1024, workload='cpu', coldStart=False, phase='sample',
                   status='OK', durationMs=120, billedGBSeconds=.1)
        summary = runner.summarize([row])[0]
        self.assertEqual(summary['meanDurationMs'], 120)
        self.assertIsNone(summary['meanHandlerMs'])
        self.assertEqual(summary['handlerSamples'], 0)

    def test_invocation_limit_counts_failed_attempts(self):
        args = SimpleNamespace(region='eu-west-2', safety=runner.Safety(1800))
        args.safety.invocations = runner.MAX_INVOCATIONS - 1
        with patch.object(runner.subprocess, 'run', return_value=SimpleNamespace(returncode=1, stderr='error', stdout='')) as call:
            with self.assertRaises(runner.AwsError):
                runner.aws(args, 'lambda', 'invoke')
            with self.assertRaises(runner.BenchmarkStopped):
                runner.aws(args, 'lambda', 'invoke')
            self.assertEqual(call.call_count, 1)
            self.assertEqual(args.safety.invocations, runner.MAX_INVOCATIONS)
            self.assertEqual(call.call_args.kwargs['env']['AWS_MAX_ATTEMPTS'], '1')

    def test_deadline_blocks_calls_but_not_restoration(self):
        args = SimpleNamespace(region='eu-west-2', safety=runner.Safety(1800))
        args.safety.deadline = 0
        with patch.object(runner.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout='{}')) as call:
            with self.assertRaises(runner.BenchmarkStopped):
                runner.aws(args, 'lambda', 'invoke')
            call.assert_not_called()
            args.safety.restoring = True
            runner.aws(args, 'lambda', 'update-function-configuration')
            self.assertIsNone(call.call_args.kwargs['timeout'])

    def run_mocked(self, failure=None, extra=(), restore_failure=False):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'lambda/target').mkdir(parents=True)
            (root / 'sample').mkdir()
            (root / 'lambda/target/function.zip').write_bytes(b'zip')
            (root / 'sample/dataset.json').write_bytes(b'dataset')
            outputs = root / 'outputs.json'
            outputs.write_text(json.dumps({'JavaBenchmarkStack': {'FunctionName': 'function', 'BucketName': 'bucket'}}))
            destination = root / 'results'
            memory = 1024
            updates = []
            invocations = []
            def fake(command, **kwargs):
                nonlocal memory
                operation = tuple(command[3:5])
                data = {}
                if operation == ('lambda', 'get-function-configuration'):
                    data = dict(MemorySize=memory, LastUpdateStatus='Successful', CodeSha256=base64.b64encode(hashlib.sha256(b'zip').digest()).decode(), Runtime='provided.al2023', Architectures=['arm64'], FunctionArn='arn:aws:lambda:eu-west-2:123:function:function')
                elif operation == ('lambda', 'update-function-configuration'):
                    memory = int(command[-1])
                    updates.append(memory)
                    if memory == 1024 and restore_failure:
                        return SimpleNamespace(returncode=1, stderr='restore denied', stdout='')
                elif operation == ('lambda', 'invoke'):
                    invocations.append(command)
                    if failure == 'partial-cancel' and len(invocations) == 2:
                        raise KeyboardInterrupt
                    if failure == 'cancel':
                        raise KeyboardInterrupt
                    if failure == 'timeout':
                        raise subprocess.TimeoutExpired(command, 1)
                    if failure == 'errors':
                        return SimpleNamespace(returncode=1, stderr='API unavailable', stdout='')
                    workload = json.loads(command[command.index('--payload') + 1])['workload']
                    response = dict(recordsProcessed=4000, checksum='b1e029a3d2d7974c', status='OK') if workload == 'cpu' else dict(objectBytes=191961, checksum='crc32:1c396adb', status='OK')
                    Path(command[-1]).write_text(json.dumps(response))
                    event = dict(event='benchmark_invocation', requestId='id', memoryMb=memory, workload=workload, coldStart=False, status='OK')
                    log = json.dumps(event) + '\nREPORT RequestId: id Duration: 1 ms Billed Duration: 1 ms'
                    data = dict(LogResult=base64.b64encode(log.encode()).decode())
                return SimpleNamespace(returncode=0, stdout=json.dumps(data), stderr='')
            argv = ['runner', '--outputs', str(outputs), '--results', str(destination), '--memories', '256', '--samples', '4', '--warmups', '0', '--repetitions', '1', '--yes', *extra]
            with patch.object(runner, 'ROOT', root), patch('sys.argv', argv), patch.object(runner.subprocess, 'run', side_effect=fake), patch('builtins.print'):
                runner.main()
            return json.loads((destination / 'final-summary.json').read_text()), updates, invocations, list(destination.glob('*.log.txt'))

    def test_five_errors_stop_and_restore(self):
        final, updates, invokes, _ = self.run_mocked('errors')
        self.assertEqual(len(invokes), 5)
        self.assertIn('5 consecutive', final['stopReason'])
        self.assertEqual(updates, [256, 1024])
        self.assertEqual(sum(c['failed'] for c in final['configurations']), 5)

    def test_cancellation_and_timeout_restore_and_record_attempt(self):
        for failure, reason in [('cancel', 'Ctrl+C'), ('timeout', 'duration')]:
            with self.subTest(failure=failure):
                final, updates, invokes, _ = self.run_mocked(failure)
                self.assertIn(reason, final['stopReason'])
                self.assertEqual(updates, [256, 1024])
                self.assertEqual(final['invocationAttempts'], 1)
                self.assertEqual(len(invokes), 1)

    def test_success_preserves_raw_results_and_classification(self):
        final, updates, invokes, logs = self.run_mocked()
        self.assertEqual(final['stopReason'], 'Completed')
        self.assertEqual(len(invokes), 8)
        self.assertEqual(len(logs), 8)
        self.assertEqual([c['warm'] for c in final['configurations']], [4, 4])
        self.assertEqual(updates, [256, 1024])

    def test_cancellation_preserves_previous_valid_result(self):
        final, updates, invokes, logs = self.run_mocked('partial-cancel')
        self.assertEqual(final['invocationAttempts'], 2)
        self.assertEqual(len(logs), 1)
        self.assertEqual(final['configurations'][0]['warm'], 1)
        self.assertEqual(final['configurations'][0]['failed'], 1)
        self.assertEqual(updates, [256, 1024])

    def test_confirmation_declined_makes_no_aws_calls(self):
        with tempfile.TemporaryDirectory() as directory:
            outputs = Path(directory) / 'outputs.json'
            outputs.write_text(json.dumps({'JavaBenchmarkStack': {'FunctionName': 'f', 'BucketName': 'b'}}))
            with patch('sys.argv', ['runner', '--outputs', str(outputs)]), patch('builtins.input', return_value='no'), patch('builtins.print') as printing, patch.object(runner.subprocess, 'run') as aws:
                runner.main()
                aws.assert_not_called()
                self.assertIn('Expected invocations: 1452', printing.call_args_list[0].args[0])

    def test_restoration_failure_is_reported(self):
        final, _, _, _ = self.run_mocked('cancel', restore_failure=True)
        self.assertEqual(final['restorationError'], 'restore denied')

    def test_over_limit_rejected_before_aws(self):
        with patch('sys.argv', ['runner', '--samples', '100']), patch.object(runner.subprocess, 'run') as aws, patch('sys.stderr'):
            with self.assertRaises(SystemExit):
                runner.main()
            aws.assert_not_called()

    def test_success_resets_consecutive_errors(self):
        args = SimpleNamespace(region='eu-west-2', safety=runner.Safety(1800))
        args.safety.errors = 4
        with patch.object(runner.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout='{}')):
            runner.aws(args, 'sts', 'get-caller-identity')
        self.assertEqual(args.safety.errors, 0)


if __name__ == '__main__':
    unittest.main()
