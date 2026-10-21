# Copyright 2026 agentoo contributors
# Distributed under the terms of the GNU General Public License v2

EAPI=8

inherit toolchain-funcs

DESCRIPTION="Lava lamp simulation using metaballs in the terminal"
HOMEPAGE="https://github.com/AngelJumbo/lavat"
SRC_URI="https://github.com/AngelJumbo/lavat/archive/refs/tags/v${PV}.tar.gz -> ${P}.tar.gz"

LICENSE="MIT"

SLOT="0"
KEYWORDS="~amd64 ~arm64"

src_compile() {
	# Upstream's makefile omits user flags and libm.
	$(tc-getCC) ${CPPFLAGS} ${CFLAGS} lavat.c ${LDFLAGS} -o lavat -lm || die
}

src_install() {
	dobin lavat
	dodoc README.md
}
