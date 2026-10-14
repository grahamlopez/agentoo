# Copyright 2026 agentoo contributors
# Distributed under the terms of the GNU General Public License v2

EAPI=8

DESCRIPTION="Dependencies for a user-managed OpenAI Codex CLI"
HOMEPAGE="https://developers.openai.com/codex/cli"
LICENSE="metapackage"
SLOT="0"
KEYWORDS="~amd64 ~arm64"

# Preserve the runtime requirements checked for the previous native package.
RDEPEND="
	>=sys-libs/glibc-2.38
	sys-libs/ncurses:0=[tinfo]
	arm64? ( sys-devel/gcc )
	app-misc/ca-certificates
	app-shells/bash
	sys-apps/bubblewrap
	dev-vcs/git
	net-misc/curl
"

S="${WORKDIR}"

src_unpack() { :; }
src_prepare() { eapply_user; }
src_configure() { :; }
src_compile() { :; }
src_install() { :; }

pkg_postinst() {
	elog "This package supplies dependencies; install Codex as your normal user:"
	elog "  curl -fsSL https://chatgpt.com/codex/install.sh | sh"
	elog "Follow the installer's PATH instructions, then run:"
	elog "  codex --version"
	elog "  codex"
	elog "Update with codex update, or rerun the installer above."
	elog "Portage tracks prerequisites, not your installed Codex version."
	elog "Linux sandboxing needs unprivileged user namespaces enabled in the kernel."
	elog "If migrating, remove dev-util/codex-cli-bin through Portage first."
}

pkg_postrm() {
	[[ -n ${REPLACED_BY_VERSION} ]] && return

	elog "Your user-installed Codex and its data have not been removed."
	elog "For the default standalone installation, run as the installing user:"
	elog '  rm -f -- "$HOME/.local/bin/codex"'
	elog '  rm -rf -- "${CODEX_HOME:-$HOME/.codex}/packages/standalone"'
	elog "If CODEX_INSTALL_DIR was customized, remove its codex entry instead."
	elog "For an npm installation, use its original npm environment instead:"
	elog "  npm uninstall -g @openai/codex"
	elog "Optional: permanently delete configuration, credentials, sessions and caches:"
	elog '  rm -rf -- "${CODEX_HOME:-$HOME/.codex}"'
	elog "Other Codex clients may share this data; project-local .codex stays in place."
	elog "Remove Codex before asking Portage to depclean its prerequisites."
}
