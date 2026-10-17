# SPDX-License-Identifier: Apache-2.0
import os,pathlib,gzip,subprocess,tempfile,json,stat
BINARY=os.environ['LUMA_ABOOT_OVERLAY_CONTROL']
ANCHOR='etc/luma-fp6-firmware-manifest.sha256'
def cpio(entries):
 data=bytearray()
 for inode,(name,body,mode,uid) in enumerate([*entries,('TRAILER!!!',b'',0,0)],1):
  encoded=name.encode()+b'\0'
  fields=[inode,mode,uid,0,1,0,len(body),0,0,0,0,len(encoded),0]
  data.extend(b'070701'+b''.join(('%08x'%v).encode() for v in fields)+encoded)
  data.extend(b'\0'*(-len(data)%4));data.extend(body);data.extend(b'\0'*(-len(data)%4))
 return gzip.compress(data,mtime=0)
rows=[]
with tempfile.TemporaryDirectory(prefix='luma-native-overlay-') as tmp:
 root=pathlib.Path(tmp);deployment=root/'ostree/deploy/luma/deploy/fixture';expected=deployment/'usr/lib/luma/fp6-firmware-manifest.sha256';expected.parent.mkdir(parents=True)
 digest=b'a'*64+b'\n';expected.write_bytes(digest)
 overlay=root/'boot/ostree/initramfs-overlays/final.img';overlay.parent.mkdir(parents=True)
 good=(ANCHOR,digest,stat.S_IFREG|0o644,0)
 def check(name,entries,code,paths=('/ostree/initramfs-overlays/final.img',)):
  overlay.write_bytes(cpio(entries))
  proc=subprocess.run([BINARY,str(root),str(deployment),*paths],capture_output=True,timeout=5)
  assert proc.returncode==code,(name,proc.returncode,proc.stderr)
  rows.append({'name':name,'exit':proc.returncode,'passed':True})
 check('real_gzip_newc_anchor',[good],0)
 check('dot_prefix_anchor',[('./'+ANCHOR,*good[1:])],0)
 check('bootprefix_overlay',[good],0,('/boot/ostree/initramfs-overlays/final.img',))
 check('missing_anchor',[],1)
 check('duplicate_anchor',[good,good],1)
 check('wrong_hash',[(ANCHOR,b'b'*64+b'\n',good[2],0)],1)
 check('wrong_owner',[(ANCHOR,digest,good[2],1000)],1)
 check('unsafe_mode',[(ANCHOR,digest,stat.S_IFREG|0o666,0)],1)
 check('symlink_anchor',[(ANCHOR,digest,stat.S_IFLNK|0o777,0)],1)
 check('wrong_length',[(ANCHOR,digest+b'x',good[2],0)],1)
 check('absolute_alias',[good,('/'+ANCHOR,*good[1:])],1)
 check('traversal_alias',[good,('etc/../'+ANCHOR,*good[1:])],1)
 check('no_tracked_overlay',[good],1,())
 prior=overlay.with_name('prior.img');prior.write_bytes(cpio([good]))
 check('only_prior_overlay_has_anchor',[],1,('/ostree/initramfs-overlays/prior.img','/ostree/initramfs-overlays/final.img'))
 os.link(expected,expected.with_name('immutable-object-hardlink'))
 check('legitimate_immutable_hardlink',[good],0)
 expected.write_bytes(b'not-a-digest\n');check('invalid_signed_requirement',[good],1)
print(json.dumps({'result':'PASS','count':len(rows),'controls':rows,'scope':'actual maintained C guard, native libarchive and gzip/newc bytes; no boot action'},indent=2))
