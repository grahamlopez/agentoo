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

## Codex CLI and Claude Code

`dev-util/codex-cli-bin` (0.162.1) and `dev-util/claude-code-bin` (2.1.287,
upstream's stable channel at packaging time) install the official native Linux
releases for amd64 and arm64. Both are selected by `@early_install`, with testing
keywords accepted in agentoo's common configuration. Claude is proprietary:
its ebuild uses `all-rights-reserved` and restricts mirroring and binary
redistribution. Agentoo already accepts all licenses in its common make.conf;
on other systems explicitly accept that license for this package after reviewing
[Anthropic's terms](https://www.anthropic.com/legal/commercial-terms).

For just these clients and their dependencies, after enabling the overlay:

```sh
emerge --ask dev-util/codex-cli-bin dev-util/claude-code-bin
```

The installer does not emerge the entire `@early_install` set automatically;
its kernel phase deliberately uses an explicit package list. Install these
clients in the configured target once the Portage foundation is ready, or after
first boot. They can be installed before creating a normal user account. No
login, home-directory initialization, npm command, or vendor installer runs
while emerging either package.

### System binaries, per-user state

Codex preserves its complete upstream package under `/opt/codex`, with
`/usr/bin/codex` pointing to its entrypoint. The package includes the code-mode
host, package marker, private ripgrep and bubblewrap, Zsh, and voice resources.
Preserving the layout allows the client to locate companion tools correctly.

Claude installs its executable under `/opt/claude-code`; `/usr/bin/claude` is a
small launcher that sets `DISABLE_UPDATES=1` before executing it. This blocks
both background and manual upstream updates; use Portage for version changes.
Do not run `claude install` to initialize a user: running `claude` is sufficient.
See the [upstream update controls](https://code.claude.com/docs/en/env-vars).

Launch either command as the account that will use it. Codex stores user state
under `~/.codex` (or `CODEX_HOME`); Claude uses `~/.claude` and `~/.claude.json`
(or its `CLAUDE_CONFIG_DIR` override). Each user signs in separately. A root
session uses root's home and credentials; nothing is copied to other users.
Existing user installations in `~/.local/bin` or npm directories can shadow the
system commands: check `command -v codex` and `command -v claude`.

### Early-install dependencies

| Package | Declared runtime dependencies | Included upstream |
| --- | --- | --- |
| Codex | glibc >= 2.38, ncurses with tinfo, GCC runtime provider on arm64, CA certificates, Bash, Git | Native CLI and code-mode host, ripgrep, bubblewrap, Zsh, voice libraries |
| Claude | glibc >= 2.26, CA certificates, Bash, Git, qrencode for phone login; bubblewrap and socat with the default `sandbox` USE flag | Native runtime and ripgrep |

The glibc floors and library dependencies were checked against **both** downloaded
architectures. Codex's main executable is static, but its bundled Zsh needs
glibc 2.38 and `libtinfo.so.6`; its arm64 voice host also needs `libgcc_s.so.1`.
Voice libraries remain private in the upstream layout, including their license
notices and source manifests. Voice device access still depends on the host's
audio setup and is not an early-install requirement.

No Rust compiler, Node.js, npm, Bun, Python, desktop, browser, or keyring is
required to install these binary packages. Portage's normal download/unpack
tools suffice; `curl` and `jq` from vendor installer recipes are not additional
runtime requirements. Working network access, DNS, trusted certificates, and
correct system time are needed to authenticate and make requests. A browser can
run on another machine for terminal-only login workflows.

Linux sandboxing requires kernel support for unprivileged user namespaces and
permission to create them. Installing Claude's sandbox dependencies does not
enable its sandbox; use `/sandbox` or user settings. Its optional additional
seccomp filter is not supplied by this ebuild. See
[Claude's Linux sandbox requirements](https://code.claude.com/docs/en/sandboxing).
Node.js/npm, Python, compilers, language servers, and MCP servers should be
installed when a project or integration needs them, rather than pulled into the
base system by these clients.

### Validation and version bumps

Initial packaging verified SHA-256 against GitHub release asset digests for
Codex and the versioned `manifest.json` at
`https://downloads.claude.ai/claude-code-releases/2.1.287/manifest.json` for
Claude. The thin Portage Manifests contain BLAKE2B and SHA512 for both architectures.

For each bump, fetch versioned artifacts for both architectures, verify those
upstream checksums, inspect ELF dependencies and bundled licenses, and regenerate
the Manifests. Check Codex's package layout and helper names rather than assuming
a standalone executable. Never use `latest` or `stable` URLs in `SRC_URI`, and
do not commit downloaded binaries. On Gentoo, run package QA and an actual emerge,
then check `codex --version`, `claude --version`, and sandbox operation as a
normal user. Packaging-time checks on the development host cover hashes, ELF
inspection, staged installation, shell syntax, and amd64 CLI startup; they do
not establish arm64 execution or a completed Gentoo installation.
