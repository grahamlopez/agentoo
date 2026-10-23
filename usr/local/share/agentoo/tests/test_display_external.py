"""DDC command selection and validation; never writes real monitor settings."""
from pathlib import Path
import io
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from test_desktop_commands import load

DISPLAY = load('display')
EXTERNAL = DISPLAY.display_external


class ExternalDisplay(unittest.TestCase):
    def command(self, *tokens, status=0):
        parser = DISPLAY.build_parser()
        args = parser.parse_args(['external', *tokens])
        with patch.object(EXTERNAL.shutil, 'which', return_value='/usr/bin/ddcutil'), \
                patch.object(EXTERNAL, 'dell_u5226kw_connected', return_value=False), \
                patch.object(EXTERNAL.subprocess, 'run', return_value=subprocess.CompletedProcess([], status)) as run:
            self.assertEqual(EXTERNAL.run(args, parser), status)
        return run.call_args.args[0]

    def test_read_commands_never_write(self):
        self.assertEqual(self.command('list'), ['ddcutil', 'detect'])
        for name, suffix in [('capabilities', ['capabilities']), ('brightness', ['getvcp', '10']),
                             ('volume', ['getvcp', '62']), ('mute', ['getvcp', '8D']),
                             ('input', ['getvcp', '60']), ('get', ['getvcp', 'E9'])]:
            with self.subTest(name=name):
                tokens = ['E9'] if name == 'get' else []
                self.assertEqual(self.command(name, *tokens, '--bus', '16'), ['ddcutil', '--bus', '16', *suffix])

    def test_write_encoding_and_exit_status(self):
        for tokens, suffix in [
            (['brightness', 'up'], ['10', '+', '5', '--verify']),
            (['brightness', 'down'], ['10', '-', '5', '--verify']),
            (['brightness', '0'], ['10', '0', '--verify']),
            (['volume', '100'], ['62', '100', '--verify']),
            (['mute', 'on'], ['8D', '1', '--verify']),
            (['mute', 'off'], ['8D', '2', '--verify']),
            (['input', '0x19', '--no-verify'], ['60', '25', '--noverify']),
            (['set', '0xe9', '0x21', '--no-verify'], ['E9', '33', '--permit-unknown-feature', '--noverify']),
        ]:
            with self.subTest(tokens=tokens):
                self.assertEqual(self.command(*tokens, '--bus', '16', status=7),
                                 ['ddcutil', '--bus', '16', 'setvcp', *suffix])

    def test_nonstandard_relative_volume_never_writes(self):
        args = DISPLAY.build_parser().parse_args(['external', 'volume', 'up', '--bus', '13'])
        with patch.object(EXTERNAL.shutil, 'which', return_value='/usr/bin/ddcutil'), \
                patch.object(EXTERNAL, 'dell_u5226kw_connected', return_value=False), \
                patch.object(EXTERNAL.subprocess, 'run', return_value=subprocess.CompletedProcess(
                    [], 0, 'VCP 62 C 178 65380\n', '')) as run:
            with self.assertRaisesRegex(RuntimeError, 'nonstandard volume'):
                EXTERNAL.run(args, None)
            self.assertEqual(run.call_count, 1)
            self.assertNotIn('setvcp', run.call_args.args[0])

    def test_relative_volume_rejects_noncontinuous_even_in_range(self):
        for reply in ('VCP 62 SNC x32', 'VCP 62 CNC x00 x64 x00 x32',
                      'VCP 62 C 101 100', 'VCP 62 C 50 101'):
            with self.subTest(reply=reply), patch.object(EXTERNAL.subprocess, 'run',
                    return_value=subprocess.CompletedProcess([], 0, reply, '')) as run:
                with self.assertRaisesRegex(RuntimeError, 'nonstandard volume'):
                    EXTERNAL.check_relative_volume(['ddcutil'])
                self.assertEqual(run.call_count, 1)
                self.assertEqual(run.call_args.kwargs['timeout'], EXTERNAL.DDC_TIMEOUT)

    def test_shared_read_returns_current_and_maximum_from_one_read(self):
        for reply, expected in [('VCP 62 C 30 100', ('C', 30, 100)),
                                ('VCP E7 CNC x04 x05 x16 x40', ('CNC', 0x1640, 0x0405))]:
            with self.subTest(reply=reply), patch.object(EXTERNAL.subprocess, 'run',
                    return_value=subprocess.CompletedProcess([], 0, reply, '')) as run:
                self.assertEqual(EXTERNAL._read_feature(['ddcutil'], reply.split()[1]), expected)
                self.assertEqual(run.call_count, 1)

    def test_internal_read_timeout_is_safe(self):
        for read in (lambda: EXTERNAL.read_feature(['ddcutil'], 'E9'),
                     lambda: EXTERNAL.check_relative_volume(['ddcutil'])):
            with patch.object(EXTERNAL.subprocess, 'run',
                              side_effect=subprocess.TimeoutExpired('ddcutil', 5)) as run:
                with self.assertRaisesRegex(RuntimeError, 'Timed out reading VCP'):
                    read()
                self.assertEqual(run.call_count, 1)

    def test_switch_timeout_never_retries(self):
        with patch.object(EXTERNAL.subprocess, 'run',
                          side_effect=subprocess.TimeoutExpired('ddcutil', 5)) as run:
            with self.assertRaisesRegex(RuntimeError, 'may have applied it.*No write was retried'):
                EXTERNAL.write_switch(['ddcutil'], 'E7', 0xFF00)
            self.assertEqual(run.call_count, 1)
            self.assertEqual(run.call_args.kwargs['timeout'], EXTERNAL.DDC_TIMEOUT)

    def test_volume_timeout_restores_only_speaker_off(self):
        args = DISPLAY.build_parser().parse_args(['external', 'volume', '40', '--bus', '13'])
        timeout = subprocess.TimeoutExpired('ddcutil', 5)
        for raw, restoration in ((45, None), (173, subprocess.CompletedProcess([], 0)),
                                 (173, subprocess.CompletedProcess([], 1)), (173, timeout)):
            effects = [timeout] if restoration is None else [timeout, restoration]
            with self.subTest(raw=raw, restoration=restoration), \
                    patch.object(EXTERNAL, 'read_feature', return_value=raw), \
                    patch.object(EXTERNAL.subprocess, 'run', side_effect=effects) as run:
                message = ('speaker state is uncertain' if restoration is timeout or
                           getattr(restoration, 'returncode', 0) else 'no volume write was retried')
                with self.assertRaisesRegex(RuntimeError, message):
                    EXTERNAL.run_dell_volume(args, ['ddcutil'])
                self.assertEqual(run.call_count, len(effects))
                for call in run.call_args_list:
                    self.assertEqual(call.kwargs['timeout'], EXTERNAL.DDC_TIMEOUT)
                if restoration is not None:
                    self.assertEqual(run.call_args.args[0],
                                     ['ddcutil', 'setvcp', '8D', '1', '--noverify'])

    def test_standard_relative_volume(self):
        args = DISPLAY.build_parser().parse_args(['external', 'volume', 'down', '--bus', '13'])
        with patch.object(EXTERNAL.shutil, 'which', return_value='/usr/bin/ddcutil'), \
                patch.object(EXTERNAL, 'dell_u5226kw_connected', return_value=False), \
                patch.object(EXTERNAL.subprocess, 'run', side_effect=[
                    subprocess.CompletedProcess([], 0, 'VCP 62 C 30 100\n', ''),
                    subprocess.CompletedProcess([], 0)]) as run:
            self.assertEqual(EXTERNAL.run(args, None), 0)
            self.assertEqual(run.call_args.args[0], ['ddcutil', '--bus', '13', 'setvcp', '62', '-', '5', '--verify'])

    def test_dell_identity_required_even_with_explicit_bus(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(EXTERNAL, 'DRM', Path(directory)):
            path = self.output(Path(directory), 'card0-DP-4', bus=13)
            edid = bytearray(128)
            edid[8:12] = bytes.fromhex('10ac9e43')
            (path / 'edid').write_bytes(edid)
            EXTERNAL.require_dell_u5226kw(13)
            edid[10] = 0
            (path / 'edid').write_bytes(edid)
            args = DISPLAY.build_parser().parse_args(['external', 'layout', '50-50', '--bus', '13'])
            with patch.object(EXTERNAL.shutil, 'which', return_value='/usr/bin/ddcutil'), \
                    patch.object(EXTERNAL.subprocess, 'run') as run:
                with self.assertRaisesRegex(RuntimeError, 'requires a connected Dell'):
                    EXTERNAL.run(args, None)
                run.assert_not_called()

    def test_feature_read_formats_and_errors(self):
        for reply, expected in [('VCP E9 CNC x00 xff x00 x22', 0x22),
                                ('VCP E8 CNC xff xff x67 x31', 0x6731),
                                ('VCP 60 SNC x19', 0x19), ('VCP 10 C 50 100', 50)]:
            code = reply.split()[1]
            with self.subTest(reply=reply), patch.object(EXTERNAL.subprocess, 'run',
                    return_value=subprocess.CompletedProcess([], 0, reply, '')):
                self.assertEqual(EXTERNAL.read_feature(['ddcutil', '--bus', '13'], code), expected)
        with patch.object(EXTERNAL.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, 'VCP E9 ERR', '')):
            with self.assertRaisesRegex(RuntimeError, 'Unexpected response'):
                EXTERNAL.read_feature(['ddcutil'], 'E9')

    def test_named_layout_waits_for_readback_without_rewriting(self):
        args = DISPLAY.build_parser().parse_args(['external', 'layout', '33-67', '--bus', '13'])
        with patch.object(EXTERNAL, 'require_dell_u5226kw'), \
                patch.object(EXTERNAL.shutil, 'which', return_value='/usr/bin/ddcutil'), \
                patch.object(EXTERNAL.time, 'sleep'), patch('sys.stdout', new_callable=io.StringIO) as output, \
                patch.object(EXTERNAL.subprocess, 'run', side_effect=[
                    subprocess.CompletedProcess([], 0),
                    subprocess.CompletedProcess([], 1, '', 'ENXIO'),
                    subprocess.CompletedProcess([], 0, 'VCP E9 CNC x00 xff x00 x24', ''),
                    subprocess.CompletedProcess([], 0, 'VCP E9 CNC x00 xff x00 x2d', '')]) as run:
            self.assertEqual(EXTERNAL.run(args, None), 0)
            writes = [c.args[0] for c in run.call_args_list if 'setvcp' in c.args[0]]
            self.assertEqual(writes, [['ddcutil', '--bus', '13', 'setvcp', 'E9', '45', '--permit-unknown-feature', '--noverify']])
            self.assertIn('33-67 (0x2D)', output.getvalue())

    def test_readback_failure_never_repeats_write(self):
        args = DISPLAY.build_parser().parse_args(['external', 'layout', 'off', '--bus', '13'])
        with patch.object(EXTERNAL, 'require_dell_u5226kw'), \
                patch.object(EXTERNAL.shutil, 'which', return_value='/usr/bin/ddcutil'), \
                patch.object(EXTERNAL.time, 'sleep'), \
                patch.object(EXTERNAL, 'write_switch') as write, \
                patch.object(EXTERNAL, 'read_feature', side_effect=RuntimeError('ENXIO')):
            with self.assertRaisesRegex(RuntimeError, 'No write was retried'):
                EXTERNAL.run(args, None)
            write.assert_called_once()

    def test_position_requires_pip_and_is_sent_only_once(self):
        args = DISPLAY.build_parser().parse_args(['external', 'pip-position', 'next', '--bus', '13'])
        with patch.object(EXTERNAL, 'require_dell_u5226kw'), \
                patch.object(EXTERNAL.shutil, 'which', return_value='/usr/bin/ddcutil'), \
                patch.object(EXTERNAL, 'read_feature', return_value=0x24), \
                patch.object(EXTERNAL, 'write_switch') as write:
            with self.assertRaisesRegex(RuntimeError, 'requires pip-small or pip-large'):
                EXTERNAL.run(args, None)
            write.assert_not_called()
        with patch.object(EXTERNAL, 'require_dell_u5226kw'), \
                patch.object(EXTERNAL.shutil, 'which', return_value='/usr/bin/ddcutil'), \
                patch.object(EXTERNAL, 'read_feature', return_value=0x22), \
                patch.object(EXTERNAL, 'write_switch') as write, patch('sys.stderr'):
            self.assertEqual(EXTERNAL.run(args, None), 0)
            write.assert_called_once_with(['ddcutil', '--bus', '13'], 'E9', 2)

    def test_sub_input_requires_mapped_active_layout(self):
        args = DISPLAY.build_parser().parse_args(['external', 'sub-input', 'hdmi1', '--bus', '13'])
        with patch.object(EXTERNAL, 'require_dell_u5226kw'), \
                patch.object(EXTERNAL.shutil, 'which', return_value='/usr/bin/ddcutil'), \
                patch.object(EXTERNAL, 'read_feature', return_value=0), \
                patch.object(EXTERNAL, 'write_switch') as write:
            with self.assertRaisesRegex(RuntimeError, 'requires a mapped active'):
                EXTERNAL.run(args, None)
            write.assert_not_called()
        with patch.object(EXTERNAL, 'require_dell_u5226kw'), \
                patch.object(EXTERNAL.shutil, 'which', return_value='/usr/bin/ddcutil'), \
                patch.object(EXTERNAL, 'read_feature', side_effect=[0x22, 0x6731]), \
                patch.object(EXTERNAL.time, 'sleep'), \
                patch.object(EXTERNAL, 'write_switch') as write, patch('sys.stdout'):
            self.assertEqual(EXTERNAL.run(args, None), 0)
            write.assert_called_once_with(['ddcutil', '--bus', '13'], 'E8', 0x6731)

    def test_dell_volume_decodes_mute_without_writes(self):
        args = DISPLAY.build_parser().parse_args(['external', 'volume', '--bus', '13'])
        with patch.object(EXTERNAL.shutil, 'which', return_value='/usr/bin/ddcutil'), \
                patch.object(EXTERNAL, 'dell_u5226kw_connected', return_value=True), \
                patch.object(EXTERNAL, 'read_feature', return_value=173), \
                patch.object(EXTERNAL.subprocess, 'run') as run, patch('sys.stdout', new_callable=io.StringIO) as output:
            self.assertEqual(EXTERNAL.run(args, None), 0)
            self.assertEqual(output.getvalue(), '45/100 (speakers off)\n')
            run.assert_not_called()

    def test_dell_relative_volume_restores_speaker_off(self):
        args = DISPLAY.build_parser().parse_args(['external', 'volume', 'up', '--bus', '13'])
        with patch.object(EXTERNAL, 'read_feature', side_effect=[173, 178]), \
                patch.object(EXTERNAL.time, 'sleep'), patch('sys.stdout'), \
                patch.object(EXTERNAL.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)) as run:
            self.assertEqual(EXTERNAL.run_dell_volume(args, ['ddcutil', '--bus', '13']), 0)
            run.assert_called_once_with(['ddcutil', '--bus', '13', 'setvcp', '62', '50', '8D', '1', '--noverify'], check=False, timeout=EXTERNAL.DDC_TIMEOUT)

    def test_dell_volume_clamps_without_toggling_speakers(self):
        args = DISPLAY.build_parser().parse_args(['external', 'volume', 'up', '--bus', '13'])
        with patch.object(EXTERNAL, 'read_feature', return_value=228), \
                patch.object(EXTERNAL.subprocess, 'run') as run, patch('sys.stdout'):
            self.assertEqual(EXTERNAL.run_dell_volume(args, ['ddcutil']), 0)
            run.assert_not_called()

    def test_dell_volume_failure_attempts_to_restore_speaker_off(self):
        args = DISPLAY.build_parser().parse_args(['external', 'volume', '40', '--bus', '13'])
        with patch.object(EXTERNAL, 'read_feature', return_value=173), \
                patch.object(EXTERNAL.subprocess, 'run', side_effect=[
                    subprocess.CompletedProcess([], 1), subprocess.CompletedProcess([], 0)]) as run:
            with self.assertRaisesRegex(RuntimeError, 'Volume write failed'):
                EXTERNAL.run_dell_volume(args, ['ddcutil'])
            self.assertEqual(run.call_args.args[0], ['ddcutil', 'setvcp', '8D', '1', '--noverify'])
        with patch.object(EXTERNAL, 'read_feature', return_value=173), \
                patch.object(EXTERNAL.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1)):
            with self.assertRaisesRegex(RuntimeError, 'Speaker Off could not be restored'):
                EXTERNAL.run_dell_volume(args, ['ddcutil'])

    def test_dell_unknown_volume_encoding_fails_before_write(self):
        args = DISPLAY.build_parser().parse_args(['external', 'volume', '40', '--bus', '13'])
        with patch.object(EXTERNAL, 'read_feature', return_value=255), \
                patch.object(EXTERNAL.subprocess, 'run') as run:
            with self.assertRaisesRegex(RuntimeError, 'Unexpected Dell volume encoding'):
                EXTERNAL.run_dell_volume(args, ['ddcutil'])
            run.assert_not_called()

    def test_named_speakers_and_audio_source_values(self):
        for name, value, code, raw in [('speakers', 'on', '8D', 2), ('speakers', 'off', '8D', 1),
                                       ('audio-source', 'window1', '63', 0xF1), ('audio-source', 'window2', '63', 0xF2)]:
            args = DISPLAY.build_parser().parse_args(['external', name, value, '--bus', '13'])
            with self.subTest(name=name, value=value), patch.object(EXTERNAL, 'require_dell_u5226kw'), \
                    patch.object(EXTERNAL, 'write_switch') as write, \
                    patch.object(EXTERNAL, 'wait_for_feature') as verify, patch('sys.stdout'):
                EXTERNAL.run_dell(args, ['ddcutil'], 13)
                write.assert_called_once_with(['ddcutil'], code, raw)
                verify.assert_called_once_with(['ddcutil'], code, raw)

    def test_usb_status_uses_mh_not_assignment_bytes(self):
        with patch.object(EXTERNAL.subprocess, 'run', return_value=subprocess.CompletedProcess(
                [], 0, 'VCP E7 CNC x04 x05 x16 x40', '')):
            self.assertEqual(EXTERNAL.read_feature(['ddcutil'], 'E7', maximum=True), 0x0405)
            self.assertEqual(EXTERNAL.read_feature(['ddcutil'], 'E7'), 0x1640)
        args = DISPLAY.build_parser().parse_args(['external', 'usb', '--bus', '13'])
        with patch.object(EXTERNAL, 'read_feature', return_value=0x0405), \
                patch.object(EXTERNAL, 'write_switch') as write, patch('sys.stdout', new_callable=io.StringIO) as output:
            EXTERNAL.run_dell_usb(args, ['ddcutil'])
            self.assertEqual(output.getvalue(), 'hdmi1 (status 0x04)\n')
            write.assert_not_called()

    def test_usb_already_selected_is_noop(self):
        args = DISPLAY.build_parser().parse_args(['external', 'usb', 'thunderbolt', '--bus', '13'])
        with patch.object(EXTERNAL, 'read_feature', return_value=0x0105) as read, \
                patch.object(EXTERNAL, 'write_switch') as write, patch('sys.stdout'):
            EXTERNAL.run_dell_usb(args, ['ddcutil'])
            self.assertEqual(read.call_count, 1)
            write.assert_not_called()

    def test_usb_target_switch_writes_once_then_polls_status(self):
        args = DISPLAY.build_parser().parse_args(['external', 'usb', 'hdmi1', '--bus', '13'])
        with patch.object(EXTERNAL, 'read_feature', side_effect=[
                0x0105, 0x2D, 0x11, 0x6739, 0x0105, 0x0405]), \
                patch.object(EXTERNAL.time, 'sleep'), \
                patch.object(EXTERNAL, 'write_switch') as write, patch('sys.stdout'):
            EXTERNAL.run_dell_usb(args, ['ddcutil'])
            write.assert_called_once_with(['ddcutil'], 'E7', 0xFF00)

    def test_usb_unmapped_layout_or_target_never_switches(self):
        args = DISPLAY.build_parser().parse_args(['external', 'usb', 'next', '--bus', '13'])
        for values in ([0x0205], [0x0105, 0, 0x11, 0x6739], [0x0105, 0x24, 0x19, 0x6739]):
            with self.subTest(values=values), patch.object(EXTERNAL, 'read_feature', side_effect=values), \
                    patch.object(EXTERNAL, 'write_switch') as write:
                with self.assertRaisesRegex(RuntimeError, 'no switch sent'):
                    EXTERNAL.run_dell_usb(args, ['ddcutil'])
                write.assert_not_called()

    def test_usb_failed_confirmation_does_not_cycle_again(self):
        args = DISPLAY.build_parser().parse_args(['external', 'usb', 'next', '--bus', '13'])
        with patch.object(EXTERNAL, 'read_feature', side_effect=[0x0105, 0x24, 0x19, 0x6731]), \
                patch.object(EXTERNAL, 'write_switch') as write, \
                patch.object(EXTERNAL, 'wait_for_feature', side_effect=RuntimeError('not confirmed')):
            with self.assertRaisesRegex(RuntimeError, 'not confirmed'):
                EXTERNAL.run_dell_usb(args, ['ddcutil'])
            write.assert_called_once_with(['ddcutil'], 'E7', 0xFF00)

    def test_invalid_values_fail_before_ddc(self):
        for tokens in [('brightness', '101'), ('brightness', '-1'), ('volume', 'toggle'),
                       ('mute', 'toggle'), ('get', 'XYZ'), ('get', '--helpful'),
                       ('set', 'E9', '65536'), ('set', 'E9', '-1'),
                       ('set', 'E9', '--bus'), ('input', 'Thunderbolt'),
                       ('capabilities', '--bus', '-1'),
                       ('capabilities', '--bus', '16', '--output', 'card0-DP-4')]:
            with self.subTest(tokens=tokens), patch.object(EXTERNAL.subprocess, 'run') as run, \
                    patch('sys.stderr'):
                with self.assertRaises(SystemExit) as error:
                    DISPLAY.build_parser().parse_args(['external', *tokens])
                self.assertEqual(error.exception.code, 2)
                run.assert_not_called()

    def output(self, root, name, status='connected', bus=16):
        path = root / name
        path.mkdir()
        (path / 'status').write_text(status)
        target = root / f'i2c-{bus}'
        target.mkdir(exist_ok=True)
        (path / 'ddc').symlink_to(target)
        return path

    def test_auto_selection_excludes_internal_and_disconnected(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(EXTERNAL, 'DRM', Path(directory)):
            root = Path(directory)
            self.output(root, 'card0-eDP-1', bus=12)
            self.output(root, 'card0-DP-1', 'disconnected', 13)
            self.output(root, 'card0-DP-4')
            parser = DISPLAY.build_parser()
            args = parser.parse_args(['external', 'brightness', '40'])
            self.assertEqual(EXTERNAL.select_bus(args), 16)
            self.output(root, 'card0-DP-5', bus=17)
            with self.assertRaisesRegex(RuntimeError, 'Multiple external outputs'):
                EXTERNAL.select_bus(args)
            args.output = 'card0-DP-5'
            self.assertEqual(EXTERNAL.select_bus(args), 17)
            args.output = 'card0-eDP-1'
            with self.assertRaisesRegex(RuntimeError, 'No connected external'):
                EXTERNAL.select_bus(args)
            args.bus = 0
            self.assertEqual(EXTERNAL.select_bus(args), 0)

    def test_no_output_and_missing_dependency(self):
        args = DISPLAY.build_parser().parse_args(['external', 'brightness'])
        with patch.object(EXTERNAL, 'connected_outputs', return_value=[]):
            with self.assertRaisesRegex(RuntimeError, 'No connected external'):
                EXTERNAL.select_bus(args)
        with patch.object(EXTERNAL.shutil, 'which', return_value=None), \
                patch.object(EXTERNAL.subprocess, 'run') as run:
            with self.assertRaisesRegex(RuntimeError, 'not installed'):
                EXTERNAL.run(args, None)
            run.assert_not_called()

    def test_help_and_completion_do_not_invoke_ddc(self):
        for tokens in [('external', '--help'), ('external', 'set', '--help')]:
            with patch.object(DISPLAY.sys, 'argv', ['agentoo-display', *tokens]), \
                    patch.object(EXTERNAL.subprocess, 'run') as run, patch('sys.stdout'):
                with self.assertRaises(SystemExit) as error:
                    DISPLAY.main()
                self.assertEqual(error.exception.code, 0)
                run.assert_not_called()
        result = subprocess.run([str(Path(DISPLAY.__file__).parent / 'agentoo'),
                                 '__complete', '3', 'display', 'external', ''], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('command\tbrightness\t', result.stdout)
        self.assertIn('command\tcapabilities\t', result.stdout)


if __name__ == '__main__':
    unittest.main()
