#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Render reviewed Tokay bootstrap digests; never access or write a phone."""
import argparse,json,re
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument("manifest",type=Path);p.add_argument("output",type=Path);a=p.parse_args()
template=Path(__file__).resolve().parents[2]/"config/mobile/tokay-physical/ram-init.in"
text=template.read_text();required=set(re.findall(r"@(SHA256_[0-9]+)@",text));values=json.loads(a.manifest.read_text())["digests"]
if set(values)!=required or not all(isinstance(v,str) and re.fullmatch(r"[0-9a-f]{64}",v) for v in values.values()):p.error("Supply exactly the required lowercase SHA256 digests from reviewed local inputs")
for key,value in values.items():text=text.replace("@"+key+"@",value)
if re.search(r"@SHA256_[0-9]+@",text):raise SystemExit("Unresolved digest")
with a.output.open("x") as f:f.write(text)
a.output.chmod(0o700)
