# Copyright 2026 agentoo contributors
# Distributed under the terms of the GNU General Public License v2

EAPI=8

PYTHON_COMPAT=( python3_{11..14} )
inherit python-single-r1 toolchain-funcs

BUSYBOX_VERSION=1.36.1
DESCRIPTION="Agentoo initramfs generator and private static BusyBox"
HOMEPAGE="https://www.busybox.net/"
SRC_URI="https://www.busybox.net/downloads/busybox-${BUSYBOX_VERSION}.tar.bz2"
S="${WORKDIR}/busybox-${BUSYBOX_VERSION}"

LICENSE="GPL-2"
SLOT="0"
KEYWORDS="~amd64"
REQUIRED_USE="${PYTHON_REQUIRED_USE}"

DEPEND="
	sys-libs/glibc[static-libs]
	sys-kernel/linux-headers
"
RDEPEND="${PYTHON_DEPS}
	app-arch/cpio
	sys-apps/kbd
	sys-devel/binutils
	sys-fs/cryptsetup
	sys-libs/glibc
"

busybox_make() {
	emake CC="$(tc-getCC)" HOSTCC="$(tc-getBUILD_CC)" AR="$(tc-getAR)" \
		CONFIG_EXTRA_CFLAGS="\"${CFLAGS} ${CPPFLAGS}\"" \
		CONFIG_EXTRA_LDFLAGS="\"${LDFLAGS}\"" SKIP_STRIP=y "$@"
}

src_configure() {
	unset KBUILD_OUTPUT KCONFIG_CONFIG KCONFIG_ALLCONFIG
	busybox_make allnoconfig
	local symbol value setting
	while IFS='=' read -r symbol value; do
		sed -i -e "s/^# ${symbol} is not set$/${symbol}=${value}/" \
			-e "s/^${symbol}=.*/${symbol}=${value}/" .config || die
	done < "${FILESDIR}/busybox.config"
	yes "" | busybox_make oldconfig
	# Fail here if a BusyBox update drops one of our required settings.
	while IFS= read -r setting; do
		grep -Fxq "${setting}" .config || die "BusyBox did not retain ${setting}"
	done < "${FILESDIR}/busybox.config"
}

src_compile() {
	busybox_make
}

src_install() {
	exeinto /usr/libexec/agentoo-initramfs
	doexe busybox "${FILESDIR}/build" "${FILESDIR}/smoke"
	insinto /usr/libexec/agentoo-initramfs
	doins "${FILESDIR}/init" "${FILESDIR}/udev-handoff"
	python_fix_shebang "${ED}/usr/libexec/agentoo-initramfs/build"
}
