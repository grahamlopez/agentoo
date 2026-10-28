"""Exercise real Tab completion in an isolated interactive zsh (no operations run)."""
import fcntl
import os
from pathlib import Path
import pty
import select
import shlex
import shutil
import subprocess
import struct
import tempfile
import termios
import time
import unittest

SHARE = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('zsh'), 'zsh is required')
class CompletionTests(unittest.TestCase):
    def test_tab_completion(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            (work / '_agentoo').write_text((SHARE / 'shell/_agentoo').read_text())
            entry = SHARE.parent.parent / 'bin/agentoo'
            (work / 'agentoo').write_text(entry.read_text().replace(
                "SHARE = BIN.parent / 'share/agentoo'", f"SHARE = Path({str(SHARE)!r})"))
            (work / 'agentoo').chmod(0o755)
            (work / 'fc-list').write_text('#!/bin/sh\nprintf "%s\\n" "Example Font"\n')
            (work / 'fc-list').chmod(0o755)
            profile = work / 'secret profile'
            profile.write_text('# comment\ncustom-category user HOME/key field pass://example\n')
            master, slave = pty.openpty()
            fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 60, 120, 0, 0))
            process = subprocess.Popen(['zsh', '-f'], stdin=slave, stdout=slave, stderr=slave,
                                       env={**os.environ, 'HOME': directory, 'TERM': 'dumb',
                                            'PS1': 'COMPLETION_READY> '})
            os.close(slave)

            def prompt(marker=b''):
                output = b''
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline:
                    if select.select([master], [], [], 0.1)[0]:
                        output += os.read(master, 65536)
                        if marker in output and b'COMPLETION_READY> ' in (output.split(marker, 1)[-1] if marker else output):
                            return output.decode(errors='replace')
                self.fail(f'zsh did not return to prompt: {output!r}')

            try:
                prompt()
                setup = (
                    f'export PATH={shlex.quote(directory)}:$PATH; '
                    f'fpath=({shlex.quote(directory)} $fpath); '
                    'autoload -Uz compinit; compinit -u; '
                    "bindkey '^I' complete-word; bindkey '^D' list-choices; "
                    f'capture() {{ print -r -- "$BUFFER" > {shlex.quote(str(work / "buffer"))}; '
                    'print CAPTURE_DONE; BUFFER=; zle accept-line; }; zle -N capture; bindkey "^X" capture'
                )
                os.write(master, (setup + '\n').encode())
                prompt()
                cases = {
                    'agentoo desktop cl': 'agentoo desktop clear ',
                    'agentoo desktop transparency se': 'agentoo desktop transparency set ',
                    'agentoo desktop blur clear --window kit': 'agentoo desktop blur clear --window kitty ',
                    'agentoo desktop animations set --windows pop': 'agentoo desktop animations set --windows popin ',
                    'agentoo scre': 'agentoo screenshot ',
                    'agentoo rep': 'agentoo repos ',
                    'agentoo ker': 'agentoo kernel ',
                    'agentoo kernel con': 'agentoo kernel config ',
                    'agentoo kernel build --lab': 'agentoo kernel build --label ',
                    'agentoo kernel fir': 'agentoo kernel firmware ',
                    'agentoo kernel firmware app': 'agentoo kernel firmware apply ',
                    'agentoo kernel firmware apply --dry': 'agentoo kernel firmware apply --dry-run ',
                    'agentoo term-c': 'agentoo term-colors ',
                    'agentoo cloud-s': 'agentoo cloud-storage ',
                    'agentoo cloud-storage pcl': 'agentoo cloud-storage pcloud ',
                    'agentoo cloud-storage pcloud star': 'agentoo cloud-storage pcloud start ',
                    'agentoo cloud-storage pcloud stat': 'agentoo cloud-storage pcloud status ',
                    'agentoo cloud-storage pcloud sto': 'agentoo cloud-storage pcloud stop ',
                    'agentoo repos --pa': 'agentoo repos --path ',
                    'agentoo term-colors --fo': 'agentoo term-colors --force ',
                    'agentoo help per': 'agentoo help permissions ',
                    'agentoo permissions ch': 'agentoo permissions check ',
                    'agentoo screenshot reg': 'agentoo screenshot region ',
                    'agentoo power show': 'agentoo power show-all ',
                    'agentoo fonts doc': 'agentoo fonts doctor ',
                    'agentoo fonts doctor --js': 'agentoo fonts doctor --json ',
                    'agentoo fonts test gre': 'agentoo fonts test greek ',
                    'agentoo fonts test --target fire': 'agentoo fonts test --target firefox ',
                    'agentoo fonts test --target=fire': 'agentoo fonts test --target=firefox ',
                    'agentoo fonts test --font Exa': 'agentoo fonts test --font Example\\ Font ',
                    'agentoo checkpoint restore saved --no-sy': 'agentoo checkpoint restore saved --no-system ',
                    'agentoo secrets install --us': 'agentoo secrets install --user ',
                    f'agentoo secrets install --profile {shlex.quote(str(profile))} custom-':
                        f'agentoo secrets install --profile {shlex.quote(str(profile))} custom-category ',
                    'agentoo git setup-h': 'agentoo git setup-hooks ',
                    'agentoo git stat': 'agentoo git status ',
                }
                for text, expected in cases.items():
                    with self.subTest(text=text):
                        os.write(master, (text + '\t\x18').encode())
                        prompt(b'CAPTURE_DONE')
                        self.assertEqual((work / 'buffer').read_text().rstrip('\n'), expected)
                for text in ('agentoo ', 'agentoo fonts ', 'agentoo fonts test '):
                    os.write(master, (text + '\x04\x18').encode())
                    output = prompt(b'CAPTURE_DONE')
                    with self.subTest(listing=text):
                        self.assertIn('Options:', output)
                        self.assertIn('Usage: agentoo', output)
                        first_section = 'Options:' if text == 'agentoo fonts test ' else 'Commands:'
                        self.assertLess(output.index('Usage:'), output.index(first_section))
                        if text == 'agentoo fonts ':
                            self.assertIn('Usage: agentoo fonts [COMMAND] [options]', output)
                        elif text == 'agentoo fonts test ':
                            self.assertIn('Usage: agentoo fonts test ', output)
                            self.assertRegex(output, r'Usage: agentoo fonts test [^\r\n]*\[SUITE\]')
                        if text == 'agentoo fonts test ':
                            self.assertLess(output.index('Options:'), output.index('  --font FONT '))
                            self.assertLess(output.index('  --font FONT '), output.index('Values:'))
                            self.assertRegex(output, r'(?m)^  greek\s*\r?$')
                            self.assertRegex(output, r'(?m)^  smoke\s*\r?$')
                        else:
                            row = '  checkpoint ' if text == 'agentoo ' else '  doctor '
                            self.assertLess(output.index('Commands:'), output.index(row))
                            self.assertLess(output.index(row), output.index('Options:'))
                        # Every alias remains a distinct row even with identical descriptions.
                        self.assertRegex(output, r'(?m)^  -h\s+.*help')
                        self.assertRegex(output, r'(?m)^  --help\s+.*help')
                for text, usage in (
                    ('agentoo checkpoint restore ', 'Usage: agentoo checkpoint restore '),
                    ('agentoo secrets ', 'usage: agentoo secrets '),
                    ('agentoo secrets install ', 'usage: agentoo secrets install '),
                    ('agentoo fonts test --target ', 'Usage: agentoo fonts test '),
                    ('agentoo fonts doctor --text ', 'Usage: agentoo fonts doctor '),
                ):
                    with self.subTest(usage=text):
                        os.write(master, (text + '\x04\x18').encode())
                        output = prompt(b'CAPTURE_DONE')
                        self.assertIn(usage, output)
                        self.assertEqual((work / 'buffer').read_text().rstrip('\n'), text)
            finally:
                process.kill()
                process.wait()
                os.close(master)
