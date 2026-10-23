# Cloud storage

The optional packages below install upstream clients only. Portage owns their
system files and updates; authentication, folder selection, autostart, and all
configuration and user state remain under the applications' native ownership.
No package set installs them automatically, and no Agentoo storage command,
service, mount configuration, or home-file deployment is added. Syncthing and
rclone remain Gentoo packages.

## Proton Drive CLI

`net-misc/proton-drive-cli-bin` installs the official 0.9.0 standalone binary as
`/usr/bin/proton-drive`, with `~amd64` and `~arm64` keywords accepted by Agentoo.
The binary embeds Bun; a separate Bun, Node.js, or npm installation is not needed.

```sh
sudo emerge --ask net-misc/proton-drive-cli-bin
proton-drive version
proton-drive auth login
```

Run authentication as your normal user. Sign-in uses your browser. The default
credential backend uses libsecret and needs a running Secret Service provider;
installing the library alone does not supply or start that service. Existing
user configuration, XDG overrides, and credential-store behavior are preserved.

For a terminal-oriented alternative, enable `USE=pass` for this package to
install `app-admin/pass`, initialize pass with your own GPG key, then select the
upstream backend explicitly in your shell:

```sh
export PROTON_DRIVE_CREDENTIALS_STORE=pass
proton-drive auth login
```

The USE flag only supplies the dependency; it does not select a backend, create
keys, unlock GPG, or modify shell configuration. Unattended commands need access
to the selected credential store. The standard upstream amd64 executable needs
AVX2; this package does not currently supply a baseline x64 or musl variant.

App data, cache, and logs use the native `proton-drive-cli` directories under
XDG data/cache/state locations. Sessions stay in the selected secret store.
See [upstream CLI usage and locations](https://github.com/ProtonDriveApps/sdk/blob/main/cli/README.md).

## pCloud Drive

`net-misc/pcloud-drive-bin` installs the official 2.3.1 amd64 AppImage intact at
`/opt/pcloud/pCloud.AppImage`, exposes `pcloud` on PATH, and installs a menu entry
and icon. Agentoo accepts its `~amd64` keyword. Accept this package's
`all-rights-reserved` license if your local license policy requires it.

```sh
sudo emerge --ask net-misc/pcloud-drive-bin
pcloud
```

Sign in and select local folders in pCloud's GUI. This is the full desktop
application, including its virtual drive: FUSE is an upstream requirement even
when the intended workflow is local-folder Sync. The ebuild supplies FUSE 2;
the running kernel and session must provide access to `/dev/fuse`. No Agentoo
mount setup is involved. See [pCloud's Linux workflow](https://www.pcloud.com/how-to-install-pcloud-drive-linux).

Agentoo's `package.use/cloud-storage` enables the required `gtk3` support in
`dev-libs/libdbusmenu`; enable that flag yourself when using only the overlay
outside a managed Agentoo system.

The AppImage retains its own launcher, bundled libraries, desktop integration,
settings, and autostart behavior. In this release the vendor launcher explicitly
passes `--no-sandbox` to Electron; the package preserves that upstream behavior.
Portage phases never launch the GUI or write to user homes. On first launch,
pCloud may create its normal user desktop/autostart files and configuration.

## Updates and removal

Update by updating the Agentoo repository and emerging the package again:

```sh
sudo emerge --ask --update net-misc/proton-drive-cli-bin net-misc/pcloud-drive-bin
```

pCloud's in-app updater cannot replace the root-owned AppImage and its containing
directory; use Portage rather than running the updater or application as root.
Upstream update notifications are retained. Unmerging either package leaves
user configuration, credentials, local synchronized files, and cloud data intact.
It also leaves application-created user launchers; disable pCloud autostart in
its settings before uninstalling if enabled.

For artifact verification, dependency inspection, and version bumps, see the
[overlay maintenance notes](../portage/README.md#cloud-storage-clients).
