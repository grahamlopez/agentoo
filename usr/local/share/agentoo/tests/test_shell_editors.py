"""Native startup checks use temporary homes, fake launchers, and package configs."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[5]
VIM_DEFAULTS = Path('/var/db/repos/gentoo/app-editors/vim-core/files/vimrc-r8')
NVIM_DEFAULTS = Path('/var/db/repos/gentoo/app-editors/neovim/files/sysinit.vim')


class ShellEditorTests(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory(prefix='agentoo-startup-')
        self.addCleanup(self.work.cleanup)
        self.home = Path(self.work.name)
        self.env = {**os.environ, 'HOME': str(self.home), 'ZDOTDIR': str(self.home),
                    'XDG_CONFIG_HOME': str(self.home / 'config'),
                    'XDG_CONFIG_DIRS': str(self.home / 'system'),
                    'XDG_DATA_HOME': str(self.home / 'data'),
                    'XDG_STATE_HOME': str(self.home / 'state'),
                    'XDG_CACHE_HOME': str(self.home / 'cache'),
                    'NVIM_LOG_FILE': str(self.home / 'nvim.log'),
                    'USER': 'graham', 'WAYLAND_DISPLAY': '', 'DISPLAY': '',
                    'FIXTURE_UID': '1000', 'FIXTURE_TTY': '/dev/tty1',
                    'TERM': 'dumb', 'LAUNCH_STATUS': '0'}

    @unittest.skipUnless(shutil.which('git'), 'Git required')
    def test_vendor_entries_are_ignored_and_native_extensions_remain_addable(self):
        subprocess.run(['git', 'init', '-q', str(self.home)], check=True, env=self.env)
        vendor = ['etc/zsh/zprofile', 'etc/vim/vimrc', 'etc/vim/sysinit.vim']
        extensions = ['etc/zsh/zshrc', 'etc/zsh/zlogin', 'etc/vim/vimrc.local', 'etc/vim/nvimrc.local']
        result = subprocess.run(['git', '-C', str(self.home), '-c',
                                 'core.excludesFile=' + str(ROOT / 'etc/agentoo/gitignore'),
                                 'check-ignore', '--no-index', *vendor, *extensions],
                                env=self.env, capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout.splitlines(), vendor)

    def shell(self, *, environment=None, login=True, interactive=True, personal='', launcher_available=True):
        if not shutil.which('zsh'):
            self.skipTest('zsh is unavailable')
        launcher = self.home / 'start-hyprland'
        launcher.write_text(f'#!{sys.executable}\n' + '''import json, os, pathlib
home = pathlib.Path(os.environ['HOME'])
with (home / 'launches').open('a') as output:
    output.write(json.dumps({key: os.environ.get(key) for key in ('STARTUP_ORDER', 'EDITOR', 'PATH')}) + '\\n')
raise SystemExit(int(os.environ['LAUNCH_STATUS']))
''')
        launcher.chmod(0o755 if launcher_available else 0o644)
        # Substitute only the privileged identity and executable in this fixture.
        startup = (ROOT / 'etc/zsh/zlogin').read_text().replace(
            '$EUID', '$FIXTURE_UID').replace('/usr/bin/start-hyprland', str(launcher))
        (self.home / 'system-zlogin').write_text(startup)
        (self.home / '.zprofile').write_text('export STARTUP_ORDER=profile\nTTY=$FIXTURE_TTY\n')
        (self.home / '.zshrc').write_text(
            f'source {ROOT}/etc/zsh/zshrc\nSTARTUP_ORDER+=:rc\nexport EDITOR=personal-editor\n')
        (self.home / '.zlogin').write_text(
            f'source {self.home}/system-zlogin\nSTARTUP_ORDER+=:login\n' + personal)
        args = ['zsh', '-d', *(['-l'] if login else []), *(['-i'] if interactive else [])]
        result = subprocess.run(args, input='print -r -- CONSOLE_AVAILABLE\nprint -r -- SECOND_PROMPT\nexit\n',
                                text=True, capture_output=True,
                                env={**self.env, **(environment or {})}, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('CONSOLE_AVAILABLE', result.stdout)
        self.assertIn('SECOND_PROMPT', result.stdout)
        log = self.home / 'launches'
        return result, [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []

    def test_desktop_sees_all_personal_startup_and_shared_path(self):
        result, launches = self.shell(personal='export EDITOR=last-editor\n')
        self.assertEqual(len(launches), 1)
        self.assertEqual(launches[0]['STARTUP_ORDER'], 'profile:rc:login')
        self.assertEqual(launches[0]['EDITOR'], 'last-editor')
        self.assertEqual(launches[0]['PATH'].split(':')[0], str(self.home / '.local/bin'))
        self.assertIn('Hyprland exited; console available.', result.stdout)

    def test_failed_launcher_leaves_console_without_retry(self):
        result, launches = self.shell(environment={'LAUNCH_STATUS': '7'})
        self.assertEqual(len(launches), 1)
        self.assertIn('Hyprland exited; console available.', result.stdout)

    def test_missing_launcher_leaves_console(self):
        result, launches = self.shell(launcher_available=False)
        self.assertEqual(launches, [])
        self.assertIn('start-hyprland is unavailable; console available.', result.stdout)

    def test_desktop_gates_and_personal_opt_out(self):
        cases = [({'USER': 'root'}, ''), ({'FIXTURE_UID': '1001'}, ''),
                 ({'FIXTURE_TTY': '/dev/tty2'}, ''), ({'WAYLAND_DISPLAY': 'wayland-1'}, ''),
                 ({'DISPLAY': ':0'}, ''), ({}, 'touch $HOME/.disable-hyprland-autostart\n')]
        for environment, personal in cases:
            with self.subTest(environment=environment, personal=personal):
                _, launches = self.shell(environment=environment, personal=personal)
                self.assertEqual(launches, [])

    def test_nonlogin_and_noninteractive_shells_do_not_launch(self):
        for login, interactive in ((False, True), (True, False)):
            with self.subTest(login=login, interactive=interactive):
                _, launches = self.shell(login=login, interactive=interactive)
                self.assertEqual(launches, [])

    @unittest.skipUnless(shutil.which('vim') and VIM_DEFAULTS.exists(), 'Vim and Gentoo package defaults required')
    def test_vim_native_extension_preserves_upstream_and_personal_defaults(self):
        native = VIM_DEFAULTS.read_text().replace('@GENTOO_PORTAGE_EPREFIX@', '')
        native = native.replace('/etc/vim/vimrc.local', str(ROOT / 'etc/vim/vimrc.local'))
        (self.home / 'system.vim').write_text(native)
        (self.home / 'personal.vim').write_text('set nonumber shiftwidth=7\n')
        checks = self.home / 'checks.vim'
        checks.write_text('''call assert_equal(100, &ttimeoutlen)
call assert_equal(0, &number)
call assert_equal(7, &shiftwidth)
call assert_equal(80, &textwidth)
call assert_match('gq', maparg('Q', 'n'))
call assert_match('gentoo', execute('autocmd FileType crontab'))
if !empty(v:errors)
  call writefile(v:errors, expand('$HOME') . '/errors')
  cquit
endif
qa!
''')
        result = subprocess.run(['vim', '-N', '-u', str(self.home / 'personal.vim'), '-i', 'NONE', '-n', '-es',
                                 '--cmd', 'source ' + str(self.home / 'system.vim'), '-S', str(checks)],
                                env=self.env, capture_output=True, text=True, timeout=15)
        errors = self.home / 'errors'
        self.assertEqual(result.returncode, 0, errors.read_text() if errors.exists() else result.stderr)

    @unittest.skipUnless(shutil.which('nvim') and NVIM_DEFAULTS.exists(), 'Neovim and Gentoo package defaults required')
    def test_neovim_native_extension_and_personal_overrides(self):
        system = self.home / 'system/nvim'
        system.mkdir(parents=True)
        native = NVIM_DEFAULTS.read_text().replace('/etc/vim/nvimrc.local', str(self.home / 'nvimrc.local'))
        (system / 'sysinit.vim').write_text(native)
        extension = (ROOT / 'etc/vim/nvimrc.local').read_text().replace(
            '/etc/xdg/nvim/agentoo.lua', str(ROOT / 'etc/xdg/nvim/agentoo.lua'))
        (self.home / 'nvimrc.local').write_text(extension)
        personal = self.home / 'config/nvim'
        personal.mkdir(parents=True)
        (personal / 'init.lua').write_text('vim.opt.number = false\nvim.g.personal_loaded = true\n')
        target = self.home / 'test.ebuild'
        target.write_text('EAPI=8  \n')
        checks = self.home / 'checks.lua'
        checks.write_text('''assert(vim.o.number == false)
assert(vim.g.personal_loaded == true)
assert(vim.g.mapleader == " ")
assert(vim.g.is_bash == 1)
assert(vim.bo.tabstop == 4 and vim.bo.shiftwidth == 4 and vim.bo.expandtab == false and vim.bo.softtabstop == 0)
vim.cmd.write()
assert(vim.fn.readfile(vim.api.nvim_buf_get_name(0))[1] == 'EAPI=8')
vim.cmd('set filetype=crontab')
assert(vim.o.backupcopy == 'yes')
vim.cmd('qa!')
''')
        command = f"lua local ok, err = pcall(dofile, '{checks}'); if not ok then print(err); vim.cmd('cquit') end"
        result = subprocess.run(['nvim', '--headless', '-i', 'NONE', '-n', str(target), '-c', command],
                                env=self.env, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
