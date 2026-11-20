# Copyright 2026 agentoo contributors
# Distributed under the terms of the GNU General Public License v2

EAPI=8

DESCRIPTION="Dependencies for a user-managed, self-updating Google Antigravity CLI"
HOMEPAGE="https://antigravity.google/docs/cli/reference"
LICENSE="metapackage"
SLOT="0"
KEYWORDS="~amd64 ~arm64"

RDEPEND="
	>=sys-libs/glibc-2.26
	app-arch/gzip
	app-arch/tar
	app-misc/ca-certificates
	app-misc/jq
	app-shells/bash
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
	elog "This package supplies dependencies; install Antigravity CLI as your normal user:"
	elog "  curl -fsSL https://antigravity.google/cli/install.sh | bash"
	elog "To enable Agentoo's shared statusline inside agy, run:"
	elog "  /statusline /usr/local/share/agentoo/agents/antigravity-statusline.sh"
	elog 'Ensure $HOME/.local/bin is on PATH, then run:'
	elog "  agy --version"
	elog "  agy"
	elog "The native installation auto-updates; manually update with agy update."
	elog "Portage tracks prerequisites, not your installed Antigravity CLI version."
	elog "Linux terminal sandboxing (--sandbox) uses kernel user namespaces and Landlock."
	elog "Desktop login uses a browser and Secret Service keyring when available;"
	elog "SSH/headless sessions print an authorization URL."
}

pkg_postrm() {
	[[ -n ${REPLACED_BY_VERSION} ]] && return

	elog "Your user-installed Antigravity CLI and its data have not been removed."
	elog "For the default installation, run as the installing user:"
	elog '  rm -f -- "$HOME/.local/bin/agy"'
	elog '  rm -rf -- "$HOME/.cache/antigravity"'
	elog "If --dir was customized during installation, remove that agy binary instead."
	elog "Optional: permanently delete configuration, credentials, and session history:"
	elog '  rm -rf -- "$HOME/.gemini/antigravity-cli"'
	elog "Other Antigravity tools may share data under ~/.gemini; project-local files stay in place."
	elog "Remove Antigravity CLI before asking Portage to depclean its prerequisites."
}
