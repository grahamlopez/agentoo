# Copyright 2026 Gentoo Authors
# Distributed under the terms of the GNU General Public License v2

EAPI=8

DESCRIPTION="Dependencies for a user-managed, self-updating Pi coding agent"
HOMEPAGE="https://pi.dev https://github.com/earendil-works/pi"

LICENSE="metapackage"
SLOT="0"
KEYWORDS="~amd64 ~arm64"
IUSE="X wayland"

RDEPEND="
	>=net-libs/nodejs-22.19.0[npm]
	app-shells/bash
	net-misc/curl
	dev-vcs/git
	sys-apps/fd
	sys-apps/ripgrep
	X? ( || ( x11-misc/xclip x11-misc/xsel ) )
	wayland? ( gui-apps/wl-clipboard )
"

S="${WORKDIR}"

src_unpack() { :; }
src_prepare() { eapply_user; }
src_configure() { :; }
src_compile() { :; }
src_install() { :; }

pkg_postinst() {
	elog "This package supplies dependencies; Pi itself is installed per user."
	elog "As your normal user, run the upstream installer and choose Install Pi:"
	elog "  curl -fsSL https://pi.dev/install.sh | sh"
	elog "Follow the installer's PATH instructions, then verify:"
	elog "  pi --version"
	elog "Update your user installation with:"
	elog "  pi update"
	elog "Portage tracks this dependency package, not your installed Pi version."
}

pkg_postrm() {
	# Replacement includes upgrades, downgrades, and same-version reinstalls.
	[[ -n ${REPLACED_BY_VERSION} ]] && return

	elog "Your user-installed Pi and its data have not been removed."
	elog "To remove Pi, run this as the user who installed it and choose Uninstall Pi:"
	elog "  curl -fsSL https://pi.dev/install.sh | sh"
	elog "For an npm global installation instead, use its original npm environment:"
	elog "  npm uninstall -g @earendil-works/pi-coding-agent"
	elog "Optional: permanently delete the default user data directory."
	elog "This deletes configuration, credentials, sessions, and installed Pi packages:"
	elog '  rm -rf -- "$HOME/.pi/agent"'
	elog "If PI_CODING_AGENT_DIR is customized, review that directory separately."
	elog "Project-local .pi directories are left in place."
	elog "Remove Pi before asking Portage to depclean its prerequisites."
}
