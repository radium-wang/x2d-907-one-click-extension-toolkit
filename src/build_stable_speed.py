"""Offline speed-only delta over the byte-pinned original public v0.4.12."""
import argparse,hashlib,io,json,re,shutil,subprocess,tarfile
from pathlib import Path
from elftools.elf.elffile import ELFFile
from camera_ui_strings import english_qml,traditional_qml
from speed_levels import build as profiles,upgrade_worker
D=Path(__file__).resolve().parent
BASELINE_SHA='8592a30073cc64cc55228c1a089b3538ae39306c43e82ec12a333fdbb9d24f75'
sha=lambda raw:hashlib.sha256(raw).hexdigest()
def build(baseline,output,stock,compiler):
 raw=(baseline/'speed-bundle.json').read_bytes()
 if sha(raw)!=BASELINE_SHA:raise ValueError('Only original v0.4.12 bytes are supported')
 manifest=json.loads(raw);rows=manifest['files']+[f for group in manifest['uiLanguages'].values() for f in group]
 for f in rows:
  if sha((baseline/f['source']).read_bytes())!=f['sha256']:raise ValueError('Baseline file drift: '+f['source'])
 if output.exists():raise FileExistsError('Use a new output directory')
 shutil.copytree(baseline,output)
 (output/'previous-bundle-0.4.12.json').write_bytes(raw)
 for f in rows:(output/'previous-payloads'/f['sha256']).write_bytes((baseline/f['source']).read_bytes())
 levels=profiles(output,stock,compiler)
 worker=upgrade_worker((baseline/'speed-worker').read_text(),levels)
 (output/'speed-worker').write_text(worker)
 subprocess.run(['sh','-n',str(output/'speed-worker')],check=True)
 names={'AutoBrightnessController':'X2dAutoBrightnessController'}
 for name in ('PlayPage','SpeedBuffController'):
  text=(D/(name+'.qml')).read_text()
  text=re.sub(r'\bAutoBrightnessController\b',names['AutoBrightnessController'],text)
  for language,content in (('',text),('.en',english_qml(text)),('.zh-Hant',traditional_qml(text))):
   (output/('X2d'+name+language+'.qml')).write_text(content)
 subprocess.run([compiler,'-target','aarch64-linux-gnu','-fuse-ld=lld','-O2','-g0','-fPIC','-shared','-nostdlib',
  '-fno-stack-protector','-fno-builtin','-Wl,--strip-all','-Wl,--no-undefined','-Wl,-z,noexecstack',
  '-Wl,-soname,libx2d_speed_server.so',str(D/'speed-buff-server.c'),str(output/'libc.so'),str(output/'libdl.so'),
  '-o',str(output/'libx2d_speed_server.so')],check=True)
 elf=ELFFile(io.BytesIO((output/'libx2d_speed_server.so').read_bytes()))
 exports=set()
 for name in ('libc.so','libdl.so'):
  lib=ELFFile(io.BytesIO((baseline/name).read_bytes()));exports.update(s.name for s in lib.get_section_by_name('.dynsym').iter_symbols() if s['st_shndx']!='SHN_UNDEF')
 imports={s.name for s in elf.get_section_by_name('.dynsym').iter_symbols() if s.name and s['st_shndx']=='SHN_UNDEF'}
 if elf['e_machine']!='EM_AARCH64' or imports-exports or any((s['p_flags']&3)==3 for s in elf.iter_segments()):raise ValueError('Service ABI validation failed')
 for f in rows:
  data=(output/f['source']).read_bytes();f.update(sha256=sha(data),bytes=len(data))
 for level in ('low','medium'):
  f=levels['levels'][level];manifest['files'].append(dict(source=f['source'],target='/system/etc/x2d-speed-buff/candidate-'+level,sha256=f['sha256'],bytes=1068))
 manifest.update(version='0.4.17',softwareBaseline='v0.4.12',localBuild='stable-speed-test-1',speedLevels=levels,multipliers=[2.5,2,1.5])
 assert manifest['features']==['afc','speed-buff','auto-rear-brightness'] and not manifest.get('aft') and not manifest.get('eyeMemory')
 (output/'speed-bundle.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
 with tarfile.open(output/'speed-bundle.tar.gz','w:gz') as tar:
  for name in sorted({f['source'] for f in rows+manifest['files']}|{'speed-bundle.json'}):tar.add(output/name,arcname=name,recursive=False)
 changed=[f['target'] for f in manifest['files'] if not (baseline/f['source']).exists() or (baseline/f['source']).read_bytes()!=(output/f['source']).read_bytes()]
 result=dict(status='PASS',baselineManifestSha256=BASELINE_SHA,payloadManifestSha256=sha((output/'speed-bundle.json').read_bytes()),deviceAccessed=False,changedTargets=changed,serviceImports=sorted(imports))
 (output/'stable-build-validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for name in ('baseline','output','stock'):p.add_argument('--'+name,type=Path,required=True)
 p.add_argument('--compiler',required=True);a=p.parse_args();build(a.baseline,a.output,a.stock,a.compiler)
