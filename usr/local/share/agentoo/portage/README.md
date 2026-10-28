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

## Gentoo zsh completion fix

Agentoo supplies a version-independent user patch at
`/etc/portage/patches/app-shells/gentoo-zsh-completions/emerge-profile-matching.patch`.
Portage applies it during `src_prepare` using Gentoo's normal recipe; no overlay
ebuild or additional testing keyword is needed. The upstream legacy
`world`/`system` alternative uses `_values`, whose separator matcher can insert
`amazon--` when completing `amazo`. The patch uses `_describe` with plain
matching instead, preserving the profile descriptions and package alternatives.

```sh
emerge --ask --oneshot --usepkg=n app-shells/gentoo-zsh-completions::gentoo
```

Rebuild after deploying the patch, even if the package is already installed.
If the former overlay revision was installed, Portage may propose a downgrade
to Gentoo's selected version. Open a new shell after rebuilding; completion
functions already loaded in an existing shell retain their old definitions.
Future source builds apply the patch automatically. A prebuilt binary package
does not run `src_prepare`; use `--usepkg=n` when rebuilding to apply this patch.
Review or remove the patch when upstream fixes the issue or changes the source
enough that it no longer applies. Validation reproduced the
original behavior in a clean zsh pseudo-terminal, checked prefix completion and
the second-Tab package list after patching, and staged the patched package with
Portage using Gentoo's unmodified ebuild and the user-patch directory. The source
archive matches Gentoo's Manifest.

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

## Cloud storage clients

User-facing installation, authentication, credential-store selection, updates,
and removal belong in [the cloud storage guide](../docs/cloud-storage.md).

The overlay supplies two optional first-party binary packages:

- `net-misc/proton-drive-cli-bin`: official standalone executable at
  `/usr/bin/proton-drive`, keyworded `~amd64` and `~arm64`. Bun is embedded.
  `USE=pass` supplies password-store without changing the upstream credential
  backend; libsecret remains a runtime dependency.
- `net-misc/pcloud-drive-bin`: complete amd64 AppImage at
  `/opt/pcloud/pCloud.AppImage`, with `/usr/bin/pcloud` and a menu entry/icon.
  The `appimagekit-pcloud` desktop ID matches upstream so its user integration
  shadows the system entry rather than adding a second menu item. Keep FUSE 2
  and the ELF/dlopen dependencies in the recipe. Agentoo's
  `/etc/portage/package.use/cloud-storage` enables `dev-libs/libdbusmenu[gtk3]`.

Keep both packages opt-in, with testing keywords accepted in
`/etc/portage/package.accept_keywords/common`. No package set selects them.
Portage owns system files and updates; phases must not authenticate, launch the
GUI, configure mounts/services, or modify user homes. Preserve upstream default
locations, XDG overrides, credentials, folder selection, and autostart behavior.
Syncthing and rclone remain Gentoo packages.

The repository-owned `agentoo-cloud-storage` command manages pCloud with an
on-demand transient systemd user service; the ebuild does not install or enable
a service. Keep that distinction when updating packaging. Recheck the
AppImage/AppRun/wrapper exec chain and the application's signal handling on each
version bump: service stop relies on SIGTERM reaching the main process, and
2.3.1's normal quit path ends with a self-inflicted SIGKILL. The service uses
`KillMode=mixed`, accepts that exit status, and does not restart automatically.
Per-service session environment and runtime process ownership belong to the
command, while credentials, synchronization, and user settings remain upstream.

The pCloud AppImage is deliberately installed intact. Its current vendor
launcher passes `--no-sandbox` to Electron; this packaging preserves that
behavior. Its updater checks for write access and cannot replace the root-owned
AppImage as an ordinary user. Recheck these assumptions on each version bump;
do not add an updater running as root or compete with upstream user state.

### Cloud packaging verification and updates

For Proton, use the versioned URLs and compare both architectures against the
publisher's SHA-512 values in the [release index](https://proton.me/download/drive/cli/index.html)
or [release JSON](https://proton.me/download/drive/cli/version.json). Inspect ELF
dependencies and CPU requirements again for every release. The project license
is fetched from an immutable upstream commit and installed with the binary.

For pCloud, the ebuild pins the public-link code for the inspected release. Its
`getpubzip` endpoint provides a reproducible single-file archive without using
an expiring CDN link. Compare the enclosed AppImage's SHA-256 against the
publisher's Linux installation page, check the desktop and embedded application
versions, then regenerate the Portage Manifest. If the publisher changes or
removes the linked file, fetching must fail rather than silently accept new
bytes. Find a new release link through the [Linux release notes](https://www.pcloud.com/release-notes/linux.html);
do not substitute the rotating latest-download URL. Reinspect runtime libraries,
the launcher, and the updater on every bump. Keep downloaded artifacts outside Git.

Initial validation on 2026-10-23 checked publisher hashes for both Proton
architectures and the pCloud AppImage; two independent pCloud ZIP downloads were
byte-identical. Both ebuilds passed unpack through install in an isolated Portage
configuration, including staging Proton's arm64 binary on the amd64 build host;
the latter reports expected missing arm64 system libraries on this host. The
menu entry passed desktop-file validation, and the amd64 runtime dependencies
resolved with Agentoo's keyword and USE fragments.
Proton's amd64 version/help commands passed with an isolated home. This does not
establish arm64 runtime operation or authenticated transfers. pCloud GUI login,
sync, FUSE operation, autostart, and update notifications require a user-session
check on the target desktop; they were not exercised during packaging.

## Amazon DCV remote desktop client

`net-misc/amazon-dcv-client-bin` installs the official amd64 Amazon DCV viewer
(formerly NICE DCV) under `/opt/amazon-dcv`, with the `dcvviewer` command,
Amazon DCV application-menu entry, `.dcv` file association, and `dcv:` URL handler.
It is optional; no package set selects it. The common keyword configuration
accepts its testing keyword.

```sh
emerge --ask net-misc/amazon-dcv-client-bin::agentoo
dcvviewer
```

Enter the server address supplied by the remote desktop administrator. Gentoo
is not supported upstream. On systems without Agentoo's configuration, accept
`~amd64` and the `NICE-EULA-8.4` license for this package first. Updates are
managed through Portage; installation does not connect to a server, authenticate,
enable services, or change user settings.

The recipe pins Amazon's Ubuntu 24.04 client package, preserving its private GTK,
GLib, GStreamer, codec, and CEF libraries. It requires glibc 2.39 or newer. The
unused HarfBuzz ICU bridge is omitted because it requires Ubuntu's ICU 74;
no packaged ELF links to it. The remaining external dependencies are declared,
including libxml2-compat for the older libxml2 ABI. A private library alias
`libjbig.so.0` supplies Gentoo's unversioned JBIG-KIT 2.1 library;
the dependency is pinned to its verified 2.1 subslot. The launcher uses the private
installation paths, application and GTK schemas are compiled during staging,
and the private image-loader cache is generated after installation. The host's
dconf backend is linked into the private GIO module directory.

For version bumps, use the versioned client links at <https://www.amazondcv.com/>,
verify the artifact against Amazon's published SHA-256 checksum, inspect all ELF
dependencies and plugins again, review the EULA, and regenerate the Manifest.
Keep downloaded artifacts outside Git. Recheck the omitted ICU bridge and all
launcher paths whenever upstream changes its bundle.

Initial validation checked the upstream checksum, Portage unpack through staged
installation, dependency resolution, shell syntax, and desktop-file validation.
The host lacks several declared runtime dependencies, so GUI startup and remote
connections remain to be checked after installation.

## User-managed AI clients

`dev-util/codex-cli-deps` and `dev-util/claude-code-deps` supply prerequisites
for user-owned upstream installations, with testing keywords accepted in
agentoo's common configuration. Select them explicitly; the former
`early_install` package list is now [historical reference](../docs/history/package-sets/early-install.txt).
`dev-util/pi-coding-agent-deps` supplies the same model for Pi and can be selected
separately (accept its testing keyword on your system first).

```sh
emerge --ask dev-util/codex-cli-deps dev-util/claude-code-deps
```

These dependency-only packages install no client binaries or launchers. They
print install instructions but do not run vendor installers, authenticate, or
modify user homes during any Portage phase. Package version `1` describes the
prerequisite recipe, not an upstream client version. The installer uses explicit package lists rather than the historical
`early_install` list.

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

## ChatGPT desktop

`app-misc/chatgpt-desktop-bin` repackages the official Linux `.deb` for amd64.
It is optional, with its testing keyword accepted in Agentoo's common keyword
configuration; no package set selects it. Gentoo is not supported upstream.
See the [official Linux guide](https://learn.chatgpt.com/docs/linux/linux-app).

```sh
sudo emerge --ask app-misc/chatgpt-desktop-bin
chatgpt
```

On systems without Agentoo's keyword configuration, accept
`app-misc/chatgpt-desktop-bin::agentoo ~amd64` first. The proprietary application
uses Gentoo's `all-rights-reserved` license identifier; accept that license for
this package if your local license policy requires it.

Portage owns `/opt/chatgpt`, `/usr/bin/chatgpt`, and desktop integration. The
application payload includes its bundled Codex, browser, plugins, and
other resources. Unusable Android, ARM, and musl device-module binaries are
removed. GTK is available without Qt; `USE=qt6` retains the optional Qt6 shim and
installs its dependencies. The obsolete Qt5 shim is removed. It does not replace a separately installed Codex CLI. Debian
maintainer scripts are not executed, and APT repositories, keys, and the
Debian-specific AppArmor profile are not installed. Systems enforcing AppArmor
user-namespace restrictions need a local policy for `/opt/chatgpt/ChatGPT`.
No installer or Portage phase signs in or changes user home directories.

### Optional desktop dependencies

| USE flag | Ebuild default | Dependency and tradeoff |
| --- | --- | --- |
| `notifications` | Enabled | Supplies libnotify. Gentoo also pulls in a notification daemon and notify-send selection. Disable to omit these dependencies; desktop notifications may be unavailable. |
| `portal` | Disabled | Supplies xdg-desktop-portal, whose Gentoo package requires FUSE with `suid`, JSON-GLib, and possibly libgudev. Enable for portal integration such as Wayland screen sharing; install and configure a suitable backend too. |
| `qt6` | Disabled | Retains the Qt6 integration shim and supplies Qt6 GUI/widgets. Global or profile USE settings can enable it. GTK remains available without it. |

For a smaller installation, add this to a file under
`/etc/portage/package.use/`:

```text
app-misc/chatgpt-desktop-bin -notifications -portal -qt6
```

These flags control optional runtime dependencies (and, for Qt6, its shim).
They do not rebuild the proprietary application or forcibly disable features;
already-installed libraries and desktop services may still be used. The minimal configuration was tested on Thinktop as recorded below. NSS/NSPR and the TPM
libraries remain mandatory because bundled binaries link to them directly. TPM
libraries do not imply a requirement for TPM hardware.

Update the Agentoo overlay, then update through Portage:

```sh
sudo emerge --ask --update app-misc/chatgpt-desktop-bin
```

Upstream documents Linux updates through the distribution package manager.
Do not run the app as root or use another installer to overwrite Portage files.
Removing the package preserves user settings, credentials, history, and shared
OpenAI client state:

```sh
sudo emerge --ask --unmerge app-misc/chatgpt-desktop-bin
```

Sandboxing needs unprivileged user namespaces; the dependency list supplies
bubblewrap for the bundled agent. Do not work around launch failures with
`--no-sandbox`. The default Wayland-session behavior uses XWayland when
available (install `x11-base/xwayland` for that path). For experimental native
Wayland, fully quit the app and run `chatgpt --ozone-platform=wayland`.
Use a running Secret Service provider if the app needs keyring storage; installing
`app-crypt/libsecret` alone does not start a provider. Hyprland file/screen
integration also needs a working desktop portal backend.

### Packaging validation and version bumps

The initial package is amd64 only. Its `.deb` SHA-256 was compared with the
publisher's `deb/dists/stable/main/binary-amd64/Packages` index, and its versioned
URL was checked. The Portage Manifest records BLAKE2B and SHA512 hashes. Downloads
remain in the local distfile cache, outside Git. For a new release, inspect the
control metadata, maintainer scripts, launcher, desktop entries, and ELF runtime
dependencies again; preserve bundled resources and license notices, and
regenerate the Manifest from the new artifact. Never use a mutable `latest` URL
in an ebuild. Do not add arm64 keywords without inspecting that artifact too.

The ebuild unpack, prepare, and install phases were checked in an isolated
Portage configuration, alongside dependency resolution and desktop-entry
validation. Install-phase QA reports the TPM libraries as absent on the build
host; `app-crypt/tpm2-tss` is an explicit runtime dependency supplying them.
On 2026-10-19, the user confirmed installation and desktop operation on Thinktop
with `-notifications -portal -qt6`: app launch, chat, opening a local project,
running a sandboxed agent command, and restarting with sign-in preserved.
This validates the core workflow with those USE flags disabled; it does not
establish that optional libraries or services were absent from the system.

Further desktop checks include launch from both a terminal and application
menu, browser sign-in callbacks, file dialogs, notifications, and screen sharing
when those optional features are enabled.
Test XWayland and native Wayland separately. Confirm that a separate user can
sign in independently and that unmerge removes package files while preserving
user data. Native Wayland has upstream limitations around focus, floating
windows, positioning, and shortcuts.

## Nerd Fonts

Five `media-fonts/*-nerd` packages provide Ubuntu Sans Mono, Ubuntu Mono,
JetBrains Mono, Fira Code, and Liberation Mono (Literation Mono) from pinned
upstream Nerd Fonts releases. `normal`, `mono` (default), and `proportional` USE
flags select installed variants. At least one variant is required. The shared
`agentoo-nerd-font` eclass installs only each ebuild's exact family prefix and
retains the archive's licenses; Gentoo continues to own standalone symbols.

See [font usage and diagnostics](../docs/fonts.md) for commands and selection.
These packages install fonts only, with no application configuration changes.

## Terminal animations

Seven optional `games-misc` packages provide terminal animations. Both bonsai
variants and both aquarium variants can be installed together:

| Package | Version | Command |
| --- | --- | --- |
| `games-misc/cbonsai` | 1.4.2, John Allbritten upstream | `cbonsai` |
| `games-misc/cbonsai-enhanced` | 1.4.2_p20260615, jakobrees fork | `cbonsai-enhanced` |
| `games-misc/asciiquarium` | 1.6, nothub fork | `asciiquarium` |
| `games-misc/asciiquarium-redux` | 1.5.0, cognitivegears Python rewrite | `asciiquarium-redux` |
| `games-misc/csakura` | 3.0.0 | `csakura` |
| `games-misc/neo` | 0.6.1 | `neo` |
| `games-misc/lavat` | 3.0.0 | `lavat` |

```sh
emerge --ask games-misc/cbonsai games-misc/cbonsai-enhanced \
  games-misc/asciiquarium games-misc/asciiquarium-redux \
  games-misc/csakura games-misc/neo games-misc/lavat
```

These packages are selected explicitly; no package set installs them automatically.
Agentoo's common keyword configuration accepts their testing keywords and the
three overlay dependencies: `dev-perl/Term-Animation`, `dev-python/asciimatics`,
and `dev-python/pyfiglet`. Most packages carry `~amd64` and `~arm64` keywords.
Classic Asciiquarium and Term-Animation initially carry only `~amd64` because
Gentoo's `dev-perl/Curses` dependency has no arm64 keyword. On systems without
Agentoo's keyword configuration, accept the appropriate testing keywords first.

The enhanced bonsai is pinned to commit
`298bf698ad080f13fa0d051588482bab8903d988`; upstream has no release tags.
Its command, man page, Bash completion, and default cache filename use
`cbonsai-enhanced`. Its default save file is
`$XDG_CACHE_HOME/cbonsai-enhanced` or `~/.cache/cbonsai-enhanced`, separate from
the classic tree. Upstream's documentation uses the original `cbonsai` name;
substitute `cbonsai-enhanced` when following the fork's examples.

Redux exports only `asciiquarium-redux`; its conflicting `asciiquarium` alias
is omitted. It installs example TOML configurations under
`/usr/share/doc/asciiquarium-redux-1.5.0/`. The terminal backend is available
by default; `USE=tk` enables the optional Tk backend's Python dependency.
For an explicit terminal session, run `asciiquarium-redux --backend terminal`.

Use a UTF-8 locale and a terminal font with the required glyphs. `cbonsai -l`
and `cbonsai-enhanced -l` animate tree growth; `csakura -t` preserves terminal
transparency, and `lavat -G` enables gravity and buoyancy. Press `q` to quit
these animations. `csakura` and `lavat` document options with `-h`.

`app-misc/no-more-secrets` remains supplied by Gentoo; install it separately
and accept its testing keyword if needed. This overlay does not duplicate it.

All ten overlay recipes passed Portage build and staged-install phases on
amd64 with Python 3.14 on 2026-10-21. Dependency resolution succeeded for all
seven applications together. Each application rendered in a pseudo-terminal
and exited successfully with `q`; staged file checks found no collisions.
The asciimatics upstream suite also passed (199 tests, 40 skipped).
The checks used isolated build and dependency images, without merging packages
into the running system. Arm64 and the optional Tk GUI were not runtime-tested.
