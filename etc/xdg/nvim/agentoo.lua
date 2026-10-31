-- Requires Neovim 0.11 or newer and Markdown Tree-sitter parsers.
-- Undo, caches, and history use writable per-user storage.
-- Agentoo Neovim defaults, adapted from dots/.config/nvim/init.lua.
-- Keybindings, Abbreviations {{{
-- For modes, see `:help map-modes`
--     To see mappings:
--     - :help [keys] for built-in keymappings
--     - :map [keys] for user-defined keymappings (with file:line location of defn)

-- Preserve Space as the familiar Neovim leader; Vim retains backslash.
vim.g.mapleader = " "
vim.g.maplocalleader = " "

vim.keymap.set("n", "<leader>co", function() vim.cmd.edit(vim.fn.stdpath("config") .. "/init.lua") end, { desc = "Edit Neovim config" })
vim.keymap.set({ "n" }, "<esc>", ":nohl<cr>", { silent = true })                       -- cancel highlighting
vim.keymap.set("n", "k", "v:count == 0 ? 'gk' : 'k'", { expr = true, silent = true }) -- deal with line wrap
vim.keymap.set("n", "j", "v:count == 0 ? 'gj' : 'j'", { expr = true, silent = true }) -- deal with line wrap
vim.keymap.set("n", "]q", ":cnext<cr>zv", {})
vim.keymap.set("n", "[q", ":cprev<cr>zv", {})
vim.keymap.set("n", "zh", "zM zv", { desc = "fold everywhere but here" })
-- :restart is available only in newer Neovim releases.
vim.keymap.set("n", "<leader>R", function()
  if vim.fn.exists(":restart") == 2 then
    vim.cmd.restart()
  else
    vim.notify("Save your files, quit, and reopen Neovim to restart.", vim.log.levels.INFO)
  end
end, { silent = true, desc = "Restart Neovim" })
vim.keymap.set({ "n" }, "<C-b>", ":buffers<CR>:b<Space>", { silent = true })

vim.cmd("cabbrev vh vert help")
-- }}}

-- Options {{{
-- intro comments {{{
--[[
    These are some options that I've been carring around
    See :help vim.o and :help vim.opt
    and Vhyrro's YT vid: https://www.youtube.com/watch?v=Cp0iap9u29c&t=334s

    each table can contain both variables and/or options. variables are essentially
    "scoped" to a buffer, window, tab, or globally. Options may apply to one of
    these but not another. Note that 'id' numbers are optional, and default to
    the current buffer/window/tab

    variables         options
    ---------         ---------
    vim.b[id]         vim.bo[id]
    vim.w[id]         vim.wo[id]
    vim.t[id]         vim.to[id]
    vim.g             vim.o
                      vim.opt
                      vim.opt_local
                      vim.opt_global

    'vim.o' automatically detects the scope(s) of an option and uses it. If the
    option is only local or only global, sets that option. If the option is
    global-local, sets both versions of the variable. Only returns the bare
    variable; not helper functions.

    'vim.opt' will set both _global and _local versions, or whichever one is
    available if it isn't a global-local variable.

    Note that for checking option values (e.g. if vim.o[pt].background == "dark")
    that vim.o.* returns the option value as a Lua primitive, while vim.opt.*
    treats each option as a special object (metatable) with methods for list
    manipulation and advanced operations, such as vim.opt.background:get().

    ':set all' to see all possible settings and their current values
    ':help options' to get to the options part of the manual
--]]
-- }}}
-- General settings {{{
vim.opt.autoindent = true                             -- Copy indent from current line
vim.opt.autoread = true
vim.opt.autowrite = true                              -- Auto-write before running commands
vim.opt.breakindent = true                            -- Maintain indent when wrapping
vim.opt.clipboard:append { "unnamed", "unnamedplus" } -- requires wl-clipboard
vim.opt.colorcolumn = ""
vim.cmd.colorscheme('default')
vim.opt.cursorline = true
vim.opt.cursorlineopt = "number"
vim.opt.completeopt = { "fuzzy", "menu", "menuone", "noselect", "noinsert" }
vim.opt.diffopt:append("linematch:60") -- Better diffs
vim.opt.expandtab = true
vim.opt.foldmethod = "expr"
vim.opt.foldexpr = "v:lua.vim.treesitter.foldexpr()"
vim.opt.foldlevel = 99
vim.opt.foldenable = true
vim.opt.foldcolumn = "0" -- "1" shows the fold gutter (click to open/close folds)
vim.opt.fillchars:append({ fold = " " })
vim.opt.hidden = true
vim.opt.history = 1000    -- More command history
vim.opt.hlsearch = true   -- Set highlight on search
vim.opt.ignorecase = true -- Case-insensitive searching UNLESS \C or capital in search
vim.opt.inccommand = "split"
vim.opt.laststatus = 3
vim.opt.linebreak = true  -- Break at word boundaries if wrap enabled
vim.g.loaded_perl_provider = 0
vim.g.loaded_python3_provider = 0
vim.g.loaded_ruby_provider = 0 -- Disable some providers for faster startup
vim.loader.enable()            -- Enable faster Lua module loading
vim.opt.number = false
vim.opt.pumblend = 10  -- Popup menu transparency
vim.opt.pumheight = 15 -- Maximum items in popup menu
vim.opt.relativenumber = false
vim.opt.scrolloff = 5
vim.opt.sessionoptions = { "buffers", "curdir", "folds", "help", "tabpages", "winsize", "winpos", "terminal", "globals", }
vim.opt.shiftwidth = 2
vim.opt.shortmess:append("c")
vim.opt.sidescrolloff = 5 -- Keep columns left/right of cursor
vim.opt.signcolumn = "auto"
vim.opt.smartcase = true
vim.opt.smartindent = true
vim.opt.softtabstop = 2
vim.opt.spell = false
vim.opt.spelllang = { "en_us" }
-- Shared policy; each account owns its spell additions (zg/zw).
local spell_dir = vim.fn.stdpath("data") .. "/site/spell"
vim.fn.mkdir(spell_dir, "p")
vim.opt.spellfile = spell_dir .. "/en.utf-8.add"
vim.opt.splitbelow = true
vim.opt.splitright = true
vim.opt.tabstop = 2                    -- Tab width
vim.opt.termguicolors = true
vim.opt.textwidth = 80                 -- Text width for formatting
vim.opt.timeoutlen = 500               -- More lenient keybindings vs. faster which-key popup
vim.opt.undofile = true                -- Persistent undo
vim.opt.updatetime = 250               -- Faster completion (4000ms default)
vim.opt.virtualedit = "block"
vim.opt.wildmode = "longest:full,full" -- Command completion mode
vim.opt.wildignore:append({ "*.o", "*.obj", ".git", "node_modules", "*.pyc" })
vim.opt.wildignorecase = true
vim.opt.wildoptions:append({ "fuzzy" }) -- FIXME: menu disappears with next keypress
vim.opt.winheight = 5
vim.opt.winminheight = 5
vim.opt.winminwidth = 5
vim.opt.winwidth = 5
vim.opt.wrap = true -- visually wrap lines when needed
-- }}}
-- }}}

-- Utilities (lightweight plugins) {{{
-- fuzzy-file-picker and TODO: live-grep {{{
local filescache = {} -- Files cache (per-process)
-- Helper to (re)build the cache from the current directory
local function build_files_cache()
  local files = vim.fn.globpath('.', '**', true, true) -- globpath('.', '**', 1, 1)
  -- filter out directories: !isdirectory(v:val)
  files = vim.tbl_filter(function(path)
    return vim.fn.isdirectory(path) == 0
  end, files)
  -- fnamemodify(v:val, ':.') to make paths relative to cwd
  files = vim.tbl_map(function(path)
    return vim.fn.fnamemodify(path, ':.')
  end, files)
  filescache = files
end
-- This is the function used by 'findfunc'
local function Find(arg, _)
  if #filescache == 0 then
    build_files_cache()
  end
  if arg == '' then
    return filescache
  end
  return vim.fn.matchfuzzy(filescache, arg)
end
-- Expose it under a global name so 'findfunc' can see it
_G.Find = Find
-- Tell :find to use this function
vim.o.findfunc = 'v:lua.Find'
-- Clear cache on CmdlineEnter :
vim.api.nvim_create_autocmd('CmdlineEnter', {
  pattern = ':',
  callback = function()
    filescache = {}
  end,
})
-- }}}

-- TODO and friends {{{
-- grep todo keywords and add to quickfix
-- == 1 is required: executable() returns 0/1, and 0 is truthy in Lua
if vim.fn.executable('rg') == 1 then
  vim.opt.grepprg = "rg --vimgrep --no-hidden --no-heading"
end
vim.api.nvim_create_user_command("Todos", function()
  vim.cmd.vimgrep({ '/\\(TODO\\|FIXME\\|IDEA\\|TRACK\\):/', '**/*' })
  vim.cmd("CopenSmart 25")
end, { desc = "vimgrep TODO and friends to quickfix", nargs = 0 })

-- Matches belong to windows; their colors are shared appearance defaults below.
local function refresh_todo_matches()
  for _, match in ipairs(vim.fn.getmatches()) do
    if match.group == "darkTodoPattern" or match.group == "lightTodoPattern" then
      vim.fn.matchdelete(match.id)
    end
  end
  local group = vim.o.background == "dark" and "darkTodoPattern" or "lightTodoPattern"
  vim.fn.matchadd(group, "\\(TODO\\|FIXME\\|IDEA\\|TRACK\\):")
end
local todo_matches = vim.api.nvim_create_augroup("agentoo_todo_matches", { clear = true })
vim.api.nvim_create_autocmd({ "VimEnter", "WinEnter" }, {
  group = todo_matches,
  callback = refresh_todo_matches,
})
vim.api.nvim_create_autocmd("OptionSet", {
  group = todo_matches,
  pattern = "background",
  callback = refresh_todo_matches,
})

local function qf_open_smart(max_height, min_height)
  max_height = max_height or 15
  min_height = min_height or 1

  local qf_list = vim.fn.getqflist()
  local n_items = #qf_list

  if n_items == 0 then return end

  local h = math.min(n_items, max_height)
  h = math.max(h, min_height)

  vim.cmd(h .. "copen")

  vim.wo.winfixheight = true
end

vim.api.nvim_create_user_command("CopenSmart", function(opts)
  -- optional: allow :CopenSmart 20
  local maxh = tonumber(opts.args) or 15
  qf_open_smart(maxh, 1)
end, { nargs = "?", desc = "Open quickfix sized to contents with max height" })

-- Auto-size quickfix after typical quickfix commands
vim.api.nvim_create_autocmd("QuickFixCmdPost", {
  pattern = { "make", "grep", "vimgrep", "lvimgrep" },
  callback = function()
    qf_open_smart(20, 3) -- max 15 lines, min 3
  end,
})
-- }}}

-- background transparency {{{
local transparent_enabled = true  -- startup default
local saved_backgrounds = {}
local groups = {
  'Normal',
  'NormalNC',
  'NormalFloat',
  'FloatBorder',
  'SignColumn',
  'WinSeparator',
}
local function save_backgrounds()
  for _, name in ipairs(groups) do
    local def = vim.api.nvim_get_hl(0, { name = name, link = false })
    saved_backgrounds[name] = { bg = def.bg, ctermbg = def.ctermbg }
  end
end
local function apply_backgrounds(transparent)
  for _, name in ipairs(groups) do
    local def = vim.api.nvim_get_hl(0, { name = name, link = false })
    if transparent then
      def.bg, def.ctermbg = nil, nil
    else
      def.bg = saved_backgrounds[name].bg
      def.ctermbg = saved_backgrounds[name].ctermbg
    end
    vim.api.nvim_set_hl(0, name, def)
  end
end
function _G.ToggleTransparent()
  if transparent_enabled then
    apply_backgrounds(false)
    transparent_enabled = false
  else
    save_backgrounds()
    apply_backgrounds(true)
    transparent_enabled = true
  end
end

vim.api.nvim_create_user_command("TransparentToggle", function()
  ToggleTransparent()
end, { desc = "Toggle background transparency", nargs = 0 })
vim.keymap.set('n', '<leader>ut', ToggleTransparent, { desc = 'Toggle transparent background' })
-- }}}

-- listchars display {{{
-- Show listchars
-- single definition (glyphs kept from the former duplicate up in Options)
vim.opt.listchars = {
  tab = "→ ",
  trail = "·",
  nbsp = "○",
  space = "·",
  extends = "▸",
  precedes = "◂",
}

-- Apply before personal init; later personal ColorScheme callbacks can override.
local function apply_appearance_defaults()
  vim.api.nvim_set_hl(0, "darkTodoPattern", { fg = "#ffaf00", bold = true })
  vim.api.nvim_set_hl(0, "lightTodoPattern", { fg = "#cd4848", bold = true })
  vim.api.nvim_set_hl(0, "Whitespace", { fg = "#d70000", ctermfg = 160 })
  vim.api.nvim_set_hl(0, "NonText", { fg = "#444444" })
  vim.api.nvim_set_hl(0, "SpecialKey", { fg = "#5f5f5f" })
  if transparent_enabled then
    save_backgrounds()
    apply_backgrounds(true)
  end
end
vim.api.nvim_create_autocmd("ColorScheme", {
  group = vim.api.nvim_create_augroup("agentoo_appearance", { clear = true }),
  callback = apply_appearance_defaults,
})
apply_appearance_defaults()
-- }}}
-- }}}

-- Filetype specifics {{{
-- Preserve comment indentation after fold markers; use the built-in indenter
-- for other lines. A native expression keeps v:lnum in its evaluation context.
vim.api.nvim_create_autocmd("FileType", {
  pattern = "lua",
  callback = function()
    vim.opt_local.indentexpr = [[getline(v:lnum) =~ '^\s*--' && prevnonblank(v:lnum - 1) > 0 ? indent(prevnonblank(v:lnum - 1)) : GetLuaIndent()]]
  end,
})
vim.api.nvim_create_autocmd("BufReadPost", {
  pattern = { "init.lua", "agentoo.lua" },
  callback = function()
    -- opt_local: global here would clobber treesitter folding everywhere else
    vim.opt_local.foldmethod = "marker"
    vim.opt_local.foldmarker = "{{{,}}}"
    vim.opt_local.foldlevel = 0
  end,
})
-- }}}

-- Gentoo's sysinit.vim supplies ebuild indentation; keep soft tabs consistent.
vim.api.nvim_create_autocmd({ "BufRead", "BufNewFile" }, {
  group = vim.api.nvim_create_augroup("agentoo_gentoo_files", { clear = true }),
  pattern = { "*.ebuild", "*.eclass" },
  callback = function()
    vim.bo.softtabstop = 0
  end,
})
