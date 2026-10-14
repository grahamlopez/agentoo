# Copyright 2026 agentoo contributors
# Distributed under the terms of the GNU General Public License v2

EAPI=8

DESCRIPTION="Anthropic Claude Code command-line client (official native binary)"
HOMEPAGE="https://code.claude.com/docs/en/overview"
SRC_URI="
	amd64? ( https://downloads.claude.ai/claude-code-releases/${PV}/linux-x64/claude -> ${P}-amd64 )
	arm64? ( https://downloads.claude.ai/claude-code-releases/${PV}/linux-arm64/claude -> ${P}-arm64 )
"
S="${WORKDIR}"

LICENSE="all-rights-reserved"
SLOT="0"
KEYWORDS="~amd64 ~arm64"
IUSE="+sandbox"
RESTRICT="mirror bindist strip"
QA_PREBUILT="opt/claude-code/claude"

RDEPEND="
	>=sys-libs/glibc-2.26
	app-misc/ca-certificates
	app-shells/bash
	dev-vcs/git
	media-gfx/qrencode
	sandbox? (
		sys-apps/bubblewrap
		net-misc/socat
	)
"

src_unpack() {
	cp "${DISTDIR}/${P}-${ARCH}" "${S}/claude" || die
}

src_install() {
	exeinto /opt/claude-code
	doexe claude
	# All update paths stay under Portage control, including explicit commands.
	cat > claude-launcher <<-EOF || die
	#!/bin/sh
	export DISABLE_UPDATES=1
	exec "${EPREFIX}/opt/claude-code/claude" "\$@"
	EOF
	newbin claude-launcher claude
}

pkg_postinst() {
	elog "Run claude as the intended user; login and configuration remain in your home."
	elog "The launcher disables upstream updates. Update this client through Portage."
	elog "Headless login with a phone: run claude (or /login inside Claude Code)."
	elog "Keep the login prompt open; in a second terminal or SSH session, run:"
	elog "  tr -d '[:space:]' | qrencode -t ANSIUTF8"
	elog "Paste the full login URL, then press Enter followed by Ctrl+D."
	elog "Make the terminal wide enough to show the entire QR code."
	elog "Scan it with your phone camera and sign in in the phone browser."
	elog "Paste the browser's login code into the original Claude login prompt."
	if use sandbox; then
		elog "Sandbox dependencies are installed; enable sandboxing with /sandbox."
		elog "The kernel must allow unprivileged user namespaces."
	fi
}
