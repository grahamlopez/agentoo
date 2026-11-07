# Copyright 2026 agentoo contributors
# Distributed under the terms of the GNU General Public License v2

EAPI=8

DESCRIPTION="Dependencies for the user-managed, self-updating Herdr desktop app"
HOMEPAGE="https://herdr.dev https://github.com/herdrdev/herdr-app"
LICENSE="metapackage"
SLOT="0"
KEYWORDS="~amd64 ~arm64"

# Inspected official Linux 0.1.13 releases on both architectures. Vulkan needs
# a working driver supplied by the host's graphics configuration.
RDEPEND="
	>=sys-libs/glibc-2.35
	sys-devel/gcc
	app-misc/ca-certificates
	app-arch/tar
	app-arch/gzip
	net-misc/curl
	dev-libs/wayland
	media-libs/fontconfig
	media-libs/freetype
	media-libs/vulkan-loader
	x11-libs/libxcb
	x11-libs/libxkbcommon[X]
	x11-misc/xdg-utils
	dev-util/desktop-file-utils
"

S="${WORKDIR}"

src_unpack() { :; }
src_prepare() { eapply_user; }
src_configure() { :; }
src_compile() { :; }
src_install() { :; }

pkg_postinst() {
	elog "This package supplies dependencies; install Herdr as your normal user:"
	elog "  curl -fsSL https://releases.herdr.dev/app/install.sh | sh"
	elog "The installer adds the desktop entry, herdr-app, and herdr-core (hc)."
	elog 'Ensure $HOME/.local/bin is on PATH, then launch herdr-app.'
	elog "A desktop session and working Vulkan driver are required."
	elog "The app downloads updates in the background and applies them on restart."
	elog "It also manages core updates; rerun the installer to update manually."
	elog "Portage tracks prerequisites, not the installed app or core version."
}

pkg_postrm() {
	[[ -n ${REPLACED_BY_VERSION} ]] && return

	elog "Your user-installed Herdr app, core, and data have not been removed."
	elog "Remove the user installation before depcleaning its prerequisites."
	elog "Quit the app and review running core terminals before removing the core."
}
