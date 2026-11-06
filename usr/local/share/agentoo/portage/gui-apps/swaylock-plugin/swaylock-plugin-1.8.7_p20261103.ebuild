# Copyright 2026 agentoo contributors
# Distributed under the terms of the GNU General Public License v2

EAPI=8

inherit meson

COMMIT="fb0eeb6fac9c7daf934c9e7468eb4eeb9f8c22ef"
DESCRIPTION="Wayland session locker with external animated backgrounds"
HOMEPAGE="https://github.com/mstoeckl/swaylock-plugin"
SRC_URI="https://github.com/mstoeckl/${PN}/archive/${COMMIT}.tar.gz -> ${P}.tar.gz"
S="${WORKDIR}/${PN}-${COMMIT}"

LICENSE="MIT"
SLOT="0"
KEYWORDS="~amd64"

DEPEND="
	>=dev-libs/wayland-1.20.0
	x11-libs/cairo
	x11-libs/libxkbcommon
	sys-libs/pam
	sys-apps/systemd
"
RDEPEND="${DEPEND}
	gui-apps/swaybg
"
BDEPEND="
	app-text/scdoc
	>=dev-libs/wayland-protocols-1.47
	>=dev-util/wayland-scanner-1.15
	virtual/pkgconfig
"

src_configure() {
	local emesonargs=(
		-Dpam=enabled
		-Dlogind=enabled
		-Dlogind-provider=systemd
		-Dgdk-pixbuf=disabled
		-Dman-pages=enabled
	)
	meson_src_configure
}
