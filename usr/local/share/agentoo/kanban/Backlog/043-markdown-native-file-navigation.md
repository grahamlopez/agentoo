# Preserve native file resolution in Markdown link navigation

Created: 2026-10-31
Status: Backlog
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

Complete when relative links resolve beside the document with a different working
directory, bare paths retain native behavior, and the mapping does not invoke
itself. Add focused native checks for cursor positions within a link and multiple
links on a line, and confirm missing destinations preserve native failure behavior.
