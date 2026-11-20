# Copyright 2026 agentoo contributors
# Distributed under the terms of the GNU General Public License v2

EAPI=8

inherit desktop optfeature unpacker xdg

MY_BUILD="4731201358004224"

DESCRIPTION="Google Antigravity agentic desktop application (official binary)"
HOMEPAGE="https://antigravity.google"
SRC_URI="https://storage.googleapis.com/antigravity-public/antigravity-hub/${PV}-${MY_BUILD}/linux-x64/Antigravity.deb -> ${P}-amd64.deb"
S="${WORKDIR}"

LICENSE="all-rights-reserved"
SLOT="0"
KEYWORDS="~amd64"
IUSE="+notifications portal"
RESTRICT="bindist mirror strip"
QA_PREBUILT="opt/antigravity/*"

RDEPEND="
	notifications? ( x11-libs/libnotify )
	portal? ( sys-apps/xdg-desktop-portal )
	app-accessibility/at-spi2-core:2
	app-misc/ca-certificates
	dev-libs/expat
	dev-libs/glib:2
	dev-libs/nspr
	dev-libs/nss
	dev-vcs/git
	media-libs/alsa-lib
	media-libs/libglvnd
	media-libs/mesa
	net-print/cups
	sys-apps/dbus
	sys-devel/gcc
	>=sys-libs/glibc-2.26
	virtual/udev
	x11-libs/cairo
	x11-libs/gdk-pixbuf:2
	x11-libs/gtk+:3
	x11-libs/libdrm
	x11-libs/libX11
	x11-libs/libxcb
	x11-libs/libXcomposite
	x11-libs/libXdamage
	x11-libs/libXext
	x11-libs/libXfixes
	x11-libs/libxkbcommon
	x11-libs/libXrandr
	x11-libs/pango
	x11-misc/xdg-utils
"

src_prepare() {
	default

	# Portage owns application updates; disable Electron's built-in updater feed
	# and drop the Debian-specific AppArmor profile.
	rm opt/Antigravity/resources/app-update.yml \
		opt/Antigravity/resources/apparmor-profile || die

	sed -i 's|^Exec=.*|Exec=antigravity %U|' \
		usr/share/applications/antigravity.desktop || die
}

src_install() {
	# Keep upstream layout and bundled language_server/MCP resources intact.
	# Do not execute Debian maintainer scripts or install AppArmor profiles.
	dodir /opt/antigravity
	cp -a opt/Antigravity/. "${ED}/opt/antigravity/" || die
	fperms 0755 /opt/antigravity/chrome-sandbox
	dosym ../../opt/antigravity/antigravity /usr/bin/antigravity

	domenu usr/share/applications/antigravity.desktop
	doicon -s 512 usr/share/icons/hicolor/512x512/apps/antigravity.png
}

pkg_postinst() {
	xdg_pkg_postinst
	elog "Launch antigravity as your normal user and sign in. Gentoo is not supported upstream."
	elog "Update through Portage; native desktop self-updates are disabled."
	elog "Removing this package preserves all user data."
	elog "Sandboxing requires unprivileged user namespaces; do not use --no-sandbox."
	elog "Native Wayland is optional: antigravity --ozone-platform=wayland"
	optfeature "XWayland support (upstream's default in Wayland sessions)" x11-base/xwayland
	optfeature "credential storage via Secret Service (needs a running provider)" app-crypt/libsecret
	if use portal; then
		optfeature "Hyprland desktop portal backend" gui-libs/xdg-desktop-portal-hyprland
	else
		elog "USE=portal supplies desktop portals for screen sharing and portal integration."
	fi
	if ! use notifications; then
		elog "USE=notifications supplies libnotify and a notification daemon."
	fi
}
