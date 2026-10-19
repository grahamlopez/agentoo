# Copyright 2026 agentoo contributors
# Distributed under the terms of the GNU General Public License v2

EAPI=8

inherit desktop optfeature unpacker xdg

DESCRIPTION="ChatGPT desktop by OpenAI (official binary)"
HOMEPAGE="https://learn.chatgpt.com/docs/linux/linux-app"
SRC_URI="https://persistent.oaistatic.com/codex-app-prod/linux/deb/pool/main/c/chatgpt/chatgpt_${PV}_amd64.deb -> ${P}-amd64.deb"
S="${WORKDIR}"

LICENSE="all-rights-reserved"
SLOT="0"
KEYWORDS="~amd64"
IUSE="+notifications portal qt6"
RESTRICT="bindist mirror strip"
QA_PREBUILT="opt/chatgpt/*"

RDEPEND="
	notifications? ( x11-libs/libnotify )
	portal? ( sys-apps/xdg-desktop-portal )
	qt6? ( dev-qt/qtbase:6[gui,widgets] )
	app-accessibility/at-spi2-core:2
	app-crypt/tpm2-tss
	app-misc/ca-certificates
	app-shells/bash
	dev-libs/expat
	dev-libs/glib:2
	dev-libs/libusb:1
	dev-libs/nspr
	dev-libs/nss
	dev-libs/openssl:0/3
	dev-vcs/git
	media-libs/alsa-lib
	media-libs/libglvnd
	media-libs/mesa
	net-print/cups
	sys-apps/bubblewrap
	sys-apps/dbus
	sys-devel/gcc
	>=sys-libs/glibc-2.30
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

	# Electron can use GTK; Qt integration is optional. Qt5 is obsolete here.
	rm usr/lib/chatgpt/libqt5_shim.so || die
	use qt6 || rm usr/lib/chatgpt/libqt6_shim.so || die

	# The vendor's device modules include Android, ARM and musl prebuilds.
	# Keep only amd64/glibc variants on this amd64/glibc package.
	local modules=usr/lib/chatgpt/resources/app.asar.unpacked/node_modules
	local device="${modules}/@worklouder/device-kit-oai/node_modules/@worklouder/wl-device-kit/node_modules"
	rm -r "${device}/node-hid/prebuilds/"*arm* \
		"${device}/node-hid/prebuilds/"*musl \
		"${device}/serialport/node_modules/@serialport/bindings-cpp/prebuilds/"android-* \
		"${device}/serialport/node_modules/@serialport/bindings-cpp/prebuilds/"linux-arm* \
		"${device}/serialport/node_modules/@serialport/bindings-cpp/prebuilds/linux-x64/node.napi.musl.node" \
		|| die
}

src_install() {
	# Keep upstream layout and bundled agent/browser resources intact.
	# Do not execute Debian maintainer scripts or install their APT integration.
	dodir /opt/chatgpt
	cp -a usr/lib/chatgpt/. "${ED}/opt/chatgpt/" || die
	dosym ../../opt/chatgpt/codex-launcher /usr/bin/chatgpt

	domenu usr/share/applications/chatgpt.desktop
	doicon usr/share/pixmaps/chatgpt.png
	insinto /usr/share/metainfo
	doins usr/share/metainfo/com.openai.chatgpt.metainfo.xml
	dodoc usr/share/doc/chatgpt/copyright
}

pkg_postinst() {
	xdg_pkg_postinst
	elog "Launch chatgpt as your normal user and sign in. Gentoo is not supported upstream."
	elog "Update through Portage. Removing this package preserves all user data."
	elog "Sandboxing requires unprivileged user namespaces; do not use --no-sandbox."
	elog "Native Wayland is experimental: chatgpt --ozone-platform=wayland"
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
