"""Check service delegation and safe migration from a manually started AppImage."""
from importlib.machinery import SourceFileLoader
import importlib.util
from contextlib import redirect_stderr, redirect_stdout
import io
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ENTRY = Path(__file__).resolve().parents[3] / 'bin/agentoo-cloud-storage'
spec = importlib.util.spec_from_loader('cloud_storage', SourceFileLoader('cloud_storage', str(ENTRY)))
cloud = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cloud)

RUNNING = {'LoadState': 'loaded', 'ActiveState': 'active'}
STOPPED = {'LoadState': 'not-found', 'ActiveState': 'inactive'}


class CloudStorageTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def result(self, code=0, stdout='', stderr=''):
        return subprocess.CompletedProcess([], code, stdout, stderr)

    def test_omitted_arguments_show_contextual_help_before_runtime_checks(self):
        for arguments, usage in [([], 'usage: agentoo cloud-storage '),
                                 (['pcloud'], 'usage: agentoo cloud-storage pcloud ')]:
            output, errors = io.StringIO(), io.StringIO()
            with self.subTest(arguments=arguments), \
                    patch.object(sys, 'argv', ['agentoo-cloud-storage', *arguments]), \
                    patch.object(cloud.os, 'geteuid', side_effect=AssertionError('checked privileges')), \
                    patch.object(cloud, 'call', side_effect=AssertionError('contacted systemd')), \
                    patch.object(cloud, 'pcloud_mains', side_effect=AssertionError('inspected processes')), \
                    redirect_stdout(output), redirect_stderr(errors):
                self.assertEqual(cloud.main(), 0)
            self.assertTrue(output.getvalue().startswith(usage))
            self.assertEqual(errors.getvalue(), '')

    def test_invalid_arguments_still_fail_before_runtime_checks(self):
        for arguments in [['unknown'], ['pcloud', 'unknown'], ['pcloud', '--unknown']]:
            with self.subTest(arguments=arguments), \
                    patch.object(sys, 'argv', ['agentoo-cloud-storage', *arguments]), \
                    patch.object(cloud, 'call', side_effect=AssertionError('contacted systemd')), \
                    redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    cloud.main()
                self.assertEqual(error.exception.code, 2)

    def test_start_is_detached_scoped_and_preserves_session_overrides(self):
        executable = self.root / 'pcloud'
        executable.write_text('#!/bin/sh\nexit 0\n')
        executable.chmod(0o755)
        env = {'HOME': str(self.root), 'DISPLAY': ':7', 'WAYLAND_DISPLAY': 'wayland-2',
               'XDG_CONFIG_HOME': str(self.root / 'my config'), 'TOKEN_NOT_FOR_PCLOUD': 'private'}
        with patch.dict(os.environ, env, clear=True), patch.object(cloud, 'PCLOUD', executable), \
                patch.object(cloud, 'pcloud_mains', return_value=[]), \
                patch.object(cloud, 'service_state', return_value=RUNNING), \
                patch.object(cloud, 'call', return_value=self.result()) as call:
            self.assertEqual(cloud.start(STOPPED), 0)
        argv = call.call_args.args[0]
        self.assertEqual(argv[:2], ['systemd-run', '--user'])
        self.assertIn('--collect', argv)
        self.assertIn('--service-type=exec', argv)
        self.assertIn('--property=KillMode=mixed', argv)
        self.assertIn('--property=SuccessExitStatus=SIGKILL', argv)
        self.assertIn('--property=Restart=no', argv)
        self.assertIn('--setenv=XDG_CONFIG_HOME=' + str(self.root / 'my config'), argv)
        self.assertEqual(argv[-1], str(executable))
        self.assertFalse(any('TOKEN_NOT_FOR_PCLOUD' in arg for arg in argv))
        self.assertFalse(any(arg in ('--scope', '--pty', '--pipe') for arg in argv))

    def test_start_is_idempotent_and_refuses_an_unmanaged_instance(self):
        with patch.object(cloud, 'call') as call:
            self.assertEqual(cloud.start(RUNNING), 0)
            call.assert_not_called()
            with patch.object(cloud, 'pcloud_mains', return_value=[123]):
                with self.assertRaisesRegex(RuntimeError, 'outside the service'):
                    cloud.start(STOPPED)
                call.assert_not_called()

    def test_start_requires_app_and_graphical_environment_before_launch(self):
        with patch.object(cloud, 'pcloud_mains', return_value=[]), \
                patch.object(cloud, 'PCLOUD', self.root / 'absent'), patch.object(cloud, 'call') as call:
            with self.assertRaisesRegex(RuntimeError, 'Install net-misc'):
                cloud.start(STOPPED)
            call.assert_not_called()
        executable = self.root / 'pcloud'
        executable.touch(mode=0o755)
        with patch.object(cloud, 'pcloud_mains', return_value=[]), \
                patch.object(cloud, 'PCLOUD', executable), patch.dict(os.environ, {}, clear=True), \
                patch.object(cloud, 'call') as call:
            with self.assertRaisesRegex(RuntimeError, 'graphical-session terminal'):
                cloud.start(STOPPED)
            call.assert_not_called()

    def test_start_reports_failure_or_early_exit(self):
        executable = self.root / 'pcloud'
        executable.touch(mode=0o755)
        with patch.object(cloud, 'PCLOUD', executable), patch.dict(os.environ, {'DISPLAY': ':7'}), \
                patch.object(cloud, 'pcloud_mains', return_value=[]), \
                patch.object(cloud, 'service_state', return_value=STOPPED):
            for result, message in [(self.result(1, stderr='unit rejected'), 'unit rejected'),
                                    (self.result(), 'exited during startup')]:
                with self.subTest(result=result), patch.object(cloud, 'call', return_value=result):
                    with self.assertRaisesRegex(RuntimeError, message):
                        cloud.start(STOPPED)

    def test_stop_waits_for_systemd_before_handling_unmanaged_processes(self):
        events = []
        def call(argv):
            events.append(argv)
            return self.result()
        with patch.object(cloud, 'call', side_effect=call), \
                patch.object(cloud, 'stop_unmanaged', side_effect=lambda: events.append('legacy')):
            self.assertEqual(cloud.stop(RUNNING), 0)
        self.assertEqual(events, [['systemctl', '--user', 'stop', cloud.UNIT], 'legacy'])
        with patch.object(cloud, 'call', return_value=self.result(1, stderr='stop failed')), \
                patch.object(cloud, 'service_state', return_value=RUNNING), \
                patch.object(cloud, 'stop_unmanaged') as legacy:
            with self.assertRaisesRegex(RuntimeError, 'stop failed'):
                cloud.stop(RUNNING)
            legacy.assert_not_called()

    def test_concurrent_stop_collection_is_success_and_start_during_stop_is_rejected(self):
        with patch.object(cloud, 'call', return_value=self.result(5, stderr='unit not loaded')), \
                patch.object(cloud, 'service_state', return_value=STOPPED), \
                patch.object(cloud, 'stop_unmanaged') as legacy:
            self.assertEqual(cloud.stop(RUNNING), 0)
            legacy.assert_called_once_with()
        with patch.object(cloud, 'call') as call:
            with self.assertRaisesRegex(RuntimeError, 'still stopping'):
                cloud.start({'LoadState': 'loaded', 'ActiveState': 'deactivating'})
            call.assert_not_called()

    def test_missing_unit_is_stopped_but_user_bus_errors_are_reported(self):
        with patch.object(cloud, 'call', return_value=self.result(
                1, 'LoadState=not-found\nActiveState=inactive\n')):
            self.assertEqual(cloud.service_state(), STOPPED)
        with patch.object(cloud, 'call', return_value=self.result(1, stderr='Failed to connect to bus')):
            with self.assertRaisesRegex(RuntimeError, 'connect to bus'):
                cloud.service_state()

    def test_status_distinguishes_managed_unmanaged_and_stopped(self):
        with patch.object(cloud.os, 'geteuid', return_value=1000), \
                patch.object(sys, 'argv', ['agentoo-cloud-storage', 'pcloud', 'status']):
            for state, mains, expected in [(RUNNING, [], 0), (STOPPED, [123], 0), (STOPPED, [], 3)]:
                with self.subTest(state=state, mains=mains), \
                        patch.object(cloud, 'service_state', return_value=state), \
                        patch.object(cloud, 'pcloud_mains', return_value=mains):
                    self.assertEqual(cloud.main(), expected)

    def test_only_owned_appimage_main_processes_match(self):
        proc = self.root / 'proc'
        proc.mkdir()
        for pid, executable, args in [
            (101, '/tmp/.mount_pCloud123/pcloud.bin', b'pcloud.bin\0--no-sandbox\0'),
            (102, '/tmp/.mount_pCloud123/pcloud.bin', b'pcloud.bin\0--type=renderer\0'),
            (103, '/tmp/.mount_pCloud123/chrome_crashpad_handler', b'chrome_crashpad_handler\0'),
            (104, '/tmp/other/pcloud.bin', b'pcloud.bin\0'),
        ]:
            directory = proc / str(pid)
            directory.mkdir()
            (directory / 'exe').symlink_to(executable)
            (directory / 'cmdline').write_bytes(args)
        with patch.object(cloud, 'PROC', proc):
            self.assertEqual(cloud.pcloud_mains(), [101])
            with patch.object(cloud.os, 'geteuid', return_value=os.geteuid() + 1):
                self.assertEqual(cloud.pcloud_mains(), [])

    def test_legacy_stop_uses_pidfds_rechecks_identity_and_waits_for_every_main(self):
        with patch.object(cloud, 'pcloud_mains', return_value=[101, 102, 103]), \
                patch.object(cloud.os, 'pidfd_open', side_effect=[10, 11, 12]), \
                patch.object(cloud, 'is_pcloud_main', side_effect=[True, False, True]), \
                patch.object(cloud.signal, 'pidfd_send_signal') as send, \
                patch.object(cloud.select, 'select', side_effect=[([10], [], []), ([12], [], [])]) as wait, \
                patch.object(cloud.os, 'close') as close:
            cloud.stop_unmanaged()
        self.assertEqual([call.args for call in send.call_args_list], [(10, signal.SIGTERM), (12, signal.SIGTERM)])
        self.assertEqual([call.args[0] for call in wait.call_args_list], [[10, 12], [12]])
        self.assertEqual({call.args[0] for call in close.call_args_list}, {10, 11, 12})

    def test_legacy_stop_timeout_closes_descriptors_without_forcing_a_kill(self):
        with patch.object(cloud, 'pcloud_mains', return_value=[101]), \
                patch.object(cloud.os, 'pidfd_open', return_value=10), \
                patch.object(cloud, 'is_pcloud_main', return_value=True), \
                patch.object(cloud.signal, 'pidfd_send_signal') as send, \
                patch.object(cloud.select, 'select', return_value=([], [], [])), \
                patch.object(cloud.time, 'monotonic', side_effect=[0, 0, 30]), \
                patch.object(cloud.os, 'close') as close:
            with self.assertRaisesRegex(RuntimeError, '30 seconds'):
                cloud.stop_unmanaged()
        send.assert_called_once_with(10, signal.SIGTERM)
        close.assert_called_once_with(10)
