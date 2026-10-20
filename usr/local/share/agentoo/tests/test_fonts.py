"""Verify noninteractive boundaries and configuration side-effect reporting."""
import contextlib
import io
from pathlib import Path
import runpy
import tempfile
import unittest
from unittest.mock import patch

MODULE = runpy.run_path(str(Path(__file__).resolve().parents[3] / 'bin/agentoo-fonts'))


class FontsTest(unittest.TestCase):
    def test_no_input_rejects_gui_before_external_calls(self):
        main = MODULE['main']
        for args in [('set',), ('test', '--font', 'Example'), ('doctor', '--render'),
                     ('test', '--target', 'firefox')]:
            with self.subTest(args=args), patch('sys.argv', ['agentoo-fonts', *args, '--no-input']), \
                    patch.dict(main.__globals__, run=lambda *args, **kw: self.fail('external operation')), \
                    contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                main()
            self.assertEqual(error.exception.code, 2)

    def test_save_reports_both_files_on_stderr(self):
        save = MODULE['save_selection']
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / 'kitty.conf'
            fragment = Path(directory) / 'agentoo-fonts.conf'
            stdout, stderr = io.StringIO(), io.StringIO()
            with patch.dict(save.__globals__, kitty_paths=lambda: (config, fragment), reload_kitties=lambda: None), \
                    contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                save('font_size 12\n')
            self.assertEqual(stdout.getvalue(), '')
            self.assertIn(str(config), stderr.getvalue())
            self.assertIn(str(fragment), stderr.getvalue())
            self.assertIn('To revert:', stderr.getvalue())

    def test_queries_have_timeout_but_preview_runner_does_not(self):
        output = MODULE['output']
        with patch.dict(output.__globals__, run=lambda *args, **kwargs: type('Result', (), {'stdout': str(kwargs)})()):
            self.assertIn("'timeout': 15", output('fc-list'))

    def test_abbreviations_rejected(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            MODULE['build_parser']().parse_args(['doctor', '--js'])

    def test_incomplete_values_do_not_prevent_requested_leaf_help(self):
        for args in [('set', '--size', '--help'), ('doctor', '--text', '--help')]:
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout), self.assertRaises(SystemExit) as error:
                MODULE['build_parser']().parse_args(args)
            self.assertEqual(error.exception.code, 0)
            self.assertIn('agentoo fonts ' + args[0], stdout.getvalue())
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            MODULE['build_parser']().parse_args(['set', '--', '--help'])
        self.assertEqual(error.exception.code, 2)
