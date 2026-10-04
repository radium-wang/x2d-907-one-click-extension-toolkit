#!/usr/bin/env python3
"""离线构建 macOS 13+ 通用应用，递归打包并检查全部动态库。"""
import argparse, json, os, plistlib, shutil, subprocess, re
from pathlib import Path
D = Path(__file__).resolve().parent
PAYLOAD = Path(os.environ.get('X2D_PAYLOAD_DIR', str(D/'native-package')))
VERSION = '0.4.4'
ARCHES = {'arm64', 'x86_64'}
MINIMUM = (13, 0)

def run(*args):
    result=subprocess.run(list(map(str,args)),capture_output=True,text=True)
    if result.returncode: raise RuntimeError(result.stderr or result.stdout)
    return result.stdout

def dependencies(path):
    return list(dict.fromkeys(line.strip().split(' (compatibility')[0] for line in run('otool','-L',path).splitlines() if line.startswith('\t')))

def load_commands(path):
    return run('otool', '-l', path)

def minimum_versions(output):
    # Both modern LC_BUILD_VERSION and legacy LC_VERSION_MIN_MACOSX matter.
    values = re.findall(r'cmd LC_BUILD_VERSION.*?\n\s*minos ([\d.]+)', output, re.S)
    values += re.findall(r'cmd LC_VERSION_MIN_MACOSX\n\s*cmdsize \d+\n\s*version ([\d.]+)', output)
    return [tuple((list(map(int, value.split('.'))) + [0, 0])[:3]) for value in values]

def resolve_dependency(dep, origin, framework):
    if dep.startswith('/Library/Frameworks/Python.framework/') and framework:
        return (framework / dep.split('/Python.framework/', 1)[1]).resolve()
    if dep.startswith('@loader_path/'):
        return (origin.parent / dep[len('@loader_path/'):]).resolve()
    if dep.startswith('@rpath/'):
        paths = re.findall(r'cmd LC_RPATH\n\s*cmdsize \d+\n\s*path (.*?) \(offset', load_commands(origin))
        for path in paths:
            candidate = resolve_dependency(path + '/' + dep[len('@rpath/'):], origin, framework)
            if candidate.exists(): return candidate
        raise RuntimeError('Unresolved rpath dependency: ' + dep)
    if dep.startswith('@'):
        raise RuntimeError('Unsupported dependency: ' + dep)
    return Path(dep).resolve()

def build(python, adb, libusb, pyusb, framework=None, libusb_license=None):
    out = D/'outputs/mac-app'; out.mkdir(parents=True, exist_ok=True)
    app = out/'x2d-907一键扩展功能-工具包.app'
    if app.exists(): shutil.rmtree(app)
    c=app/'Contents'; r=c/'Resources'; m=c/'MacOS'
    r.mkdir(parents=True); m.mkdir()
    runtime=r/'runtime'; (runtime/'bin').mkdir(parents=True); (runtime/'lib').mkdir()
    if framework:
        framework = framework.resolve()
        base = framework/'Versions/3.13'
        info = dict(exe=str(base/'Resources/Python.app/Contents/MacOS/Python'), stdlib=str(base/'lib/python3.13'))
    else:
        info=json.loads(run(python,'-c','import json,sys,sysconfig;print(json.dumps(dict(exe=sys.base_prefix+"/Resources/Python.app/Contents/MacOS/Python",stdlib=sysconfig.get_path("stdlib"))))'))
    exe=runtime/'bin/python3.13'; shutil.copy2(info['exe'],exe)
    stdlib=runtime/'lib/python3.13'
    shutil.copytree(info['stdlib'], stdlib, ignore=shutil.ignore_patterns('site-packages','__pycache__','test','tests','idlelib','tkinter','turtledemo','config-*','_tkinter*.so','_test*.so'))
    shutil.copytree(pyusb,r/'usb',ignore=shutil.ignore_patterns('__pycache__'))
    (r/'bin').mkdir(); shutil.copy2(adb.resolve(),r/'bin/adb')
    (r/'lib').mkdir(); shutil.copy2(libusb.resolve(),r/'lib/libusb-1.0.dylib')
    transport=D/'transport'
    for name in ('collect_x2d_af_usb.py',):
        shutil.copy2(transport/name,r/name)
    shutil.copy2(D/'x2d_play_software.py',r/'x2d_play_software.py')
    shutil.copy2(D/'translations.json',r/'translations.json')
    shutil.copy2(D/'app_updates.py',r/'app_updates.py')
    shutil.copy2(D/'reinstall_confirmation.py',r/'reinstall_confirmation.py')
    native=r/'native-package'; native.mkdir()
    manifest=json.loads((PAYLOAD/'speed-bundle.json').read_text())
    english={f['source'] for f in (manifest.get('uiLanguages') or {}).get('en') or []}
    for source in {f['source'] for f in manifest['files']} | english | {'speed-bundle.json','speed-bundle.tar.gz','previous-bundle.json','previous-speed-server.so','previous-bundle-0.3.0.json','previous-bundle-0.3.2.json','previous-bundle-0.3.3.json','previous-bundle-0.4.2.json','previous-bundle-auto-brightness.json','previous-bundle-brightness-display.json'}:
        shutil.copy2(PAYLOAD/source,native/source)
    shutil.copytree(PAYLOAD/'previous-payloads',native/'previous-payloads')
    # Relocate every non-system Mach-O dependency. Never rely on Homebrew at runtime.
    queue=[exe]+list(stdlib.rglob('*.so'))+[r/'lib/libusb-1.0.dylib',r/'bin/adb']
    origins={exe:Path(info['exe']).resolve(), r/'lib/libusb-1.0.dylib':libusb.resolve(), r/'bin/adb':adb.resolve()}
    origins.update({path:Path(info['stdlib'])/path.relative_to(stdlib) for path in stdlib.rglob('*.so')})
    mapping={origin:dest for dest,origin in origins.items()}; visited=set(); binaries=[]
    while queue:
        dest=queue.pop(0)
        if dest in visited: continue
        visited.add(dest); binaries.append(dest)
        for dep in dependencies(dest):
            if dep.startswith(('/usr/lib/','/System/Library/')): continue
            source=resolve_dependency(dep, origins[dest], framework)
            # A dylib may list its own install name as the first otool row.
            if mapping.get(source)==dest or (source.name==dest.name and source.read_bytes()==dest.read_bytes()): continue
            if source not in mapping:
                name='Python' if source.name=='Python' else source.name
                target=runtime/'lib'/name
                if target.exists(): raise RuntimeError('Dependency filename collision: '+name)
                shutil.copy2(source,target); mapping[source]=target; origins[target]=source; queue.append(target)
            target=mapping[source]
            relative=os.path.relpath(target,dest.parent)
            run('install_name_tool','-change',dep,'@loader_path/'+relative,dest)
    minimum=MINIMUM
    for binary in binaries:
        if binary.suffix in ('.so','.dylib') or binary.name=='Python':
            run('install_name_tool','-id','@loader_path/'+binary.name,binary)
        # Removing inherited absolute rpaths helps make missing bundled libraries visible.
        output=run('otool','-l',binary).splitlines()
        versions=minimum_versions('\n'.join(output))
        if not versions: raise RuntimeError('Missing deployment target: '+str(binary))
        for version in versions:
            if version > MINIMUM+(0,): raise RuntimeError('Dependency requires newer macOS: '+str(binary)+' '+str(version))
        if not ARCHES.issubset(set(run('lipo', '-archs', binary).split())):
            raise RuntimeError('Missing universal architecture: '+str(binary))
        for i,line in enumerate(output):
            if line.strip()=='cmd LC_RPATH':
                path=output[i+2].strip().split('path ',1)[-1].split(' (offset')[0]
                if path.startswith(('/opt/homebrew/','/Library/Frameworks/')): run('install_name_tool','-delete_rpath',path,binary)
        run('codesign','--force','--sign','-',binary)
    slices=[]
    for arch in sorted(ARCHES):
        target=out/('X2DPlay-'+arch)
        run('swiftc','-O','-module-cache-path',out/'swift-cache','-target',arch+'-apple-macosx13.0',D/'MacApp.swift','-o',target)
        slices.append(target)
    run('lipo','-create',*slices,'-output',m/'X2DPlay')
    binaries.append(m/'X2DPlay')
    (c/'Info.plist').write_bytes(plistlib.dumps({
        'CFBundleName':'x2d/907一键扩展功能-工具包','CFBundleDisplayName':'x2d/907一键扩展功能-工具包',
        'CFBundleIdentifier':'local.x2d.play','CFBundleExecutable':'X2DPlay',
        'CFBundlePackageType':'APPL','CFBundleShortVersionString':VERSION,
        'CFBundleVersion':'20','LSMinimumSystemVersion':'.'.join(map(str,minimum)),
        'NSHighResolutionCapable':True,'NSHumanReadableCopyright':'Local experimental X2D / 907X 100C 4.2.0 tool'}))
    licenses=r/'licenses'; licenses.mkdir()
    shutil.copy2(D.parent/'LICENSE',licenses/'X2D-907-Toolkit.txt')
    shutil.copy2(D.parent/'THIRD_PARTY_NOTICES.md',licenses/'THIRD_PARTY_NOTICES.md')
    shutil.copy2(D/'brightness/LICENSE',licenses/'X2D-New-Extension.txt')
    shutil.copy2(next(pyusb.parent.glob('pyusb-*.dist-info/LICENSE')),licenses/'PyUSB.txt')
    shutil.copy2(libusb_license or libusb.resolve().parent.parent/'COPYING',licenses/'libusb.txt')
    python_license=Path(info['stdlib'])/'LICENSE.txt'
    if python_license.exists(): shutil.copy2(python_license,licenses/'Python.txt')
    if framework:
        # The official installer includes notices for statically bundled libraries too.
        package=framework.parent.parent
        shutil.copy2(package/'Python_Documentation.pkg/Payload/_sources/license.rst.txt',licenses/'Python-third-party.txt')
        shutil.copy2(package/'Resources/License.rtf',licenses/'Python-installer.rtf')
    notice=adb.resolve().parent/'NOTICE.txt'
    if notice.exists(): shutil.copy2(notice,licenses/'Android-platform-tools.txt')
    for source in mapping:
        roots=[parent for parent in source.parents if parent.parent.parent.name=='Cellar']
        if roots:
            root=roots[0]
            names=list(root.glob('LICENSE*'))+list(root.glob('COPYING*'))+list(root.glob('COPYRIGHT*'))
            if root.parent.name=='sqlite': names+=list(root.glob('README*'))
            for notice in names:
                if notice.is_file(): shutil.copy2(notice,licenses/(root.parent.name+'-'+notice.name))
    run('codesign','--force','--sign','-',app)
    run('codesign','--verify','--deep','--strict',app)
    env=os.environ.copy(); env.pop('X2D_PAYLOAD_DIR',None); env.update(PYTHONHOME=str(runtime),PYTHONPATH=str(r),PYTHONNOUSERSITE='1')
    subprocess.run([str(exe),'-B','-c','import ctypes,json,usb.core;ctypes.CDLL("'+str(r/'lib/libusb-1.0.dylib')+'");print("PACKAGED_RUNTIME_OK")'],env=env,check=True)
    audit=[]
    for binary in binaries:
        versions=minimum_versions(load_commands(binary))
        if not versions or any(v>MINIMUM+(0,) for v in versions): raise RuntimeError('Invalid deployment target: '+str(binary))
        for dep in dependencies(binary):
            if dep.startswith(('/usr/lib/','/System/Library/')): continue
            if not dep.startswith('@loader_path/'): raise RuntimeError('Unrelocated dependency: '+dep)
            target=(binary.parent/dep[len('@loader_path/'):]).resolve()
            if app.resolve() not in target.parents or not target.is_file(): raise RuntimeError('Missing bundled dependency: '+dep)
        audit.append(dict(path=str(binary.relative_to(app)),architectures=run('lipo','-archs',binary).split(),minimumVersions=versions,dependencies=dependencies(binary)))
    (out/'macOS-compatibility-audit.json').write_text(json.dumps(dict(version=VERSION,minimumMacOS='13.0',binaries=audit),indent=2)+'\n')
    zipfile=out/('x2d-907-extension-toolkit-macOS-Universal-'+VERSION+'.zip')
    readme=out/'使用说明-macOS.txt'
    shutil.copy2(D/'MAC-READ-ME.txt',readme)
    if zipfile.exists(): zipfile.unlink()
    # Explicit UTF-8 filenames, UNIX executable modes; no resource forks required.
    import zipfile as zip_module
    with zip_module.ZipFile(zipfile, 'w', zip_module.ZIP_DEFLATED, compresslevel=6) as archive:
        archive.write(readme,readme.name)
        archive.write(app, app.name)
        for path in sorted(app.rglob('*')):
            archive.write(path, str(path.relative_to(out)))
    import hashlib
    (out/'SHA256.txt').write_text(hashlib.sha256(zipfile.read_bytes()).hexdigest()+'  '+zipfile.name+'\n')
    print(app);print(zipfile)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    inputs=p.add_mutually_exclusive_group(required=True)
    inputs.add_argument('--python',type=Path)
    p.add_argument('--adb',type=Path,required=True)
    p.add_argument('--libusb',type=Path,required=True)
    p.add_argument('--pyusb',type=Path,required=True)
    inputs.add_argument('--python-framework',type=Path,help='解包后的官方 Python.framework；无需安装或执行安装脚本')
    p.add_argument('--libusb-license',type=Path)
    a=p.parse_args();build(a.python,a.adb,a.libusb,a.pyusb,a.python_framework,a.libusb_license)
