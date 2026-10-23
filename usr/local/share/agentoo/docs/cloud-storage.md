# Cloud storage

The optional packages below install upstream clients only. Portage owns their
system files and updates; authentication, folder selection, autostart, and all
configuration and user state remain under the applications' native ownership.
No package set installs them automatically. `agentoo cloud-storage pcloud`
manages the desktop process through a systemd user service; folder sync and the
virtual drive remain pCloud features. User configuration and state stay
untracked in their native locations. Syncthing and rclone remain Gentoo packages.

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

`pass` is optional: terminal commands can use the default Secret Service backend
when it is available and unlocked. The `pass` backend means the local GPG-based
password-store program, not Proton Pass or `pass-cli`. It stores Drive's
authenticated session; Proton Pass CLI is not an upstream-supported replacement
for that credential backend.

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
agentoo cloud-storage pcloud start
```

Sign in and select local folders in pCloud's GUI. This is the full desktop
application, including its virtual drive: FUSE is an upstream requirement even
when the intended workflow is local-folder Sync. The ebuild supplies FUSE 2;
the running kernel and session must provide access to `/dev/fuse`. No Agentoo
mount setup is involved. See [pCloud's Linux workflow](https://www.pcloud.com/how-to-install-pcloud-drive-linux).

In 2.3.1, Add Sync's cloud-folder picker does not allow selecting the drive root.
To mirror your existing ordinary top-level folders, create an empty local
counterpart for each and add a separate sync pair, for example
`~/pCloud-local/Documents` with cloud `/Documents`. pCloud downloads the nested
contents; you do not need to recreate that tree manually. Use an ordinary local
directory outside the virtual `~/pCloudDrive` mount. New cloud top-level folders
need their own sync pairs, and files stored directly at the cloud root are not
covered by these pairs.

Agentoo's `package.use/cloud-storage` enables the required `gtk3` support in
`dev-libs/libdbusmenu`; enable that flag yourself when using only the overlay
outside a managed Agentoo system.

The AppImage retains its own launcher, bundled libraries, desktop integration,
settings, and autostart behavior. In this release the vendor launcher explicitly
passes `--no-sandbox` to Electron; the package preserves that upstream behavior.
Portage phases never launch the GUI or write to user homes. On first launch,
pCloud may create its normal user desktop/autostart files and configuration.

### Access the virtual drive at another path

The official 2.3.1 Linux client sets its mount location to `~/pCloudDrive` at
startup; changing the internal `fsroot` setting does not persist across starts.
For a different access path, create a local symlink, for example:

```sh
mkdir -p "$HOME/Cloud"
ln -sT -- "$HOME/pCloudDrive" "$HOME/Cloud/pcloud"
```

Choose a link path that does not already exist. The actual mount remains at
`~/pCloudDrive`; keep that directory in place. The symlink does not create a
local copy or make cloud files available after the virtual drive is unmounted.

### Start, stop, and status

Run these as your desktop user, without sudo:

```sh
agentoo cloud-storage pcloud start
agentoo cloud-storage pcloud status
agentoo cloud-storage pcloud stop
```

Start creates the transient systemd user service `agentoo-pcloud.service` and
returns to your prompt. No backgrounding or disowning is needed; terminal
closure does not stop the service. Repeating start leaves an active service
alone. The service is collected after exit and is recreated on the next start;
it is not enabled at login and does not restart after you quit pCloud.

Start from a graphical-session terminal. The command passes its display,
D-Bus, locale, and XDG overrides to this service without changing the user
manager's global environment. Stop and status also work from a TTY or SSH
session with access to your systemd user manager. Starting confirms execution
of the process, not successful authentication, mounting, or completed sync.

Disable **Start pCloud Drive on system startup** in pCloud's own settings when
using service management. The application menu entry still runs the native
client directly. If pCloud is already running outside the service, start
reports that rather than launching another copy. Run stop once, then start, to
switch an existing manually launched AppImage to service management. Stop
recognizes only your normal AppImage main processes, not renderer helpers or
other users' instances.

The packaged 2.3.1 client handles `SIGTERM` by invoking its application quit
path, as the tray's Quit action does. Closing the window alone keeps it running.
The service sends this signal to the main process first, with a 30-second stop
timeout and systemd cleanup of remaining processes. For an unmanaged AppImage,
the command uses a PID file descriptor to signal the main process and wait for
exit; it reports a timeout without force-killing that process.

Wait for transfers to finish in the app before quitting: neither the upstream
quit path nor this command waits for the upload queue to drain. pCloud's
upstream quit handler ultimately sends itself `SIGKILL`; the service accepts
that exit status so an ordinary quit is not reported as a service failure.

Inspect service startup and shutdown diagnostics with:

```sh
journalctl --user -u agentoo-pcloud.service -b
```

Omitting the provider (`agentoo cloud-storage`) or action
(`agentoo cloud-storage pcloud`) shows help for that level and exits successfully.

Status prints whether pCloud is service-managed, running outside the service,
or stopped. Its exit status is 0 when running and 3 when stopped; operational
failures use 1 and syntax errors use 2. Help and completion perform no service
operations. No service files or process records are written to your home.

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
