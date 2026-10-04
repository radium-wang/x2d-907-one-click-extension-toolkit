"""Resolve the exact 4.2.0 display bridge and emit guarded trampolines offline."""
import hashlib, struct
from capstone import Cs, CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN
SYSTEM_SHA='bf854a21881148565ff2cc00376426c37a2b82fed94c653abf024e23ed4ceda6'
SYMBOLS={
 'BRIGHTNESS':('_ZN13ScreenHandler13setBrightnessEN9HblmTypes9E_ScreensEj',0x76298),
 'IDLE':('_ZN10IdleDetect9setStatusEN9HblmTypes14E_ScreenStatusE',0xbb998),
 'QOBJECT_CTOR':('_ZN7QObjectC1EPS_',0x17a078),
 'QOBJECT_DTOR':('_ZN7QObjectD1Ev',0x17a3e8),
 'QOBJECT_DELETE':('_ZN7QObjectD0Ev',0x69ea0),
 'QOBJECT_TIMER':('_ZN7QObject10startTimerEiN2Qt9TimerTypeE',0x17c318),
 'QOBJECT_THREAD':('_ZNK7QObject6threadEv',0x17a3b0),
 'CURRENT_THREAD':('_ZN7QThread13currentThreadEv',0x1d0d18),
 'QOBJECT_VTABLE':('_ZTV7QObject',0x563e80),
}
def generate(binary,gui,out):
 if hashlib.sha256(binary.data).hexdigest()!=SYSTEM_SHA:raise ValueError('Wrong camera-system')
 # The stock formatter initializer loads this 1..100 pair and an adjacent step=1.
 if struct.unpack('<ii',gui.read(0x1528468,8))!=(1,100):raise ValueError('Brightness range changed')
 header=['#define DISPLAY_SYSTEM_SHA "'+SYSTEM_SHA+'"']
 assembly=['.section .text','.balign 4']
 report={}
 for key,(name,address) in SYMBOLS.items():
  va,size=binary.symbol(name)
  if va!=address:raise ValueError('Display symbol moved: '+key)
  header.append('#define DISPLAY_'+key+' 0x%xUL'%va)
  report[key]=dict(address=hex(va),bytes=size,sha256=hashlib.sha256(binary.read(va,min(size,64))).hexdigest())
  if key not in ('BRIGHTNESS','IDLE'):continue
  code=binary.read(va,16)
  ins=list(Cs(CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN).disasm(code,va))
  if len(ins)!=4 or any(i.mnemonic not in ('sub','stp','add') for i in ins):raise ValueError('Non-relocatable prologue')
  header.append('static const unsigned char display_'+key.lower()+'_original[16]={'+','.join(str(x) for x in code)+'};')
  label='display_original_'+key.lower();slot='display_resume_'+key.lower()
  assembly+=['.global '+label,'.hidden '+label,label+':','.byte '+','.join(str(x) for x in code),
   'adrp x16, '+slot,'ldr x16, [x16, :lo12:'+slot+']','br x16']
 assembly+=['.section .data','.balign 8']
 for key in ('brightness','idle'):
  assembly+=['.global display_resume_'+key,'.hidden display_resume_'+key,'display_resume_'+key+':','.quad 0']
 (out/'display-generated.h').write_text('\n'.join(header)+'\n')
 (out/'display-trampolines.S').write_text('\n'.join(assembly)+'\n')
 return report
