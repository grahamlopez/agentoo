# Copyright 2026 Gentoo Authors
# Distributed under the terms of the GNU General Public License v2

# @ECLASS: agentoo-nerd-font.eclass
# @MAINTAINER:
# Agentoo maintainers
# @BLURB: Install selected variants of one pinned Nerd Fonts family
# @DESCRIPTION:
# Set NERD_ARCHIVE and NERD_PREFIX before inheriting. Archives can contain
# unrelated families; only exact prefix/variant matches are installed.

case ${EAPI} in
	8) ;;
	*) die "Unsupported EAPI ${EAPI}" ;;
esac

FONT_SUFFIX=ttf
inherit font

HOMEPAGE="https://www.nerdfonts.com/ https://github.com/ryanoasis/nerd-fonts"
SRC_URI="https://github.com/ryanoasis/nerd-fonts/releases/download/v${PV}/${NERD_ARCHIVE}.zip -> ${P}.zip"
S=${WORKDIR}
IUSE="normal +mono proportional"
REQUIRED_USE="|| ( normal mono proportional )"
BDEPEND="app-arch/unzip"

agentoo-nerd-font_src_install() {
	local variant suffix file count document
	mkdir selected || die
	for variant in normal mono proportional; do
		use "${variant}" || continue
		case ${variant} in
			normal) suffix= ;;
			mono) suffix=Mono ;;
			proportional) suffix=Propo ;;
		esac
		count=0
		for file in "${NERD_PREFIX}${suffix}"-*.ttf; do
			[[ -f ${file} ]] || continue
			cp -p -- "${file}" selected/ || die
			(( count += 1 ))
		done
		[[ ${count} -gt 0 ]] || die "No ${variant} fonts found for ${NERD_PREFIX}"
	done
	FONT_S="${S}/selected"
	DOCS=()
	font_src_install
	for document in LICENSE LICENCE.txt LICENCE-FAQ.txt OFL.txt README.md; do
		[[ ! -f ${document} ]] || dodoc "${document}"
	done
}

EXPORT_FUNCTIONS src_install
