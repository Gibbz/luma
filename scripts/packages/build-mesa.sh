#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Build packaging/rpm/mesa.spec for aarch64 in the Fedora builder.
#   LUMA_MESA_SOURCE_DIR  take the pinned tarballs from this directory when present
set -euo pipefail
repo_root=$(CDPATH='' cd -- "$(dirname -- "$0")/../.." && pwd)
. "$repo_root/config/desktop/inputs.env"
. "$repo_root/config/mobile/mesa-source.env"
output="$repo_root/build/packages/mesa/aarch64"
[ ! -e "$output" ] || { echo 'Existing output must be retained' >&2; exit 1; }
mkdir -p "$(dirname "$output")"
work=$(mktemp -d "$output.work.XXXXXX")
mkdir -p "$work/rpmbuild"/{BUILD,BUILDROOT,RPMS,SRPMS,SOURCES,SPECS}
src=$work/rpmbuild/SOURCES

while read -r sha name url; do
	[ -n "$sha" ] || continue
	if [ -f "${LUMA_MESA_SOURCE_DIR:-/nonexistent}/$name" ]; then
		cp -- "$LUMA_MESA_SOURCE_DIR/$name" "$src/$name"
	else
		curl -fsSL "$url" -o "$src/$name"
	fi
	[ "$(sha256sum "$src/$name" | cut -d' ' -f1)" = "$sha" ] || { echo "checksum differs: $name" >&2; exit 1; }
done <<<"$LUMA_MESA_SOURCES"
install -m 0644 "$repo_root"/patches/mesa/[0-9][0-9][0-9][0-9]-*.patch "$src/"
install -m 0644 "$repo_root/packaging/mesa/Mesa-MLAA-License-Clarification-Email.txt" "$src/"
install -m 0644 "$repo_root/packaging/rpm/mesa.spec" "$work/rpmbuild/SPECS/mesa.spec"

export LUMA_RPM_BUILDER_ARCHITECTURE=aarch64
"$repo_root/scripts/packages/run-in-rpm-builder.sh" "$work/rpmbuild" "$FEDORA_RPM_BUILD_CONTAINER_AARCH64" '
set -euo pipefail
dnf5 -y install rpm-build "dnf5-command(builddep)"
dnf5 -y builddep SPECS/mesa.spec
# Dynamic BuildRequires (the Rust crates NVK needs).
for i in 1 2 3 4; do
	rm -f SRPMS/*.buildreqs.nosrc.rpm
	rc=0; rpmbuild -br --define "_topdir $PWD" SPECS/mesa.spec || rc=$?
	[ "$rc" -eq 11 ] || break
	dnf5 -y builddep SRPMS/*.buildreqs.nosrc.rpm
done
rm -f SRPMS/*.buildreqs.nosrc.rpm
rpmbuild -ba --define "_topdir $PWD" SPECS/mesa.spec
'
mkdir "$work/output"
cp -a "$work/rpmbuild/RPMS" "$work/rpmbuild/SRPMS" "$work/output/"
(cd "$work/output"; find RPMS SRPMS -type f -name '*.rpm' -exec sha256sum {} + | sort >SHA256SUMS)
mv "$work/output" "$output"
rm -rf "$work"
printf 'built %s\n' "$output"
