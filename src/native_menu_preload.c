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
extern void *dlsym(void *, const char *);
extern char *getenv(const char *);
extern ssize_t readlink(const char *, char *, size_t);
extern const unsigned char stock_unit[], stock_unit_end[], extended_unit[], extended_unit_end[];
extern const unsigned char control_stock[], control_stock_end[];
extern const unsigned char popover_stock[], popover_stock_end[];
extern const unsigned char liveview_stock[], liveview_stock_end[];
extern const unsigned char focus_tree[], focus_tree_end[], focus_names[], focus_names_end[], focus_data[], focus_data_end[];
typedef _Bool (*resource_function)(int, const unsigned char *, const unsigned char *, const unsigned char *);
struct cache { const unsigned char *data; const void *aot; const void *unused; };
struct patch { void *address; const void *before; const void *after; size_t size; };
#ifndef X2D_RESOURCE_POINTER
#define X2D_RESOURCE_POINTER(base,offset) ((void *)((base)+(offset)))
#endif
#ifndef X2D_REGISTER_PREFIX_HASH
#define X2D_REGISTER_PREFIX_HASH 0xc9fc129776a01367UL
#define X2D_UNREGISTER_PREFIX_HASH 0x458e2d498ccb2da9UL
#endif
static uintptr_t resource_prefix_hash(const unsigned char *code) {
    uintptr_t hash=14695981039346656037UL;
    for(size_t i=0;i<64;++i) hash=(hash^code[i])*1099511628211UL;
    return hash;
}
static resource_function local_resource_api(uintptr_t base, uintptr_t offset, uintptr_t expected) {
    if(!expected || resource_prefix_hash((const unsigned char *)(base+offset))!=expected) return 0;
    return (resource_function)X2D_RESOURCE_POINTER(base,offset);
}

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
    const char *mask=getenv("X2D_FEATURE_MASK");
    unsigned int selected_mask=7;
    if(mask) {
        if(mask[0]>='1' && mask[0]<='9' && !mask[1]) selected_mask=mask[0]-'0';
        else if(mask[0]=='1' && mask[1]>='0' && mask[1]<='5' && !mask[2]) selected_mask=10+mask[1]-'0';
        else {status("FEATURE_MASK_INVALID\n");return;}
    }
    if(!(selected_mask&1)) {
        /* Non-AF-C installs only attach the shared menu. Keep stock focus UI. */
        int attempt=open("/tmp/x2d-native-menu-attempt",1|64|128,0600);
        if(attempt<0) {status("SKIPPED_RETRY\n");return;}
        close(attempt);
        const unsigned char *next=extended_unit;
        struct patch menu={&c->data,&original,&next,sizeof(next)};
        int fd=open("/proc/self/mem",2);
        if(fd<0) {status("OPEN_FAILED\n");return;}
        if(!write_word(fd,&menu,0)) {
            int restored=write_word(fd,&menu,1);close(fd);
            status(restored ? "WRITE_FAILED_RESTORED\n" : "RESTORE_FAILED\n");return;
        }
        close(fd);__asm__ __volatile__("dmb ish" ::: "memory");
        status("MENU_AND_AFC_SWITCHABLE_READY\n");return;
    }
    struct cache *control=(struct cache *)(base+0x20ac690UL);
    struct cache *popover=(struct cache *)(base+0x20ad2c0UL);
    struct cache *liveview=(struct cache *)(base+0x20ac978UL);
    const unsigned char *old_control=(const unsigned char *)(base+0x16c6300UL);
    const unsigned char *old_popover=(const unsigned char *)(base+0x1876ea0UL);
    const unsigned char *old_liveview=(const unsigned char *)(base+0x172c360UL);
    unsigned int *gate=(unsigned int *)(base+0x18a2a64UL);
    unsigned int old_gate=*gate, enabled_gate=1;
    if ((old_gate!=0 && old_gate!=1) ||
        control->data!=old_control || control->aot!=(const void *)(base+0x215cc90UL) || control->unused ||
        popover->data!=old_popover || popover->aot!=(const void *)(base+0x217aec0UL) || popover->unused ||
        liveview->data!=old_liveview || liveview->aot!=(const void *)(base+0x2163f60UL) || liveview->unused ||
        control_stock_end-control_stock!=71108 || popover_stock_end-popover_stock!=13552 ||
        liveview_stock_end-liveview_stock!=6196 ||
        focus_tree_end-focus_tree!=440 || focus_names_end-focus_names<6 || focus_data_end-focus_data<4 ||
        memcmp(old_control,control_stock,71108) || memcmp(old_popover,popover_stock,13552) ||
        memcmp(old_liveview,liveview_stock,6196)) {
        status("AFC_BUILD_MISMATCH\n");return;
    }
    /* A failed GUI restart in this boot must fall back to unmodified stock. */
    int attempt=open("/tmp/x2d-native-menu-attempt",1|64|128,0600);
    if(attempt<0) {status("SKIPPED_RETRY\n");return;}
    close(attempt);
    resource_function register_icons=(resource_function)dlsym((void *)0,"_Z21qRegisterResourceDataiPKhS0_S0_");
    resource_function unregister_icons=(resource_function)dlsym((void *)0,"_Z23qUnregisterResourceDataiPKhS0_S0_");
    /* Qt is statically linked with STB_LOCAL symbols in the pinned camera GUI.
     * Dynamic lookup alone cannot find these two APIs. Verify code fingerprints
     * before using their fixed offsets; never guess offsets on another build. */
    if(!register_icons) register_icons=local_resource_api(base,0x8a9c90UL,X2D_REGISTER_PREFIX_HASH);
    if(!unregister_icons) unregister_icons=local_resource_api(base,0x8a9f10UL,X2D_UNREGISTER_PREFIX_HASH);
    if(!register_icons || !unregister_icons) {status("FOCUS_RESOURCE_API_MISSING\n");return;}
    if(!register_icons(3,focus_tree,focus_names,focus_data)) {status("FOCUS_RESOURCE_REGISTER_FAILED\n");return;}
    const unsigned char *next=extended_unit;
    /* Stock focus caches and AOT tables stay intact for the entire process.
     * QML opts into the private popup and reversible visual bindings only
     * while the master and AF-C switches are both enabled. */
    struct patch patches[] = {
        {&c->data,&original,&next,sizeof(next)},
        {gate,&old_gate,&enabled_gate,sizeof(enabled_gate)}
    };
    int fd=open("/proc/self/mem",2);
    if(fd<0) {unregister_icons(3,focus_tree,focus_names,focus_data);status("OPEN_FAILED\n");return;}
    int count=(int)(sizeof(patches)/sizeof(patches[0]));
    for(int i=0;i<count;++i) {
        if(!write_word(fd,&patches[i],0)) {
            int restored=1;
            /* 包括本次可能部分写入的字段，逆序恢复，不能留下半套菜单。 */
            for(int j=i;j>=0;--j) if(!write_word(fd,&patches[j],1)) restored=0;
            int resources_removed=restored ? unregister_icons(3,focus_tree,focus_names,focus_data) : 0;
            close(fd);status(restored ? (resources_removed ? "WRITE_FAILED_RESTORED\n" :
                "WRITE_FAILED_RESTORED_RESOURCE_CLEAR_FAILED\n") : "RESTORE_FAILED\n");return;
        }
    }
    close(fd);
    __asm__ __volatile__("dmb ish" ::: "memory");
    status("MENU_AND_AFC_SWITCHABLE_READY\n");
}
