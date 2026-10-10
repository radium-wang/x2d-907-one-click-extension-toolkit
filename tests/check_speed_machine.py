"""Execute original and candidate AArch64 functions offline; never accesses USB."""
import hashlib
import io
import json
import random
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
from speed_stock_elf import Binary

def system_elf(unused_path, expected):
    if len(sys.argv) != 2:
        raise SystemExit('Usage: python verify_candidate.py path/to/libaaa.so')
    return Binary(sys.argv[1], expected)

from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm64_const import *

SHA = 'feef8a8dc3a27395e47232c2b25a5da7a7ab335922fbb527e637c439e35bcec7'
ENTRY, END = 0xac380, 0xac7ac
PARAM, LENS, TLS, OUT, STACK, HALT = (0x2000000,0x2001000,0x2002000,0x2003000,0x2100000,0x2004000)

def pack(fmt, value): return struct.pack('<'+fmt, value)
def fbits(v): return struct.unpack('<I',pack('f',v))[0]
def fvalue(v): return struct.unpack('<f',pack('I',v & 0xffffffff))[0]

class Runner:
    def __init__(self, binary, ranges=(), oracle=False):
        self.u=Uc(UC_ARCH_ARM64, UC_MODE_ARM)
        self.u.mem_map(0x1000,0xb00000)
        for seg in binary.elf.iter_segments():
            if seg['p_type']=='PT_LOAD': self.u.mem_write(seg['p_vaddr'],seg.data())
        self.u.mem_map(PARAM,0x20000)
        self.u.mem_map(STACK,0x20000)
        for va, data in ranges: self.u.mem_write(va,data)
        self.u.reg_write(UC_ARM64_REG_TPIDR_EL0,TLS)
        self.u.reg_write(UC_ARM64_REG_SP,STACK+0x10000)
        self.u.mem_write(0xa2f2f0,pack('Q',LENS))
        self.u.mem_write(TLS+0x28,pack('Q',0x12345678))
        self.u.hook_add(UC_HOOK_CODE,self.hook)
        self.oracle=oracle
        self.context=self.u.context_save()
        self.reached=False

    def hook(self,u,a,n,unused):
        if a==HALT: u.emu_stop(); return
        if a==0xac724 and self.case['type'] & 0xffff in (0,1,2):
            self.reached=True
            if self.oracle:
                scale=self.scales[self.case['type'] & 0xffff]
                u.reg_write(UC_ARM64_REG_S10,fbits(fvalue(u.reg_read(UC_ARM64_REG_S10))*scale))
        if self.oracle and a==0xac6c4 and self.case['type'] & 0xffff in (0,1,2) and self.case['mode']==2:
            u.reg_write(UC_ARM64_REG_S0,fbits(min(21844,max(0,fvalue(u.reg_read(UC_ARM64_REG_S0))))))
        if a in (0x2bf70,0xacaa4): raise AssertionError('stack/assert failure')
        if a>=0x30000: return
        out=u.reg_read(UC_ARM64_REG_X1)
        if a==0x2daa0:
            u.reg_write(UC_ARM64_REG_X0,PARAM)
        elif a in (0x2e3c0,0x2fb00,0x2f9c0,0x2f9d0):
            u.mem_write(out,pack('H',self.case['lens_speed']))
            u.reg_write(UC_ARM64_REG_W0,self.case.get('lens_error',0)&0xffffffff)
        elif a in (0x2d2d0,0x2e9e0):
            key='aperture' if a==0x2d2d0 else 'fps_limit_factor'
            u.mem_write(out,pack('f',self.case[key]))
            u.reg_write(UC_ARM64_REG_W0,self.case.get('aperture_error',0) if a==0x2d2d0 else 0)
        elif a==0x2f9b0:
            u.mem_write(out,pack('d',self.case['lens_factor']))
            u.reg_write(UC_ARM64_REG_W0,self.case.get('factor_error',0))
        elif a==0x2cc00:
            u.mem_write(out,pack('I',self.case['focal']))
            u.reg_write(UC_ARM64_REG_W0,0)
        elif a in (0x2bf00,0x2bf10,0x2bf20): u.reg_write(UC_ARM64_REG_W0,0)
        else: raise AssertionError('unmodelled call '+hex(a))
        u.reg_write(UC_ARM64_REG_PC,u.reg_read(UC_ARM64_REG_LR))

    def run(self,c):
        self.case=c; self.reached=False
        u=self.u;u.context_restore(self.context)
        u.mem_write(PARAM,bytes(0x100));u.mem_write(OUT,b'\x9c\x9c')
        for offset,fmt,value in [(4,'I',c['mode']),(8,'B',1),(12,'f',60),(16,'H',c['steps']),
                                  (32,'I',35),(36,'f',c['close_scale']),(40,'f',c['slow_scale'])]:
            u.mem_write(PARAM+offset,pack(fmt,value))
        u.mem_write(LENS+8,pack('H',c['maximum']))
        u.mem_write(LENS+0x6b,pack('B',c['fallback']))
        u.reg_write(UC_ARM64_REG_X0,0);u.reg_write(UC_ARM64_REG_W1,c['type'])
        u.reg_write(UC_ARM64_REG_X2,OUT);u.reg_write(UC_ARM64_REG_S0,fbits(c['fps']))
        u.reg_write(UC_ARM64_REG_LR,HALT)
        for r in range(19,29):u.reg_write(globals()['UC_ARM64_REG_X'+str(r)],0x300000+r)
        u.emu_start(ENTRY,HALT,count=4000)
        assert u.reg_read(UC_ARM64_REG_PC)==HALT
        assert u.reg_read(UC_ARM64_REG_SP)==STACK+0x10000
        for r in range(19,29): assert u.reg_read(globals()['UC_ARM64_REG_X'+str(r)])==0x300000+r
        return (u.reg_read(UC_ARM64_REG_W0),struct.unpack('<H',u.mem_read(OUT,2))[0])

def main():
    folder=Path(sys.argv[1]);binary=Binary(sys.argv[2],SHA)
    manifest=json.loads((folder/'speed-bundle.json').read_text());profiles=manifest['speedLevels']['levels']
    base=dict(type=0,mode=2,lens_speed=5200,aperture=2.5,fps_limit_factor=1,
              lens_factor=.01175,focal=55,steps=1100,close_scale=1,slow_scale=.5,
              maximum=10000,fps=60,fallback=0)
    cases=[]
    for t in range(8):
        for mode in (0,1,2):
            for fps in (15,30,38,60,98,120):
                for fb in (0,1): cases.append(dict(base,type=t,mode=mode,fps=fps,fallback=fb))
    for t in range(6):
        for change in ({'aperture':0},{'steps':0},{'lens_error':-1},{'aperture_error':1},
                       {'factor_error':1},{'lens_factor':0},{'focal':20,'close_scale':.7}):
            cases.append(dict(base,type=t,**change))
    rng=random.Random(5515)
    for n in range(1000):
        cases.append(dict(base,type=rng.choice([0,1,2,3,4,5,6,65536,65537,65538,65539]),
            mode=rng.choice([0,1,2]),fps=rng.choice([24,38,60,98]),steps=rng.randrange(1,2000),
            lens_factor=rng.uniform(.0001,.02),aperture=rng.choice([2.5,4,8,11]),
            slow_scale=rng.choice([.25,.5,.75,1]),focal=rng.choice([20,35,55]),
            close_scale=rng.choice([.6,.8,1]),lens_speed=rng.randrange(1,10001)))
    for t in range(3):
        for speed in (0,21844,21845,32767,65535):
            for fps in (15,60,120):
                cases.append(dict(base,type=t,lens_speed=speed,fallback=1,fps=fps))
        for factor in (.000001,.0001,.001):
            for fps in (15,60,120):
                cases.append(dict(base,type=t,lens_factor=factor,fps=fps))

    reports=[]
    for level,spec in profiles.items():
        data=(folder/spec['source']).read_bytes()
        assert len(data)==1068 and hashlib.sha256(data).hexdigest()==spec['sha256']
        candidate=Runner(binary,[(ENTRY,data)]);oracle=Runner(binary,oracle=True);original=Runner(binary)
        oracle.scales=spec['multipliers']
        changed=0
        for idx,c in enumerate(cases):
            a=original.run(c);o=oracle.run(c);p=candidate.run(c)
            assert o==p,(level,idx,c,a,o,p)
            if c['type']&0xffff not in (0,1,2) or c['mode']!=2:assert a==p
            changed+=a!=p
        reports.append(dict(level=level,cases=len(cases),changed=changed,sha256=spec['sha256']))
    assert (folder/'speed-original').read_bytes()==binary.read(ENTRY,END-ENTRY)
    result=dict(status='PASS',machineCodeCases=sum(r['cases'] for r in reports),profiles=reports,
                deviceAccessed=False,externalGettersMocked=True,actualMaximum=None)
    (folder/'speed-machine-validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))

if __name__=='__main__':main()
