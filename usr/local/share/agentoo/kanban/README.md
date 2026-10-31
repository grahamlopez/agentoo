# Development Kanban

This board records deferred project work. Move each card between `Backlog`,
`Open`, and `Completed` as its status changes; retain the context and add
implementation and validation notes when completing it.

This repository uses `/` as its work tree on managed installations. The board
therefore lives under `/usr/local/share/agentoo/kanban` as
passive development documentation, outside configuration fragments and executable
paths. No installer or configuration tool should consume cards as instructions
or apply them automatically. Tracking a card does not authorize its implementation.

## Review handoff, 2026-10-31

The user agreed to the coordinated sequence below for non-installer cards
036–048. Execution has not started; resume after context compaction when the user
asks to continue. Check AGENTS.md, Git status, and the current cards first.
This sequence supersedes the immediate installer-next plan in card 030.

Use up to three worker agents, with the primary agent reviewing proposals and
integrating changes. Give workers isolated Git worktrees and bounded file
ownership. Each assignment starts by validating its finding and reporting a
short proposal: preserved requirements, native alternatives, intended changes,
and verification. Review proposals internally before implementation. Integrate
completed changes sequentially, with useful commits and evidence in each card.

First parallel batch:

- Worker A: [036, kernel installation consistency](Backlog/036-kernel-installed-module-consistency.md).
- Worker B: [037, secret destination directories](Backlog/037-secrets-parent-directory-policy.md).
- Worker C: [039, local identity exclusions](Backlog/039-ignore-local-host-and-boot-identity.md),
  then [048, derived compiler settings](Backlog/048-derived-portage-compiler-settings.md).

Next parallel batch:

- Worker A: [047, firmware indirection](Backlog/047-firmware-application-indirection.md),
  then [041, kernel documentation](Backlog/041-kernel-manual-guide-authority.md),
  using settled kernel behavior.
- Worker B: coordinate [038, shell startup](Backlog/038-desktop-shell-startup-order.md)
  with [040, native configuration ownership](Backlog/040-native-shell-editor-extension-points.md),
  then address [042, editor precedence](Backlog/042-neovim-local-override-precedence.md)
  and [043, Markdown navigation](Backlog/043-markdown-native-file-navigation.md).
- Worker C: investigate [045, appearance loading](Backlog/045-desktop-appearance-loading.md)
  and [046, native animation modeling](Backlog/046-native-animation-model.md)
  together, initially read-only. Use one owner for any resulting desktop changes.

[044, configuration cleanup](Backlog/044-retire-inactive-configuration-and-fallbacks.md)
follows the affected configuration changes. Leave the
[030 installer pilot](Backlog/030-installer-readable-procedures.md) outside these batches.

Preserve confirmed command features, JSON appearance storage, and concrete safety
checks. The previous `desktop-lua` experiment did not establish a simpler format
replacement. Reusing a kernel label requests replacement, as clarified in card
036; do not remove that capability. Avoid speculative abstractions, compatibility
paths, unrelated cleanup, and live hardware operations or desktop reloads.
A justified decision to retain an implementation is a valid investigation result.

Review every diff for simpler operating procedures, fewer concepts and policy
definitions, and removal of superseded paths. Run focused checks per change and
combined checks when changes interact. An available worker can independently
review higher-risk kernel/desktop changes. The preceding read-only review passed
300 non-installer Python tests and all five Lua scripts without skips, plus
disposable reproductions recorded in the cards; no live system changes ran.
Report concisely after each batch: changes, complexity removed, verification,
and any unresolved requirement decisions. No further preparation input was
identified after the kernel replacement clarification.
