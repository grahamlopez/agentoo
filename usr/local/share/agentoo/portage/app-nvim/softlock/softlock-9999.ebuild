# Copyright 2026 agentoo contributors
# Distributed under the terms of the GNU General Public License v2

EAPI=8

inherit git-r3

DESCRIPTION="Neovim plugin for passphrase-encrypted text files using GnuPG"
HOMEPAGE="https://github.com/grahamlopez/softlock.nvim"
EGIT_REPO_URI="https://github.com/grahamlopez/softlock.nvim.git"

LICENSE="MIT"
SLOT="0"

BDEPEND="app-editors/neovim"
RDEPEND=">=app-editors/neovim-0.12.3
	>=app-crypt/gnupg-2.2"

src_compile() {
	nvim --headless -u NONE -i NONE -n -c 'helptags doc' -c 'quit' || die
}

src_install() {
	insinto /usr/share/nvim/site/pack/agentoo/start/softlock
	doins -r plugin doc
	dodoc README.md LICENSE
}
