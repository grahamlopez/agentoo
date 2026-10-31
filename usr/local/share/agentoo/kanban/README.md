# Development Kanban

This board records deferred project work. Move each card between `Backlog`,
`Open`, and `Completed` as its status changes; retain the context and add
implementation and validation notes when completing it.

This repository uses `/` as its work tree on managed installations. The board
therefore lives under `/usr/local/share/agentoo/kanban` as
passive development documentation, outside configuration fragments and executable
paths. No installer or configuration tool should consume cards as instructions
or apply them automatically. Tracking a card does not authorize its implementation.

## Non-installer review, 2026-10-31

Cards 036–048 are complete. Three workers used isolated Git worktrees; proposals
were reviewed before implementation and changes integrated sequentially. Kernel,
desktop, shell/editor, and navigation changes also received independent review.
Twelve cards produced changes; the animation investigation retained the existing
implementation because native APIs do not offer a simpler equivalent.

- Installation safety: [kernel image/module consistency](Completed/036-kernel-installed-module-consistency.md)
  and [secret destination directories](Completed/037-secrets-parent-directory-policy.md).
- Native configuration: [desktop startup order](Completed/038-desktop-shell-startup-order.md),
  [shell/editor ownership](Completed/040-native-shell-editor-extension-points.md),
  [Neovim override precedence](Completed/042-neovim-local-override-precedence.md),
  and [Markdown navigation](Completed/043-markdown-native-file-navigation.md).
- Shared policy: [local identity exclusions](Completed/039-ignore-local-host-and-boot-identity.md),
  [derived compiler flags](Completed/048-derived-portage-compiler-settings.md),
  and [inactive configuration cleanup](Completed/044-retire-inactive-configuration-and-fallbacks.md).
- Readable procedures and documentation: [firmware application](Completed/047-firmware-application-indirection.md)
  and [kernel guide authority](Completed/041-kernel-manual-guide-authority.md).
- Desktop state: [one validated appearance snapshot](Completed/045-desktop-appearance-loading.md)
  and [native animation API findings](Completed/046-native-animation-model.md).

Confirmed command features and JSON appearance storage remain supported. Existing
installations need to restore and accept the three packaged shell/editor entry
files when deploying their removal from Git; see
[deployment guidance](../../../../../etc/agentoo/README.md#shell-and-editor-environment).
Kernel replacement retains matching image/module backups and protects the running
modular release; cross-filesystem power-loss recovery remains an operator step
in the [kernel guide](../docs/kernel.md#install).

The first integrated batch passed 331 Python tests and all five then-existing
Lua scripts without skips. The final combined suite passed 349 Python tests and
all six Lua scripts without skips. Checks of changed Markdown files found no
missing targets among 113 local links and nine anchors; `git diff --check` passed.
Individual cards record focused native and disposable checks. No live hardware
operations, package rebuilds, desktop reloads, or configuration deployment ran.

The [030 installer pilot](Backlog/030-installer-readable-procedures.md) remains
deferred, outside this review. No implementation remains for cards 036–048.
