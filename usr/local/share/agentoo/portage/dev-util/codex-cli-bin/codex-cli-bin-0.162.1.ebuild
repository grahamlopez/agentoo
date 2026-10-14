# Copyright 2026 agentoo contributors
# Distributed under the terms of the GNU General Public License v2

EAPI=8

DESCRIPTION="OpenAI Codex command-line client (official binary package)"
HOMEPAGE="https://developers.openai.com/codex/cli https://github.com/openai/codex"
SRC_URI="
	amd64? ( https://github.com/openai/codex/releases/download/rust-v${PV}/codex-package-x86_64-unknown-linux-musl.tar.gz -> ${P}-amd64.tar.gz )
	arm64? ( https://github.com/openai/codex/releases/download/rust-v${PV}/codex-package-aarch64-unknown-linux-musl.tar.gz -> ${P}-arm64.tar.gz )
"
S="${WORKDIR}"

# Includes upstream's ripgrep, bubblewrap, Zsh and voice library bundle.
LICENSE="Apache-2.0 MIT BSD BSD-2 ZSH LGPL-2+ LGPL-2.1+ ZLIB"
SLOT="0"
KEYWORDS="~amd64 ~arm64"
RESTRICT="mirror strip"
QA_PREBUILT="opt/codex/*"

RDEPEND="
	>=sys-libs/glibc-2.38
	sys-libs/ncurses:0=[tinfo]
	arm64? ( sys-devel/gcc )
	app-misc/ca-certificates
	app-shells/bash
	dev-vcs/git
"

src_install() {
	# Keep the package marker and resources beside bin/: Codex resolves its
	# companion executables and bundled tools relative to this layout.
	dodir /opt/codex
	cp -a bin codex-package.json codex-path codex-resources "${ED}/opt/codex/" || die
	dosym ../../opt/codex/bin/codex /usr/bin/codex
}

pkg_postinst() {
	elog "Run codex as the intended user; login and configuration remain in ~/.codex."
	elog "Update through Portage, rather than an upstream installer."
	elog "Linux sandboxing needs unprivileged user namespaces enabled in the kernel."
}
