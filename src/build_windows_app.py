"""在 Mac 上离线交叉构建 Windows x64 原生启动器与自带运行库的 ZIP。"""
import argparse, hashlib, json, os, shutil, subprocess, zipfile
from pathlib import Path
from windows_app import VERSION
D = Path(__file__).resolve().parent
PAYLOAD = Path(os.environ.get('X2D_PAYLOAD_DIR', str(D/'native-package')))

def run(*args):
    result = subprocess.run(list(map(str, args)), capture_output=True, text=True)
    if result.returncode: raise RuntimeError(result.stderr or result.stdout)
    return result.stdout

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def build(inputs, pyusb, llvm):
    out = D / 'outputs/windows-app'
    out.mkdir(parents=True, exist_ok=True)
    builddir = out / 'launcher-build'; builddir.mkdir(exist_ok=True)
    root = out / 'x2d-907一键扩展功能-工具包-Windows-x64'
    if root.exists(): shutil.rmtree(root)
    root.mkdir()
    runtime = root / 'runtime'; runtime.mkdir()
    assert sha(inputs / 'python-embed.zip') == 'd1f04d990aee1253d8569e8e5104e30fa9f5fa830899f14843448872d936a2cf'
    assert sha(inputs / 'libusb.7z') == '7fb1dfec805b97983763d7d0ae244320da12add1003d4249c96cc4d586398c79'
    with zipfile.ZipFile(inputs / 'python-embed.zip') as z:
        assert all('/' not in n and '\\' not in n and n not in ('..', '.') for n in z.namelist())
        z.extractall(runtime)
    (runtime / 'python313._pth').write_text('python313.zip\n.\n..\n', encoding='ascii')
    for name in ('app_updates.py', 'app_settings.py', 'reinstall_confirmation.py', 'windows_app.py', 'x2d_play_software.py', 'windows_factory_usb.py', 'windows_connection.py', 'localization.py', 'translations.json'):
        shutil.copy2(D / name, root / name)
    transport = D / 'transport'
    for name in ('collect_x2d_af_usb.py',):
        shutil.copy2(transport / name, root / name)
    shutil.copytree(pyusb, root / 'usb', ignore=shutil.ignore_patterns('__pycache__'))
    bindir = root / 'bin'; bindir.mkdir()
    licenses = root / 'licenses'; licenses.mkdir()
    with zipfile.ZipFile(inputs / 'platform-tools.zip') as z:
        for name in ('adb.exe', 'AdbWinApi.dll', 'AdbWinUsbApi.dll'):
            (bindir / name).write_bytes(z.read('platform-tools/' + name))
        (licenses / 'Android-platform-tools.txt').write_bytes(z.read('platform-tools/NOTICE.txt'))
        adbversion = z.read('platform-tools/source.properties').decode().strip()
    lib = root / 'lib'; lib.mkdir()
    shutil.copy2(inputs / 'libusb/VS2022/MS64/dll/libusb-1.0.dll', lib / 'libusb-1.0.dll')
    # DLL loader can use the bundled VC runtime beside the USB library as well.
    shutil.copy2(runtime / 'vcruntime140.dll', lib / 'vcruntime140.dll')
    shutil.copy2(next(pyusb.parent.glob('pyusb-*.dist-info/LICENSE')), licenses / 'PyUSB.txt')
    shutil.copy2(inputs / 'libusb-license.txt', licenses / 'libusb.txt')
    shutil.copy2(runtime / 'LICENSE.txt', licenses / 'Python.txt')
    driver = root / 'driver'; driver.mkdir()
    provenance = json.loads((inputs / 'camera-winusb/provenance.json').read_text())
    for name in ('camera-driver.exe','libwdi.dll','libwdi-source.zip'):
        source = inputs / 'camera-winusb' / name
        assert sha(source) == provenance['files'][name]
        shutil.copy2(source,driver/name)
    shutil.copy2(inputs / 'camera-winusb/provenance.json',driver/'provenance.json')
    for name in ('COPYING','COPYING-LGPL'):
        shutil.copy2(inputs / 'camera-winusb/source/libwdi-1.5.1' / name,licenses / ('libwdi-'+name+'.txt'))
    native = root / 'native-package'; native.mkdir()
    manifest = json.loads((PAYLOAD/'speed-bundle.json').read_text())
    english={f['source'] for f in (manifest.get('uiLanguages') or {}).get('en') or []}
    for source in {f['source'] for f in manifest['files']} | english | {'speed-bundle.json','speed-bundle.tar.gz','previous-bundle.json','previous-speed-server.so','previous-bundle-0.3.0.json','previous-bundle-0.3.2.json','previous-bundle-0.3.3.json'}:
        shutil.copy2(PAYLOAD / source, native / source)
    shutil.copytree(PAYLOAD/'previous-payloads',native / 'previous-payloads')
    # Generate import libraries with lld-link. Stub DLLs are build artifacts only.
    linker = shutil.which('lld-link') or str(llvm / 'lld-link')
    for dll, exports in {'kernel32':['GetModuleFileNameW','CreateProcessW','CloseHandle','ExitProcess'],
                         'user32':['MessageBoxW']}.items():
        definition = builddir / (dll + '.def')
        definition.write_text('LIBRARY '+dll+'.dll\nEXPORTS\n'+'\n'.join(exports)+'\n')
        run(linker, '/dll', '/noentry', '/machine:x64', '/def:'+str(definition),
            '/out:'+str(builddir / (dll + '.dll')), '/implib:'+str(builddir / (dll + '.lib')))
    obj = builddir / 'launcher.obj'
    run(llvm / 'clang', '--target=x86_64-pc-windows-msvc', '-Oz', '-ffreestanding',
        '-fno-stack-protector', '-fno-builtin', '-c', D / 'windows_launcher.c', '-o', obj)
    executable = root / 'x2d-907一键扩展功能-工具包.exe'
    run(linker, obj, builddir / 'kernel32.lib', builddir / 'user32.lib',
        '/out:'+str(executable), '/entry:mainCRTStartup', '/subsystem:windows,6.02',
        '/manifest:embed', '/manifestuac:level="requireAdministrator" uiAccess="false"',
        '/nodefaultlib', '/machine:x64', '/dynamicbase', '/nxcompat', '/highentropyva', '/opt:ref')
    # Python/UI/USB are x64; Google's adb and its companion DLLs are 32-bit processes.
    # Windows x64 supports the original vendor's complete adb set through WOW64.
    system = {'kernel32.dll','user32.dll','gdi32.dll','advapi32.dll','shell32.dll','ole32.dll',
              'ws2_32.dll','ntdll.dll','bcrypt.dll','secur32.dll','iphlpapi.dll','winmm.dll',
              'setupapi.dll','cfgmgr32.dll','msvcrt.dll','winusb.dll','version.dll','shlwapi.dll',
              'crypt32.dll','comdlg32.dll','comctl32.dll','wtsapi32.dll','psapi.dll','wldap32.dll',
              'normaliz.dll','dbghelp.dll','mswsock.dll','dnsapi.dll','rpcrt4.dll','netapi32.dll',
              'powrprof.dll','ucrtbase.dll','propsys.dll','oleaut32.dll','bcryptprimitives.dll'}
    packaged = {p.name.lower() for p in root.rglob('*') if p.is_file()}
    audits = []
    for path in root.rglob('*'):
        if path.suffix.lower() not in ('.exe','.dll','.pyd'): continue
        output = run(llvm / 'llvm-readobj', '--file-headers', '--coff-imports', path)
        architecture = 'x86' if path.parent == bindir else 'x86_64'
        machine = 'IMAGE_FILE_MACHINE_I386' if architecture == 'x86' else 'IMAGE_FILE_MACHINE_AMD64'
        assert 'Machine: '+machine in output, path
        imports = [line.strip().split(': ',1)[1].lower() for line in output.splitlines() if line.strip().startswith('Name: ')]
        missing = [n for n in imports if n not in system and n not in packaged and not n.startswith(('api-ms-win-', 'ext-ms-win-'))]
        if missing: raise RuntimeError('Missing imports for '+path.name+': '+str(missing))
        audits.append(dict(file=path.relative_to(root).as_posix(), architecture=architecture, sha256=sha(path), imports=imports))
    (root / '版本与校验.json').write_text(json.dumps(dict(version=VERSION,architecture='x86_64',
        models=manifest['compatibleModels'],firmware='4.2.0',python='3.13.15',libusb='1.0.30',
        adb=adbversion,driverPreparation='camera Interface 3 only; libwdi 1.5.1 modified native WinUSB; Windows test pending',verification='cross-build and offline checks; Windows device test pending',
        binaries=audits),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    shutil.copy2(D / 'WINDOWS-READ-ME.txt', root / '使用说明.txt')
    archive = out / ('x2d-907-extension-toolkit-Windows-x64-'+VERSION+'.zip')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for path in sorted(root.rglob('*')):
            if path.is_file(): z.write(path, path.relative_to(out).as_posix())
    (out / 'SHA256.txt').write_text(sha(archive)+'  '+archive.name+'\n')
    print('Windows x64:', len(audits), 'PE files audited;', archive)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--pyusb', type=Path, required=True)
    parser.add_argument('--llvm', type=Path, required=True)
    args = parser.parse_args()
    build(args.inputs.resolve(), args.pyusb.resolve(), args.llvm.resolve())
