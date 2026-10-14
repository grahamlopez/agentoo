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
