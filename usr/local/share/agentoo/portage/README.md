# agentoo Portage overlay

This local overlay inherits Gentoo. The tracked repository configuration points
to `/usr/local/share/agentoo/portage`; updates arrive through the agentoo Git
workflow, not `emerge --sync`.

## Enable the overlay

On a managed agentoo system, deploying this repository supplies both the overlay
directory and `/etc/portage/repos.conf/agentoo.conf`, which enables it
automatically. No `eselect repository enable` step is needed.

For an existing system, ensure the overlay files are present at
`/usr/local/share/agentoo/portage` and create
`/etc/portage/repos.conf/agentoo.conf` with:

```ini
[agentoo]
location = /usr/local/share/agentoo/portage
auto-sync = no
```

The Gentoo repository must also be configured because this overlay inherits it.
Check that Portage recognizes the overlay with `portageq get_repo_path / agentoo`;
it should print `/usr/local/share/agentoo/portage`.

## Keyd

`app-misc/keyd` builds the tagged upstream 2.6.0 release and installs the
system-wide remapping daemon, systemd and OpenRC services, man page, layouts,
compose data, and configuration examples. `acct-group/keyd` creates its IPC
access group through Portage. This initial package covers the core daemon;
the optional Python application mapper and GNOME extensions are not installed.

```sh
emerge --ask app-misc/keyd::agentoo
```

Both packages carry `~amd64` and `~arm64` keywords. On systems without agentoo's
keyword configuration, accept the appropriate testing keyword for both
`app-misc/keyd::agentoo` and `acct-group/keyd::agentoo` first.

Agentoo tracks `/etc/keyd/default.conf`, restored from the legacy configuration.
It applies to all keyboards: Caps Lock sends Escape when tapped and Control
when held; holding Left Alt maps H/J/K/L to the arrow keys. The `[nav:A]` layer
preserves Alt for other keys, including Alt+Tab. Adjust this file directly to
change the shared mapping.

Then run `systemctl enable --now keyd`, or on OpenRC run
`rc-update add keyd default` followed by `rc-service keyd start`.
The kernel needs evdev and uinput support (`CONFIG_INPUT_EVDEV` and
`CONFIG_INPUT_UINPUT`). Use `keyd monitor` to identify key names and
`keyd reload` after configuration edits. Members of the `keyd` group can
control the daemon through its socket; add users only when they need that
access. Installing the package does not enable the service; the tracked mapping
takes effect when the daemon starts.

## Proton Pass CLI

`app-admin/proton-pass-cli-bin` installs the official, versioned Linux binary as
`/usr/bin/pass-cli`. It does not run Proton's installer, authenticate, or install
secrets. No package set selects it automatically.

The package is initially keyworded for testing. Agentoo's managed
`/etc/portage/package.accept_keywords/common` accepts its `~amd64` and `~arm64`
keywords. Install it with:

```sh
emerge --ask app-admin/proton-pass-cli-bin
```

On a system without agentoo's keyword configuration, add
`app-admin/proton-pass-cli-bin ~amd64` (or `~arm64`) to a file in
`/etc/portage/package.accept_keywords/` first.

Update through Portage, rather than
`pass-cli update`. Upstream's notification checks can be suppressed with
`PROTON_PASS_NO_UPDATE_CHECK=1`; this does not disable an explicitly invoked
self-update command. Root ownership prevents ordinary users replacing the
binary, but does not prevent replacement by an updater running as root.

Version bumps must download both artifacts, compare SHA-256 hashes with Proton's
release manifest, inspect runtime dependencies, and regenerate the Portage
Manifest. Do not commit downloaded binaries. The download manifest is available
at <https://proton.me/download/pass-cli/versions.json>.

## User-managed AI clients

`dev-util/codex-cli-deps` and `dev-util/claude-code-deps` supply prerequisites
for user-owned upstream installations. Both are selected by `@early_install`,
with testing keywords accepted in agentoo's common configuration.
`dev-util/pi-coding-agent-deps` supplies the same model for Pi and can be selected
separately (accept its testing keyword on your system first).

```sh
emerge --ask dev-util/codex-cli-deps dev-util/claude-code-deps
```

These dependency-only packages install no client binaries or launchers. They
print install instructions but do not run vendor installers, authenticate, or
modify user homes during any Portage phase. Package version `1` describes the
prerequisite recipe, not an upstream client version. The installer does not
emerge the entire `@early_install` set automatically; its kernel phase uses an
explicit package list.

### Install and update as your normal user

Codex's [standalone installer](https://developers.openai.com/codex/cli) installs
the complete upstream package, preserving its companion tools and resources:

```sh
curl -fsSL https://chatgpt.com/codex/install.sh | sh
```

Run `codex update` to update a release that supports self-update, or rerun the
installer. The visible command defaults to `~/.local/bin/codex`; its package
cache is under `CODEX_HOME/packages/standalone` (default `~/.codex`).

For Claude, use the native installer with the stable channel:

```sh
curl -fsSL https://claude.ai/install.sh | bash -s stable
```

The native installation auto-updates; `claude update` performs a manual update.
Use `latest` instead of `stable` for releases as soon as they ship. See
[Claude's installation and update documentation](https://code.claude.com/docs/en/setup).
The default executable is `~/.local/bin/claude`, with versions under
`~/.local/share/claude`. No update-disabling launcher is installed.

Pi's [managed installer](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/quickstart.md)
pins its dependencies and supports `pi update`:

```sh
curl -fsSL https://pi.dev/install.sh | sh
```

Follow each installer's PATH instructions. Run `command -v codex`,
`command -v claude`, and the appropriate `--version` commands to verify the
user-owned installations. Each user installs and signs in separately. Codex
state lives in `~/.codex` (or `CODEX_HOME`); Claude uses `~/.claude` and
`~/.claude.json` (or its `CLAUDE_CONFIG_DIR` override).

### Migrate existing Portage installations

Install the new dependency packages first, then remove the old binaries through
Portage before running the user installers:

```sh
emerge --ask dev-util/codex-cli-deps dev-util/claude-code-deps
emerge --ask --unmerge dev-util/codex-cli-bin dev-util/claude-code-bin
```

Unmerge only the old packages you actually installed. Their removal deletes the
Portage-owned binaries and Claude's update-disabling wrapper, leaving user data
intact. Removing ebuilds from the overlay does not uninstall existing packages.
No automatic package move is declared: a rename would not create a user-owned
installation. Remove any separately configured `DISABLE_UPDATES` or
`DISABLE_AUTOUPDATER` setting if you want Claude updates enabled.

### Prerequisites and tradeoffs

Codex retains the previously inspected native package's runtime prerequisites:
glibc >= 2.38, ncurses with tinfo, and the GCC runtime provider on arm64, plus
Bash, Git, CA certificates, and curl for installation. It also supplies bubblewrap
for Linux sandboxing; Codex uses the `bwrap` executable from `PATH`. Claude retains glibc
>= 2.26, Bash, Git, CA certificates and qrencode for phone login, and adds curl
and jq for installation. Its default `sandbox` USE flag supplies bubblewrap and
socat. Neither native installer requires Node.js or npm; Pi does require Node
and npm. Future upstream releases may change these requirements, so dependency
ebuilds still need occasional maintenance.

Linux sandboxing requires unprivileged user namespaces and permission to create
them. Claude's sandbox dependencies do not enable sandboxing: use `/sandbox` or
user settings. Its optional additional seccomp filter is not supplied here. See
[Claude's sandbox requirements](https://code.claude.com/docs/en/sandboxing).
The Claude post-install message also retains the phone-login QR code instructions.

This model keeps client updates independent of overlay release bumps. Portage
tracks prerequisites rather than client versions, so client updates are not
covered by Portage binary rollback or artifact checksums. An upstream installer
also needs working network access when each user installs the client. Use
upstream version/channel controls when you need a particular release.

### Remove a user installation

Unmerging a dependency package prints copy/paste removal instructions and leaves
user files intact. The message is suppressed during upgrades, downgrades, and
reinstalls. Remove the client before depcleaning its prerequisites.

For the default Codex standalone installation:

```sh
rm -f -- "$HOME/.local/bin/codex"
rm -rf -- "${CODEX_HOME:-$HOME/.codex}/packages/standalone"
```

If `CODEX_INSTALL_DIR` was customized, remove its `codex` entry instead. For the
default Claude native installation:

```sh
rm -f -- "$HOME/.local/bin/claude"
rm -rf -- "$HOME/.local/share/claude"
```

For Pi, rerun its installer and choose **Uninstall Pi**. For npm installations,
use the corresponding `npm uninstall -g` command in the original npm environment.

These commands preserve settings and sessions. The ebuild messages separately
provide optional deletion commands for user data, including credentials and
session history. Review custom paths and other clients sharing those directories
before deleting data. Project-local configuration is preserved.

### Validation

Check shell syntax, Portage dependency metadata, and install/removal messages,
including suppression during replacement. On Gentoo, run package QA and emerge
the dependency packages, then install upstream clients as a normal user and check
versions and sandbox operation. Do not run upstream installers from Portage phases.

## Nerd Fonts

Five `media-fonts/*-nerd` packages provide Ubuntu Sans Mono, Ubuntu Mono,
JetBrains Mono, Fira Code, and Liberation Mono (Literation Mono) from pinned
upstream Nerd Fonts releases. `normal`, `mono` (default), and `proportional` USE
flags select installed variants. At least one variant is required. The shared
`agentoo-nerd-font` eclass installs only each ebuild's exact family prefix and
retains the archive's licenses; Gentoo continues to own standalone symbols.

See [font usage and diagnostics](../docs/fonts.md) for commands and selection.
These packages install fonts only, with no application configuration changes.
