"""Offline regression checks for usr/local/share/agentoo/installer/user-dots.sh."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[5]
INSTALLER = ROOT / 'usr/local/share/agentoo/installer/user-dots.sh'


class UserDotsTests(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory(prefix='agentoo-user-dots-')
        self.addCleanup(self.work.cleanup)
        self.base = Path(self.work.name)
        # Include a space to verify path quoting across shell, vim, lua, tmux, and git.
        self.home = self.base / 'user home'
        self.home.mkdir()
        self.softlock_src = self.base / 'softlock-src'
        (self.softlock_src / 'plugin').mkdir(parents=True)
        (self.softlock_src / 'doc').mkdir(parents=True)
        (self.softlock_src / 'plugin/softlock.lua').write_text('vim.g.softlock_loaded_fixture = true\n')
        (self.softlock_src / 'doc/softlock.txt').write_text('*softlock.txt*\tFixture help\n')
        (self.softlock_src / 'README.md').write_text('# softlock fixture\n')
        self.env = {
            **os.environ,
            'HOME': str(self.home),
            'XDG_CONFIG_HOME': str(self.home / '.config'),
            'XDG_DATA_HOME': str(self.home / '.local/share'),
            'XDG_STATE_HOME': str(self.home / '.local/state'),
            'XDG_CACHE_HOME': str(self.home / '.cache'),
            'NVIM_LOG_FILE': str(self.home / 'nvim.log'),
            'GIT_CONFIG_NOSYSTEM': '1',
            'SHELL': '/bin/bash',
        }
        for key in ('GIT_CONFIG_GLOBAL', 'GIT_DIR', 'GIT_WORK_TREE', 'ZDOTDIR'):
            self.env.pop(key, None)

    def run_installer(self, *extra_args, env=None, check=True):
        cmd = [
            'bash', str(INSTALLER),
            '--source-dir', str(ROOT),
            '--softlock-dir', str(self.softlock_src),
            *extra_args,
        ]
        return subprocess.run(cmd, env=env or self.env, text=True, capture_output=True, check=check)

    def test_shell_syntax_and_help(self):
        syntax = subprocess.run(['bash', '-n', str(INSTALLER)], text=True, capture_output=True)
        self.assertEqual(syntax.returncode, 0, syntax.stderr)
        help_res = subprocess.run(['bash', str(INSTALLER), '--help'], text=True, capture_output=True, check=True)
        self.assertIn('--dry-run', help_res.stdout)
        self.assertIn('--source-dir', help_res.stdout)

    def test_dry_run_makes_no_changes(self):
        (self.home / '.zshrc').write_text('# existing unmanaged zshrc\n')
        res = self.run_installer('--dry-run')
        self.assertIn('dry-run: no files will be modified', res.stdout)
        self.assertIn('backup  ', res.stdout)
        self.assertFalse((self.home / '.local/share/agentoo/user-dots').exists())
        self.assertFalse((self.home / '.tmux.conf').exists())
        self.assertEqual((self.home / '.zshrc').read_text(), '# existing unmanaged zshrc\n')

    def test_install_backup_warning_and_idempotent_local_overrides(self):
        (self.home / '.zshrc').write_text('# old unmanaged zshrc\n')
        (self.home / '.gitconfig').write_text('[user]\n    name = Old\n')

        first = self.run_installer()
        self.assertIn('WARNING: Backed up existing unmanaged file', first.stderr)
        self.assertIn('BACKUP SUMMARY', first.stderr)

        zsh_backups = list(self.home.glob('.zshrc.pre-agentoo.*'))
        git_backups = list(self.home.glob('.gitconfig.pre-agentoo.*'))
        self.assertEqual(len(zsh_backups), 1)
        self.assertEqual(len(git_backups), 1)
        self.assertEqual(zsh_backups[0].read_text(), '# old unmanaged zshrc\n')
        self.assertEqual(git_backups[0].read_text(), '[user]\n    name = Old\n')

        bundle = self.home / '.local/share/agentoo/user-dots'
        for rel in (
            'zsh/zshrc',
            'tmux.conf',
            'vim/vimrc.local',
            'nvim/agentoo.lua',
            'nvim/queries/markdown/highlights.scm',
            'nvim/site/after/ftplugin/markdown.lua',
            'git/gitconfig-user',
            'git/gitignore-user',
            'git/git_wrap_commit_msg.py',
        ):
            self.assertTrue((bundle / rel).is_file(), rel)
        self.assertEqual((bundle / 'git/git_wrap_commit_msg.py').stat().st_mode & 0o777, 0o755)
        softlock = self.home / '.local/share/nvim/site/pack/agentoo/start/softlock'
        self.assertTrue((softlock / 'plugin/softlock.lua').is_file())
        self.assertTrue((softlock / 'doc/softlock.txt').is_file())
        if shutil.which('nvim'):
            self.assertTrue((softlock / 'doc/tags').is_file())

        # Add host-local overrides below managed loaders; re-run must preserve them and make no new backups.
        for path, line in (
            (self.home / '.zshrc', 'export HOST_LOCAL_TEST=1\n'),
            (self.home / '.tmux.conf', 'set -g status-interval 30\n'),
            (self.home / '.vimrc', 'set shiftwidth=4\n'),
            (self.home / '.config/nvim/init.lua', 'vim.g.host_local_nvim = true\n'),
            (self.home / '.gitconfig', '[user]\n    name = Local Override\n'),
        ):
            self.assertTrue(path.read_text().endswith('\n'), str(path))
            with path.open('a') as handle:
                handle.write(line)

        second = self.run_installer()
        self.assertNotIn('WARNING:', second.stderr)
        self.assertNotIn('BACKUP SUMMARY', second.stderr)
        self.assertEqual(len(list(self.home.glob('.zshrc.pre-agentoo.*'))), 1)
        self.assertIn('export HOST_LOCAL_TEST=1', (self.home / '.zshrc').read_text())
        self.assertIn('vim.g.host_local_nvim = true', (self.home / '.config/nvim/init.lua').read_text())
        self.assertIn('name = Local Override', (self.home / '.gitconfig').read_text())

    def test_failed_staging_leaves_existing_bundle_intact(self):
        self.run_installer()
        bundle = self.home / '.local/share/agentoo/user-dots'
        marker = bundle / 'zsh/zshrc'
        original = marker.read_text()

        empty_src = self.base / 'broken-src'
        empty_src.mkdir()
        failed = subprocess.run(
            ['bash', str(INSTALLER), '--source-dir', str(empty_src), '--softlock-dir', str(self.softlock_src)],
            env=self.env, text=True, capture_output=True,
        )
        self.assertNotEqual(failed.returncode, 0)
        self.assertEqual(marker.read_text(), original)

    def test_curl_download_path_passes_output_flag_before_end_of_options(self):
        # Exercise the remote fetch path offline with a fake curl that rejects flags after --.
        archive = self.base / 'softlock.tar.gz'
        subprocess.run(
            ['tar', '-czf', str(archive), '-C', str(self.base), 'softlock-src'],
            check=True,
        )
        fake_bin = self.base / 'fake-bin'
        fake_bin.mkdir()
        fake_curl = fake_bin / 'curl'
        fake_curl.write_text(f'''#!/usr/bin/env python3
import shutil, sys
from pathlib import Path

args = sys.argv[1:]
dest = None
url = None
end_of_opts = False
i = 0
while i < len(args):
    a = args[i]
    if not end_of_opts and a == '--':
        end_of_opts = True
        i += 1
        continue
    if not end_of_opts and a == '-o':
        dest = args[i + 1]
        i += 2
        continue
    if not end_of_opts and a in ('--retry', '--connect-timeout'):
        i += 2
        continue
    if not end_of_opts and a.startswith('-'):
        i += 1
        continue
    if url is not None:
        sys.exit(f'unexpected extra positional arg (e.g. option after --): {{a}}')
    url = a
    i += 1

assert dest and url, f'missing dest or url: {{args}}'
raw_prefix = 'https://raw.githubusercontent.com/grahamlopez/agentoo/main/'
if url.startswith(raw_prefix):
    rel = url[len(raw_prefix):]
    shutil.copyfile(Path({str(ROOT)!r}) / rel, dest)
elif url == 'https://github.com/grahamlopez/softlock.nvim/archive/main.tar.gz':
    shutil.copyfile({str(archive)!r}, dest)
else:
    sys.exit(f'unexpected url: {{url}}')
''')
        fake_curl.chmod(0o755)
        env = {**self.env, 'PATH': f'{fake_bin}:{self.env["PATH"]}'}
        res = subprocess.run(['bash', str(INSTALLER)], env=env, text=True, capture_output=True)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertTrue((self.home / '.local/share/agentoo/user-dots/zsh/zshrc').is_file())
        self.assertTrue((self.home / '.local/share/nvim/site/pack/agentoo/start/softlock/plugin/softlock.lua').is_file())

    @unittest.skipUnless(shutil.which('git'), 'Git required')
    def test_deployed_git_config_ignores_and_commit_hook(self):
        self.run_installer()
        (self.home / '.gitconfig-local').write_text('[user]\n    name = Satellite\n    email = sat@example.invalid\n')

        repo = self.home / 'project'
        subprocess.run(['git', 'init', '-q', str(repo)], env=self.env, check=True)
        alias = subprocess.run(['git', '-C', str(repo), 'config', '--get', 'alias.st'],
                               env=self.env, text=True, capture_output=True, check=True).stdout.strip()
        self.assertEqual(alias, 'status')

        # User gitignore excludes bytecode and ssh keys, NOT agentoo /etc system paths.
        ignored = subprocess.run(
            ['git', '-C', str(repo), 'check-ignore', '--no-index',
             '__pycache__/a.pyc', '.ssh/id_ed25519', '.ssh/config', 'etc/fstab'],
            env=self.env, text=True, capture_output=True,
        ).stdout.splitlines()
        self.assertEqual(ignored, ['__pycache__/a.pyc', '.ssh/id_ed25519'])

        # Commit-msg hook wraps long body lines and enforces subject width.
        (repo / 'README.md').write_text('hello\n')
        subprocess.run(['git', '-C', str(repo), 'add', 'README.md'], env=self.env, check=True)
        long_body = 'word ' * 25
        subprocess.run(['git', '-C', str(repo), 'commit', '-m', 'Short subject', '-m', long_body.strip()],
                       env=self.env, text=True, capture_output=True, check=True)
        body = subprocess.run(['git', '-C', str(repo), 'log', '-1', '--format=%b'],
                              env=self.env, text=True, capture_output=True, check=True).stdout.strip()
        self.assertTrue(all(len(line) <= 80 for line in body.splitlines()), body)
        self.assertGreater(len(body.splitlines()), 1)

    @unittest.skipUnless(shutil.which('zsh'), 'zsh required')
    def test_deployed_zshrc_loads_and_guards_emerge(self):
        self.run_installer()
        with (self.home / '.zshrc').open('a') as handle:
            handle.write('export LOCAL_OVERRIDE_MARKER=yes\n')
        # Use a PATH without emerge to simulate a non-Gentoo host.
        fake_bin = self.base / 'bin'
        fake_bin.mkdir()
        for tool in ('zsh', 'dircolors', 'mktemp', 'rm', 'infocmp'):
            found = shutil.which(tool)
            if found:
                (fake_bin / tool).symlink_to(found)
        env = {**self.env, 'PATH': str(fake_bin), 'TERM': 'dumb'}
        res = subprocess.run(
            ['zsh', '-d', '-i', '-c',
             'print -r -- "LESS=$LESS LOCAL=$LOCAL_OVERRIDE_MARKER BEMERGE=${aliases[bemerge]-unset}"'],
            env=env, text=True, capture_output=True, timeout=15, start_new_session=True,
        )
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn('LESS=-ifqMR', res.stdout)
        self.assertIn('LOCAL=yes', res.stdout)
        self.assertIn('BEMERGE=unset', res.stdout)

    @unittest.skipUnless(shutil.which('nvim'), 'Neovim required')
    def test_deployed_nvim_loads_agentoo_markdown_and_softlock(self):
        self.run_installer()
        with (self.home / '.config/nvim/init.lua').open('a') as handle:
            handle.write('vim.g.satellite_local = "ok"\n')
        md = self.home / 'note.md'
        md.write_text('# Heading\n\nBody\n')
        check_lua = self.home / 'verify.lua'
        check_lua.write_text('''
local ok, err = pcall(function()
  assert(vim.g.mapleader == " ", "mapleader not set")
  assert(vim.g.satellite_local == "ok", "local override missing")
  assert(vim.g.softlock_loaded_fixture == true, "softlock plugin not loaded")
  local rtp = vim.opt.rtp:get()
  local cfg = vim.fn.stdpath("config")
  local bundle = vim.env.XDG_DATA_HOME .. "/agentoo/user-dots"
  local idx = {}
  for i, p in ipairs(rtp) do idx[p] = i end
  assert(idx[cfg] < idx[bundle .. "/nvim"], "user config must precede bundle nvim")
  assert(idx[bundle .. "/nvim/site/after"] < idx[cfg .. "/after"], "bundle after must precede user after")
  vim.cmd.edit(vim.fn.fnameescape(vim.env.HOME .. "/note.md"))
  assert(vim.bo.filetype == "markdown", "expected markdown filetype")
  assert(vim.bo.textwidth == 0, "expected markdown after/ftplugin textwidth=0")
end)
if not ok then
  io.stderr:write(tostring(err) .. "\\n")
  vim.cmd("cquit")
end
vim.cmd("qa!")
''')
        res = subprocess.run(
            ['nvim', '--headless', '-i', 'NONE', '-n', '-c', 'luafile ' + str(check_lua)],
            env=self.env, text=True, capture_output=True, timeout=15,
        )
        self.assertEqual(res.returncode, 0, res.stderr)

    @unittest.skipUnless(shutil.which('vim'), 'Vim required')
    def test_deployed_vimrc_loads_and_allows_local_overrides(self):
        self.run_installer()
        with (self.home / '.vimrc').open('a') as handle:
            handle.write('set shiftwidth=4\n')
        checks = self.home / 'vim_checks.vim'
        checks.write_text(
            'call assert_equal(4, &shiftwidth)\n'
            'call assert_equal(80, &textwidth)\n'
            'if !empty(v:errors)\n'
            '  call writefile(v:errors, expand("$HOME") . "/vim_errors")\n'
            '  cquit\n'
            'endif\n'
            'qa!\n'
        )
        res = subprocess.run(
            ['vim', '-N', '-u', str(self.home / '.vimrc'), '-i', 'NONE', '-n', '-Es', '-S', str(checks)],
            env=self.env, text=True, capture_output=True, timeout=15,
        )
        errors_file = self.home / 'vim_errors'
        detail = errors_file.read_text() if errors_file.exists() else res.stderr
        self.assertEqual(res.returncode, 0, detail)

    @unittest.skipUnless(shutil.which('tmux'), 'tmux required')
    def test_deployed_tmux_conf_parses_cleanly(self):
        self.run_installer()
        with (self.home / '.tmux.conf').open('a') as handle:
            handle.write('set -g status-interval 30\n')
        sock = self.base / 'tmux.sock'
        try:
            res = subprocess.run(
                ['tmux', '-S', str(sock), '-f', str(self.home / '.tmux.conf'),
                 'start-server', ';', 'show-options', '-gv', 'prefix', ';',
                 'show-options', '-gv', 'status-interval'],
                env=self.env, text=True, capture_output=True, timeout=15,
            )
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertEqual(res.stdout.splitlines(), ['C-a', '30'])
        finally:
            subprocess.run(['tmux', '-S', str(sock), 'kill-server'], env=self.env,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == '__main__':
    unittest.main()
