# Development Kanban

This board records deferred project work. Cards live in `Backlog` until work
starts, then in `Open`. When a card is complete, record its implementation and
validation notes in the commit that finishes it, delete the card, and add one
line to the completed index below. Full card text stays in Git history.

This repository uses `/` as its work tree on managed installations. The board
therefore lives under `/usr/local/share/agentoo/kanban` as
passive development documentation, outside configuration fragments and executable
paths. No installer or configuration tool should consume cards as instructions
or apply them automatically. Tracking a card does not authorize its implementation.

## Completed

To read a removed card, find the commit that deleted it and show the file from
that commit's parent:

```sh
path=usr/local/share/agentoo/kanban/Completed/018-host-firmware-savedconfig.md
git show "$(git log -1 --format=%H --diff-filter=D -- "$path")^:$path"
```

- 001 Consolidate the installer into agentoo (`001-consolidate-installer.md`)
- 002 Establish minimal systemd policy during installation (`002-minimal-systemd-initial-policy.md`)
- 003 Clarify time readiness in early-boot diagnostics (`003-investigate-time-synchronization.md`)
- 007 Installer and post-boot simplification (`007-installer-postboot-simplification.md`)
- 009 Prefer binary packages and require an explicit installation target (`009-installer-defaults.md`)
- 010 Explore Proton CLI access for installation secrets (`010-proton-install-secrets.md`)
- 011 Refactor permissions policy to support recursive definitions (`011-recursive-permissions-policy.md`)
- 012 Build a minimal Hyprland base on a physical target (`012-minimal-hyprland-base.md`)
- 014 Establish the single binary kernel baseline (`014-single-binary-kernel-baseline.md`)
- 015 Develop the kernel configuration and rebuild workflow (`015-shared-kernel-configuration-workflow.md`)
- 016 Reduce kernel code using test and usage evidence (`016-kernel-reduction-and-evidence.md`)
- 018 Trim installed firmware through host selected savedconfig (`018-host-firmware-savedconfig.md`)
- 019 Make Hyprland media and system function keys work (`019-hyprland-media-system-keys.md`)
- 021 Restructure the Agentoo CLI and establish durable command conventions (`021-cli-restructure-and-conventions.md`)
- 022 Restore shared clipboard across Neovim, tmux, and Hyprland (`022-shared-desktop-clipboard.md`)
- 029 Improve agentoo secrets diagnostics and usability (`029-secrets-usability.md`)
- 031 Make Python host-selector parsing consistent (`031-host-selector-consistency.md`)
- 032 Simplify desktop appearance state dependencies (`032-desktop-appearance-dependencies.md`)
- 033 Base desktop conflict handling on active configuration (`033-desktop-conflict-ownership.md`)
- 034 Retire the backlight compatibility entry point (`034-retire-backlight-alias.md`)
- 035 Decide whether pCloud should manage only service-owned processes (`035-pcloud-process-scope.md`)
- 036 Keep installed kernel images and modules consistent (`036-kernel-installed-module-consistency.md`)
- 037 Preserve existing directories when installing secret files (`037-secrets-parent-directory-policy.md`)
- 038 Start the desktop after its shell environment is configured (`038-desktop-shell-startup-order.md`)
- 039 Exclude local host and boot identity from Git (`039-ignore-local-host-and-boot-identity.md`)
- 040 Use native shell and editor extensions instead of replacing vendor entry files (`040-native-shell-editor-extension-points.md`)
- 041 Resolve the active kernel baseline recipe's authority and safety (`041-kernel-manual-guide-authority.md`)
- 042 Make Neovim appearance defaults respect local overrides (`042-neovim-local-override-precedence.md`)
- 043 Preserve native file resolution in Markdown link navigation (`043-markdown-native-file-navigation.md`)
- 044 Retire inactive configuration experiments and unnecessary fallbacks (`044-retire-inactive-configuration-and-fallbacks.md`)
- 045 Investigate consolidating desktop appearance loading and transport (`045-desktop-appearance-loading.md`)
- 046 Investigate reducing the duplicated native animation model (`046-native-animation-model.md`)
- 047 Simplify single-use indirection in firmware application (`047-firmware-application-indirection.md`)
- 048 Centralize derived Portage compiler settings after host selection (`048-derived-portage-compiler-settings.md`)
