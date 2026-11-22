# agentoo Portage overlay

Local Portage overlay inheriting Gentoo. Tracked `/etc/portage/repos.conf/agentoo.conf`
points to `/usr/local/share/agentoo/portage` (`auto-sync = no`); updates arrive
through `agentoo git pull`, not `emerge --sync`. Check recognition with
`portageq get_repo_path / agentoo`.

## Where package documentation lives

Do not add per-package essays here. Every package's documentation lives in its
native Portage location so it stays beside the recipe and surfaces through
standard Gentoo tools:

- **USE flags & descriptions:** `equery uses <category/pkg>` (reads `metadata.xml`
  in the package directory).
- **Install & runtime usage:** printed by `emerge` via `pkg_postinst`/`pkg_postrm`
  (inspect directly in the `.ebuild`), plus `files/README.gentoo` (installed to
  `/usr/share/doc/<PF>/README.gentoo`) for packages with longer setup notes.
- **Maintainer version-bump checklists:** `# Bump:` header comments at the top
  of each `*.ebuild`.

## Host profiles

The overlay supplies `agentoo:hosts/{generic,qemu,flattop,startop,thinktop,bequiet}`
in `profiles/profiles.desc`. They inherit Gentoo's AMD64 23.0 desktop/systemd
baseline, `agentoo:common`, and hardware parents (`hardware/intel-laptop`) where
needed. Unstarred profile `packages` entries belong to `@profile` (part of
`@world`). See [host selection](../../../../../etc/agentoo/README.md#host-selection).

## Packaging conventions

- **Opt-in by default:** Packages are installed explicitly unless selected by a
  set under `/etc/portage/sets/` or a host profile. Shared testing keywords live
  in `/etc/portage/package.accept_keywords/common`.
- **Clean ownership:** Portage owns system files and updates; ebuild phases
  never run vendor installers, authenticate, start services, or touch `$HOME`.
  Unmerging preserves user data.
- **Pinned artifacts:** Binary recipes use versioned, checksummed URLs recorded
  in `Manifest` (never mutable `latest` URLs); distfiles stay out of Git.
- **`-deps` vs. `-bin`:** Fast-moving AI CLIs use `*-deps` metapackages for
  system prerequisites while users install/update the upstream client in
  `~/.local/bin`. Repackaged desktop apps (`*-bin`) disable native self-updaters
  so Portage owns upgrades.

## Package catalog

| Package(s) | Purpose |
| --- | --- |
| `sys-kernel/agentoo-initramfs` | Private static BusyBox and embedded early-boot archive generator (`@kernel-dev`, [initramfs guide](../docs/initramfs.md)) |
| `app-misc/keyd`, `acct-group/keyd` | System-wide key remapping daemon (`@gui-desktop`; shared map in `/etc/keyd/default.conf`) |
| `app-nvim/softlock` | Live `git-r3` Neovim encryption plugin (`@terminal-env`, [shell-editors guide](../docs/shell-editors.md)) |
| `app-admin/proton-pass-cli-bin` | Official Proton Pass CLI (`pass-cli`) |
| `net-misc/proton-drive-cli-bin` | Official Proton Drive CLI ([README.gentoo](net-misc/proton-drive-cli-bin/files/README.gentoo)) |
| `net-misc/pcloud-drive-bin` | Official pCloud Drive AppImage ([README.gentoo](net-misc/pcloud-drive-bin/files/README.gentoo); `agentoo cloud-storage pcloud --help`) |
| `net-misc/amazon-dcv-client-bin` | Official Amazon DCV remote desktop viewer (`dcvviewer`) |
| `net-misc/teleport-tsh-bin` | Official Teleport Community `tsh` client and shell completions |
| `www-client/prisma-browser-bin` | Official Prisma Access Browser enterprise binary ([README.gentoo](www-client/prisma-browser-bin/files/README.gentoo)) |
| `dev-util/{codex-cli,claude-code,antigravity-cli,pi-coding-agent,herdr-app}-deps` | Prerequisite metapackages for user-managed AI/dev tools |
| `dev-util/antigravity-bin`, `app-misc/chatgpt-desktop-bin`, `dev-util/thinkrail-bin` | Official AI desktop binaries (self-updaters disabled) |
| `media-fonts/{ubuntu-sans-mono,ubuntu-mono,jetbrains-mono,fira-code,liberation-mono}-nerd` | Pinned Nerd Font families via `agentoo-nerd-font.eclass` (`normal`/`mono`/`proportional` USE) |
| `games-misc/{cbonsai,cbonsai-enhanced,asciiquarium,asciiquarium-redux,csakura,neo,lavat}`, `app-misc/ttfx` | Optional terminal animations and text effects (plus Perl/Python animation deps) |
