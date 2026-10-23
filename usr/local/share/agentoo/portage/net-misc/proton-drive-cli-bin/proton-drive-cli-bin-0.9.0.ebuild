# Copyright 2026 agentoo contributors
# Distributed under the terms of the GNU General Public License v2

EAPI=8

DESCRIPTION="Proton Drive command-line client (official binary)"
HOMEPAGE="https://proton.me/support/drive-cli https://github.com/ProtonDriveApps/sdk"
SRC_URI="
	amd64? ( https://proton.me/download/drive/cli/${PV}/linux-x64/proton-drive -> ${P}-amd64 )
	arm64? ( https://proton.me/download/drive/cli/${PV}/linux-arm64/proton-drive -> ${P}-arm64 )
	https://raw.githubusercontent.com/ProtonDriveApps/sdk/ab3c8a7ae7aed70f8e66a5e9dd1c2dfc91f43e19/LICENSE.md -> ${P}-LICENSE.md
"
S="${WORKDIR}"

# Includes the statically linked Bun runtime and its libraries.
LICENSE="MIT BSD BSD-2 Apache-2.0 LGPL-2 LGPL-2.1+ ZLIB IJG openssl"
SLOT="0"
KEYWORDS="~amd64 ~arm64"
IUSE="pass"
RESTRICT="mirror strip"
QA_PREBUILT="usr/bin/proton-drive"

RDEPEND="
	>=sys-libs/glibc-2.17
	app-crypt/libsecret
	app-misc/ca-certificates
	x11-misc/xdg-utils
	pass? ( app-admin/pass )
"

src_unpack() {
	cp "${DISTDIR}/${P}-${ARCH}" proton-drive || die
}

src_install() {
	dobin proton-drive
	newdoc "${DISTDIR}/${P}-LICENSE.md" LICENSE.md
}

pkg_postinst() {
	elog "Run proton-drive auth login as your normal user; sign-in uses your browser."
	elog "The default credential store needs a running Secret Service provider."
	elog "For pass/GPG instead: export PROTON_DRIVE_CREDENTIALS_STORE=pass"
	elog "Initialize pass first; USE=pass supplies it without changing the default store."
	if use amd64; then
		elog "Upstream's standard x64 build requires an AVX2-capable CPU."
	fi
	elog "Update through Portage. User settings and sessions remain in native locations."
}
