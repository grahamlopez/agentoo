# Copyright 2026 agentoo contributors
# Distributed under the terms of the GNU General Public License v2

EAPI=8

inherit desktop xdg

DESCRIPTION="pCloud Drive desktop client (official AppImage)"
HOMEPAGE="https://www.pcloud.com/"
# Public-link content verified as 2.3.1; the Manifest pins the exact bytes.
# getpubzip supplies a reproducible archive without an expiring CDN URL.
SRC_URI="https://api.pcloud.com/getpubzip?code=XZtJmbJZp6YyRQOCSjbAwPVct6fTXJloyHhy -> ${P}-amd64.zip"
S="${WORKDIR}"

LICENSE="all-rights-reserved"
SLOT="0"
KEYWORDS="~amd64"
RESTRICT="bindist mirror strip"
QA_PREBUILT="opt/pcloud/pCloud.AppImage"

BDEPEND="app-arch/unzip"
RDEPEND="
	>=sys-libs/glibc-2.29
	app-accessibility/at-spi2-core:2
	app-misc/ca-certificates
	app-shells/bash
	dev-libs/dbus-glib
	dev-libs/expat
	dev-libs/glib:2
	dev-libs/libdbusmenu[gtk3]
	dev-libs/nspr
	dev-libs/nss
	media-libs/alsa-lib
	media-libs/libglvnd
	media-libs/mesa
	net-print/cups
	sys-apps/dbus
	sys-devel/gcc
	sys-fs/fuse:0
	virtual/udev
	virtual/zlib
	x11-libs/cairo
	x11-libs/gdk-pixbuf:2
	x11-libs/gtk+:3
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

src_unpack() {
	default
	chmod +x pCloud.AppImage || die
	# Extract only to obtain the vendor's icon and license notices. Like Gentoo's
	# Joplin recipe, this uses the AppImage runtime without mounting or launching it.
	./pCloud.AppImage --appimage-extract >/dev/null || die
}

src_install() {
	# Preserve the complete upstream layout and launcher behavior.
	exeinto /opt/pcloud
	doexe pCloud.AppImage
	dosym ../../opt/pcloud/pCloud.AppImage /usr/bin/pcloud

	# Match the upstream desktop ID so its user integration shadows this entry
	# instead of creating a second application-menu item.
	newmenu "${FILESDIR}/appimagekit-pcloud.desktop" appimagekit-pcloud.desktop
	newicon squashfs-root/pcloud.png appimagekit-pcloud.png
	dodoc squashfs-root/LICENSE.electron.txt squashfs-root/LICENSES.chromium.html
}

pkg_postinst() {
	xdg_pkg_postinst
	elog "Run pcloud as your normal user and configure folders in its GUI."
	elog "The upstream AppImage and virtual drive require working FUSE (/dev/fuse)."
	elog "Update through Portage; the in-app updater cannot replace this system-owned AppImage."
	elog "Removing this package preserves user settings, sessions, and synchronized files."
}
