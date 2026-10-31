# Start the desktop after its shell environment is configured

Created: 2026-10-31
Status: Completed
Priority: Medium

The former `/etc/zsh/zprofile` started Hyprland
synchronously before Zsh read the user's `.zprofile`, either `zshrc`, or either
`zlogin`. Their environment changes reach the login shell only after the desktop
exits. Agentoo's own `~/.local/bin` PATH addition is in `zshrc`, so it too is late
for the initial desktop environment. The installed Zsh startup manual confirms
this order; the review did not launch or restart the live desktop.

Move startup to an appropriate later native lifecycle point and document which
personal startup files affect the desktop environment. Preserve the current
graham/UID/tty1 selection, opt-out, recovery console, and shell availability after
Hyprland exits. Avoid introducing a session manager or launch framework without
a concrete requirement.

Completed on 2026-10-31 with [card 040](040-native-shell-editor-extension-points.md).
The project-owned native `zlogin` registers a one-time `precmd` callback, after
interactive defaults load. It removes itself before checking the existing
user/UID/TTY/display/opt-out conditions and calling `start-hyprland` without
`exec`. Personal `.zlogin` runs before this first prompt too, so all personal
startup environment and the shared `.local/bin` PATH reach the desktop.
The callback is required by this native lifecycle ordering; no new session
manager, restart loop, or copied user configuration was introduced. GUI and
shell/editor guidance describe the resulting behavior and package ownership.

Validation: all eight tests in `test_shell_editors.py` passed without skips.
Native Zsh runs against disposable personal startup files and a fake launcher;
tests verify all three personal environment stages, shared PATH, editor override,
user/UID/TTY/display and late personal opt-out gates, no launch for non-login or
noninteractive shells, and continued prompts without retries after launcher
failure or absence. Only the fixture UID and launcher path are substituted.
Native headless editor tests cover the paired ownership change. Zsh syntax
checks and `git diff --check` passed. No live desktop was started or reloaded.
