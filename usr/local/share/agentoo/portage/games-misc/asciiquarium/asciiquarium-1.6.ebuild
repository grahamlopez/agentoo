# Copyright 2026 agentoo contributors
# Distributed under the terms of the GNU General Public License v2

EAPI=8

DESCRIPTION="Animated terminal aquarium with transparency and interactive creatures"
HOMEPAGE="https://github.com/nothub/asciiquarium"
SRC_URI="https://github.com/nothub/asciiquarium/archive/refs/tags/v${PV}.tar.gz -> ${P}.tar.gz"

LICENSE="GPL-2+"

SLOT="0"
KEYWORDS="~amd64"

RDEPEND="dev-lang/perl
	dev-perl/Curses
	>=dev-perl/Term-Animation-2.0"

src_install() {
	dobin asciiquarium
	dodoc README.md CHANGES.txt
}
