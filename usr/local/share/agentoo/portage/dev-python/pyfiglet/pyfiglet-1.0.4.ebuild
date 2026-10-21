# Copyright 2026 agentoo contributors
# Distributed under the terms of the GNU General Public License v2

EAPI=8

PYTHON_COMPAT=( python3_{11..14} )
DISTUTILS_USE_PEP517=setuptools
inherit distutils-r1 pypi

DESCRIPTION="Pure Python implementation of FIGlet text rendering"
HOMEPAGE="https://github.com/pwaller/pyfiglet"

LICENSE="MIT"

SLOT="0"
KEYWORDS="~amd64 ~arm64"

src_prepare() {
	# Modern setuptools backend also supports the upstream setup.py.
	sed -i 's/setuptools.build_meta:__legacy__/setuptools.build_meta/' pyproject.toml || die
	distutils-r1_src_prepare
}
