"""Git configuration changes use disposable repositories, without networking."""
from contextlib import redirect_stderr
from importlib.machinery import SourceFileLoader
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ENTRY = Path(__file__).resolve().parents[3] / 'bin/agentoo-git'
spec = importlib.util.spec_from_loader('agentoo_git', SourceFileLoader('agentoo_git', str(ENTRY)))
git = importlib.util.module_from_spec(spec)
spec.loader.exec_module(git)


class GitTests(unittest.TestCase):
    def test_enable_write_replaces_https_push_override_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temporary, \
             patch.dict(os.environ, GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL='/dev/null'):
            root = Path(temporary)
            repository = root / 'repository.git'
            subprocess.run(['git', 'init', '--bare', str(repository)], check=True, capture_output=True)
            command = ['git', f'--git-dir={repository}']
            https = 'https://github.com/grahamlopez/agentoo.git'
            subprocess.run([*command, 'remote', 'add', 'origin', https], check=True)
            subprocess.run([*command, 'config', 'remote.origin.pushurl', https], check=True)
            with patch.object(git, 'SYSTEM_GIT_DIR', repository), \
                 patch.object(git, 'SYSTEM_WORK_TREE', root), \
                 patch.object(git.os, 'geteuid', return_value=0), \
                 patch.object(git.sys, 'argv', ['agentoo-git', 'enable-write']), \
                 redirect_stderr(io.StringIO()):
                for _ in range(2):
                    self.assertEqual(git.main(), 0)
                    for options in ([], ['--push']):
                        result = subprocess.run([*command, 'remote', 'get-url', *options, 'origin'],
                                                check=True, text=True, capture_output=True)
                        self.assertEqual(result.stdout.strip(), git.SSH_REMOTE)


if __name__ == '__main__':
    unittest.main()
