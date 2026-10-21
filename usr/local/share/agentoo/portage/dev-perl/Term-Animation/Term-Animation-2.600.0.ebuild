# Copyright 2026 agentoo contributors
# Distributed under the terms of the GNU General Public License v2

EAPI=8

DIST_AUTHOR=KBAUCOM
DIST_VERSION=2.6
inherit perl-module

DESCRIPTION="ASCII sprite animation framework for terminal applications"

LICENSE="Artistic GPL-1+"

SLOT="0"
KEYWORDS="~amd64"

RDEPEND="dev-perl/Curses"
BDEPEND="${RDEPEND}"
