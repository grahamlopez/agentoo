# Preserve native file resolution in Markdown link navigation

Created: 2026-10-31
Status: Completed
Priority: Medium

[The Markdown ftplugin](../../../nvim/site/after/ftplugin/markdown.lua)
replaces `gf`, calls remapped `gf` again after moving the cursor, and falls back
to `:edit` with `<cfile>`. That loses native file resolution and can open a new,
wrong file instead of following a document-relative link.

The review reproduced `[target](target.md)` in `docs/source.md` with an existing
`docs/target.md` and the working directory above `docs/`. The actual mapping
opened `<working-directory>/target.md` instead. The reproduction used headless
Neovim and disposable documents.

Keep any necessary link-location behavior small, then delegate resolution to
native `gf` without re-entering the mapping. Check whether the native Markdown
filetype configuration already supplies enough behavior before retaining custom
link parsing. Avoid a general Markdown navigation subsystem.

Completed on 2026-10-31. The native Markdown ftplugin was inspected: it does not
provide the desired label/bracket navigation. The small project mapping now
finds only the balanced link containing the cursor, moves to its destination,
and delegates to nonremapped native `[count]gf`. Bare paths use the same native
operation. The remapped recursive call and `:edit` fallback were removed; no
custom path resolver or general Markdown parser was added.

Validation: all three native headless checks in `test_markdown_navigation.py`
passed without skips. Disposable documents verify every cursor position across
two same-line links, document-relative resolution with another working directory,
bare paths, native suffix/path/count handling, and native `E447` for missing link
or bare destinations without opening a new buffer. Tests load the actual project
ftplugin; only unrelated Tree-sitter startup is stubbed, so no parser is required
to exercise real `gf`. `git diff --check` passed. No live editor state changed.
