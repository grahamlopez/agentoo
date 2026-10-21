# Copyright 2026 agentoo contributors
# Distributed under the terms of the GNU General Public License v2

EAPI=8

inherit bash-completion-r1 toolchain-funcs

MY_COMMIT="298bf698ad080f13fa0d051588482bab8903d988"

DESCRIPTION="Bonsai trees with seasonal colors and persistent growth (jakobrees fork)"
HOMEPAGE="https://github.com/jakobrees/cbonsai"
SRC_URI="https://github.com/jakobrees/cbonsai/archive/${MY_COMMIT}.tar.gz -> ${P}.tar.gz"
S="${WORKDIR}/cbonsai-${MY_COMMIT}"

LICENSE="GPL-3+"

SLOT="0"
KEYWORDS="~amd64 ~arm64"

DEPEND="sys-libs/ncurses:=[unicode(+)]"
RDEPEND="${DEPEND}"
BDEPEND="app-text/scdoc
	virtual/pkgconfig"

src_prepare() {
	default
	# Keep command, completion, manual and save files separate from classic cbonsai.
	sed -i 's/cbonsai/cbonsai-enhanced/g' src/cbonsai.c cbonsai.scd \
		completions/bash/cbonsai.bash || die
}

src_compile() {
	local curses_cflags curses_libs
	curses_cflags=$($(tc-getPKG_CONFIG) --cflags ncursesw panelw) || die
	curses_libs=$($(tc-getPKG_CONFIG) --libs ncursesw panelw) || die
	$(tc-getCC) ${CPPFLAGS} ${CFLAGS} ${curses_cflags} src/cbonsai.c src/msaw.c \
		${LDFLAGS} -o cbonsai-enhanced ${curses_libs} || die
	scdoc < cbonsai.scd > cbonsai-enhanced.6 || die
}

src_install() {
	dobin cbonsai-enhanced
	doman cbonsai-enhanced.6
	newbashcomp completions/bash/cbonsai.bash cbonsai-enhanced
	dodoc README.md
}
