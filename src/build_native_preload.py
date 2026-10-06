"""构建主菜单、“耍起功能”入口与 AF-C 菜单的启动模块；仅离线。"""
import hashlib
import io
import json
import os
import re
import shutil
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode=True
D=Path(__file__).resolve().parent
sys.path.insert(0, str(D))
from camera_ui_strings import english_qml, traditional_qml
support = os.environ.get('X2D_BUILD_SUPPORT')
if not support: raise SystemExit('Set X2D_BUILD_SUPPORT to the reviewed research tool directory containing inspect_menu_resources.py')
sys.path.insert(0, support)
from inspect_menu_resources import load_gui, GUI_SHA, resources
from brightness.menu_patch import generate as brightness_menu
from firmware_image import system_file
from elftools.elf.elffile import ELFFile

O=Path(os.environ.get('X2D_PAYLOAD_DIR', str(D/'native-package')))
O.mkdir(exist_ok=True)
b=load_gui()
resource_apis=[]
for name,address,expected in [('_Z21qRegisterResourceDataiPKhS0_S0_',0x8a9c90,0xc9fc129776a01367),
                              ('_Z23qUnregisterResourceDataiPKhS0_S0_',0x8a9f10,0x458e2d498ccb2da9)]:
    matches=[s for s in b.symbols if s.name==name]
    assert len(matches)==1 and matches[0]['st_value']==address
    assert matches[0]['st_info']['bind']=='STB_LOCAL'
    value=14695981039346656037
    for byte in b.read(address,64): value=((value^byte)*1099511628211)&((1<<64)-1)
    assert value==expected, 'Unrecognized Qt resource API code'
    assert name not in {s.name for s in b.elf.get_section_by_name('.dynsym').iter_symbols()}
    resource_apis.append(dict(symbol=name,address=address,prefixBytes=64,prefixFnv64=hex(expected),binding='STB_LOCAL'))
symbol=next(s for s in b.symbols if s.name.endswith('32_app_qml_mainmenu_MainScreen_qml7qmlDataE'))
stock=b.read(symbol['st_value'],symbol['st_size'])
(O/'stock-unit.bin').write_bytes(stock)
inputs=Path(os.environ['X2D_QML_UNIT_DIR'])
focus_inputs=Path(os.environ['X2D_FOCUS_UI_DIR'])
focus_hashes={'focus-popup.qt64.bin':'18f591e1ce551ed2f74f993d46989aa9fa1849f9f77306565a2440e9cbab2c8b',
              'liveview-stock.bin':'ae2ee04e839f03f4a28cf29e74d4d50a828058f84adb49eeab179a6722417207',
              'focus.tree':'4813c021519fd420159eb2b15cfa29fa1dfdd569ddcddb3eb8af3a1676d1fe28',
              'focus.names':'8bf867963f07e48676a5d8cbdd8353d53047f501d9caba6572fc27d9fdc4ed54',
              'focus.data':'653a8a134ffaa22567ae25898efefe43e56bcc8b95a0ed4d3eb1511caebb200d'}
for name,expected in focus_hashes.items():
    if hashlib.sha256((focus_inputs/name).read_bytes()).hexdigest()!=expected:
        raise ValueError('Unrecognized focus UI input: '+name)
clone=(inputs/'main-screen-bootstrap-device.bin').read_bytes()
for name in ('control-stock.bin','popover-stock.bin'):
    shutil.copy2(inputs/name,O/name)
for source,target in [('liveview-stock.bin','liveview-stock.bin'),
                      ('focus.tree','focus.tree'),('focus.names','focus.names'),('focus.data','focus.data')]:
    shutil.copy2(focus_inputs/source,O/target)
assert (O/'liveview-stock.bin').stat().st_size == 6196
popup=(focus_inputs/'focus-popup.qt64.bin').read_bytes()
assert popup[:16] == b'qv4cdata' + bytes.fromhex('3600000001040600')
assert popup[76:92] == hashlib.md5(popup[92:]).digest()
assert 15084 < len(clone) < 20000
(O/'extended-unit.bin').write_bytes(clone)
assembly='.section .rodata\n.balign 8\n'
for label,file in [('stock_unit','stock-unit.bin'),('extended_unit','extended-unit.bin'),
                   ('control_stock','control-stock.bin'),('popover_stock','popover-stock.bin'),
                   ('liveview_stock','liveview-stock.bin'),
                   ('focus_tree','focus.tree'),('focus_names','focus.names'),('focus_data','focus.data')]:
    assembly+=f'.global {label}, {label}_end\n{label}:\n.incbin "{(O/file).as_posix()}"\n{label}_end:\n.balign 8\n'
(O/'units.S').write_text(assembly)
exports=set()
deps=[]
for name in ('libc.so','libdl.so'):
    raw=system_file('/lib64/'+name)
    (O/name).write_bytes(raw)
    elf=ELFFile(io.BytesIO(raw))
    exports.update(s.name for s in elf.get_section_by_name('.dynsym').iter_symbols() if s['st_shndx']!='SHN_UNDEF')
    deps.append(dict(name=name,sha256=hashlib.sha256(raw).hexdigest()))
env=os.environ.copy()
env['ZIG_LOCAL_CACHE_DIR']=str(D.parent/'.zig-cache')
env['ZIG_GLOBAL_CACHE_DIR']=str(D.parent/'.zig-global')
target=O/'libx2d_native_menu.so'
if os.environ.get('X2D_CC'):
    compiler=[os.environ['X2D_CC'], '-fuse-ld=lld']
elif shutil.which('zig'):
    compiler=[shutil.which('zig'),'cc']
elif shutil.which('clang') and shutil.which('ld.lld'):
    compiler=[shutil.which('clang'),'-fuse-ld=lld']
else:
    raise SystemExit('Need X2D_CC, zig, or clang plus ld.lld for the AArch64 build')
subprocess.run(compiler+['-target','aarch64-linux-gnu','-O2','-g0','-fPIC','-shared','-nostdlib',
               '-DEXTENDED_UNIT_SIZE='+str(len(clone)),
               '-fno-stack-protector','-fno-builtin','-Wl,--strip-all','-Wl,--no-undefined','-Wl,-z,noexecstack',
               '-Wl,-soname,libx2d_native_menu.so',str(D/'native_menu_preload.c'),str(O/'units.S'),
               str(O/'libc.so'),str(O/'libdl.so'),'-o',str(target)],env=env,check=True)
raw=target.read_bytes();elf=ELFFile(io.BytesIO(raw))
assert elf['e_machine']=='EM_AARCH64'
assert not any((s['p_flags']&3)==3 for s in elf.iter_segments())
imports={s.name for s in elf.get_section_by_name('.dynsym').iter_symbols() if s.name and s['st_shndx']=='SHN_UNDEF'}
assert imports<=exports, imports-exports
files=[]
english_files=[]
traditional_files=[]
names={'Bootstrap':'X2dNativeMenuBootstrap','PlayMenuModel':'X2dNativeMenuModel',
       'PlayMenuRoute':'X2dNativeMenuRoute','ResidentPlayHost':'X2dNativeMenuHost',
       'PrankIbisPage':'X2dPrankIbisPage','PlayPage':'X2dPlayPage','AfcMenuController':'X2dAfcMenuController',
       'SpeedBuffController':'X2dSpeedBuffController','AutoBrightnessController':'X2dAutoBrightnessController',
       'DisplaySettings':'X2dDisplaySettings','DisplayRearBrightness':'X2dDisplayRearBrightness',
       'BrightnessSlider':'X2dBrightnessSlider'}
generated=brightness_menu(dict(resources(b)),O)
sources=[generated[name] if name in generated else D/(name+'.qml') for name in names]
paths=[target]
for source in sources:
    text=source.read_text(encoding='utf-8')
    text=re.sub(r'\b('+'|'.join(names)+r')\b',lambda m:names[m[0]],text)
    play_icon_url=os.environ.get('X2D_PLAY_ICON_URL')
    if play_icon_url:
        assert play_icon_url.startswith('file:///') and '..' not in play_icon_url
        text=text.replace('file:///system/etc/X2dPlayIcon',play_icon_url)
    packaged=names[source.stem]+'.qml'
    path=O/packaged
    with path.open('w',encoding='utf-8',newline='\n') as stream:
        stream.write(text)
    paths.append(path)
    target_path='/system/etc/'+packaged
    english=english_qml(text)
    if english!=text:
        en_name=names[source.stem]+'.en.qml'
        en_path=O/en_name
        with en_path.open('w',encoding='utf-8',newline='\n') as stream:
            stream.write(english)
        english_files.append(dict(source=en_name,target=target_path,bytes=en_path.stat().st_size,
                                  sha256=hashlib.sha256(en_path.read_bytes()).hexdigest()))
    traditional=traditional_qml(text)
    if traditional!=text:
        hant_name=names[source.stem]+'.zh-Hant.qml'
        hant_path=O/hant_name
        with hant_path.open('w',encoding='utf-8',newline='\n') as stream:
            stream.write(traditional)
        traditional_files.append(dict(source=hant_name,target=target_path,bytes=hant_path.stat().st_size,
                                      sha256=hashlib.sha256(hant_path.read_bytes()).hexdigest()))
# Keep the original popup cache untouched. This private file is loaded only
# when both camera switches are ON, through the stock popup Loader lifecycle.
popup_source=(focus_inputs/'ported-source/app/qml/popups/PopoverFocusMode.qml').read_text()
expected_source='4f961d09c9f10b8d323dc534ebeec0242d760775f59a8b8017a060fa3f4cc144'
if hashlib.sha256(popup_source.encode()).hexdigest()!=expected_source:
    raise ValueError('Unrecognized reviewed focus popup source')
popup_source=popup_source.replace('import "../components"','import "qrc:/app/qml/components"')
popup_source=popup_source.replace('import "../scripts/Keys.js"','import "qrc:/app/qml/scripts/Keys.js"')
popup_path=O/'X2dFocusModePopup.qml'
popup_path.write_text(popup_source,encoding='utf-8')
paths.append(popup_path)
icon=D/'assets/ic_main_menu_play.svg'
assert icon.is_file()
output_icon=O/'ic_main_menu_play.svg'
output_icon.write_bytes(icon.read_bytes())
paths.append(output_icon)
for path in paths:
    location='/system/lib64/' if path==target else '/system/etc/'
    target_name='X2dPlayIcon.svg' if path==output_icon else path.name
    files.append(dict(source=path.name,target=location+target_name,bytes=path.stat().st_size,
                      sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
assert english_files, 'English camera UI siblings were not produced'
assert traditional_files, 'Traditional Chinese camera UI siblings were not produced'
report=dict(guiSha256=GUI_SHA,files=files,uiLanguages={'en':english_files,'zh-Hant':traditional_files},dependencies=deps,
            resourceApis=resource_apis,
            imports=sorted(imports),
            deployed=False,deviceValidated=False,bootConfigurationWritten=False,
            guard='exact four original units/cache pointers; private icon registration; opt-in; disable-file; once per boot; rollback both writes',
            menuOnly=False,
            featureScope=['main-menu-play-entry','stock-style-play-settings','master-switch',
                          'afc-runtime-model-switch','afc-three-item-popover','afc-gate',
                          'x2d2-focus-popup','liveview-focus-mode-icons'],
            focusUi=dict(privateIcons=18,popupModelCountAdaptive=True,originalTypographyAndBorders=True,
                         stockFocusCachesAndAotPreserved=True,stockModelObjectsPreserved=True,
                         masterAndAfcRequired=True,reversibleIconBindings=True,
                         diskGuiChanged=False,deviceValidated=False),
            afcRuntimeModelMutationValidated=False,
            playPressedHighlightCorrected=True)
(O/'package.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(dict(compiled=True,files=len(files),englishFiles=len(english_files),
                      bytes=len(raw),deviceValidated=False)))
