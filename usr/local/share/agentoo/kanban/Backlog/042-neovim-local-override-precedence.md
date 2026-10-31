# Make Neovim appearance defaults respect local overrides

Created: 2026-10-31
Status: Backlog
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

Complete when a personal highlight preference survives ordinary option changes
and window transitions. Add a focused native regression covering shared defaults,
personal overrides, and relevant colorscheme/transparent-background behavior.
Coordinate entry-point changes with
[card 040](040-native-shell-editor-extension-points.md).
