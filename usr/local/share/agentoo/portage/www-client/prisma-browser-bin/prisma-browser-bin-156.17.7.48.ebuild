# Copyright 2026 agentoo contributors
# Distributed under the terms of the GNU General Public License v2

EAPI=8
PYTHON_COMPAT=( python3_{11..14} )

inherit chromium-2 desktop optfeature python-single-r1 systemd unpacker xdg

DESCRIPTION="Prisma Access Browser by Palo Alto Networks (official binary)"
HOMEPAGE="https://docs.paloaltonetworks.com/prisma-browser"
SRC_URI="https://updates.talon-sec.com/linux/prisma-access-browser/deb/pool/stable/main/prisma-access-browser-stable_${PV}-1_amd64.deb -> ${P}-amd64.deb"
S="${WORKDIR}"

LICENSE="all-rights-reserved"
SLOT="0"
KEYWORDS="~amd64"
IUSE="protection qt6"
REQUIRED_USE="protection? ( ${PYTHON_REQUIRED_USE} )"
RESTRICT="bindist mirror strip"
QA_PREBUILT="opt/paloaltonetworks/pab/*"

RDEPEND="
	app-accessibility/at-spi2-core:2
	app-misc/ca-certificates
	app-shells/bash
	dev-libs/expat
	>=dev-libs/glib-2.49.3:2
	dev-libs/nspr
	dev-libs/nss
	media-fonts/liberation-fonts
	media-libs/alsa-lib
	media-libs/mesa[gbm(+)]
	media-libs/vulkan-loader
	net-misc/curl
	net-print/cups
	sys-apps/dbus
	sys-devel/gcc
	>=sys-libs/glibc-2.25
	virtual/udev
	x11-libs/cairo
	x11-libs/gdk-pixbuf:2
	x11-libs/gtk+:3
	x11-libs/libdrm
	x11-libs/libX11
	x11-libs/libxcb
	x11-libs/libXcomposite
	x11-libs/libXdamage
	x11-libs/libXext
	x11-libs/libXfixes
	x11-libs/libxkbcommon
	x11-libs/libXrandr
	x11-libs/pango
	x11-misc/xdg-utils
	qt6? ( dev-qt/qtbase:6[gui,widgets] )
	protection? (
		${PYTHON_DEPS}
		$(python_gen_cond_dep 'dev-util/bcc[python,${PYTHON_USEDEP}]')
		llvm-core/clang
		sys-apps/systemd
	)
"

PAB_HOME="/opt/paloaltonetworks/pab"

pkg_setup() {
	chromium_suid_sandbox_check_kernel_config
	if use protection; then
		python-single-r1_pkg_setup
	fi
}

src_prepare() {
	default
	rm "opt/paloaltonetworks/pab/libqt5_shim.so" || die
	use qt6 || rm "opt/paloaltonetworks/pab/libqt6_shim.so" || die
	# Portage owns updates. Never run the Debian maintainer scripts.
	rm -r opt/paloaltonetworks/pab/cron || die
	gunzip usr/share/man/man1/prisma-access-browser-stable.1.gz || die
}

src_install() {
	dodir "${PAB_HOME}"
	cp -a opt/paloaltonetworks/pab/. "${ED}${PAB_HOME}/" || die
	# Match Gentoo's Chrome sandbox permissions; the helper must remain root-owned.
	fperms 4711 "${PAB_HOME}/chrome-sandbox"
	dosym "${PAB_HOME}/prisma-access-browser" /usr/bin/prisma-access-browser-stable
	dosym prisma-access-browser-stable /usr/bin/prisma-access-browser

	domenu usr/share/applications/*.desktop
	local size
	for size in 16 24 32 48 64 128 256; do
		newicon -s "${size}" "opt/paloaltonetworks/pab/product_logo_${size}.png" prisma-access-browser.png
	done
	insinto /usr/share/metainfo
	doins usr/share/appdata/prisma-access-browser.appdata.xml
	doman usr/share/man/man1/prisma-access-browser-stable.1
	dodoc "${FILESDIR}/README.gentoo"

	if use protection; then
		python_fix_shebang "${ED}${PAB_HOME}/linux_protector.py"
		sed -e "s|@PYTHON@|${PYTHON}|g" "${FILESDIR}/pab-protection.service" \
			> "${T}/pab-protection.service" || die
		systemd_dounit "${T}/pab-protection.service"
	fi
}

pkg_postinst() {
	xdg_pkg_postinst
	elog "Run prisma-access-browser as your normal user and sign in to your organization."
	elog "Gentoo is unsupported upstream. Update through Portage."
	elog "Verify sandbox status at chrome://sandbox; never use --no-sandbox."
	elog "Native Wayland: prisma-access-browser --ozone-platform=wayland"
	if use protection; then
		elog "If required by your organization, enable: systemctl enable --now pab-protection"
		elog "Protection requires matching running-kernel build headers and BPF/kprobe support."
		elog "For BPF LSM protection enable CONFIG_BPF_LSM and include bpf in the active LSM list."
		elog "Inspect journalctl -u pab-protection before relying on managed protection."
	else
		elog "USE=protection installs the BCC-based systemd service required by some policies."
	fi
	elog "Device-trust key enrollment is not configured automatically; see README.gentoo."
	optfeature "XWayland fallback" x11-base/xwayland
	optfeature "screen sharing portals (also install a desktop backend)" sys-apps/xdg-desktop-portal
	optfeature "credential storage (requires a running Secret Service provider)" app-crypt/libsecret
}
