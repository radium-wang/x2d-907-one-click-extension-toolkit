"""Build a fixed X2D 4.2.0 software bundle offline; no device access."""
from pathlib import Path
import hashlib,json,tarfile,subprocess,os,shutil,io
from elftools.elf.elffile import ELFFile
D=Path(__file__).resolve().parent
O=Path(os.environ.get('X2D_PAYLOAD_DIR', str(D/'native-package')))
sha=lambda b:hashlib.sha256(b).hexdigest()
# Rebuild the service from source so boot behavior is never a stale binary.
compiler=os.environ.get('X2D_CC') or shutil.which('clang')
if not compiler: raise RuntimeError('Need clang / X2D_CC for the AArch64 service')
subprocess.run([compiler,'-target','aarch64-linux-gnu','-fuse-ld=lld','-O2','-g0',
    '-fPIC','-shared','-nostdlib','-fno-stack-protector','-fno-builtin',
    '-Wl,--strip-all','-Wl,--no-undefined','-Wl,-z,noexecstack',
    '-Wl,-soname,libx2d_speed_server.so',str(D/'speed-buff-server.c'),
    str(O/'libc.so'),str(O/'libdl.so'),'-o',str(O/'libx2d_speed_server.so')],check=True)
service=ELFFile(io.BytesIO((O/'libx2d_speed_server.so').read_bytes()))
assert service['e_machine']=='EM_AARCH64'
assert not any((segment['p_flags']&3)==3 for segment in service.iter_segments())
exports=set()
for library in ('libc.so','libdl.so'):
    elf=ELFFile(io.BytesIO((O/library).read_bytes()))
    exports.update(symbol.name for symbol in elf.get_section_by_name('.dynsym').iter_symbols()
                   if symbol['st_shndx']!='SHN_UNDEF')
imports={symbol.name for symbol in service.get_section_by_name('.dynsym').iter_symbols()
         if symbol.name and symbol['st_shndx']=='SHN_UNDEF'}
assert imports <= exports, imports-exports
(O/'speed-worker').write_bytes((D/'speed-buff-worker.sh').read_bytes())
backend=(D/'device_backend.sh').read_text()
lines=backend.splitlines(keepends=True)
lens=[line for line in lines if '${EXPECTED_PRODUCT:-81470}' in line]
assert len(lens)==1
(O/'speed-backend').write_text(''.join(line for line in lines if line not in lens))
(O/'speed-transaction').write_bytes((D/'transaction.sh').read_bytes())
package=json.loads((O/'package.json').read_text())
files=package['files']
ui_languages=package.get('uiLanguages') or {}
english=ui_languages.get('en') or []
assert english, 'package.json is missing uiLanguages.en camera UI siblings'
for src,target in {
 'libx2d_speed_server.so':'/system/lib64/libx2d_speed_server.so',
 'speed-worker':'/system/etc/x2d-speed-buff/worker',
 'speed-backend':'/system/etc/x2d-speed-buff/backend',
 'speed-transaction':'/system/etc/x2d-speed-buff/transaction',
 'speed-original':'/system/etc/x2d-speed-buff/original',
 'speed-candidate':'/system/etc/x2d-speed-buff/candidate',
}.items():
 data=(O/src).read_bytes();files.append(dict(source=src,target=target,sha256=sha(data),bytes=len(data)))
for f in files:assert sha((O/f['source']).read_bytes())==f['sha256']
for f in english:assert sha((O/f['source']).read_bytes())==f['sha256']
chinese_targets={f['target'] for f in files}
assert {f['target'] for f in english}<=chinese_targets
for name in ('speed-worker','speed-backend','speed-transaction'):
 subprocess.run(['sh','-n',str(O/name)],check=True)
manifest=dict(format=3,model='X2D 100C',firmware='4.2.0',guiSha256='16391452abdc69de9e0807e065c0f4ab3f1ccb5fc288f6fc4e6f5cb3bdca12e0',files=files,entryIndex=11,multipliers=[3,3,2],lensRestriction=False, serviceExecutable='/system/bin/camera-gui', features=['afc','speed-buff'])
manifest['entryIndexesByModel']={'X2D 100C':11,'907X & CFV 100C':10}
manifest['compatibleModels']=['X2D 100C','907X & CFV 100C']
manifest['validation']={'X2D 100C':'prior-menu-and-buff-device-tested; startup-focus-mode-fix-awaiting-device-test','907X & CFV 100C':'USB-and-service-installation-user-reported; ten-item-menu-fix-awaiting-device-test'}
manifest['uiLanguages']=dict(en=english)
(O/'speed-bundle.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
archive_names={f['source'] for f in files}|{f['source'] for f in english}
with tarfile.open(O/'speed-bundle.tar.gz','w:gz') as tar:
 for name in sorted(archive_names):tar.add(O/name,arcname=name,recursive=False)
 tar.add(O/'speed-bundle.json',arcname='speed-bundle.json',recursive=False)
print('Verified bundle:',len(files),'files,',len(english),'english UI files,',
      (O/'speed-bundle.tar.gz').stat().st_size,'bytes')
