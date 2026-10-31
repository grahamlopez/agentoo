"""Headless Neovim checks use the actual shared Lua with disposable editor state."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[5]


@unittest.skipUnless(shutil.which('nvim'), 'Neovim required')
class NeovimTests(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory(prefix='agentoo-neovim-')
        self.addCleanup(self.work.cleanup)
        self.home = Path(self.work.name)
        self.env = {**os.environ, 'HOME': str(self.home),
                    'XDG_DATA_HOME': str(self.home / 'data'),
                    'XDG_STATE_HOME': str(self.home / 'state'),
                    'XDG_CACHE_HOME': str(self.home / 'cache'),
                    'NVIM_LOG_FILE': str(self.home / 'nvim.log')}

    def lua(self, body):
        script = self.home / 'check.lua'
        script.write_text('local ok, err = pcall(function()\n' +
                          'dofile(' + json.dumps(str(ROOT / 'etc/xdg/nvim/agentoo.lua')) + ')\n' + body +
                          "\nend)\nif not ok then print(err); vim.cmd('cquit') end\nvim.cmd('qa!')\n")
        result = subprocess.run(['nvim', '--headless', '-u', 'NONE', '-i', 'NONE', '-n',
                                 '-c', 'luafile ' + str(script)], env=self.env,
                                text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_personal_highlights_survive_startup_options_and_windows(self):
        self.lua('''
assert(vim.api.nvim_get_hl(0, {name='Whitespace'}).fg == 0xd70000)
assert(vim.api.nvim_get_hl(0, {name='darkTodoPattern'}).fg == 0xffaf00)
assert(vim.api.nvim_get_hl(0, {name='Normal'}).bg == nil)
for _, group in ipairs({'Whitespace','NonText','SpecialKey','darkTodoPattern','lightTodoPattern','Normal'}) do
  vim.api.nvim_set_hl(0, group, {fg='#123456', bg='#234567', bold=true})
end
vim.api.nvim_exec_autocmds('VimEnter', {})
local personal_match = vim.fn.matchadd('ErrorMsg', 'PERSONAL')
local before = vim.fn.getmatches()
vim.api.nvim_exec_autocmds('OptionSet', {pattern='number'})
assert(vim.deep_equal(before, vim.fn.getmatches()))
vim.cmd.vsplit()
vim.cmd.wincmd('p')
for _, group in ipairs({'Whitespace','NonText','SpecialKey','darkTodoPattern','lightTodoPattern','Normal'}) do
  local hl = vim.api.nvim_get_hl(0, {name=group})
  assert(hl.fg == 0x123456 and hl.bg == 0x234567 and hl.bold == true, group)
end
local own_matches = 0
local kept_personal = false
for _, match in ipairs(vim.fn.getmatches()) do
  if match.group == 'darkTodoPattern' or match.group == 'lightTodoPattern' then own_matches=own_matches+1 end
  if match.id == personal_match then kept_personal=true end
end
assert(own_matches == 1 and kept_personal)
vim.o.background = 'light'
vim.api.nvim_exec_autocmds('OptionSet', {pattern='background'})
for _, match in ipairs(vim.fn.getmatches()) do
  assert(match.group ~= 'darkTodoPattern')
end
''')

    def test_colorscheme_defaults_then_personal_callbacks_and_native_opt_out(self):
        colors = self.home / 'colors'
        colors.mkdir()
        (colors / 'fixture.lua').write_text("vim.api.nvim_set_hl(0, 'Normal', {fg='#aabbcc', bg='#112233', bold=true})\n"
                                           "vim.api.nvim_set_hl(0, 'Whitespace', {fg='#abcdef'})\n")
        self.lua('vim.opt.runtimepath:prepend(' + json.dumps(str(self.home)) + ''')
vim.cmd.colorscheme('fixture')
local normal = vim.api.nvim_get_hl(0, {name='Normal'})
assert(normal.fg == 0xaabbcc and normal.bg == nil and normal.bold == true)
assert(vim.api.nvim_get_hl(0, {name='Whitespace'}).fg == 0xd70000)
vim.api.nvim_create_autocmd('ColorScheme', {
group=vim.api.nvim_create_augroup('personal_appearance', {}), callback=function()
  vim.api.nvim_set_hl(0, 'Whitespace', {fg='#123456'})
  vim.api.nvim_set_hl(0, 'Normal', {fg='#123456', bg='#456789'})
end})
vim.cmd.colorscheme('fixture')
assert(vim.api.nvim_get_hl(0, {name='Whitespace'}).fg == 0x123456)
assert(vim.api.nvim_get_hl(0, {name='Normal'}).bg == 0x456789)
vim.api.nvim_clear_autocmds({group='agentoo_appearance'})
vim.api.nvim_clear_autocmds({group='personal_appearance'})
vim.cmd.colorscheme('fixture')
assert(vim.api.nvim_get_hl(0, {name='Whitespace'}).fg == 0xabcdef)
assert(vim.api.nvim_get_hl(0, {name='Normal'}).bg == 0x112233)
''')

    def test_transparency_changes_only_background_and_tracks_new_schemes(self):
        self.lua('''
vim.api.nvim_set_hl(0, 'Normal', {fg='#aabbcc', bg='#112233', ctermbg=17, bold=true})
vim.api.nvim_exec_autocmds('ColorScheme', {})
local normal = vim.api.nvim_get_hl(0, {name='Normal'})
assert(normal.fg == 0xaabbcc and normal.bold == true and normal.bg == nil and normal.ctermbg == nil)
normal.fg = 0x123456
vim.api.nvim_set_hl(0, 'Normal', normal)
vim.cmd.TransparentToggle()
normal = vim.api.nvim_get_hl(0, {name='Normal'})
assert(normal.fg == 0x123456 and normal.bold == true and normal.bg == 0x112233 and normal.ctermbg == 17)
normal.bg = 0x223344
vim.api.nvim_set_hl(0, 'Normal', normal)
vim.cmd.TransparentToggle()
normal = vim.api.nvim_get_hl(0, {name='Normal'})
assert(normal.fg == 0x123456 and normal.bold == true and normal.bg == nil and normal.ctermbg == nil)
vim.cmd.TransparentToggle()
assert(vim.api.nvim_get_hl(0, {name='Normal'}).bg == 0x223344)
vim.api.nvim_set_hl(0, 'Normal', {fg='#abcdef', bg='#334455'})
vim.api.nvim_exec_autocmds('ColorScheme', {})
assert(vim.api.nvim_get_hl(0, {name='Normal'}).bg == 0x334455)
vim.cmd.TransparentToggle()
assert(vim.api.nvim_get_hl(0, {name='Normal'}).bg == nil)
vim.cmd.TransparentToggle()
assert(vim.api.nvim_get_hl(0, {name='Normal'}).bg == 0x334455)
''')
