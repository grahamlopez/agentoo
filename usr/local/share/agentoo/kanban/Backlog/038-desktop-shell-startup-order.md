# Start the desktop after its shell environment is configured

Created: 2026-10-31
Status: Backlog
Priority: Medium

[The system zprofile](../../../../../../etc/zsh/zprofile) starts Hyprland
synchronously before Zsh reads the user's `.zprofile`, either `zshrc`, or either
`zlogin`. Their environment changes reach the login shell only after the desktop
exits. Agentoo's own `~/.local/bin` PATH addition is in `zshrc`, so it too is late
for the initial desktop environment. The installed Zsh startup manual confirms
this order; the review did not launch or restart the live desktop.

Move startup to an appropriate later native lifecycle point and document which
personal startup files affect the desktop environment. Preserve the current
graham/UID/tty1 selection, opt-out, recovery console, and shell availability after
Hyprland exits. Avoid introducing a session manager or launch framework without
a concrete requirement.

Complete when shared and supported personal environment overrides are evaluated
before desktop launch. Verify ordering with a disposable shell/launcher harness,
including the PATH addition, personal variables, opt-out, other TTYs/users, and
launcher failure. Update [GUI guidance](../../docs/gui-base.md).
Coordinate with [card 040](040-native-shell-editor-extension-points.md) so the
solution also respects package ownership.
