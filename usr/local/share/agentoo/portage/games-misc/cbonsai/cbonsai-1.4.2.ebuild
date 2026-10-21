# Copyright 2026 agentoo contributors
# Distributed under the terms of the GNU General Public License v2

EAPI=8

inherit bash-completion-r1 toolchain-funcs

DESCRIPTION="Grow procedurally generated bonsai trees in your terminal"
HOMEPAGE="https://gitlab.com/jallbrit/cbonsai"
SRC_URI="https://gitlab.com/jallbrit/cbonsai/-/archive/v${PV}/cbonsai-v${PV}.tar.gz -> ${P}.tar.gz"
S="${WORKDIR}/cbonsai-v${PV}"

LICENSE="GPL-3+"

SLOT="0"
KEYWORDS="~amd64 ~arm64"

DEPEND="sys-libs/ncurses:=[unicode(+)]"
RDEPEND="${DEPEND}"
BDEPEND="app-text/scdoc
	virtual/pkgconfig"

src_compile() {
	local curses_cflags curses_libs
	curses_cflags=$($(tc-getPKG_CONFIG) --cflags ncursesw panelw) || die
	curses_libs=$($(tc-getPKG_CONFIG) --libs ncursesw panelw) || die
	$(tc-getCC) ${CPPFLAGS} ${CFLAGS} ${curses_cflags} cbonsai.c \
		${LDFLAGS} -o cbonsai ${curses_libs} || die
	scdoc < cbonsai.scd > cbonsai.6 || die
}

src_install() {
	dobin cbonsai
	doman cbonsai.6
	newbashcomp completions/bash/cbonsai.bash cbonsai
	dodoc README.md
}
