"""离线构建相机限定的 WinUSB 准备工具；仅支持 Windows 10/11 x64。

输入来自 pbatard/libwdi v1.5.1 与 mstorsjo/llvm-mingw 20260922 官方源码/工具链。
WinUSB.sys 由 Windows 提供；采用微软无 coinstaller 的现代 INF 格式。
修改后的 libwdi 源码及构建材料随输出归档，保留 LGPL 重建与替换能力。
"""
import argparse, hashlib, json, shutil, subprocess, tarfile, zipfile
from pathlib import Path
D = Path(__file__).resolve().parent
SOURCE_SHA = 'a695e93db0977dfdc5c6a99a4ea91b22f9027547d0177b2a0f3075078643c929'
TOOLCHAIN_SHA = '52e5f5a7b131021d0c39a37a38fa380a1da7885cd04bd61afd0cd4ecfb8bc1f3'

def build(inputs):
    def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
    assert sha(inputs / 'libwdi-source.tar.gz') == SOURCE_SHA
    assert sha(inputs / 'llvm-mingw.tar.xz') == TOOLCHAIN_SHA
    out = inputs / 'camera-winusb'; out.mkdir(exist_ok=True)
    source = out / 'source'
    if source.exists(): shutil.rmtree(source)
    source.mkdir()
    with tarfile.open(inputs / 'libwdi-source.tar.gz') as archive:
        for member in archive.getmembers():
            assert (member.name == 'libwdi-1.5.1' or member.name.startswith('libwdi-1.5.1/')) and '..' not in Path(member.name).parts
            assert member.isfile() or member.isdir()
        archive.extractall(source)
    lib = source / 'libwdi-1.5.1/libwdi'
    toolchain = inputs / 'llvm-mingw-20260922-ucrt-macos-universal/bin'
    cc = toolchain / 'x86_64-w64-mingw32-clang'
    def run(*args):
        result = subprocess.run(list(map(str,args)),capture_output=True,text=True)
        if result.returncode: raise RuntimeError(result.stderr[-9000:])
    (lib / 'config.h').write_text('#define OPT_M64\n#define WDK_DIR "in-box Windows WinUSB"\n#define WDF_VER 1011\n#define ENABLE_LOGGING 1\n')
    # Native system WinUSB has no redistributed coinstaller to query for version.
    # This version describes our INF package, not Microsoft's kernel driver.
    path = lib / 'libwdi.c'; code = path.read_text()
    needle = '\tif (driver_type < WDI_USER) {\t// github issue #40'
    assert code.count(needle) == 1
    code = code.replace(needle, '''\tif (driver_type == WDI_WINUSB) {
        memset(&driver_version[WDI_WINUSB], 0, sizeof(VS_FIXEDFILEINFO));
        driver_version[WDI_WINUSB].dwSignature = 0xFEEF04BD;
        driver_version[WDI_WINUSB].dwFileVersionMS = 3;
        driver_version[WDI_WINUSB].dwFileVersionLS = 1 << 16;
        if (driver_info != NULL) *driver_info = driver_version[WDI_WINUSB];
        return TRUE;
    }
''' + needle)
    path.write_text(code)
    # Only our helper and the WinUSB template are embedded. No kernel binaries,
    # legacy coinstallers, alternative drivers, WCID or filter drivers.
    installer=lib/'installer.c'
    installer.write_text(installer.read_text().replace('\tdisable_system_restore(TRUE);','\t/* Preserve Windows restore-point policy. */').replace('\tdisable_system_restore(FALSE);','\t/* No policy change to restore. */'))
    run(cc,'-O2','-static','-I'+str(lib),lib/'installer.c','-o',out/'installer_x64.exe',
        '-lsetupapi','-lnewdev','-lole32','-ladvapi32')
    resources = [('.', 'installer_x64.exe', (out/'installer_x64.exe').read_bytes()),
                 ('', 'winusb.inf.in', (D/'windows_winusb.inf.in').read_bytes()),
                 ('', 'winusb.cat.in', b'# Only the generated INF uses native system WinUSB\n')]
    content = ['#include <stdint.h>\nstruct res { char *subdir; char *name; size_t size; int64_t creation_time; const unsigned char *data; };\n']
    for i, (_,_,data) in enumerate(resources):
        content.append('static const unsigned char file_%d[] = {%s};\n' % (i, ','.join(str(b) for b in data)))
    content.append('const struct res resource[] = {\n')
    for i, (subdir,name,data) in enumerate(resources):
        content.append('{"%s","%s",%d,INT64_C(1781355600),file_%d},\n' % (subdir,name,len(data),i))
    content.append('};\nconst int nb_resources = sizeof(resource)/sizeof(resource[0]);\n')
    (lib/'embedded.h').write_text(''.join(content))
    for _,name,data in resources[1:]: (lib/name).write_bytes(data)
    files = ('logging.c','tokenizer.c','vid_data.c','pki.c','libwdi_dlg.c','libwdi.c')
    run(cc,'-O2','-shared','-static','-DLIBWDI_DLL_EXPORT','-I'+str(lib),
        *(lib/name for name in files),'-o',out/'libwdi.dll',
        '-Wl,--out-implib,'+str(out/'libwdi.dll.a'),
        '-lsetupapi','-lole32','-lntdll','-ladvapi32','-luser32','-lgdi32','-lcomctl32','-luuid')
    run(cc,'-O2','-static','-I'+str(lib),'-I'+str(D),D/'windows_driver_helper.c',
        out/'libwdi.dll.a','-o',out/'camera-driver.exe','-lshell32','-ladvapi32')
    for name in ('build_windows_driver.py','windows_driver_helper.c','windows_driver_policy.h','windows_winusb.inf.in'):
        shutil.copy2(D/name, source/name)
    (source/'BUILD.txt').write_text('''相机 WinUSB 准备工具，Windows 10/11 x64，libwdi 1.5.1 修改版。
原始源码：https://github.com/pbatard/libwdi/tree/v1.5.1
交叉编译器：https://github.com/mstorsjo/llvm-mingw/releases/tag/20260922
INF 格式：https://learn.microsoft.com/en-us/windows-hardware/drivers/usbcon/winusb-installation
修改：仅嵌入 x64 安装程序与现代 WinUSB INF，省去旧系统 coinstaller。
WinUSB 分支的版本号描述本应用 INF；签名、校验与安装流程保留；不临时更改 Windows 还原点策略。
构建：Python build_windows_driver.py --inputs <包含官方归档与解压工具链的目录>
二进制动态链接 libwdi.dll，可用重建后的相同 ABI DLL 替换。仅调用自己的固定目标安装器。
此输出为交叉构建与离线验证，自动驱动安装尚待 Windows 实机验证。
''',encoding='utf-8')
    with zipfile.ZipFile(out/'libwdi-source.zip','w',zipfile.ZIP_DEFLATED) as z:
        for path in sorted(source.rglob('*')):
            if path.is_file(): z.write(path,path.relative_to(source))
    (out/'provenance.json').write_text(json.dumps(dict(libwdi='1.5.1 modified: native WinUSB',
        originalSourceSHA256=SOURCE_SHA, toolchainSHA256=TOOLCHAIN_SHA,
        files={name:sha(out/name) for name in ('camera-driver.exe','libwdi.dll','installer_x64.exe','libwdi-source.zip')}),indent=2)+'\n')
    print('Built camera WinUSB helper:',out)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--inputs',type=Path,required=True)
    build(parser.parse_args().inputs.resolve())
