# Copyright 2026 agentoo contributors
# Distributed under the terms of the GNU General Public License v2

EAPI=8

inherit systemd toolchain-funcs

DESCRIPTION="System-wide key remapping daemon for Linux"
HOMEPAGE="https://github.com/rvaiya/keyd"
SRC_URI="https://github.com/rvaiya/keyd/archive/refs/tags/v${PV}.tar.gz -> ${P}.tar.gz"

LICENSE="MIT"
SLOT="0"
KEYWORDS="~amd64 ~arm64"

DEPEND="sys-kernel/linux-headers"
RDEPEND="acct-group/keyd"

src_prepare() {
	default
	# Keep upstream's required defines while honoring the user's compiler flags.
	sed -i \
		-e '/-I\/usr\/local\/include/d' \
		-e '/-L\/usr\/local\/lib/d' \
		-e 's/$(CC) $(CFLAGS) -O3/$(CC) $(CPPFLAGS) $(CFLAGS)/' \
		Makefile || die
	sed 's#@PREFIX@#/usr#g' keyd.service.in > keyd.service || die
	gunzip data/keyd.1.gz || die
}

src_compile() {
	emake CC="$(tc-getCC)" COMMIT=release PREFIX=/usr
}

src_test() {
	# The IO harness runs without root or access to live input devices.
	emake CC="$(tc-getCC)" COMMIT=release test-io
}

src_install() {
	dobin bin/keyd
	doman data/keyd.1
	dodoc README.md docs/*.md
	docinto examples
	dodoc examples/*
	insinto /usr/share/keyd
	doins data/keyd.compose
	doins -r layouts
	keepdir /etc/keyd
	systemd_dounit keyd.service
	newinitd "${FILESDIR}/keyd.initd" keyd
}

pkg_postinst() {
	elog "Create /etc/keyd/default.conf using the installed examples."
	elog "Then start keyd: systemctl enable --now keyd (systemd), or"
	elog "rc-update add keyd default && rc-service keyd start (OpenRC)."
	elog "The kernel must provide evdev and uinput support."
	elog "Members of the keyd group may control keyd through its IPC socket."
}
