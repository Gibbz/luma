# We haven't tried to ship the tests on RHEL
%if 0%{?rhel}
    %bcond_with tests
%else
    %bcond_without tests
%endif

Summary: Tool for managing bootable, immutable filesystem trees
Name: ostree
Version: 2026.5
Release: 1.luma.2%{?dist}
Source0: libostree-%{version}.tar.gz
License: LGPL-2.0-or-later AND LGPL-2.1-or-later AND BSD-2-Clause AND LicenseRef-old-glib-tests
URL: https://ostreedev.github.io/ostree/

# Conditional to ELN right now to reduce blast radius; xref
# https://github.com/containers/composefs/pull/229#issuecomment-1838735764
%if 0%{?rhel} >= 10
ExcludeArch:    %{ix86}
%endif

BuildRequires: make
BuildRequires: gcc
BuildRequires: openssl elfutils jq gjs parallel python3-PyYAML gnome-desktop-testing
BuildRequires: which
BuildRequires: git
# We always run autogen.sh
BuildRequires: autoconf automake libtool
# For docs
BuildRequires: gtk-doc
# Core requirements
BuildRequires: pkgconfig(zlib)
BuildRequires: pkgconfig(libcurl)
BuildRequires: openssl-devel
BuildRequires: pkgconfig(composefs)
%if %{with tests}
BuildRequires: pkgconfig(libsoup-3.0)
%endif
BuildRequires: libattr-devel
# The tests require attr
BuildRequires: attr
# Extras
BuildRequires: pkgconfig(libarchive)
BuildRequires: pkgconfig(liblzma)
BuildRequires: pkgconfig(libselinux)
BuildRequires: pkgconfig(mount)
%if 0%{?fedora} <= 36
BuildRequires: pkgconfig(fuse)
%else
BuildRequires: pkgconfig(fuse3)
%endif
BuildRequires: pkgconfig(e2p)
BuildRequires: libcap-devel
BuildRequires: gpgme-devel
BuildRequires: pkgconfig(libsystemd)
BuildRequires: /usr/bin/g-ir-scanner
BuildRequires: dracut
BuildRequires:  bison

# Runtime requirements
Requires: dracut
Requires: /usr/bin/gpgv2
Requires: systemd-units
Requires: %{name}-libs%{?_isa} = %{?epoch:%{epoch}:}%{version}-%{release}
# Strictly speaking, this is not a current hard requirement, but it will
# be in the future.
Requires: composefs

%description
libostree is a shared library designed primarily for
use by higher level tools to manage host systems (e.g. rpm-ostree),
as well as container tools like flatpak and the atomic CLI.

%package libs
Summary: C shared libraries %{name}
Requires: bubblewrap

%description libs
The %{name}-libs provides shared libraries for %{name}.

%package devel
Summary: Development headers for %{name}
Requires: %{name}-libs%{?_isa} = %{?epoch:%{epoch}:}%{version}-%{release}

%description devel
The %{name}-devel package includes the header files for the %{name} library.

%ifnarch s390 s390x
%package grub2
Summary: GRUB2 integration for OSTree
%ifnarch aarch64 %{arm}
Requires: grub2
%else
Requires: grub2-efi
%endif
Requires: ostree

%description grub2
GRUB2 integration for OSTree
%endif

%if %{with tests}
%package tests
Summary: Tests for the %{name} package
Requires: %{name}%{?_isa} = %{?epoch:%{epoch}:}%{version}-%{release}
Requires: %{name}-libs%{?_isa} = %{?epoch:%{epoch}:}%{version}-%{release}

%description tests
This package contains tests that can be used to verify
the functionality of the installed %{name} package.
%endif

%prep
%autosetup -Sgit -n libostree-%{version}

%build
env NOCONFIGURE=1 ./autogen.sh
%configure --disable-silent-rules \
           --enable-gtk-doc \
           --with-selinux \
           --with-curl \
           --with-openssl \
           --without-soup \
           --with-composefs \
           %{?with_tests:--with-soup3} \
           %{?!with_tests:--without-soup3} \
           %{?with_tests:--enable-installed-tests=yes} \
           --with-dracut=yesbutnoconf
%make_build

%check
%make_build check
cc -Wall -Wextra -Werror -O2 tests/luma-aboot-overlay-native-control.c -o luma-overlay-control $(pkg-config --cflags --libs glib-2.0 gio-2.0 libarchive)
LUMA_ABOOT_OVERLAY_CONTROL=$PWD/luma-overlay-control python3 tests/luma-test-aboot-overlay-native.py

%install
%make_install INSTALL="install -p -c"
find %{buildroot} -name '*.la' -delete
# Preserve bundled-source notices even when ostree-libs is installed alone.
mkdir -p luma-license-notices/bsdiff luma-license-notices/libglnx
cp -p COPYING luma-license-notices/
cp -p bsdiff/LICENSE luma-license-notices/bsdiff/
cp -p libglnx/COPYING luma-license-notices/libglnx/
cp -a libglnx/LICENSES luma-license-notices/libglnx/

# Needed to enable the service at compose time currently
%post
%systemd_post ostree-remount.service

%preun
%systemd_preun ostree-remount.service

%files
%{!?_licensedir:%global license %%doc}
%license COPYING luma-license-notices
%doc README.md
%{_bindir}/ostree
%{_bindir}/rofiles-fuse
%{_datadir}/ostree
%{_datadir}/bash-completion/completions/*
%dir %{_prefix}/lib/dracut/modules.d/50ostree
%{_prefix}/lib/systemd/system/ostree*.*
%{_prefix}/lib/dracut/modules.d/50ostree/*
%{_mandir}/man*/*.gz
%{_prefix}/lib/systemd/system-generators/ostree-system-generator
%exclude %{_sysconfdir}/grub.d/*ostree
%exclude %{_libexecdir}/libostree/grub2*
%{_prefix}/lib/tmpfiles.d/*
%{_prefix}/lib/ostree
# Moved in git master
%{_libexecdir}/libostree/*

%files libs
%license luma-license-notices
%{_sysconfdir}/ostree
%{_libdir}/*.so.1*
%{_libdir}/girepository-1.0/OSTree-1.0.typelib

%files devel
%{_libdir}/lib*.so
%{_includedir}/*
%{_libdir}/pkgconfig/*
%dir %{_datadir}/gtk-doc/html/ostree
%{_datadir}/gtk-doc/html/ostree
%{_datadir}/gir-1.0/OSTree-1.0.gir

%ifnarch s390 s390x
%files grub2
%{_sysconfdir}/grub.d/*ostree
%dir %{_libexecdir}/libostree
%{_libexecdir}/libostree/grub2*
%endif

%if %{with tests}
%files tests
%{_libexecdir}/installed-tests
%{_datadir}/installed-tests
%endif

%changelog
* Wed Oct 14 2026 Luma Build <build@luma.invalid> - 2026.5-1.luma.2
- Ship bundled OSTree, bsdiff and libglnx notices with both runtime packages.
* Wed Oct 14 2026 Luma Build <build@luma.invalid> - 2026.5-1.luma.1
- Maintain native boot image assembly, prepare-root and signing capacity fixes.
