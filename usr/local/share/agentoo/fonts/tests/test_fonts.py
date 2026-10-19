import argparse
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import hashlib

spec = importlib.util.spec_from_file_location('fonts', Path(__file__).resolve().parents[2]/'commands/fonts.py')
f = importlib.util.module_from_spec(spec)
spec.loader.exec_module(f)

class FontsTests(unittest.TestCase):
    def test_kitty_preserves_unrelated_config_and_prints_exact_undo(self):
        with tempfile.TemporaryDirectory() as d:
            config, fragment = Path(d)/'kitty.conf', Path(d)/'agentoo-fonts.conf'
            config.write_text('include host.conf\nsymbol_map U+2800-U+28FF Unifont\n')
            fragment.write_text('font_size 10\n')
            a=argparse.Namespace(font='UbuntuSansMono Nerd Font',style='Medium',size=12)
            with patch.object(f,'kitty_paths',return_value=(config,fragment)), patch('sys.stdout',new_callable=io.StringIO) as out:
                f.kitty_set(a)
            self.assertIn('symbol_map U+2800-U+28FF Unifont',config.read_text())
            self.assertEqual(config.read_text().count('include agentoo-fonts.conf'),1)
            self.assertIn("'font_size 10\n'",out.getvalue())
            self.assertIn('font_size 12',fragment.read_text())

    def test_firefox_pref_preserves_primary_and_prints_clear_undo(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d); (p/'prefs.js').write_text('user_pref("font.name.monospace.x-western", "Liberation Mono");\n')
            a=argparse.Namespace()
            with patch.object(f,'profile',return_value=p),patch('sys.stdout',new_callable=io.StringIO) as out:
                f.firefox_pref(a,'font.name-list.monospace.x-western','Noto Sans Symbols 2')
            self.assertIn('--clear',out.getvalue())
            self.assertEqual(f.prefs(p)['font.name.monospace.x-western'],'Liberation Mono')
            with patch.object(f,'profile',return_value=p),patch('sys.stdout',new_callable=io.StringIO):
                f.firefox_pref(a,'font.name-list.monospace.x-western',None)
            self.assertNotIn('font.name-list.monospace.x-western',f.prefs(p))

    def test_locked_firefox_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d); (p/'lock').symlink_to('host:+1234')
            with patch.object(f,'profile',return_value=p),self.assertRaises(ValueError):
                f.firefox_pref(argparse.Namespace(),'font.test','value')
            self.assertFalse((p/'user.js').exists())

    def test_console_restores_on_interrupted_preview(self):
        a=argparse.Namespace(font='ter-v24n',size=None,style=None,console='/dev/tty1',command='preview')
        calls=[]
        def root(*args): calls.append(args)
        with patch.object(f,'root_run',side_effect=root),patch.object(f,'read',return_value='KEYMAP=us\n'),patch.object(f.sys.stdin,'isatty',return_value=True),patch.object(f,'terminal_test',side_effect=KeyboardInterrupt),self.assertRaises(KeyboardInterrupt):
            f.console_set(a)
        self.assertEqual(calls[0][3],'-O')
        self.assertTrue(calls[-1][-1].endswith('font.psf'))
        self.assertFalse(any(c[0]=='install' for c in calls))

    def test_download_mismatch_never_installs(self):
        release={'tag_name':'vtest','assets':[{'name':'FiraCode.zip','browser_download_url':'https://example.invalid/font','digest':'sha256:'+'0'*64}]}
        a=argparse.Namespace(font='fira-code',system=False,variant='standard',command='install')
        with tempfile.TemporaryDirectory() as d,patch.dict(f.os.environ,{'XDG_DATA_HOME':d}),patch.object(f,'download',side_effect=[json.dumps(release).encode(),b'bad']),patch('sys.stdout',new_callable=io.StringIO),self.assertRaisesRegex(ValueError,'checksum mismatch'):
            f.install_fonts(a)
            self.assertFalse((Path(d)/'fonts').exists())

    def test_verified_install_filters_variant_and_preserves_license(self):
        blob=io.BytesIO()
        with zipfile.ZipFile(blob,'w') as z:
            z.writestr('FiraCodeNerdFont-Regular.ttf',b'font')
            z.writestr('FiraCodeNerdFontMono-Regular.ttf',b'mono')
            z.writestr('LICENSE',b'license')
        data=blob.getvalue()
        release={'tag_name':'vtest','assets':[{'name':'FiraCode.zip','browser_download_url':'https://example.invalid/font','digest':'sha256:'+hashlib.sha256(data).hexdigest()}]}
        a=argparse.Namespace(font='fira-code',system=False,variant='standard',command='install')
        with tempfile.TemporaryDirectory() as d,patch.dict(f.os.environ,{'XDG_DATA_HOME':d}),patch.object(f,'download',side_effect=[json.dumps(release).encode(),data]),patch.object(f,'run'),patch.object(f,'output',return_value='FiraCode Nerd Font'),patch('sys.stdout',new_callable=io.StringIO):
            f.install_fonts(a)
            dest=Path(d)/'fonts/agentoo/fira-code-standard'
            self.assertTrue((dest/'LICENSE').exists())
            self.assertFalse((dest/'FiraCodeNerdFontMono-Regular.ttf').exists())
            self.assertEqual(json.loads((dest/'agentoo-install.json').read_text())['version'],'vtest')

if __name__ == '__main__': unittest.main()
