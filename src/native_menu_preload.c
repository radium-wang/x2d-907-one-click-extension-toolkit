#ifndef POPOVER_UNIT_SIZE
#define POPOVER_UNIT_SIZE 13552
#endif
/* Exact-build, process-local bootstrap. No camera/radio calls and no disk GUI patch. */
typedef unsigned long size_t;
typedef long ssize_t;
typedef unsigned long uintptr_t;
struct dl_phdr_info { uintptr_t base; const char *name; const void *phdr; unsigned short phnum; };
extern int dl_iterate_phdr(int (*)(struct dl_phdr_info *, size_t, void *), void *);
extern int open(const char *, int, ...);
extern int close(int);
extern ssize_t read(int, void *, size_t);
extern ssize_t write(int, const void *, size_t);
extern long lseek(int, long, int);
extern int memcmp(const void *, const void *, size_t);
extern int strcmp(const char *, const char *);
extern char *getenv(const char *);
extern ssize_t readlink(const char *, char *, size_t);
extern const unsigned char stock_unit[], stock_unit_end[], extended_unit[], extended_unit_end[];
extern const unsigned char control_stock[], control_stock_end[], control_afc[], control_afc_end[];
extern const unsigned char popover_stock[], popover_stock_end[], popover_afc[], popover_afc_end[];
struct cache { const unsigned char *data; const void *aot; const void *unused; };
struct patch { void *address; const void *before; const void *after; size_t size; };

static int write_word(int fd, const struct patch *p, int restore) {
    const void *value=restore ? p->before : p->after;
    return lseek(fd,(long)(uintptr_t)p->address,0)==(long)(uintptr_t)p->address &&
           write(fd,value,p->size)==(ssize_t)p->size && !memcmp(p->address,value,p->size);
}

static void status(const char *s) {
    size_t n = 0; while (s[n]) ++n;
    int fd = open("/tmp/x2d-native-menu-preload.status", 1|64|512, 0600);
    if (fd >= 0) { (void)write(fd,s,n); close(fd); }
}
static int image(struct dl_phdr_info *info, size_t size, void *out) {
    (void)size;
    if (!info->name || !info->name[0] || !strcmp(info->name,"/system/bin/camera-gui")) {
        *(uintptr_t *)out=info->base; return 1;
    }
    return 0;
}
__attribute__((constructor)) static void install(void) {
    const char *enabled=getenv("X2D_NATIVE_MENU");
    if (!enabled || strcmp(enabled,"1")) return;
    int disabled=open("/blackbox/x2d-native-menu.disable",0);
    if (disabled>=0) {close(disabled);status("DISABLED\n");return;}
    char exe[128]; ssize_t n=readlink("/proc/self/exe",exe,sizeof(exe)-1);
    if(n<=0 || n>=(ssize_t)sizeof(exe)-1) return;
    exe[n]=0;
    if(strcmp(exe,"/system/bin/camera-gui")) return;
    uintptr_t base=0; dl_iterate_phdr(image,&base);
    if(!base) {status("NO_IMAGE\n");return;}
    struct cache *c=(struct cache *)(base+0x20acc78UL);
    const unsigned char *original=(const unsigned char *)(base+0x17b67f0UL);
    if((size_t)(stock_unit_end-stock_unit)!=15084 || c->data!=original ||
       c->aot!=(const void *)(base+0x216d650UL) || c->unused ||
       memcmp(original,stock_unit,15084)) {status("BUILD_MISMATCH\n");return;}
    if((size_t)(extended_unit_end-extended_unit)!=EXTENDED_UNIT_SIZE ||
       memcmp(extended_unit,"qv4cdata",8)) {status("PAYLOAD_MISMATCH\n");return;}
    struct cache *control=(struct cache *)(base+0x20ac690UL);
    struct cache *popover=(struct cache *)(base+0x20ad2c0UL);
    const unsigned char *old_control=(const unsigned char *)(base+0x16c6300UL);
    const unsigned char *old_popover=(const unsigned char *)(base+0x1876ea0UL);
    unsigned int *gate=(unsigned int *)(base+0x18a2a64UL);
    unsigned int old_gate=*gate, enabled_gate=1;
    if ((old_gate!=0 && old_gate!=1) ||
        control->data!=old_control || control->aot!=(const void *)(base+0x215cc90UL) || control->unused ||
        popover->data!=old_popover || popover->aot!=(const void *)(base+0x217aec0UL) || popover->unused ||
        control_stock_end-control_stock!=71108 || control_afc_end-control_afc!=75576 ||
        popover_stock_end-popover_stock!=13552 || popover_afc_end-popover_afc!=POPOVER_UNIT_SIZE ||
        memcmp(old_control,control_stock,71108) || memcmp(old_popover,popover_stock,13552)) {
        status("AFC_BUILD_MISMATCH\n");return;
    }
    /* A failed GUI restart in this boot must fall back to unmodified stock. */
    int attempt=open("/tmp/x2d-native-menu-attempt",1|64|128,0600);
    if(attempt<0) {status("SKIPPED_RETRY\n");return;}
    close(attempt);
    const unsigned char *next=extended_unit;
    /* Keep the focus list at the stock two items until the page switch opts in. */
    const unsigned char *next_control=control_stock, *next_popover=popover_afc;
    struct patch patches[] = {
        {&c->data,&original,&next,sizeof(next)},
        {&control->data,&old_control,&next_control,sizeof(next_control)},
        {&popover->data,&old_popover,&next_popover,sizeof(next_popover)},
        {gate,&old_gate,&enabled_gate,sizeof(enabled_gate)}
    };
    int fd=open("/proc/self/mem",2);
    if(fd<0) {status("OPEN_FAILED\n");return;}
    for(int i=0;i<4;++i) {
        if(!write_word(fd,&patches[i],0)) {
            int restored=1;
            /* 包括本次可能部分写入的字段，逆序恢复，不能留下半套菜单。 */
            for(int j=i;j>=0;--j) if(!write_word(fd,&patches[j],1)) restored=0;
            close(fd);status(restored ? "WRITE_FAILED_RESTORED\n" : "RESTORE_FAILED\n");return;
        }
    }
    close(fd);
    __asm__ __volatile__("dmb ish" ::: "memory");
    status("MENU_AND_AFC_SWITCHABLE_READY\n");
}
