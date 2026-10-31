"""Markdown navigation delegates to real native gf against disposable documents."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[5]
PLUGIN = ROOT / 'usr/local/share/nvim/site/after/ftplugin/markdown.lua'


@unittest.skipUnless(shutil.which('nvim'), 'Neovim required')
class MarkdownNavigationTests(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory(prefix='agentoo-markdown-')
        self.addCleanup(self.work.cleanup)
        self.root = Path(self.work.name)
        self.docs = self.root / 'docs'
        self.docs.mkdir()
        self.source = self.docs / 'source.md'
        self.source.write_text('[first](target.md) and [second](second.md)\n')
        (self.docs / 'target.md').write_text('first destination\n')
        (self.docs / 'second.md').write_text('second destination\n')

    def lua(self, body):
        script = self.root / 'check.lua'
        script.write_text('local ok, err = pcall(function()\n' +
                          'local source = ' + json.dumps(str(self.source)) + '\n' +
                          'local plugin = ' + json.dumps(str(PLUGIN)) + '\n' +
                          '''-- Navigation does not require a Tree-sitter parser.
vim.treesitter.start = function() end
local function open_source()
  vim.cmd.edit(source)
  vim.bo.filetype = 'markdown'
  dofile(plugin)
end
''' + body + "\nend)\nif not ok then print(err); vim.cmd('cquit') end\nvim.cmd('qa!')\n")
        env = {**os.environ, 'HOME': str(self.root),
               'XDG_DATA_HOME': str(self.root / 'data'),
               'XDG_STATE_HOME': str(self.root / 'state'),
               'XDG_CACHE_HOME': str(self.root / 'cache'),
               'NVIM_LOG_FILE': str(self.root / 'nvim.log')}
        result = subprocess.run(['nvim', '--headless', '-u', 'NONE', '-i', 'NONE', '-n',
                                 '-c', 'luafile ' + str(script)], cwd=self.root, env=env,
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_each_link_position_and_multiple_links_resolve_beside_document(self):
        self.lua('''
for col = 0, #'[first](target.md)' - 1 do
  open_source()
  vim.api.nvim_win_set_cursor(0, {1, col})
  vim.cmd.normal('gf')
  assert(vim.api.nvim_buf_get_name(0) == vim.fn.fnamemodify(source, ':h') .. '/target.md', col)
end
for col = #'[first](target.md) and ', #'[first](target.md) and [second](second.md)' - 1 do
  open_source()
  vim.api.nvim_win_set_cursor(0, {1, col})
  vim.cmd.normal('gf')
  assert(vim.api.nvim_buf_get_name(0) == vim.fn.fnamemodify(source, ':h') .. '/second.md', col)
end
''')

    def test_bare_paths_use_native_path_suffix_and_count(self):
        self.source.write_text('target\n')
        other = self.root / 'other'
        other.mkdir()
        (other / 'target.md').write_text('second search result\n')
        self.lua('''
for count = 1, 2 do
  open_source()
  local other = vim.fn.fnamemodify(source, ':h:h') .. '/other'
  vim.opt_local.suffixesadd = {'.md'}
  vim.opt_local.path = {'.', other}
  vim.cmd.normal(count .. 'gf')
  local expected = (count == 1 and vim.fn.fnamemodify(source, ':h') or other) .. '/target.md'
  assert(vim.api.nvim_buf_get_name(0) == expected)
end
''')

    def test_missing_link_and_bare_destination_fail_without_opening_new_buffer(self):
        self.source.write_text('[missing](missing.md)\nmissing.md\n')
        self.lua('''
for row = 1, 2 do
  open_source()
  vim.api.nvim_win_set_cursor(0, {row, 0})
  local ok, err = pcall(vim.cmd.normal, 'gf')
  assert(not ok and err:match('E447'), tostring(err))
  assert(vim.api.nvim_buf_get_name(0) == source)
end
''')
