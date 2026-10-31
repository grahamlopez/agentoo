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
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        self.output(root, 'card0-DP-4', bus=13)
        drm = patch.object(EXTERNAL, 'DRM', root)
        drm.start()
        self.addCleanup(drm.stop)
        dependency = patch.object(EXTERNAL.shutil, 'which', return_value='/usr/bin/ddcutil')
        dependency.start()
        self.addCleanup(dependency.stop)

    def test_layout_preserves_kvm_after_video_reassignment(self):
        parser = DISPLAY.build_parser()
        for original, after, main, secondary in [
                (0x0100, 0x0400, 'hdmi1', 'thunderbolt'),
                (0x0400, 0x0100, 'thunderbolt', 'hdmi1'),
                (0x0100, 0x0100, 'hdmi1', 'thunderbolt')]:
            args = parser.parse_args(['external', 'layout', '33-67', '--left', main, '--right', secondary])
            events = []
            readings = iter([original, after, 0x2D, EXTERNAL.DELL_MAIN_INPUTS[main],
                             EXTERNAL.DELL_SECONDARY_INPUTS[secondary]])
            def read(command, code, **kwargs):
                events.append(('read', code))
                return next(readings)
            with self.subTest(original=original, after=after), \
                    patch.object(EXTERNAL, 'read_feature', side_effect=read), \
                    patch.object(EXTERNAL, 'write_switch', side_effect=lambda c, k, v: events.append(('write', k, v))), \
                    patch.object(EXTERNAL, 'wait_for_feature', side_effect=lambda c, k, v, **kw: events.append(('wait', k, v))), \
                    patch('sys.stdout', new_callable=io.StringIO) as output:
                EXTERNAL.run(args, None)
            expected = [('read', 'E7'), ('write', 'E9', 0x2D), ('wait', 'E9', 0x2D),
                        ('write', '60', EXTERNAL.DELL_MAIN_INPUTS[main]),
                        ('wait', '60', EXTERNAL.DELL_MAIN_INPUTS[main]),
                        ('write', 'E8', EXTERNAL.DELL_SECONDARY_INPUTS[secondary]),
                        ('wait', 'E8', EXTERNAL.DELL_SECONDARY_INPUTS[secondary]), ('read', 'E7')]
            if original != after:
                expected += [('read', 'E9'), ('read', '60'), ('read', 'E8'),
                             ('write', 'E7', EXTERNAL.DELL_USB_SWITCH), ('wait', 'E7', original)]
            self.assertEqual(events, expected)
            self.assertIn('preserved', output.getvalue())

    def test_layout_kvm_restore_failure_reports_completed_video_without_retry(self):
        args = DISPLAY.build_parser().parse_args(['external', 'layout', '33-67'])
        with patch.object(EXTERNAL, 'read_feature', side_effect=[0x0100, 0x0400, 0x2D, 0x11, 0x6739]), \
                patch.object(EXTERNAL, 'write_switch') as write, \
                patch.object(EXTERNAL, 'wait_for_feature', side_effect=[None, RuntimeError('readback failed')]):
            with self.assertRaisesRegex(RuntimeError, 'video inputs confirmed, but KVM target thunderbolt could not be preserved'):
                EXTERNAL.run(args, None)
        self.assertEqual([call.args[1] for call in write.call_args_list], ['E9', 'E7'])

    def test_layout_kvm_restore_rejects_unsupported_pair(self):
        args = DISPLAY.build_parser().parse_args(['external', 'layout', '33-67', '--left', 'dp1'])
        with patch.object(EXTERNAL, 'read_feature', side_effect=[0x0100, 0x0400, 0x2D, 0x0F, 0x6731]), \
                patch.object(EXTERNAL, 'write_switch') as write, \
                patch.object(EXTERNAL, 'wait_for_feature'):
            with self.assertRaisesRegex(RuntimeError, 'could not be preserved.*requires a mapped'):
                EXTERNAL.run(args, None)
        self.assertEqual([call.args[1] for call in write.call_args_list], ['E9', '60'])

    def test_input_aliases_and_case(self):
        parser = DISPLAY.build_parser()
        for command, canonical in [('left', 'input'), ('right', 'sub-input'), ('kvm', 'usb')]:
            args = parser.parse_args(['external', command])
            self.assertEqual(args.external_action, canonical)
        for name, expected in EXTERNAL.DELL_MAIN_INPUTS.items():
            args = parser.parse_args(['external', 'left', name.upper(), '--bus', '13'])
            with patch.object(EXTERNAL.shutil, 'which', return_value='ddcutil'), \
                    patch.object(EXTERNAL.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)) as run:
                EXTERNAL.run(args, parser)
            self.assertIn(str(expected), run.call_args.args[0])

    def test_combined_layout_inputs_and_partial_failure(self):
        parser = DISPLAY.build_parser()
        for left, right in [('--left', '--right'), ('--input', '--sub-input')]:
            for failure in (None, '60', 'E8'):
                args = parser.parse_args(['external', 'layout', '33-67', left, 'DP1', right, 'HDMI1'])
                def wait(command, code, value):
                    if code == failure:
                        raise RuntimeError('unconfirmed')
                with self.subTest(left=left, failure=failure), \
                        patch.object(EXTERNAL, 'select_dell_usb', return_value=('hdmi1', 4)), \
                        patch.object(EXTERNAL, 'write_switch') as write, \
                        patch.object(EXTERNAL, 'wait_for_feature', side_effect=wait), patch('sys.stdout'):
                    if failure:
                        with self.assertRaisesRegex(RuntimeError, 'confirmed.*not confirmed'):
                            EXTERNAL.run(args, None)
                    else:
                        EXTERNAL.run(args, None)
                    expected = [('E9', 0x2D), ('60', 0x0F)]
                    if failure != '60':
                        expected.append(('E8', 0x6731))
                    self.assertEqual([call.args[1:] for call in write.call_args_list], expected)

    def test_observed_secondary_mappings(self):
        parser = DISPLAY.build_parser()
        for name, value in [('HDMI1', 0x6731), ('HDMI2', 0x6732),
                            ('DP1', 0x672F), ('DP2', 0x6733), ('Thunderbolt', 0x6739)]:
            args = parser.parse_args(['external', 'right', name])
            with self.subTest(name=name), patch.object(EXTERNAL, 'read_feature', return_value=0x2D), \
                    patch.object(EXTERNAL, 'write_switch') as write, \
                    patch.object(EXTERNAL, 'wait_for_feature') as wait, patch('sys.stdout'):
                EXTERNAL.run(args, None)
            write.assert_called_once_with(['ddcutil', '--bus', '13'], 'E8', value)
            wait.assert_called_once_with(['ddcutil', '--bus', '13'], 'E8', value)

    def test_off_right_fails_before_writes(self):
        parser = DISPLAY.build_parser()
        args = parser.parse_args(['external', 'layout', '100', '--right', 'hdmi1'])
        with patch('sys.stderr'), self.assertRaises(SystemExit):
            EXTERNAL.run(args, parser)

    def test_numeric_secondary_is_explicit_raw_value(self):
        args = DISPLAY.build_parser().parse_args(['external', 'right', '0x6731'])
        with patch.object(EXTERNAL, 'read_feature', return_value=0x2D), \
                patch.object(EXTERNAL, 'write_switch') as write, \
                patch.object(EXTERNAL, 'wait_for_feature'), patch('sys.stdout'):
            EXTERNAL.run(args, None)
        write.assert_called_once_with(['ddcutil', '--bus', '13'], 'E8', 0x6731)

    def command(self, *tokens, status=0):
        parser = DISPLAY.build_parser()
        args = parser.parse_args(['external', *tokens])
        with patch.object(EXTERNAL.shutil, 'which', return_value='/usr/bin/ddcutil'), \
                patch.object(EXTERNAL.subprocess, 'run', return_value=subprocess.CompletedProcess([], status)) as run:
            self.assertEqual(EXTERNAL.run(args, parser), status)
        return run.call_args.args[0]

    def test_read_commands_never_write(self):
        self.assertEqual(self.command('list'), ['ddcutil', 'detect'])
        for name, suffix in [('capabilities', ['capabilities']), ('brightness', ['getvcp', '10']),
                             ('mute', ['getvcp', '8D']),
                             ('input', ['getvcp', '60']), ('get', ['getvcp', 'E9'])]:
            with self.subTest(name=name):
                tokens = ['E9'] if name == 'get' else []
                self.assertEqual(self.command(name, *tokens, '--bus', '13'), ['ddcutil', '--bus', '13', *suffix])

    def test_write_encoding_and_exit_status(self):
        for tokens, suffix in [
            (['brightness', 'up'], ['10', '+', '5', '--verify']),
            (['brightness', 'down'], ['10', '-', '5', '--verify']),
            (['brightness', '0'], ['10', '0', '--verify']),
            (['mute', 'on'], ['8D', '1', '--verify']),
            (['mute', 'off'], ['8D', '2', '--verify']),
            (['input', '0x19', '--no-verify'], ['60', '25', '--noverify']),
            (['set', '0xe9', '0x21', '--no-verify'], ['E9', '33', '--permit-unknown-feature', '--noverify']),
        ]:
            with self.subTest(tokens=tokens):
                self.assertEqual(self.command(*tokens, '--bus', '13', status=7),
                                 ['ddcutil', '--bus', '13', 'setvcp', *suffix])

    def test_internal_read_timeout_is_safe(self):
        for code in ('E9', '62'):
            with patch.object(EXTERNAL.subprocess, 'run',
                              side_effect=subprocess.TimeoutExpired('ddcutil', 5)) as run:
                with self.assertRaisesRegex(RuntimeError, 'Timed out reading VCP'):
                    EXTERNAL.read_feature(['ddcutil', '--bus', '13'], code)
                self.assertEqual(run.call_count, 1)

    def test_switch_timeout_never_retries(self):
        with patch.object(EXTERNAL.subprocess, 'run',
                          side_effect=subprocess.TimeoutExpired('ddcutil', 5)) as run:
            with self.assertRaisesRegex(RuntimeError, 'may have applied it.*No write was retried'):
                EXTERNAL.write_switch(['ddcutil', '--bus', '13'], 'E7', 0xFF00)
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
                    EXTERNAL.run(args, None)
                self.assertEqual(run.call_count, len(effects))
                for call in run.call_args_list:
                    self.assertEqual(call.kwargs['timeout'], EXTERNAL.DDC_TIMEOUT)
                if restoration is not None:
                    self.assertEqual(run.call_args.args[0],
                                     ['ddcutil', '--bus', '13', 'setvcp', '8D', '1', '--noverify'])

    def test_dell_identity_required_for_every_operation(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(EXTERNAL, 'DRM', Path(directory)):
            path = self.output(Path(directory), 'card0-DP-4', bus=13)
            edid = bytearray(128)
            edid[8:12] = bytes.fromhex('10ac9e43')
            (path / 'edid').write_bytes(edid)
            args = DISPLAY.build_parser().parse_args(['external', 'brightness', '--bus', '13'])
            with patch.object(EXTERNAL.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)) as ddc:
                self.assertEqual(EXTERNAL.run(args, None), 0)
            self.assertEqual(ddc.call_args.args[0][:3], ['ddcutil', '--bus', '13'])
            edid[10] = 0
            (path / 'edid').write_bytes(edid)
            for tokens in [('brightness', '40'), ('brightness',), ('volume', 'up'),
                           ('input', '0x19'), ('get', 'E9'), ('set', 'E9', '0'),
                           ('capabilities',), ('layout', '50-50')]:
                args = DISPLAY.build_parser().parse_args(['external', *tokens, '--bus', '13'])
                with self.subTest(tokens=tokens), patch.object(EXTERNAL.subprocess, 'run') as run:
                    with self.assertRaisesRegex(RuntimeError, 'No connected Dell U5226KW'):
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
                EXTERNAL.read_feature(['ddcutil', '--bus', '13'], 'E9')

    def test_named_layout_waits_for_readback_without_rewriting(self):
        args = DISPLAY.build_parser().parse_args(['external', 'layout', '33-67', '--bus', '13'])
        with patch.object(EXTERNAL, 'select_dell_usb', return_value=('hdmi1', 4)), \
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

    def test_fullscreen_input_sequence(self):
        for alias, target, resolved in [('off', 'thunderbolt', 'thunderbolt'),
                                        ('100', 'hdmi1', 'hdmi1'),
                                        ('100', 'active_kvm', 'hdmi1')]:
            with self.subTest(alias=alias, target=target):
                args = DISPLAY.build_parser().parse_args(
                    ['external', 'layout', alias, '--input', target, '--bus', '13'])
                events = []
                def read(*args, **kwargs):
                    events.append(('read', args[1]))
                    return 0x0400
                with patch.object(EXTERNAL, 'select_dell_usb', return_value=('hdmi1', 4)), \
                        patch.object(EXTERNAL, 'read_feature', side_effect=read), \
                        patch.object(EXTERNAL, 'write_switch', side_effect=lambda c, k, v: events.append(('write', k, v))), \
                        patch.object(EXTERNAL, 'wait_for_feature', side_effect=lambda c, k, v: events.append(('wait', k, v))), \
                        patch('sys.stdout', new_callable=io.StringIO) as output:
                    EXTERNAL.run(args, None)
                expected = []
                expected += [('write', 'E9', 0), ('wait', 'E9', 0),
                             ('write', '60', EXTERNAL.DELL_MAIN_INPUTS[resolved]),
                             ('wait', '60', EXTERNAL.DELL_MAIN_INPUTS[resolved])]
                self.assertEqual(events, expected)
                self.assertIn('off (0x00)', output.getvalue())
                self.assertIn(f'input {resolved}', output.getvalue())

    def test_fullscreen_alias_without_input(self):
        args = DISPLAY.build_parser().parse_args(['external', 'layout', '100'])
        with patch.object(EXTERNAL, 'select_dell_usb', return_value=('hdmi1', 4)), \
                patch.object(EXTERNAL, 'write_switch') as write, \
                patch.object(EXTERNAL, 'wait_for_feature'), patch('sys.stdout'):
            EXTERNAL.run(args, None)
        write.assert_called_once_with(['ddcutil', '--bus', '13'], 'E9', 0)

    def test_fullscreen_rejects_invalid_input_usage_before_ddc(self):
        for value in ([], ['33-67']):
            parser = DISPLAY.build_parser()
            args = parser.parse_args(['external', 'layout', *value, '--input', 'active_kvm'])
            with patch.object(EXTERNAL, 'connected_outputs') as discover, patch('sys.stderr'), self.assertRaises(SystemExit) as error:
                EXTERNAL.run(args, parser)
            self.assertEqual(error.exception.code, 2)
            discover.assert_not_called()

    def test_fullscreen_unknown_kvm_sends_no_writes(self):
        args = DISPLAY.build_parser().parse_args(['external', 'layout', 'off', '--input', 'active_kvm'])
        with patch.object(EXTERNAL, 'read_feature', return_value=0x9900), \
                patch.object(EXTERNAL, 'write_switch') as write:
            with self.assertRaisesRegex(RuntimeError, 'Unmapped active USB target'):
                EXTERNAL.run(args, None)
        write.assert_not_called()

    def test_fullscreen_partial_failure_never_retries_or_continues(self):
        args = DISPLAY.build_parser().parse_args(['external', 'layout', 'off', '--input', 'hdmi1'])
        for failure in ('E9', '60'):
            def wait(command, code, value):
                if code == failure:
                    raise RuntimeError('readback unavailable')
            with self.subTest(failure=failure), patch.object(EXTERNAL, 'select_dell_usb', return_value=('hdmi1', 4)), \
                    patch.object(EXTERNAL, 'write_switch') as write, \
                    patch.object(EXTERNAL, 'wait_for_feature', side_effect=wait):
                with self.assertRaisesRegex(RuntimeError, 'Layout off confirmed' if failure == '60' else 'readback unavailable'):
                    EXTERNAL.run(args, None)
                self.assertEqual([call.args[1] for call in write.call_args_list],
                                 ['E9'] if failure == 'E9' else ['E9', '60'])

    def test_readback_failure_never_repeats_write(self):
        args = DISPLAY.build_parser().parse_args(['external', 'layout', 'off', '--bus', '13'])
        with patch.object(EXTERNAL, 'select_dell_usb', return_value=('hdmi1', 4)), \
                patch.object(EXTERNAL.shutil, 'which', return_value='/usr/bin/ddcutil'), \
                patch.object(EXTERNAL.time, 'sleep'), \
                patch.object(EXTERNAL, 'write_switch') as write, \
                patch.object(EXTERNAL, 'read_feature', side_effect=RuntimeError('ENXIO')):
            with self.assertRaisesRegex(RuntimeError, 'No write was retried'):
                EXTERNAL.run(args, None)
            write.assert_called_once()

    def test_position_requires_pip_and_is_sent_only_once(self):
        args = DISPLAY.build_parser().parse_args(['external', 'pip-position', 'next', '--bus', '13'])
        with patch.object(EXTERNAL.shutil, 'which', return_value='/usr/bin/ddcutil'), \
                patch.object(EXTERNAL, 'read_feature', return_value=0x24), \
                patch.object(EXTERNAL, 'write_switch') as write:
            with self.assertRaisesRegex(RuntimeError, 'requires pip-small or pip-large'):
                EXTERNAL.run(args, None)
            write.assert_not_called()
        with patch.object(EXTERNAL.shutil, 'which', return_value='/usr/bin/ddcutil'), \
                patch.object(EXTERNAL, 'read_feature', return_value=0x22), \
                patch.object(EXTERNAL, 'write_switch') as write, patch('sys.stderr'):
            self.assertEqual(EXTERNAL.run(args, None), 0)
            write.assert_called_once_with(['ddcutil', '--bus', '13'], 'E9', 2)

    def test_sub_input_requires_mapped_active_layout(self):
        args = DISPLAY.build_parser().parse_args(['external', 'sub-input', 'hdmi1', '--bus', '13'])
        with patch.object(EXTERNAL.shutil, 'which', return_value='/usr/bin/ddcutil'), \
                patch.object(EXTERNAL, 'read_feature', return_value=0), \
                patch.object(EXTERNAL, 'write_switch') as write:
            with self.assertRaisesRegex(RuntimeError, 'requires a mapped active'):
                EXTERNAL.run(args, None)
            write.assert_not_called()
        with patch.object(EXTERNAL.shutil, 'which', return_value='/usr/bin/ddcutil'), \
                patch.object(EXTERNAL, 'read_feature', side_effect=[0x22, 0x6731]), \
                patch.object(EXTERNAL.time, 'sleep'), \
                patch.object(EXTERNAL, 'write_switch') as write, patch('sys.stdout'):
            self.assertEqual(EXTERNAL.run(args, None), 0)
            write.assert_called_once_with(['ddcutil', '--bus', '13'], 'E8', 0x6731)

    def test_dell_volume_decodes_mute_without_writes(self):
        args = DISPLAY.build_parser().parse_args(['external', 'volume', '--bus', '13'])
        with patch.object(EXTERNAL.shutil, 'which', return_value='/usr/bin/ddcutil'), \
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
            self.assertEqual(EXTERNAL.run(args, None), 0)
            run.assert_called_once_with(['ddcutil', '--bus', '13', 'setvcp', '62', '50', '8D', '1', '--noverify'], check=False, timeout=EXTERNAL.DDC_TIMEOUT)

    def test_dell_volume_clamps_without_toggling_speakers(self):
        args = DISPLAY.build_parser().parse_args(['external', 'volume', 'up', '--bus', '13'])
        with patch.object(EXTERNAL, 'read_feature', return_value=228), \
                patch.object(EXTERNAL.subprocess, 'run') as run, patch('sys.stdout'):
            self.assertEqual(EXTERNAL.run(args, None), 0)
            run.assert_not_called()

    def test_dell_volume_failure_attempts_to_restore_speaker_off(self):
        args = DISPLAY.build_parser().parse_args(['external', 'volume', '40', '--bus', '13'])
        with patch.object(EXTERNAL, 'read_feature', return_value=173), \
                patch.object(EXTERNAL.subprocess, 'run', side_effect=[
                    subprocess.CompletedProcess([], 1), subprocess.CompletedProcess([], 0)]) as run:
            with self.assertRaisesRegex(RuntimeError, 'Volume write failed'):
                EXTERNAL.run(args, None)
            self.assertEqual(run.call_args.args[0], ['ddcutil', '--bus', '13', 'setvcp', '8D', '1', '--noverify'])
        with patch.object(EXTERNAL, 'read_feature', return_value=173), \
                patch.object(EXTERNAL.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1)):
            with self.assertRaisesRegex(RuntimeError, 'Speaker Off could not be restored'):
                EXTERNAL.run(args, None)

    def test_dell_unknown_volume_encoding_fails_before_write(self):
        args = DISPLAY.build_parser().parse_args(['external', 'volume', '40', '--bus', '13'])
        with patch.object(EXTERNAL, 'read_feature', return_value=255), \
                patch.object(EXTERNAL.subprocess, 'run') as run:
            with self.assertRaisesRegex(RuntimeError, 'Unexpected Dell volume encoding'):
                EXTERNAL.run(args, None)
            run.assert_not_called()

    def test_named_speakers_and_audio_source_values(self):
        for name, value, code, raw in [('speakers', 'on', '8D', 2), ('speakers', 'off', '8D', 1),
                                       ('audio-source', 'window1', '63', 0xF1), ('audio-source', 'window2', '63', 0xF2)]:
            args = DISPLAY.build_parser().parse_args(['external', name, value, '--bus', '13'])
            with self.subTest(name=name, value=value), patch.object(EXTERNAL, 'write_switch') as write, \
                    patch.object(EXTERNAL, 'wait_for_feature') as verify, patch('sys.stdout'):
                EXTERNAL.run(args, None)
                write.assert_called_once_with(['ddcutil', '--bus', '13'], code, raw)
                verify.assert_called_once_with(['ddcutil', '--bus', '13'], code, raw)

    def test_usb_status_uses_mh_not_assignment_bytes(self):
        with patch.object(EXTERNAL.subprocess, 'run', return_value=subprocess.CompletedProcess(
                [], 0, 'VCP E7 CNC x04 x05 x16 x40', '')):
            self.assertEqual(EXTERNAL.read_feature(['ddcutil', '--bus', '13'], 'E7', maximum=True), 0x0405)
            self.assertEqual(EXTERNAL.read_feature(['ddcutil', '--bus', '13'], 'E7'), 0x1640)
        args = DISPLAY.build_parser().parse_args(['external', 'usb', '--bus', '13'])
        with patch.object(EXTERNAL, 'read_feature', return_value=0x0405), \
                patch.object(EXTERNAL, 'write_switch') as write, patch('sys.stdout', new_callable=io.StringIO) as output:
            EXTERNAL.run(args, None)
            self.assertEqual(output.getvalue(), 'hdmi1 (status 0x04)\n')
            write.assert_not_called()

    def test_usb_already_selected_is_noop(self):
        args = DISPLAY.build_parser().parse_args(['external', 'usb', 'thunderbolt', '--bus', '13'])
        with patch.object(EXTERNAL, 'read_feature', return_value=0x0105) as read, \
                patch.object(EXTERNAL, 'write_switch') as write, patch('sys.stdout'):
            EXTERNAL.run(args, None)
            self.assertEqual(read.call_count, 1)
            write.assert_not_called()

    def test_usb_target_switch_writes_once_then_polls_status(self):
        args = DISPLAY.build_parser().parse_args(['external', 'usb', 'hdmi1', '--bus', '13'])
        with patch.object(EXTERNAL, 'read_feature', side_effect=[
                0x0105, 0x2D, 0x11, 0x6739, 0x0105, 0x0405]), \
                patch.object(EXTERNAL.time, 'sleep'), \
                patch.object(EXTERNAL, 'write_switch') as write, patch('sys.stdout'):
            EXTERNAL.run(args, None)
            write.assert_called_once_with(['ddcutil', '--bus', '13'], 'E7', 0xFF00)

    def test_usb_unmapped_layout_or_target_never_switches(self):
        args = DISPLAY.build_parser().parse_args(['external', 'usb', 'next', '--bus', '13'])
        for values in ([0x0205], [0x0105, 0, 0x11, 0x6739], [0x0105, 0x24, 0x19, 0x6739]):
            with self.subTest(values=values), patch.object(EXTERNAL, 'read_feature', side_effect=values), \
                    patch.object(EXTERNAL, 'write_switch') as write:
                with self.assertRaisesRegex(RuntimeError, 'no switch sent'):
                    EXTERNAL.run(args, None)
                write.assert_not_called()

    def test_usb_failed_confirmation_does_not_cycle_again(self):
        args = DISPLAY.build_parser().parse_args(['external', 'usb', 'next', '--bus', '13'])
        with patch.object(EXTERNAL, 'read_feature', side_effect=[0x0105, 0x24, 0x19, 0x6731]), \
                patch.object(EXTERNAL, 'write_switch') as write, \
                patch.object(EXTERNAL, 'wait_for_feature', side_effect=RuntimeError('not confirmed')):
            with self.assertRaisesRegex(RuntimeError, 'not confirmed'):
                EXTERNAL.run(args, None)
            write.assert_called_once_with(['ddcutil', '--bus', '13'], 'E7', 0xFF00)

    def test_invalid_values_fail_before_ddc(self):
        for tokens in [('brightness', '101'), ('brightness', '-1'), ('volume', 'toggle'),
                       ('mute', 'toggle'), ('get', 'XYZ'), ('get', '--helpful'),
                       ('set', 'E9', '65536'), ('set', 'E9', '-1'),
                       ('set', 'E9', '--bus'), ('input', 'unknown'),
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
        edid = bytearray(128)
        edid[8:12] = bytes.fromhex('10ac9e43')
        (path / 'edid').write_bytes(edid)
        target = root / f'i2c-{bus}'
        target.mkdir(exist_ok=True)
        (path / 'ddc').symlink_to(target)
        return path

    def test_auto_selection_excludes_internal_disconnected_and_other_models(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(EXTERNAL, 'DRM', Path(directory)), \
                patch.object(EXTERNAL.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)) as ddc:
            root = Path(directory)
            self.output(root, 'card0-eDP-1', bus=12)
            self.output(root, 'card0-DP-1', 'disconnected', 13)
            self.output(root, 'card0-DP-4')
            other = self.output(root, 'card0-HDMI-A-1', bus=14)
            (other / 'edid').write_bytes(bytes(128))
            parser = DISPLAY.build_parser()
            args = parser.parse_args(['external', 'brightness', '40'])
            self.assertEqual(EXTERNAL.run(args, parser), 0)
            self.assertEqual(ddc.call_args.args[0][:3], ['ddcutil', '--bus', '16'])
            self.output(root, 'card0-DP-5', bus=17)
            with self.assertRaisesRegex(RuntimeError, 'Multiple Dell U5226KW outputs'):
                EXTERNAL.run(args, parser)
            args.output = 'card0-DP-5'
            self.assertEqual(EXTERNAL.run(args, parser), 0)
            self.assertEqual(ddc.call_args.args[0][:3], ['ddcutil', '--bus', '17'])
            args.output = 'card0-eDP-1'
            with self.assertRaisesRegex(RuntimeError, 'No connected Dell U5226KW'):
                EXTERNAL.run(args, parser)
            args.output = None
            args.bus = 0
            with self.assertRaisesRegex(RuntimeError, 'No connected Dell U5226KW'):
                EXTERNAL.run(args, parser)
            self.output(root, 'card0-DP-6', bus=0)
            self.assertEqual(EXTERNAL.run(args, parser), 0)
            self.assertEqual(ddc.call_args.args[0][:3], ['ddcutil', '--bus', '0'])

    def test_no_output_and_missing_dependency(self):
        args = DISPLAY.build_parser().parse_args(['external', 'brightness'])
        with patch.object(EXTERNAL, 'connected_outputs', return_value=[]):
            with self.assertRaisesRegex(RuntimeError, 'No connected Dell U5226KW'):
                EXTERNAL.run(args, None)
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
