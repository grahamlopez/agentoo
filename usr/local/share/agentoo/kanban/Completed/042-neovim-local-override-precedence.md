# Make Neovim appearance defaults respect local overrides

Created: 2026-10-31
Status: Completed
Priority: Medium

[Shared Neovim configuration](../../../../../../etc/xdg/nvim/agentoo.lua)
registers a highlight callback for `ColorScheme`, every `OptionSet`, `VimEnter`,
`WinNew`, and `WinEnter`. It repeatedly assigns `Whitespace`, `NonText`, and
`SpecialKey`. Loading personal configuration afterward does not provide lasting
precedence.

The review reproduced this with the actual shared Lua in a disposable headless
Neovim session: setting `Whitespace` to `#123456`, then triggering an unrelated
`OptionSet` event, restored Agentoo's `#d70000`. No live editor settings changed.

Apply shared defaults at the narrowest necessary lifecycle events and provide
an explicit native way to override persistent behavior. Review related shared
appearance callbacks for the same precedence issue, without expanding into a
theme framework. Preserve the intended shared appearance where no override exists.

Completed on 2026-10-31, following the native entry-point change in
[card 040](040-native-shell-editor-extension-points.md). One shared appearance
procedure runs during shared initialization and on `ColorScheme`, in the native
`agentoo_appearance` group. There is no late `VimEnter` appearance reset.
Personal initialization runs afterward; later personal `ColorScheme` callbacks
can override theme updates, or clear this native group. Shell/editor guidance
documents these extension points without adding a theme settings schema.

Per-window TODO matches remain independent, in `agentoo_todo_matches`, refreshed
at window entry, initial editor entry, and `OptionSet` only for `background`.
They preserve unrelated matches and no longer redefine shared highlight colors.
Transparency now saves and changes only backgrounds, preserving foregrounds and
styles. Each opaque-to-transparent transition captures the current background,
so personal edits made while opaque survive toggling back. Scheme changes keep
the existing enabled/disabled choice.

Validation: all three native headless checks in `test_neovim.py` passed, plus
all eight shell/editor integration checks, without skips. Disposable tests use
the actual shared Lua and cover defaults, personal overrides through startup,
unrelated option changes and window transitions, TODO match isolation, later
personal colorscheme callbacks, native group opt-out, RGB/terminal backgrounds,
foreground/style preservation, opaque personal edits, and new-scheme toggling.
`git diff --check` passed. No live editor configuration was changed.
