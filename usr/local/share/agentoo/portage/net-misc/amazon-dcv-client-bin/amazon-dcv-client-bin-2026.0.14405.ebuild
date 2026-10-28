# Copyright 2026 agentoo contributors
# Distributed under the terms of the GNU General Public License v2

EAPI=8

inherit desktop multilib unpacker xdg

DESCRIPTION="Amazon DCV remote desktop client (official binary, formerly NICE DCV)"
HOMEPAGE="https://www.amazondcv.com/"
SRC_URI="https://d1uj6qtbmh3dt5.cloudfront.net/${PV%.*}/Clients/nice-dcv-viewer_${PV}-1_amd64.ubuntu2404.deb"
S="${WORKDIR}"

LICENSE="NICE-EULA-8.4"
SLOT="0"
KEYWORDS="~amd64"
RESTRICT="bindist mirror strip"
QA_PREBUILT="opt/amazon-dcv/*"

# The vendor bundles GTK, GLib, codecs and GStreamer; these are private to DCV.
# These dependencies cover the remaining ELF requirements, including plugins.
RDEPEND="
	>=sys-libs/glibc-2.39
	>=sys-devel/gcc-13
	app-accessibility/at-spi2-core:2
	app-crypt/mit-krb5
	app-misc/ca-certificates
	app-shells/bash
	gnome-base/dconf
	app-arch/libdeflate
	dev-libs/libgudev
	sys-libs/libunwind
	dev-libs/libxml2-compat:2
	dev-libs/nspr
	dev-libs/nss
	dev-libs/openssl:0/3
	media-libs/alsa-lib
	media-libs/gst-plugins-base:1.0[opengl]
	media-libs/jbigkit
	media-libs/lerc
	media-libs/libglvnd
	media-libs/libpng:0/16
	media-libs/libpulse
	media-libs/libva[X]
	x11-libs/libvdpau
	media-libs/mesa
	sys-apps/pcsc-lite
	net-print/cups
	sys-apps/dbus
	sys-libs/libselinux
	virtual/zlib
	app-arch/brotli
	app-arch/bzip2
	app-arch/xz-utils
	app-arch/zstd
	dev-libs/elfutils
	virtual/udev
	x11-libs/libdrm
	dev-libs/libthai
	x11-libs/libX11
	x11-libs/libxcb
	x11-libs/libXcomposite
	x11-libs/libXcursor
	x11-libs/libXdamage
	x11-libs/libXext
	x11-libs/libXfixes
	x11-libs/libXft
	x11-libs/libXi
	x11-libs/libXinerama
	x11-libs/libxkbcommon
	x11-libs/libXrandr
	x11-libs/libXrender
"
BDEPEND="dev-libs/glib:2"

src_prepare() {
	default

	# No ELF in the package uses this optional HarfBuzz ICU bridge. It requires
	# Ubuntu's ICU 74, which Gentoo no longer supplies. Keep the core HarfBuzz.
	rm usr/lib/x86_64-linux-gnu/dcvviewer/libharfbuzz-icu.so.0 || die

	# Preserve the vendor layout privately, including helper and plugin paths.
	sed -i \
		-e 's|basedir=/usr|basedir=/opt/amazon-dcv/usr|' \
		-e 's|:/usr/share/${variant}/cef:|:${datadir}/${variant}/cef:|' \
		-e '/^export LD_LIBRARY_PATH=/i export DCV_DATA_DIR="${datadir}/${variant}"\nexport DCV_LIBEXEC_DIR="${libexecdir}/${variant}"' \
		usr/bin/dcvviewer || die
	# The private GSETTINGS_SCHEMA_DIR must include both application and GTK schemas.
	cp usr/share/glib-2.0/schemas/*.xml usr/share/dcvviewer/schemas/ || die
}

src_install() {
	dodir /opt/amazon-dcv
	cp -a usr "${ED}/opt/amazon-dcv/" || die
	dosym /opt/amazon-dcv/usr/bin/dcvviewer /usr/bin/dcvviewer

	local private=/opt/amazon-dcv/usr/lib/x86_64-linux-gnu/dcvviewer
	# Supply the host's dconf backend to the vendor's private GIO module directory.
	dosym /usr/$(get_libdir)/gio/modules/libdconfsettings.so "${private}/gio/modules/libdconfsettings.so"
	touch "${ED}${private}/gdk-pixbuf-2.0/2.10.0/loaders.cache" || die
	glib-compile-schemas "${ED}/opt/amazon-dcv/usr/share/dcvviewer/schemas" || die

	domenu usr/share/applications/com.nicesoftware.DcvViewer.desktop
	insinto /usr/share
	doins -r usr/share/icons usr/share/mime usr/share/metainfo
}

pkg_postinst() {
	xdg_pkg_postinst
	local private="${EROOT}opt/amazon-dcv/usr/lib/x86_64-linux-gnu/dcvviewer"
	LD_LIBRARY_PATH="${private}" "${private}/gdk-pixbuf-query-loaders" \
		"${private}"/gdk-pixbuf-2.0/2.10.0/loaders/*.so \
		> "${private}/gdk-pixbuf-2.0/2.10.0/loaders.cache" \
		|| ewarn "Could not regenerate DCV's private image-loader cache."
	elog "Launch dcvviewer as your normal user, or choose Amazon DCV in the application menu."
	elog "Gentoo is not supported upstream. Update the client through Portage."
}
