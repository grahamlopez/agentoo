# Copyright 2026 agentoo contributors
# Distributed under the terms of the GNU General Public License v2

# Bump: check https://proton.me/download/pass-cli/versions.json, verify both
# amd64 and arm64 SHA-256 hashes, inspect ELF dependencies, and regenerate Manifest.

EAPI=8

DESCRIPTION="Proton Pass command-line client (official binary)"
HOMEPAGE="https://protonpass.github.io/pass-cli/"
SRC_URI="
	amd64? ( https://proton.me/download/pass-cli/${PV}/pass-cli-linux-x86_64 -> ${P}-amd64 )
	arm64? ( https://proton.me/download/pass-cli/${PV}/pass-cli-linux-aarch64 -> ${P}-arm64 )
"
S="${WORKDIR}"

LICENSE="GPL-3+"
SLOT="0"
KEYWORDS="~amd64 ~arm64"
RESTRICT="mirror strip"
QA_PREBUILT="usr/bin/pass-cli"

RDEPEND="
	>=sys-libs/glibc-2.34
	amd64? ( sys-devel/gcc )
	app-misc/ca-certificates
"

src_unpack() {
	cp "${DISTDIR}/${P}-${ARCH}" "${S}/pass-cli" || die
}

src_install() {
	dobin pass-cli
}

pkg_postinst() {
	elog "Update this client through Portage; do not run pass-cli update."
	elog "Set PROTON_PASS_NO_UPDATE_CHECK=1 to suppress upstream update notifications."
}
