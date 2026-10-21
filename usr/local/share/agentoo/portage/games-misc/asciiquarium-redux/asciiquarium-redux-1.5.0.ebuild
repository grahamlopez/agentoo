# Copyright 2026 agentoo contributors
# Distributed under the terms of the GNU General Public License v2

EAPI=8

PYTHON_COMPAT=( python3_{11..14} )
PYTHON_REQ_USE="tk?"
DISTUTILS_USE_PEP517=hatchling
inherit distutils-r1

DESCRIPTION="Configurable Python reimagining of the classic terminal aquarium"
HOMEPAGE="https://github.com/cognitivegears/asciiquarium_redux"
SRC_URI="https://github.com/cognitivegears/asciiquarium_redux/archive/refs/tags/v${PV}.tar.gz -> ${P}.tar.gz"
S="${WORKDIR}/asciiquarium_redux-${PV}"

LICENSE="GPL-2+"

SLOT="0"
KEYWORDS="~amd64 ~arm64"

IUSE="tk"
RDEPEND=">=dev-python/asciimatics-1.15.0[${PYTHON_USEDEP}]"

src_prepare() {
	# Upstream also exports 'asciiquarium', owned by the classic package.
	sed -i '/^asciiquarium = /d' pyproject.toml || die
	# Limit wheel contents to the package; docs are installed below.
	cat >> pyproject.toml <<-EOF || die
	[tool.hatch.build.targets.wheel]
	packages = ["asciiquarium_redux"]
	EOF
	distutils-r1_src_prepare
}

python_install_all() {
	distutils-r1_python_install_all
	dodoc sample-config.toml fishtank-config-sample.toml ocean-config-sample.toml
}
