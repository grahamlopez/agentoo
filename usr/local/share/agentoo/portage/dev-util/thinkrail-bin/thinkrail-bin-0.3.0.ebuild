# Copyright 2026 agentoo contributors
# Distributed under the terms of the GNU General Public License v2

EAPI=8

inherit desktop unpacker xdg

DESCRIPTION="ThinkRail agentic IDE (official desktop binary)"
HOMEPAGE="https://thinkrail.ai https://github.com/JetBrains/thinkrail"
SRC_URI="
	amd64? ( https://github.com/JetBrains/thinkrail/releases/download/v${PV}/stable-linux-x64-ThinkRail-${PV}.tar.zst )
	arm64? ( https://github.com/JetBrains/thinkrail/releases/download/v${PV}/stable-linux-arm64-ThinkRail-${PV}.tar.zst )
	https://raw.githubusercontent.com/JetBrains/thinkrail/v${PV}/LICENSE -> ${P}-LICENSE
	https://raw.githubusercontent.com/oven-sh/bun/bun-v1.4.4/LICENSE.md -> ${P}-Bun-LICENSE.md
"
S="${WORKDIR}/ThinkRail"

# Includes Electrobun, Bun and its statically linked libraries, and bundled fonts.
LICENSE="Apache-2.0 Apache-2.0-with-LLVM-exceptions BSD BSD-2 IJG LGPL-2 LGPL-2.1+ MIT openssl OFL-1.1 ZLIB"
SLOT="0"
KEYWORDS="~amd64 ~arm64"
RESTRICT="mirror strip"
QA_PREBUILT="opt/thinkrail/*"

BDEPEND="app-arch/zstd"
RDEPEND="
	app-misc/ca-certificates
	dev-libs/glib:2
	dev-libs/libayatana-appindicator
	dev-vcs/git
	gnome-base/librsvg:2
	net-libs/libsoup:3.0
	net-libs/webkit-gtk:4.1
	sys-devel/gcc
	>=sys-libs/glibc-2.38
	x11-libs/cairo
	x11-libs/gdk-pixbuf:2
	x11-libs/gtk+:3
	x11-misc/xdg-utils
"

src_prepare() {
	default

	# A valid HTTPS feed enables native updates. Portage owns this installation.
	sed -i 's|https://github.com/JetBrains/thinkrail/releases/download/desktop-updates||' \
		Resources/version.json || die
	sed -i -e 's|^Exec=.*|Exec=thinkrail|' \
		-e 's|^Icon=.*|Icon=thinkrail|' \
		-e 's|^Comment=.*|Comment=Agentic development environment|' \
		-e 's|^Categories=.*|Categories=Development;IDE;|' ThinkRail.desktop || die

	rm Resources/app/runtime/macos-trash Resources/app/runtime/windows-trash.exe || die
}

src_install() {
	dodir /opt/thinkrail
	cp -a bin Resources "${ED}/opt/thinkrail/" || die
	dosym ../../opt/thinkrail/bin/launcher /usr/bin/thinkrail
	newmenu ThinkRail.desktop thinkrail.desktop
	newicon Resources/appIcon.png thinkrail.png
	newdoc "${DISTDIR}/${P}-LICENSE" LICENSE
	newdoc "${DISTDIR}/${P}-Bun-LICENSE.md" Bun-LICENSE.md
}

pkg_postinst() {
	xdg_pkg_postinst
	elog "Launch thinkrail as your normal user and connect a model provider."
	elog "Update through Portage; native self-updates are disabled."
}
