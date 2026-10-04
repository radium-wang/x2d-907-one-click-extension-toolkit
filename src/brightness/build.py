"""Build only the rear-display runtime from exact local 4.2.0 inputs; no USB."""
import hashlib
import io
import json
import lzma
import os
from pathlib import Path
import subprocess
from elftools.elf.elffile import ELFFile
from display_bridge import generate, SYSTEM_SHA

D = Path(__file__).resolve().parent

class Binary:
    def __init__(self, path, expected):
        self.data = Path(path).read_bytes()
        if hashlib.sha256(self.data).hexdigest() != expected:
            raise ValueError('Unrecognized stock build: ' + Path(path).name)
        self.elf = ELFFile(io.BytesIO(self.data))
        self.symbols = self.elf.get_section_by_name('.symtab')
        if self.symbols is None:
            debug = self.elf.get_section_by_name('.gnu_debugdata')
            self.debug = ELFFile(io.BytesIO(lzma.decompress(debug.data())))
            self.symbols = self.debug.get_section_by_name('.symtab')
    def symbol(self, name):
        matches = [s for s in self.symbols.iter_symbols() if s.name == name]
        if len(matches) != 1: raise ValueError('Missing/ambiguous display symbol: ' + name)
        return matches[0]['st_value'], matches[0]['st_size']
    def read(self, address, length):
        for segment in self.elf.iter_segments():
            if segment['p_type'] == 'PT_LOAD' and segment['p_vaddr'] <= address and address + length <= segment['p_vaddr'] + segment['p_filesz']:
                start = segment['p_offset'] + address - segment['p_vaddr']
                return self.data[start:start + length]
        raise ValueError('Display address outside stock image')

def build(out, system, compiler):
    out = Path(out); system = Path(system)
    out.mkdir(parents=True, exist_ok=True)
    gui = Binary(system/'bin/camera-gui', '16391452abdc69de9e0807e065c0f4ab3f1ccb5fc288f6fc4e6f5cb3bdca12e0')
    evidence = generate(Binary(system/'bin/camera-system', SYSTEM_SHA), gui, out)
    exports = set()
    deps = []
    for name in ('libc.so', 'libdl.so', 'libm.so'):
        data = (system/'lib64'/name).read_bytes()
        (out/name).write_bytes(data)
        elf = ELFFile(io.BytesIO(data))
        exports.update(s.name for s in elf.get_section_by_name('.dynsym').iter_symbols() if s['st_shndx'] != 'SHN_UNDEF')
        deps.append(str(out/name))
    target = out/'libx2d_play_brightness.so'
    subprocess.run([compiler, '-target', 'aarch64-linux-gnu', '-fuse-ld=lld', '-O2', '-g0', '-fPIC', '-shared', '-nostdlib',
                    '-fno-stack-protector', '-fno-builtin', '-mno-outline-atomics', '-Wl,--strip-all', '-Wl,--no-undefined',
                    '-Wl,-z,noexecstack', '-Wl,-z,now', '-Wl,-z,relro', '-Wl,-soname,libx2d_play_brightness.so',
                    '-I'+str(out), str(D/'display_runtime.c'), str(D/'brightness_policy.c'), str(D/'sha256.c'),
                    str(out/'display-trampolines.S'), *deps, '-o', str(target)], check=True)
    elf = ELFFile(io.BytesIO(target.read_bytes()))
    imports = {s.name for s in elf.get_section_by_name('.dynsym').iter_symbols() if s.name and s['st_shndx'] == 'SHN_UNDEF'}
    if elf['e_machine'] != 'EM_AARCH64' or any((s['p_flags'] & 3) == 3 for s in elf.iter_segments()) or not imports <= exports:
        raise ValueError('Invalid display library architecture, permissions or imports')
    (out/'brightness-build-validation.json').write_text(json.dumps(dict(compiled=True, cameraAccessed=False,
        deviceValidated=False, sha256=hashlib.sha256(target.read_bytes()).hexdigest(), bridge=evidence, imports=sorted(imports)), indent=2)+'\n')
    return target

if __name__ == '__main__':
    build(os.environ['X2D_PAYLOAD_DIR'], os.environ['X2D_SYSTEM_ROOT'], os.environ['X2D_CC'])
