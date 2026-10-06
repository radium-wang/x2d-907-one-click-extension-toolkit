"""Prepare private focus UI inputs from the verified X2D port; offline only.

The supplied port contains vendor-derived source and resources. Outputs must
remain outside the tracked source tree. Compile the prepared popup with the
documented Qt 6.4.1 host check before building the native preload.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import shutil
import struct

from elftools.elf.elffile import ELFFile

STOCK_GUI = '16391452abdc69de9e0807e065c0f4ab3f1ccb5fc288f6fc4e6f5cb3bdca12e0'
VERIFIED_GUI = 'd67de8355bea7d19260ace257fdfe0d30ab71455f1d8572f09320d2fd1e2e706'
LIVEVIEW_SHA = 'f4cca4d51eb53f19b7267e49e5c3a1e93a26c191db98bd711afef5aad938f7eb'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def elf_range(data, address, size):
    elf = ELFFile(io.BytesIO(data))
    if elf['e_machine'] != 'EM_AARCH64':
        raise ValueError('Expected the pinned AArch64 GUI')
    for segment in elf.iter_segments():
        if segment['p_type'] == 'PT_LOAD':
            start = segment['p_vaddr']
            if start <= address and address + size <= start + segment['p_filesz']:
                offset = segment['p_offset'] + address - start
                return data[offset:offset + size]
    raise ValueError('UI range is not file-backed')


def qt_hash(name):
    value = 0
    for char in name:
        value = (value << 4) + ord(char)
        value ^= (value & 0xf0000000) >> 23
        value &= 0x0fffffff
    return value


def icon_tables(icons):
    """Qt RCC v3: one private /icons directory, without stock aliases."""
    names, data = bytearray(), bytearray()

    def name_record(name):
        offset = len(names)
        names.extend(struct.pack('>HI', len(name), qt_hash(name)) + name.encode('utf-16be'))
        return offset

    empty, directory = name_record(''), name_record('icons')
    nodes = [struct.pack('>IHIIQ', empty, 2, 1, 1, 0),
             struct.pack('>IHIIQ', directory, 2, len(icons), 2, 0)]
    for path in sorted(icons, key=lambda p: (qt_hash(Path(p).name), Path(p).name)):
        name = Path(path).name
        if path != '/icons/' + name or not name.startswith('ic_x2d2_') or not name.endswith('.svg'):
            raise ValueError('Only private focus SVG aliases are allowed')
        offset = len(data)
        data.extend(struct.pack('>I', len(icons[path])) + icons[path])
        nodes.append(struct.pack('>IHHHIQ', name_record(name), 0, 0, 1, offset, 0))
    return b''.join(nodes), bytes(names), bytes(data)


def prepare(port, stock_gui, output):
    if output.exists():
        raise FileExistsError('Refusing to overwrite private build inputs')
    candidate_dir = port / 'elf-candidate-liveview-stock-style'
    metadata = json.loads((candidate_dir / 'candidate.json').read_text())
    gui = (candidate_dir / 'camera-gui.compact.NOT_FOR_DEVICE').read_bytes()
    stock = stock_gui.read_bytes()
    if digest(gui) != VERIFIED_GUI or digest(stock) != STOCK_GUI:
        raise ValueError('GUI input hash mismatch')
    if not metadata.get('postRebootDisplayVerified'):
        raise ValueError('Expected the accepted focus UI port')
    tree = elf_range(gui, 0x2200028, 22 * 393)
    # Read each accepted private alias directly from the pinned ELF. Directory
    # node counts differ from file counts, so stop using the root's structure.
    root_count, root_first = struct.unpack_from('>II', tree, 6)
    raw_names = elf_range(gui, 0x22021f0, 0x2208a18 - 0x22021f0)
    icons = {}
    expected = {item['path']: item for item in metadata['privateFocusIcons']}

    def walk(index, parent):
        row = tree[index * 22:(index + 1) * 22]
        name_offset, flags = struct.unpack_from('>IH', row)
        length = struct.unpack_from('>H', raw_names, name_offset)[0]
        name = raw_names[name_offset + 6:name_offset + 6 + length * 2].decode('utf-16be')
        path = parent + '/' + name if index else ''
        if flags & 2:
            count, first = struct.unpack_from('>II', row, 6)
            for child in range(first, first + count):
                walk(child, path)
        elif path in expected:
            if flags:
                raise ValueError('Private icons must be uncompressed')
            offset = struct.unpack_from('>I', row, 10)[0]
            size = struct.unpack('>I', elf_range(gui, 0x2208a18 + offset, 4))[0]
            content = elf_range(gui, 0x2208a18 + offset + 4, size)
            if digest(content) != expected[path]['sha256']:
                raise ValueError('Private icon hash mismatch')
            icons[path] = content

    if root_count < 1 or root_first < 1:
        raise ValueError('Invalid graphics resource tree')
    walk(0, '')
    if set(icons) != set(expected) or len(icons) != 18:
        raise ValueError('Expected exactly eighteen verified private aliases')
    output.mkdir(parents=True)
    for name, content in zip(('focus.tree', 'focus.names', 'focus.data'), icon_tables(icons)):
        (output / name).write_bytes(content)
    liveview = elf_range(gui, 0x21fe3f8, 7212)
    if digest(liveview) != LIVEVIEW_SHA:
        raise ValueError('Liveview unit hash mismatch')
    (output / 'liveview-modes.bin').write_bytes(liveview)
    (output / 'liveview-stock.bin').write_bytes(elf_range(stock, 0x172c360, 6196))
    source = port / 'ported-source/app/qml/popups/PopoverFocusMode.qml'
    text = source.read_text()
    if text.count('readonly property int numItems: 3') != 1:
        raise ValueError('Unexpected accepted popup source')
    text = text.replace('readonly property int numItems: 3',
                        'readonly property int numItems: Math.max(1, root.focusModeModel.length)')
    text = text.replace('/ (numItems - 1) + highlightWidth',
                        '/ Math.max(1, numItems - 1) + highlightWidth')
    popup = output / 'ported-source/app/qml/popups/PopoverFocusMode.qml'
    popup.parent.mkdir(parents=True)
    popup.write_text(text)
    for relative in ('components/FocusModeListItem.qml', 'components/HblListView.qml', 'scripts/Keys.js'):
        target = output / 'x2d-resources/app/qml' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(port / 'x2d-resources/app/qml' / relative, target)
    report = dict(sourceGuiSha256=VERIFIED_GUI, targetGuiSha256=STOCK_GUI,
                  privateIcons=[dict(path=p, sha256=digest(data), bytes=len(data)) for p, data in sorted(icons.items())],
                  popupModelCountAdaptive=True, originalTypographyAndBorders=True,
                  popupCompilePending=True, deviceValidated=False)
    (output / 'focus-ui-inputs.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verified-port', type=Path, required=True)
    parser.add_argument('--stock-gui', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    prepare(args.verified_port, args.stock_gui, args.output)
