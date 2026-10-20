# SPDX-License-Identifier: Apache-2.0
# Built by scripts/packages/build-titan2e-kernel.sh; krel, kver and krelease
# are passed with --define.
%global debug_package %{nil}
%global __os_install_post %{nil}
%global _build_id_links none

Name: titan2e-kernel-modules
Version: %{kver}
Release: %{krelease}%{?dist}
Summary: Kernel modules for the Unihertz Titan 2 Elite kernel %{krel}
License: GPL-2.0-only
Source0: modules-%{krel}.tar
ExclusiveArch: aarch64
Requires(post): kmod

%description
Modules of the Unihertz Titan 2 Elite (MediaTek MT6878) kernel %{krel}. The
kernel itself is flashed as boot_a.img.

%prep

%build

%install
mkdir -p %{buildroot}%{_prefix}/lib/modules
tar -C %{buildroot}%{_prefix}/lib/modules -xf %{SOURCE0}

%post
/usr/sbin/depmod -a %{krel} || :

%files
%dir %{_prefix}/lib/modules/%{krel}
%{_prefix}/lib/modules/%{krel}/kernel
%{_prefix}/lib/modules/%{krel}/modules.*

%changelog
* Mon Oct 19 2026 Project Luma <builds@project-luma.local>
- Modules of the Titan 2 Elite kernel built from patches/linux-mt6878.
