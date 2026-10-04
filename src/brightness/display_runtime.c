/* Adapted from X2D New Extension (MIT), 2026 Hasselblad Feature Extensions contributors.
 * Toolkit integration: own preference paths, Tweaks master gating and independent service.
 * X2D 4.2.0 private, process-local display bridge. No AF calls or lens locks. */
#include "abi.h"
#include "brightness_policy.h"
#include "display-generated.h"
extern int x2d_hash_file(const char *,const char *);
extern int pthread_mutex_init(void *,const void *),pthread_mutex_lock(void *),pthread_mutex_unlock(void *);
extern void *malloc(size_t), *calloc(size_t,size_t);
extern void free(void *);
extern double strtod(const char *,char **);
extern long lseek(int,long,int);
extern int usleep(unsigned),clock_gettime(int,void *);
extern void *opendir(const char *),*readdir(void *);
extern int closedir(void *);
extern int display_original_brightness(void *,int,unsigned);
extern void display_original_idle(void *,int);
extern uintptr_t display_resume_brightness,display_resume_idle;
#define GET(p) __atomic_load_n(&(p),__ATOMIC_ACQUIRE)
#define PUT(p,v) __atomic_store_n(&(p),(v),__ATOMIC_RELEASE)
#define PREF "/blackbox/x2d-play-auto-brightness.enabled"
#define FEATURE "/blackbox/x2d-play-auto-brightness.available"
#define STATUS "/tmp/x2d-play-brightness.json"
struct timespec_local {long sec,nsec;};
struct dirent_local {u64 ino;long off;unsigned short reclen;unsigned char type;char name[256];};
static uintptr_t base;
static void *screen,*timer_object;
static uintptr_t timer_vtable[14];
static struct brightness_policy policy;
static int manual_level=50,idle_state=255,desired_enable,desired_available,feature_pending,bridge_ready,dead,restoring;
static unsigned revision,sensor_seq;
static u64 sensor_value_bits,sensor_time_bits;
static int sensor_valid,master_enabled;
#define MASTER "/blackbox/x2d-speed-buff.master"
static int master_is_on(void){int fd=open(MASTER,0|0x20000|0x80000);if(fd<0)return 0;close(fd);return 1;}
static int manual_known,last_output=50,pref_pending,display_eligible;
static u64 pref_lock[8];
static const char *reason="waiting_for_display";
static double session_end;
static double last_publish;
static char status_snapshot[1024];
static unsigned snapshot_seq;
static double monotonic(void){struct timespec_local t;if(clock_gettime(1,&t))return 0;return t.sec+t.nsec/1e9;}
static u64 bits(double v){union {double d;u64 u;} x={.d=v};return x.u;}
static double number(u64 v){union {double d;u64 u;} x={.u=v};return x.d;}
static int read_text(const char *p,char *out,size_t n){
 int fd=open(p,0|0x80000);if(fd<0)return 0;ssize_t got=read(fd,out,n-1);close(fd);
 if(got<=0)return 0;out[got]=0;return 1;
}
static int save_flag(const char *path,int value){
 char tmp[160];snprintf(tmp,sizeof(tmp),"%s.next",path);int fd=open(tmp,1|64|512|0x20000|0x80000,0600);
 if(fd<0)return 0;
 int ok=write(fd,value?"1\n":"0\n",2)==2&&!fsync(fd);close(fd);
 if(!ok||rename(tmp,path)){unlink(tmp);return 0;}return 1;
}
static int save_preference(int value){return save_flag(PREF,value);}
static void cancel_auto(void){if(__atomic_exchange_n(&desired_enable,0,__ATOMIC_ACQ_REL))PUT(pref_pending,1);__atomic_add_fetch(&revision,1,__ATOMIC_ACQ_REL);}
static void remove_feature(void){
 if(__atomic_exchange_n(&desired_available,0,__ATOMIC_ACQ_REL))PUT(feature_pending,1);
 cancel_auto();
}
static int eligible(void){
 if(!screen||!manual_known||GET(idle_state)!=0)return 0;
 unsigned char *p=screen;
 return p[0x40]==1 && p[0x51] && ((*(unsigned *)(p+0x44))&1);
}
static void publish(double sensor,int valid,int active){
 char buf[1024];
 int n=snprintf(buf,sizeof(buf),"{\"ok\":true,\"pid\":%d,\"ready\":%s,\"enabled\":%s,\"available\":%s,\"master\":%s,\"effective\":%s,\"state\":\"%s\",\"sensorValid\":%s,\"sensor\":%.3f,\"manual\":%d,\"applied\":%d,\"filtered\":%.3f,\"eligible\":%s,\"generation\":%u}\n",getpid(),GET(bridge_ready)&&manual_known?"true":"false",GET(desired_enable)?"true":"false",GET(desired_available)?"true":"false",GET(master_enabled)?"true":"false",policy.effective?"true":"false",GET(reason),valid?"true":"false",valid?sensor:0,manual_level,policy.applied,policy.filtered,active?"true":"false",GET(revision));
 if(n<=0||n>=(int)sizeof(buf))return;
 __atomic_add_fetch(&snapshot_seq,1,__ATOMIC_ACQ_REL);
 for(int i=0;i<=n;i++)__atomic_store_n(&status_snapshot[i],buf[i],__ATOMIC_RELAXED);
 __atomic_add_fetch(&snapshot_seq,1,__ATOMIC_RELEASE);
 /* Tmpfs status is diagnostic only; preferences are written solely on commands. */
 int fd=open(STATUS ".next",1|64|512|0x80000,0600);
 if(fd>=0){if(write(fd,buf,n)==n)rename(STATUS ".next",STATUS);close(fd);}
}
static void tick(void *self,void *event){
 (void)event;if(self!=timer_object||GET(dead))return;
 double now=monotonic();int valid=0;double value=0,stamp=0;
 for(int attempt=0;attempt<3;attempt++){
  unsigned a=GET(sensor_seq);if(a&1)continue;
  value=number(GET(sensor_value_bits));stamp=number(GET(sensor_time_bits));valid=GET(sensor_valid);
  if(a==GET(sensor_seq))break;valid=0;
 }
 valid=valid&&stamp>0&&now>=stamp&&now-stamp<=.7;
 if(!GET(master_enabled)&&(GET(desired_enable)||GET(desired_available)))remove_feature();
 if(session_end>0&&now>=session_end&&GET(desired_enable)){cancel_auto();PUT(reason,"temporary_session_expired");}
 int active=eligible(),output=0;PUT(display_eligible,active);
 if(!GET(master_enabled))PUT(reason,"master_off");
 else if(!GET(desired_enable))PUT(reason,session_end>0&&now>=session_end?"temporary_session_expired":"manual");
 else if(!active)PUT(reason,"stock_display_inactive");
 else if(!valid)PUT(reason,"sensor_unavailable");
 else PUT(reason,"auto");
 unsigned generation=GET(revision);
 if(brightness_step(&policy,GET(desired_enable),valid,value,active,manual_level,now,&output)){
  /* HTTP commands can invalidate work while the Qt owner thread computes. */
  if(generation==GET(revision)&&eligible()){
   restoring=1;display_original_brightness(screen,1,(unsigned)output);restoring=0;last_output=output;
  }else {brightness_reset(&policy,last_output,now);}
 }
 /* Keep diagnostic disk/IPC snapshots at 5 Hz; only the animation runs at 50 Hz. */
 if(now-last_publish>=.2||now<last_publish){publish(value,valid,active);last_publish=now;}
}
static void timer_destroy(void *self){
 PUT(dead,1);PUT(bridge_ready,0);cancel_auto();timer_object=0;screen=0;
 ((void(*)(void *))(base+DISPLAY_QOBJECT_DTOR))(self);
}
static void timer_delete(void *self){
 PUT(dead,1);PUT(bridge_ready,0);cancel_auto();timer_object=0;screen=0;
 ((void(*)(void *))(base+DISPLAY_QOBJECT_DELETE))(self);
}
static void attach_timer(void){
 if(timer_object||GET(dead))return;
#ifndef X2D_DISPLAY_HOST_TEST
 void *owner=((void *(*)(void *))(base+DISPLAY_QOBJECT_THREAD))(screen);
 if(owner!=((void *(*)(void))(base+DISPLAY_CURRENT_THREAD))()){
  PUT(reason,"display_thread_mismatch");return;
 }
#endif
 void *object=calloc(1,16);if(!object){PUT(reason,"timer_allocation_failed");return;}
 ((void(*)(void *,void *))(base+DISPLAY_QOBJECT_CTOR))(object,screen);
 uintptr_t *original=*(uintptr_t **)object;
 if((uintptr_t)original!=base+DISPLAY_QOBJECT_VTABLE+16){
  PUT(reason,"qt_object_layout_mismatch");((void(*)(void *))(base+DISPLAY_QOBJECT_DELETE))(object);return;
 }
 memcpy(timer_vtable,original-2,sizeof(timer_vtable));
 timer_vtable[5]=(uintptr_t)timer_destroy;timer_vtable[6]=(uintptr_t)timer_delete;
 timer_vtable[9]=(uintptr_t)tick;*(uintptr_t **)object=timer_vtable+2;
 timer_object=object;
 int timer=((int(*)(void *,int,int))(base+DISPLAY_QOBJECT_TIMER))(object,20,0);
 if(timer<=0){PUT(reason,"qt_timer_failed");timer_delete(object);return;}
 PUT(bridge_ready,1);
}
static int brightness_hook(void *self,int which,unsigned level){
 /* Auto uses the stock trampoline; eligible ceiling edits defer to its timer. */
 if(which==1 && level>=1 && level<=100){
  if(!screen){screen=self;manual_level=(int)level;manual_known=1;brightness_reset(&policy,manual_level,monotonic());}
  else if(screen==self&&!restoring){
   manual_level=(int)level;
   if(GET(desired_enable)&&GET(desired_available)&&GET(master_enabled)&&GET(bridge_ready)){
    __atomic_add_fetch(&revision,1,__ATOMIC_ACQ_REL);
    if(eligible())return 0; /* Apply the new ceiling at the next owner-thread tick. */
   }else brightness_reset(&policy,manual_level,monotonic());
  }
 }
 int result=display_original_brightness(self,which,level);
 if(which==1&&screen==self&&level>=1&&level<=100){
  last_output=(int)level;
  if(GET(desired_enable)&&!eligible())brightness_reset(&policy,last_output,monotonic());
 }
 if(screen==self&&!timer_object)attach_timer();
 return result;
}
static void idle_hook(void *self,int value){
 if(GET(idle_state)!=value){PUT(idle_state,value);__atomic_add_fetch(&revision,1,__ATOMIC_ACQ_REL);}
 display_original_idle(self,value);
}
static int discover(char *path,size_t capacity){
 void *dir=opendir("/sys/bus/iio/devices");if(!dir)return 0;
 int matches=0;struct dirent_local *entry;
 while((entry=readdir(dir))){
  if(strncmp(entry->name,"iio:device",10))continue;
  unsigned n=10;while(entry->name[n]>='0'&&entry->name[n]<='9')n++;
  if(n==10||entry->name[n])continue;
  char file[256],text[64];snprintf(file,sizeof(file),"/sys/bus/iio/devices/%s/name",entry->name);
  if(!read_text(file,text,sizeof(text)))continue;
  if(strcmp(text,"cm32181\n")&&strcmp(text,"cm32181"))continue;
  matches++;snprintf(path,capacity,"/sys/bus/iio/devices/%s/in_illuminance_input",entry->name);
 }
 closedir(dir);return matches==1;
}
static void *sample(void *unused){
 (void)unused;double next=monotonic();
 while(!GET(dead)){
  char path[256],text[128],*end;double value=0;
  PUT(master_enabled,master_is_on());
  if(!GET(master_enabled)&&(GET(desired_enable)||GET(desired_available)))remove_feature();
  if(GET(feature_pending)){pthread_mutex_lock(pref_lock);
   if(GET(feature_pending)&&!GET(desired_available)&&save_flag(FEATURE,0))PUT(feature_pending,0);
   pthread_mutex_unlock(pref_lock);
  }
  if(GET(pref_pending)){pthread_mutex_lock(pref_lock);
   if(GET(pref_pending)&&!GET(desired_enable)&&save_preference(0))PUT(pref_pending,0);
   pthread_mutex_unlock(pref_lock);
  }
  int valid=GET(desired_enable)&&GET(display_eligible)&&discover(path,sizeof(path))&&read_text(path,text,sizeof(text));
  if(valid){value=strtod(text,&end);valid=end!=text;
   while(*end==' '||*end=='\n'||*end=='\r'||*end=='\t')end++;
   valid=valid&&!*end&&__builtin_isfinite(value)&&value>=0;
  }
  __atomic_add_fetch(&sensor_seq,1,__ATOMIC_ACQ_REL);
  PUT(sensor_value_bits,bits(value));PUT(sensor_time_bits,bits(monotonic()));PUT(sensor_valid,valid);
  __atomic_add_fetch(&sensor_seq,1,__ATOMIC_RELEASE);
  next+=.2;double wait=next-monotonic();if(wait>0)usleep((unsigned)(wait*1e6));else next=monotonic();
 }
 return 0;
}
static int snapshot(char *out,size_t capacity){
 for(int attempt=0;attempt<3;attempt++){
  unsigned a=GET(snapshot_seq);if(a&1)continue;
  size_t i;for(i=0;i+1<capacity;i++){out[i]=__atomic_load_n(&status_snapshot[i],__ATOMIC_RELAXED);if(!out[i])break;}out[capacity-1]=0;
  if(a==GET(snapshot_seq)&&out[0])return 1;
 }
 return 0;
}
/* Commands are durable; an ordinary Display disable keeps the menu feature. */
static int command(int feature,int enable){
 int ok=0;PUT(master_enabled,master_is_on());
 if(!enable){
  if(feature)remove_feature();else cancel_auto();
  pthread_mutex_lock(pref_lock);
  ok=save_preference(0);if(ok)PUT(pref_pending,0);
  if(feature){int saved=save_flag(FEATURE,0);if(saved)PUT(feature_pending,0);ok=ok&&saved;}
  pthread_mutex_unlock(pref_lock);return ok;
 }
 unsigned generation=GET(revision);pthread_mutex_lock(pref_lock);
 if(master_is_on()&&GET(bridge_ready)&&GET(manual_known)&&
    (feature||GET(desired_available))&&(!session_end||monotonic()<session_end)){
  if(feature&&!save_flag(FEATURE,1))goto done;
  int previous_available=GET(desired_available);
  if(feature)PUT(desired_available,1);
  if(save_preference(1)){
   PUT(desired_enable,1);
   if(__atomic_compare_exchange_n(&revision,&generation,generation+1,0,__ATOMIC_ACQ_REL,__ATOMIC_ACQUIRE))ok=1;
   else {if(feature)remove_feature();else cancel_auto();save_preference(0);if(feature)save_flag(FEATURE,0);}
  }else if(feature){PUT(desired_available,previous_available);save_flag(FEATURE,previous_available);}
 }
done: pthread_mutex_unlock(pref_lock);return ok;
}
static void reply_flag(char *body,const char *name,int value){
 char old[1024],needle[64];memcpy(old,body,sizeof(old));snprintf(needle,sizeof(needle),"\"%s\":",name);
 char *p=strstr(old,needle);if(!p)return;
 size_t prefix=(size_t)(p-old),length=0;while(needle[length])length++;
 char *tail=p+length;while(*tail&&*tail!=',')tail++;
 old[prefix]=0;snprintf(body,1024,"%s%s%s%s",old,needle,value?"true":"false",tail);
}
static void *serve(void *unused){
 (void)unused;int s=socket(2,1|0x80000,0),one=1;
 if(s<0){cancel_auto();PUT(reason,"display_control_failed");return 0;}
 setsockopt(s,1,2,&one,sizeof(one));
 struct {unsigned short family,port;unsigned int ip;char pad[8];} addr={2,0x4d49,0x0100007f,{0}};
 if(bind(s,&addr,sizeof(addr))||listen(s,4)){close(s);cancel_auto();PUT(reason,"display_control_failed");return 0;}
 while(!GET(dead)){
  int c=accept(s,0,0);if(c<0)break;
  struct {long sec,usec;} timeout={0,250000};setsockopt(c,1,20,&timeout,sizeof(timeout));setsockopt(c,1,21,&timeout,sizeof(timeout));
  char request[1024],body[1024],reply[1400];size_t used=0;int complete=0;
  while(used+1<sizeof(request)){
   ssize_t n=read(c,request+used,sizeof(request)-used-1);if(n<=0)break;used+=n;request[used]=0;
   if(strstr(request,"\r\n\r\n")){complete=1;break;}
  }
  int known=0,ok=0;
  if(complete){
   if(!strncmp(request,"GET /display/status HTTP/1.1\r\n",30)){known=ok=1;}
   else if(!strncmp(request,"POST /display/feature-enable HTTP/1.1\r\n",sizeof("POST /display/feature-enable HTTP/1.1\r\n")-1)){known=1;ok=command(1,1);}
   else if(!strncmp(request,"POST /display/feature-disable HTTP/1.1\r\n",sizeof("POST /display/feature-disable HTTP/1.1\r\n")-1)){known=1;ok=command(1,0);}
   else if(!strncmp(request,"POST /display/enable HTTP/1.1\r\n",31)){known=1;ok=command(0,1);}
   else if(!strncmp(request,"POST /display/disable HTTP/1.1\r\n",32)||!strncmp(request,"POST /display/manual HTTP/1.1\r\n",31)){known=1;ok=command(0,0);}
  }
  if(!known||!ok)snprintf(body,sizeof(body),"{\"ok\":false,\"ready\":false,\"state\":\"display_request_failed\"}\n");
  else if(!snapshot(body,sizeof(body)))snprintf(body,sizeof(body),"{\"ok\":true,\"ready\":false,\"enabled\":false,\"available\":false,\"master\":false,\"state\":\"waiting_for_display\"}\n");
  /* Publish command flags immediately without reading Qt-owned mutable policy. */
  if(ok&&known){reply_flag(body,"enabled",GET(desired_enable));reply_flag(body,"available",GET(desired_available));reply_flag(body,"master",GET(master_enabled));}
  size_t len=0;while(body[len])len++;
  int n=snprintf(reply,sizeof(reply),"HTTP/1.1 %s\r\nContent-Type: application/json\r\nAccess-Control-Allow-Origin: *\r\nCache-Control: no-store\r\nContent-Length: %lu\r\nConnection: close\r\n\r\n%s",ok?"200 OK":"503 Unavailable",len,body);
  if(n>0&&n<(int)sizeof(reply))send(c,reply,n,0x4000);close(c);
 }
 close(s);cancel_auto();return 0;
}
static void flush(void *address,size_t n){
#ifdef X2D_DISPLAY_HOST_TEST
 (void)address;(void)n;
#else
 uintptr_t a=(uintptr_t)address,ctr;
 __asm__ volatile("mrs %0, ctr_el0":"=r"(ctr));
 uintptr_t dline=4UL<<((ctr>>16)&15),iline=4UL<<(ctr&15);
 for(uintptr_t p=a&~(dline-1);p<a+n;p+=dline)__asm__ volatile("dc cvau, %0"::"r"(p):"memory");
 __asm__ volatile("dsb ish":::"memory");
 for(uintptr_t p=a&~(iline-1);p<a+n;p+=iline)__asm__ volatile("ic ivau, %0"::"r"(p):"memory");
 __asm__ volatile("dsb ish; isb":::"memory");
#endif
}
static int image(struct dl_phdr_info *info,size_t n,void *out){
 (void)n;if(!info->name||!info->name[0]||!strcmp(info->name,"/system/bin/camera-system")){*(uintptr_t *)out=info->base;return 1;}return 0;
}
static int patch(int fd,uintptr_t address,const void *data){
 if(lseek(fd,(long)address,0)!=(long)address)return 0;
 int ok=write(fd,data,16)==16&&!memcmp((void *)address,data,16);flush((void *)address,16);return ok;
}
#ifndef X2D_DISPLAY_HOST_TEST
__attribute__((constructor)) static void initialize(void){
 const char *enabled=getenv("X2D_DISPLAY_RUNTIME");if(!enabled||strcmp(enabled,"1"))return;
 int disabled=open("/blackbox/x2d-native-menu.disable",0);if(disabled>=0){close(disabled);return;}
 char exe[128];ssize_t n=readlink("/proc/self/exe",exe,sizeof(exe)-1);if(n<=0)return;exe[n]=0;
 if(strcmp(exe,"/system/bin/camera-system")||!x2d_hash_file(exe,DISPLAY_SYSTEM_SHA))return;
 int attempt=open("/tmp/x2d-play-brightness.attempt",1|64|128|0x20000|0x80000,0600);
 if(attempt<0)return;close(attempt);
 dl_iterate_phdr(image,&base);if(!base)return;
 uintptr_t a=base+DISPLAY_BRIGHTNESS,b=base+DISPLAY_IDLE;
 if(memcmp((void *)a,display_brightness_original,16)||memcmp((void *)b,display_idle_original,16))return;
 display_resume_brightness=a+16;display_resume_idle=b+16;
 struct {u32 load,branch;uintptr_t target;} jump_a={0x58000050,0xd61f0200,(uintptr_t)brightness_hook},jump_b={0x58000050,0xd61f0200,(uintptr_t)idle_hook};
 int fd=open("/proc/self/mem",2);if(fd<0)return;
 if(!patch(fd,a,&jump_a)||!patch(fd,b,&jump_b)){
  int first=patch(fd,a,display_brightness_original),second=patch(fd,b,display_idle_original);close(fd);
  if(!first||!second)_exit(126);return;
 }
 close(fd);
 PUT(master_enabled,master_is_on());
 char pref[16],feature[16];
 int saved_enable=read_text(PREF,pref,sizeof(pref))&&!strcmp(pref,"1\n");
 int has_feature=read_text(FEATURE,feature,sizeof(feature));
 /* Preserve the earlier local build's enabled preference on a runtime restart. */
 int saved_feature=has_feature?!strcmp(feature,"1\n"):saved_enable;
 if(GET(master_enabled)&&saved_feature){PUT(desired_available,1);PUT(desired_enable,saved_enable);}

 const char *session=getenv("X2D_DISPLAY_SESSION_SECONDS");
 if(session){char *end;double seconds=strtod(session,&end);if(*end||seconds<1||seconds>600){PUT(dead,1);return;}session_end=monotonic()+seconds;PUT(desired_enable,0);}
 if(pthread_mutex_init(pref_lock,0)){cancel_auto();return;}
 unsigned long t;
 if(!pthread_create(&t,0,sample,0))pthread_detach(t);else PUT(reason,"sensor_thread_failed");
 if(!pthread_create(&t,0,serve,0))pthread_detach(t);else {cancel_auto();PUT(reason,"control_thread_failed");}
}

#endif
