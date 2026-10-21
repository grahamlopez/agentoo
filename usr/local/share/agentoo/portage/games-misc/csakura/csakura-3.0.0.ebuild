# Copyright 2026 agentoo contributors
# Distributed under the terms of the GNU General Public License v2

EAPI=8

inherit toolchain-funcs

DESCRIPTION="Procedural cherry blossom trees with drifting petals in the terminal"
HOMEPAGE="https://github.com/realstrawhat/csakura"
SRC_URI="https://github.com/realstrawhat/csakura/archive/refs/tags/v${PV}.tar.gz -> ${P}.tar.gz"

LICENSE="MIT"

SLOT="0"
KEYWORDS="~amd64 ~arm64"

DEPEND="sys-libs/ncurses:=[unicode(+)]"
RDEPEND="${DEPEND}"
BDEPEND="virtual/pkgconfig"

src_compile() {
	local curses_cflags curses_libs
	curses_cflags=$($(tc-getPKG_CONFIG) --cflags ncursesw) || die
	curses_libs=$($(tc-getPKG_CONFIG) --libs ncursesw) || die
	$(tc-getCC) ${CPPFLAGS} ${CFLAGS} -std=c99 ${curses_cflags} \
		src/csakura.c ${LDFLAGS} -o csakura ${curses_libs} -lm || die
}

src_install() {
	dobin csakura
	dodoc README.md
}
