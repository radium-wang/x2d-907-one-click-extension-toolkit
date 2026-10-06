"""Run the real preload transaction with host memory/Qt substitutes; no USB."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SIZES = {'stock_unit':15084, 'extended_unit':18000,
         'control_stock':71108, 'control_afc':75576,
         'popover_stock':13552, 'popover_afc':47948,
         'liveview_stock':6196, 'liveview_modes':7212,
         'focus_tree':440, 'focus_names':32, 'focus_data':32}
HARNESS = r'''
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#define __attribute__(value)
#define __asm__
#define __volatile__(...) ((void)0)
extern void *test_resource_pointer(unsigned long,unsigned long);
#define X2D_RESOURCE_POINTER(base,offset) test_resource_pointer(base,offset)
#define X2D_REGISTER_PREFIX_HASH 0xb9b23f3a46fd0825UL
#define X2D_UNREGISTER_PREFIX_HASH 0xb9b23f3a46fd0825UL
#include "native_menu_preload.c"
#undef __attribute__
#undef __asm__
#undef __volatile__
static unsigned char arena[0x2180000];
static int failure, writes, registrations, removals;
static const char *mode;
static uintptr_t destination;
static char last_status[100];
static char *selected_mask;
char *getenv(const char *name) { return !strcmp(name,"X2D_NATIVE_MENU") ? "1" : !strcmp(name,"X2D_FEATURE_MASK") ? selected_mask : 0; }
ssize_t readlink(const char *path,char *out,size_t size) {
    const char *text="/system/bin/camera-gui"; size_t n=strlen(text);
    if(size<n) return -1; memcpy(out,text,n); return (ssize_t)n;
}
int dl_iterate_phdr(int (*callback)(struct dl_phdr_info *,size_t,void *),void *out) {
    struct dl_phdr_info info={(uintptr_t)arena,"",0,0}; return callback(&info,sizeof(info),out);
}
static _Bool register_resources(int version,const unsigned char *a,const unsigned char *b,const unsigned char *c) {
    if(version!=3 || a!=focus_tree || b!=focus_names || c!=focus_data) exit(80);
    ++registrations; return strcmp(mode,"register-failed")!=0;
}
static _Bool unregister_resources(int version,const unsigned char *a,const unsigned char *b,const unsigned char *c) {
    ++removals; return 1;
}
void *dlsym(void *handle,const char *name) {
    if(!strcmp(mode,"missing-api") || !strcmp(mode,"local-api") || !strcmp(mode,"local-api-mismatch")) return 0;
    if(!strcmp(name,"_Z21qRegisterResourceDataiPKhS0_S0_")) return (void *)register_resources;
    if(!strcmp(name,"_Z23qUnregisterResourceDataiPKhS0_S0_")) return (void *)unregister_resources;
    return 0;
}
void *test_resource_pointer(unsigned long base,unsigned long offset) {
    if(!strcmp(mode,"missing-api")) return 0;
    return offset==0x8a9c90 ? (void *)register_resources : (void *)unregister_resources;
}
int open(const char *path,int flags,...) {
    if(!strcmp(path,"/blackbox/x2d-native-menu.disable")) return !strcmp(mode,"disabled") ? 9 : -1;
    if(!strcmp(path,"/tmp/x2d-native-menu-attempt")) return !strcmp(mode,"retry") ? -1 : 9;
    if(!strcmp(path,"/proc/self/mem")) return !strcmp(mode,"open-failed") ? -1 : 2;
    if(!strcmp(path,"/tmp/x2d-native-menu-preload.status")) return 4;
    /* An unexpected disk target is a test failure, even if open would fail. */
    exit(83);
}
int close(int fd) { return 0; }
ssize_t read(int fd,void *out,size_t size) { return -1; }
long lseek(int fd,long position,int whence) { destination=(uintptr_t)position; return position; }
ssize_t write(int fd,const void *data,size_t size) {
    if(fd==4) { if(size>=sizeof(last_status)) exit(81); memcpy(last_status,data,size); last_status[size]=0; return size; }
    if(fd!=2 || destination<(uintptr_t)arena || destination+size>(uintptr_t)(arena+sizeof(arena))) exit(82);
    ++writes; size_t n=writes==failure ? size/2 : size;
    memcpy((void *)destination,data,n); return (ssize_t)n;
}
int main(int argc,char **argv) {
    mode=argc>1 ? argv[1] : "ok"; failure=argc>2 ? atoi(argv[2]) : 0;
    selected_mask=argc>3 ? argv[3] : 0;
    uintptr_t base=(uintptr_t)arena;
    struct cache *main_cache=(struct cache *)(base+0x20acc78);
    struct cache *control=(struct cache *)(base+0x20ac690);
    struct cache *popup=(struct cache *)(base+0x20ad2c0);
    struct cache *liveview=(struct cache *)(base+0x20ac978);
    struct cache original_main={(unsigned char *)(base+0x17b67f0),(void *)(base+0x216d650),0};
    struct cache original_control={(unsigned char *)(base+0x16c6300),(void *)(base+0x215cc90),0};
    struct cache original_popup={(unsigned char *)(base+0x1876ea0),(void *)(base+0x217aec0),0};
    struct cache original_liveview={(unsigned char *)(base+0x172c360),(void *)(base+0x2163f60),0};
    *main_cache=original_main; *control=original_control; *popup=original_popup; *liveview=original_liveview;
    memcpy((void *)original_main.data,stock_unit,15084);
    memcpy((void *)original_control.data,control_stock,71108);
    memcpy((void *)original_popup.data,popover_stock,13552);
    memcpy((void *)original_liveview.data,liveview_stock,6196);
    if(!strcmp(mode,"stock-mismatch")) arena[0x172c360]^=1;
    if(!strcmp(mode,"local-api-mismatch")) arena[0x8a9c90]^=1;
    install();
    if(!strcmp(mode,"ok") || !strcmp(mode,"local-api")) {
        if(strcmp(last_status,"MENU_AND_AFC_SWITCHABLE_READY\n") || registrations!=1 || removals || writes!=2) return 90;
        if(main_cache->data!=extended_unit || memcmp(control,&original_control,sizeof(*control)) ||
           memcmp(popup,&original_popup,sizeof(*popup)) || memcmp(liveview,&original_liveview,sizeof(*liveview)) ||
           *(unsigned int *)(base+0x18a2a64)!=1) return 91;
    } else if(!strcmp(mode,"menu-only")) {
        if(strcmp(last_status,"MENU_AND_AFC_SWITCHABLE_READY\n") || writes!=1 || registrations || removals || main_cache->data!=extended_unit) return 97;
        if(memcmp(control,&original_control,sizeof(*control)) || memcmp(popup,&original_popup,sizeof(*popup)) || memcmp(liveview,&original_liveview,sizeof(*liveview)) || *(unsigned int *)(base+0x18a2a64)) return 98;
    } else {
        if(memcmp(main_cache,&original_main,sizeof(*main_cache)) || memcmp(control,&original_control,sizeof(*control)) ||
           memcmp(popup,&original_popup,sizeof(*popup)) || memcmp(liveview,&original_liveview,sizeof(*liveview)) ||
           *(unsigned int *)(base+0x18a2a64)) return 92;
        if(!strcmp(mode,"partial") && (strcmp(last_status,"WRITE_FAILED_RESTORED\n") || registrations!=1 || removals!=1)) return 93;
        if(!strcmp(mode,"open-failed") && (writes || registrations!=1 || removals!=1)) return 94;
        if((!strcmp(mode,"disabled") || !strcmp(mode,"retry") || !strcmp(mode,"stock-mismatch") ||
            !strcmp(mode,"missing-api") || !strcmp(mode,"local-api-mismatch")) && (writes || registrations || removals)) return 95;
        if(!strcmp(mode,"register-failed") && (writes || registrations!=1 || removals)) return 96;
    }
    printf("%s",last_status); return 0;
}
'''


class NativeFocusUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler=shutil.which('clang')
        if not compiler:
            raise unittest.SkipTest('Host C compiler unavailable')
        cls.directory=tempfile.TemporaryDirectory(prefix='focus-preload-')
        cls.root=Path(cls.directory.name)
        definitions=[]
        prefix='_' if sys.platform=='darwin' else ''
        for name,size in SIZES.items():
            initial='"qv4cdata"' if name in ('extended_unit','popover_afc','liveview_modes') else '{0}'
            definitions.append('const unsigned char '+name+'['+str(size)+']='+initial+';')
            definitions.append('__asm__(".globl '+prefix+name+'_end\\n.set '+prefix+name+'_end, '+prefix+name+' + '+str(size)+'");')
        code='\n'.join(definitions)+'\n'+HARNESS
        source=cls.root/'probe.c';source.write_text(code)
        cls.executable=cls.root/'probe'
        result=subprocess.run([compiler,'-fno-builtin','-DEXTENDED_UNIT_SIZE=18000','-DPOPOVER_UNIT_SIZE=47948',
                               '-I',str(ROOT/'src'),str(source),'-o',str(cls.executable)],capture_output=True,text=True)
        if result.returncode:
            cls.directory.cleanup()
            raise RuntimeError(result.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def run_probe(self,mode,failed_write=0,mask=None):
        result=subprocess.run([str(self.executable),mode,str(failed_write)]+([] if mask is None else [str(mask)]),capture_output=True,text=True,timeout=5)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        return result.stdout.strip()

    def test_unselected_afc_keeps_stock_focus_caches_gate_and_resources(self):
        for mask in (2,4,6,8,10,12,14):
            with self.subTest(mask=mask): self.assertEqual(self.run_probe('menu-only',mask=mask),'MENU_AND_AFC_SWITCHABLE_READY')
        for mask in ('0','16','x','01','+8','-8','15x'):
            self.assertEqual(self.run_probe('invalid-mask',mask=mask),'FEATURE_MASK_INVALID')
        self.assertEqual(self.run_probe('partial-menu',failed_write=1,mask=2),'WRITE_FAILED_RESTORED')

    def test_success_keeps_all_stock_focus_caches_and_aot_tables_intact(self):
        self.assertEqual(self.run_probe('ok'),'MENU_AND_AFC_SWITCHABLE_READY')
        for mask in (1,3,5,7,9,11,13,15):
            self.assertEqual(self.run_probe('ok',mask=mask),'MENU_AND_AFC_SWITCHABLE_READY')

    def test_static_local_qt_symbols_use_verified_code_addresses(self):
        self.assertEqual(self.run_probe('local-api'),'MENU_AND_AFC_SWITCHABLE_READY')
        self.assertEqual(self.run_probe('local-api-mismatch'),'FOCUS_RESOURCE_API_MISSING')

    def test_each_partial_write_restores_all_original_fields_and_unregisters_icons(self):
        for write in range(1,3):
            with self.subTest(write=write):self.run_probe('partial',write)

    def test_disabled_retry_and_stock_mismatch_make_no_memory_or_resource_changes(self):
        for mode in ('disabled','retry','stock-mismatch'):
            with self.subTest(mode=mode):self.run_probe(mode)

    def test_missing_qt_api_failed_registration_and_mem_open_are_fail_closed(self):
        for mode in ('missing-api','register-failed','open-failed'):
            with self.subTest(mode=mode):self.run_probe(mode)
