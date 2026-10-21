# Copyright 2026 agentoo contributors
# Distributed under the terms of the GNU General Public License v2

EAPI=8

PYTHON_COMPAT=( python3_{11..14} )
DISTUTILS_USE_PEP517=setuptools
inherit distutils-r1 pypi

DESCRIPTION="Cross-platform terminal animation and user interface library"
HOMEPAGE="https://github.com/peterbrittain/asciimatics"

LICENSE="Apache-2.0"

SLOT="0"
KEYWORDS="~amd64 ~arm64"

RDEPEND=">=dev-python/pyfiglet-0.7.2[${PYTHON_USEDEP}]
	>=dev-python/pillow-2.7.0[${PYTHON_USEDEP}]
	dev-python/wcwidth[${PYTHON_USEDEP}]"
BDEPEND="dev-python/setuptools-scm[${PYTHON_USEDEP}]"

distutils_enable_tests unittest
