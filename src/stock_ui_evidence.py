#!/usr/bin/env python3
"""Extract pinned stock Qt resource banks for local UI checks; never USB.

Raw banks and vendor resources stay in an ignored caller-selected output.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import zlib
from elftools.elf.elffile import ELFFile

GUI_SHA='16391452abdc69de9e0807e065c0f4ab3f1ccb5fc288f6fc4e6f5cb3bdca12e0'
BANKS_SHA='623b39d9be70971abff5375250340a1d4e031727f463a499a45cea2e7a9577d2'
REQUIRED_SHA={
 '/app/qml/common/GlobalConstants.qml':'662b2456617a8e13642724dc803a68cad94be9e68c4cd64b1d6611e7485e5255',
 '/app/qml/components/controls/PopupListSelector.qml':'be93b80b13466aaf01944c5dd584e27c6d736c4a3913c396140cd60cdc59a7e9',
 '/app/qml/components/PopupBackground.qml':'15969ed0fd1a030815f1d7c04502b29edccd9282be6037b9317433b003dc9494',
 '/app/qml/components/ListGradient.qml':'19679dd8d3be039434523786547d27122c307bbee3c98471cb3da507dc0428ae',
 '/app/qml/components/HblListView.qml':'5dbca5c1ee02541168760a0c53684e8d9d97585755bbe7e6237e5d708678f3b8',
 '/app/qml/components/ScaledDelegate.qml':'c60fcb85e6b3d4e63e114a5f1be9c892cbe649d2694366ab5dbf35e12f1ff00d',

 '/app/qml/popups/Popover.qml':'17b99b59233da2f603e95f5aa0a243b7531160a651255d9639f4c5d6fd9ee268',
 '/app/qml/popups/PopoverFocusMode.qml':'0a248ff9d99f230d3777c032f8a4a3efd79b31fc0dd8899cdeb8c15eeff2781b',
 '/app/qml/components/buttons/FramedImage.qml':'239ade0d8b54d1c59383e36fac691331358ba3c7ac437b965731649f351e1af7',
 '/app/qml/components/buttons/FramedItem.qml':'0b0afb398e5d3a99ef93ef68418172cce9bb2abb68066591f8edb64b13fb8dc9',
 '/app/qml/components/ScaledImage.qml':'0aacd7ab73207d721eff8aa130e9f32398967ed42d1c293a64baea8b718fb04b',
 '/app/qml/components/UiImage.qml':'8820820ac40a2abafdeef9170e15f222ec557b8a0d376720fd10487555eb2dbe',
 '/app/qml/components/FocusModeListItem.qml':'7ab66488fd11ed4786e6ba1bcc17a2bdc7ffd9d1b498a8ba8d1d8da83922ce89',
 '/app/qml/scripts/Keys.js':'82a0cbb06212e208b9f63360d21ecb68b6ae610c9ffc544de4d45754eefcbb79',
 '/app/qml/mainmenu/MenuHeader.qml':'4e1b6c4666a020f542520781b56c9f25767ff5f43fb455b0e64ea9c66904afb2',
 '/app/qml/mainmenu/MenuBoolSelector.qml':'eb59800f3d9084c8cf0d78f978d83ea11d0b7a2c6bd6656ed034e23756fe7a21'}
REQUIRED=('/app/qml/common/GlobalConstants.qml',
          '/app/qml/components/controls/PopupListSelector.qml',
          '/app/qml/components/PopupBackground.qml','/app/qml/components/HblListView.qml',
          '/app/qml/components/ScaledDelegate.qml','/app/qml/components/ListGradient.qml',
          '/app/qml/popups/Popover.qml','/app/qml/popups/PopoverFocusMode.qml',
          '/app/qml/components/buttons/FramedImage.qml','/app/qml/components/buttons/FramedItem.qml',
          '/app/qml/components/ScaledImage.qml','/app/qml/components/UiImage.qml',
          '/app/qml/components/FocusModeListItem.qml','/app/qml/scripts/Keys.js',
          '/app/qml/mainmenu/MenuHeader.qml','/app/qml/mainmenu/MenuBoolSelector.qml')
def sha(data):return hashlib.sha256(data).hexdigest()

def banks(elf):
    groups={name:[] for name in ('struct','name','data')}
    symbols={'_ZL'+str(len('qt_resource_'+name))+'qt_resource_'+name:name for name in groups}
    for symbol in elf.get_section_by_name('.symtab').iter_symbols():
        if symbol.name in symbols:groups[symbols[symbol.name]].append(symbol)
    for values in groups.values():values.sort(key=lambda s:s['st_value'])
    if len({len(v) for v in groups.values()})!=1:raise ValueError('stock Qt resource groups differ')
    cached={}
    def blob(symbol):
        index=symbol['st_shndx']
        if index not in cached:
            section=elf.get_section(index);cached[index]=(section['sh_addr'],section.data())
        start,data=cached[index];offset=symbol['st_value']-start
        return data[offset:offset+symbol['st_size']]
    for group in zip(groups['struct'],groups['name'],groups['data']):yield tuple(map(blob,group))

def entries(tree,names,data):
    def walk(index,parent):
        at=index*22;offset,flags=struct.unpack_from('>IH',tree,at)
        length=struct.unpack_from('>H',names,offset)[0]
        name=names[offset+6:offset+6+2*length].decode('utf-16be') if index else ''
        if '/' in name or name in ('.','..'):raise ValueError('invalid resource name')
        path=parent+'/'+name if index else ''
        if flags&2:
            count,first=struct.unpack_from('>II',tree,at+6)
            if first+count>len(tree)//22:raise ValueError('resource tree overflow')
            for child in range(first,first+count):yield from walk(child,path)
        else:
            offset=struct.unpack_from('>I',tree,at+10)[0];size=struct.unpack_from('>I',data,offset)[0]
            raw=data[offset+4:offset+4+size]
            if len(raw)!=size:raise ValueError('resource data overflow')
            content=None if flags&4 else zlib.decompress(raw[4:]) if flags&1 else raw
            if flags&1 and len(content)!=struct.unpack_from('>I',raw)[0]:raise ValueError('decompression mismatch')
            yield path,content,flags
    yield from walk(0,'')

def prepare(gui,output):
    if sha(gui.read_bytes())!=GUI_SHA:raise ValueError('stock GUI is not pinned X2D 4.2.0')
    output.mkdir(parents=True,exist_ok=False);index={};tables=[]
    with gui.open('rb') as handle:
        for i,group in enumerate(banks(ELFFile(handle))):
            table={}
            for suffix,data in zip(('tree','names','data'),group):
                name=f'stock-{i}.{suffix}';(output/name).write_bytes(data)
                table[suffix]=dict(source=name,sha256=sha(data),bytes=len(data))
            tables.append(table)
            for path,content,flags in entries(*group):
                record=dict(group=i,flags=flags,sha256=sha(content) if content is not None else None)
                if path in index and index[path]!=record:raise ValueError('ambiguous stock resource: '+path)
                index[path]=record
                if path in REQUIRED:
                    if content is None:raise ValueError('required stock QML compression unsupported')
                    target=output/'sources'/path.lstrip('/');target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(content)
    if set(REQUIRED)-index.keys():raise ValueError('required stock visual types missing')
    if any('FocusFramedImage.qml' in path for path in index):raise ValueError('unexpected second-generation visual type')
    result=dict(guiSha256=GUI_SHA,tables=tables,resources=index,required=list(REQUIRED),deviceAccessed=False)
    (output/'stock-ui.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(groups=len(tables),resources=len(index),realVisualTypes=list(REQUIRED),
                         shaders=[p for p in index if p.endswith('.qsb')],deviceAccessed=False)))

def verify(folder):
    result=json.loads((folder/'stock-ui.json').read_text())
    if result['guiSha256']!=GUI_SHA:raise ValueError('unknown stock UI evidence')
    combined=hashlib.sha256()
    if len(result['tables'])!=40:raise ValueError('stock resource-bank count mismatch')
    for table in result['tables']:
        for name in ('tree','names','data'):
            f=table[name];data=(folder/f['source']).read_bytes()
            if sha(data)!=f['sha256']:raise ValueError('stock resource-bank mismatch')
            combined.update(data)
    if combined.hexdigest()!=BANKS_SHA:raise ValueError('resource banks are not byte-exact stock')
    if set(REQUIRED)-result['resources'].keys():raise ValueError('stock visual-type evidence incomplete')
    for path in REQUIRED:
        record=result['resources'][path]
        if sha((folder/'sources'/path.lstrip('/')).read_bytes())!=REQUIRED_SHA[path] or record['sha256']!=REQUIRED_SHA[path]:raise ValueError('stock visual source mismatch')
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--gui',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();prepare(args.gui,args.output)
