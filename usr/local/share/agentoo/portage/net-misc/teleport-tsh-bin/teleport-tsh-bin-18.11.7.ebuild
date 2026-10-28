# Copyright 2026 agentoo contributors
# Distributed under the terms of the GNU General Public License v2

EAPI=8

inherit shell-completion

DESCRIPTION="Teleport tsh client for SSH and infrastructure access (official binary)"
HOMEPAGE="https://goteleport.com/ https://github.com/gravitational/teleport"
SRC_URI="
	amd64? ( https://cdn.teleport.dev/teleport-v${PV}-linux-amd64-bin.tar.gz )
	arm64? ( https://cdn.teleport.dev/teleport-v${PV}-linux-arm64-bin.tar.gz )
"
S="${WORKDIR}/teleport"

# Official Community binaries carry this license, rather than the source AGPL.
LICENSE="Teleport-Community-1.0"
SLOT="0"
KEYWORDS="~amd64 ~arm64"
RESTRICT="bindist mirror strip"
QA_PREBUILT="usr/bin/tsh"

RDEPEND="
	>=sys-libs/glibc-2.17
	app-misc/ca-certificates
	x11-misc/xdg-utils
"

src_unpack() {
	# The upstream archive also includes server/admin tools and service files.
	# Extract only the client and its accompanying license, never the installer.
	tar -xzf "${DISTDIR}/teleport-v${PV}-linux-${ARCH}-bin.tar.gz" \
		teleport/tsh teleport/LICENSE-community || die
}

src_install() {
	dobin tsh
	dodoc LICENSE-community
	# Generated with this release's --completion-script-{bash,zsh}; kept as
	# architecture-independent files so staging never executes the target binary.
	newbashcomp "${FILESDIR}/tsh.bash" tsh
	dozshcomp "${FILESDIR}/_tsh"
}

pkg_postinst() {
	elog "Run tsh login --proxy=YOUR_PROXY as your normal user."
	elog "Match your cluster's major version; a newer-major client is unsupported."
	elog "Portage owns /usr/bin/tsh. Upstream managed updates may select binaries in ~/.tsh/bin."
	elog "Set TELEPORT_TOOLS_VERSION=off to use only the Portage-installed client."
}
