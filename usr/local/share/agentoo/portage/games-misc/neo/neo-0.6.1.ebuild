# Copyright 2026 agentoo contributors
# Distributed under the terms of the GNU General Public License v2

EAPI=8

inherit autotools

DESCRIPTION="Matrix digital rain with Unicode and truecolor support"
HOMEPAGE="https://github.com/st3w/neo"
SRC_URI="https://github.com/st3w/neo/archive/refs/tags/v${PV}.tar.gz -> ${P}.tar.gz"

LICENSE="GPL-3+"

SLOT="0"
KEYWORDS="~amd64 ~arm64"

DEPEND="sys-libs/ncurses:=[unicode(+)]"
RDEPEND="${DEPEND}"

src_prepare() {
	default
	eautoreconf
}

src_install() {
	default
	dodoc doc/NEWS
}
