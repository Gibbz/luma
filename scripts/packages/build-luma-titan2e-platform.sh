#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
repo_root=$(CDPATH='' cd -- "$(dirname -- "$0")/../.." && pwd)
. "$repo_root/config/desktop/inputs.env"
output="$repo_root/build/packages/luma-titan2e-platform"
[ ! -e "$output" ] || { echo 'Existing output must be retained' >&2; exit 1; }
mkdir -p "$(dirname "$output")"
work=$(mktemp -d "$output.work.XXXXXX")
mkdir -p "$work/rpmbuild"/{BUILD,BUILDROOT,RPMS,SRPMS,SOURCES,SPECS}
install -m 0644 "$repo_root"/src/luma-titan2e-platform/* "$work/rpmbuild/SOURCES/"
install -m 0644 "$repo_root/packaging/rpm/luma-titan2e-platform.spec" "$work/rpmbuild/SPECS/package.spec"
"$repo_root/scripts/packages/run-in-rpm-builder.sh" "$work/rpmbuild" "$FEDORA_RPM_BUILD_CONTAINER" '
set -euo pipefail
dnf5 -y install rpm-build systemd-rpm-macros
rpmbuild -ba --define "_topdir $PWD" SPECS/package.spec
'
mkdir "$work/output"
cp -a "$work/rpmbuild/RPMS" "$work/rpmbuild/SRPMS" "$work/output/"
(cd "$work/output"; find RPMS SRPMS -type f -name '*.rpm' -exec sha256sum {} + | sort >SHA256SUMS)
mv "$work/output" "$output"
rm -rf "$work"
printf 'built %s\n' "$output"
