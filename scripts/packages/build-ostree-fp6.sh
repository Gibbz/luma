#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
repo_root=$(CDPATH='' cd -- "$(dirname -- "$0")/../.." && pwd)
. "$repo_root/config/desktop/inputs.env"
[ "$(uname -s)" = Linux ] || { echo 'Build OSTree on a native Linux builder' >&2; exit 1; }
arch=$(uname -m)
case "$arch" in aarch64|x86_64) ;; *) echo 'Unsupported native build architecture' >&2; exit 1;; esac
for tool in python3 curl patch tar sha256sum podman; do command -v "$tool" >/dev/null; done
python3 - "$repo_root/config/mobile/fp6-ostree-source.json" "$repo_root/packaging/rpm/ostree-fp6.spec" <<'PY_CHECK'
import json, re, sys
config = json.load(open(sys.argv[1]))
spec = open(sys.argv[2]).read()
assert re.search(r'^Version:\s*' + re.escape(config['version']) + r'$', spec, re.M)
assert re.search(r'^Release:\s*' + re.escape(config['release']) + r'%\{\?dist\}$', spec, re.M)
PY_CHECK
output="$repo_root/build/packages/ostree/$arch"
mkdir -p "$(dirname "$output")"
work=$(mktemp -d "$output.work.XXXXXX")
# Preserve a failed normal build and its logs for diagnosis.
trap 'printf "OSTree build workspace retained: %s\n" "$work" >&2' EXIT
mkdir -p "$work/cache" "$work/rpmbuild"/{BUILD,BUILDROOT,RPMS,SOURCES,SPECS,SRPMS}
python3 - "$repo_root/config/mobile/fp6-ostree-source.json" >"$work/archives.tsv" <<'PY'
import json, sys
for row in json.load(open(sys.argv[1]))['archives']:
    print(row['name'], row['url'], row['sha256'], sep='\t')
PY
while IFS=$'\t' read -r name url digest; do
  curl --fail --location --retry 3 --output "$work/cache/$name.tar.gz" "$url"
  printf '%s  %s\n' "$digest" "$work/cache/$name.tar.gz" | sha256sum -c -
done <"$work/archives.tsv"
version=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' "$repo_root/config/mobile/fp6-ostree-source.json")
python3 "$repo_root/scripts/packages/prepare-ostree-fp6-source.py" --cache "$work/cache" --output "$work/libostree-$version" >"$work/source-admission.json"
COPYFILE_DISABLE=1 tar --sort=name --owner=0 --group=0 --numeric-owner \
  --mtime='2026-10-14 00:00:00Z' -C "$work" -czf "$work/rpmbuild/SOURCES/libostree-$version.tar.gz" "libostree-$version"
install -m 0644 "$repo_root/packaging/rpm/ostree-fp6.spec" "$work/rpmbuild/SPECS/ostree.spec"
"$repo_root/scripts/packages/run-in-rpm-builder.sh" "$work/rpmbuild" "$FEDORA_RPM_BUILD_CONTAINER" '
  set -euo pipefail
  dnf5 -y install rpm-build dnf5-plugins
  dnf5 -y builddep SPECS/ostree.spec
  rpmbuild -ba --define "_topdir $PWD" SPECS/ostree.spec
' >"$work/normal.log" 2>&1
# Do not replace a previous package cohort implicitly.
[ ! -e "$output" ] || { echo "Output already exists: $output; qualified build retained at $work" >&2; exit 1; }
qualified="$work/qualified-output"
mkdir "$qualified"
cp -a "$work/rpmbuild/RPMS" "$work/rpmbuild/SRPMS" "$qualified/"
cp "$work/source-admission.json" "$work/normal.log" "$qualified/"
(cd "$qualified"; find RPMS SRPMS -type f -name '*.rpm' -exec sha256sum {} + | sort >SHA256SUMS)
python3 - "$qualified" "$output" <<'PY_PUBLISH'
from pathlib import Path
import os, sys
source, destination = map(Path, sys.argv[1:])
if destination.exists():
    raise SystemExit('Refusing to replace an existing package output')
os.rename(source, destination)
PY_PUBLISH
printf 'Native OSTree packages: %s\n' "$output"
