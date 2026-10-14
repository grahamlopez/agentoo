# Copyright 2026 agentoo contributors
# Distributed under the terms of the GNU General Public License v2

EAPI=8

DESCRIPTION="Dependencies for a user-managed, self-updating Claude Code"
HOMEPAGE="https://code.claude.com/docs/en/setup"
LICENSE="metapackage"
SLOT="0"
KEYWORDS="~amd64 ~arm64"
IUSE="+sandbox"

RDEPEND="
	>=sys-libs/glibc-2.26
	app-misc/ca-certificates
	app-shells/bash
	dev-vcs/git
	net-misc/curl
	app-misc/jq
	media-gfx/qrencode
	sandbox? (
		sys-apps/bubblewrap
		net-misc/socat
	)
"

S="${WORKDIR}"

src_unpack() { :; }
src_prepare() { eapply_user; }
src_configure() { :; }
src_compile() { :; }
src_install() { :; }

pkg_postinst() {
	elog "This package supplies dependencies; install Claude as your normal user:"
	elog "  curl -fsSL https://claude.ai/install.sh | bash -s stable"
	elog "Follow the installer's PATH instructions, then run:"
	elog "  claude --version"
	elog "  claude"
	elog "The native installation auto-updates; manually update with claude update."
	elog "Use latest instead of stable in the install command for faster releases."
	elog "Portage tracks prerequisites, not your installed Claude version."
	elog "If migrating, remove dev-util/claude-code-bin through Portage first."
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

pkg_postrm() {
	[[ -n ${REPLACED_BY_VERSION} ]] && return

	elog "Your user-installed Claude and its data have not been removed."
	elog "For the default native installation, run as the installing user:"
	elog '  rm -f -- "$HOME/.local/bin/claude"'
	elog '  rm -rf -- "$HOME/.local/share/claude"'
	elog "For an npm installation, use its original npm environment instead:"
	elog "  npm uninstall -g @anthropic-ai/claude-code"
	elog "Optional: permanently delete configuration, credentials and session history:"
	elog '  rm -rf -- "${CLAUDE_CONFIG_DIR:-$HOME/.claude}"'
	elog '  rm -f -- "$HOME/.claude.json"'
	elog "Other Claude clients may share this data; project-local files stay in place."
	elog "Review custom install/configuration paths separately."
	elog "Remove Claude before asking Portage to depclean its prerequisites."
}
