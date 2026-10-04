/* Execute the actual adapter callbacks with a fake ScreenHandler and clock. */
#define X2D_DISPLAY_HOST_TEST 1
#define clock_gettime test_clock_gettime
#define open test_open
#define socket test_socket
#define rename test_rename
#define unlink test_unlink
#include "../src/brightness/display_runtime.c"
#undef rename
#undef unlink
#undef socket
#undef open
#undef clock_gettime
extern int printf(const char *,...);
static double test_time=10;
static int writes,last_level,last_screen;
static unsigned char fake_screen[128];
static const char *test_directory;
static int test_master=1,fail_save;
extern int open(const char *,int,...),rename(const char *,const char *),unlink(const char *);
static void mapped(const char *path,char *out){
 const char *name=path;for(const char *p=path;*p;p++)if(*p=='/')name=p+1;
 snprintf(out,512,"%s/%s",test_directory,name);
}
int test_open(const char *p,int flags,...){
 if(!strcmp(p,MASTER))return test_master?open("/dev/null",0):-1;
 if(!test_directory||fail_save)return -1;
 char path[512];mapped(p,path);
 /* Map Linux O_CREAT/O_TRUNC to macOS flags; no camera paths are accessed. */
 return open(path,(flags&3)|((flags&64)?0x200:0)|((flags&512)?0x400:0),0600);
}
int test_rename(const char *a,const char *b){char from[512],to[512];mapped(a,from);mapped(b,to);return rename(from,to);}
int test_unlink(const char *p){char path[512];mapped(p,path);return unlink(path);}
int test_socket(int domain,int type,int protocol){(void)domain;(void)type;(void)protocol;return -1;}
int test_clock_gettime(int clock,void *out){(void)clock;struct timespec_local *t=out;t->sec=(long)test_time;t->nsec=(long)((test_time-t->sec)*1e9);return 0;}
uintptr_t display_resume_brightness,display_resume_idle;
int display_original_brightness(void *self,int which,unsigned value){
 if(self!=fake_screen)return -1;writes++;last_level=value;last_screen=which;return 0;
}
void display_original_idle(void *self,int value){(void)self;(void)value;}
#define CHECK(x) do{if(!(x)){printf("FAIL line %d: %s\n",__LINE__,#x);return 1;}}while(0)
static void sensor(double value,int valid){PUT(sensor_value_bits,bits(value));PUT(sensor_time_bits,bits(test_time-.001));PUT(sensor_valid,valid);}
static void advance(double seconds,double value,int valid){
 int n=(int)(seconds/.02+.5);for(int i=0;i<n;i++){test_time+=.02;if(i%10==0)sensor(value,valid);tick(timer_object,0);}
}
int main(int argc,char **argv){
 CHECK(argc==2);test_directory=argv[1];CHECK(!pthread_mutex_init(pref_lock,0));
 master_enabled=1;
 screen=fake_screen;timer_object=(void *)0x1234;manual_known=1;manual_level=100;last_output=50;
 fake_screen[0x40]=1;fake_screen[0x51]=1;*(unsigned *)(fake_screen+0x44)=1;
 idle_state=0;bridge_ready=1;brightness_reset(&policy,50,test_time);desired_available=1;desired_enable=1;
 advance(5,750,1);CHECK(last_level==100&&policy.effective&&last_screen==1);
 int before=writes;idle_hook(0,1);advance(2,0,1);CHECK(writes==before&&!policy.effective);
 idle_hook(0,2);advance(1,2621,1);CHECK(writes==before);
 idle_hook(0,0);*(unsigned *)(fake_screen+0x44)=2;advance(1,0,1);CHECK(writes==before);
 *(unsigned *)(fake_screen+0x44)=1;advance(16,0,1);CHECK(last_level==5&&policy.effective);
 advance(.2,0,0);CHECK(last_level==100&&!policy.effective&&desired_enable==1);
 advance(5,2621,1);CHECK(last_level==100&&policy.effective);
 /* Automatic model writes change the ceiling without flashing or cancelling. */
 before=writes;brightness_hook(fake_screen,1,37);
 CHECK(desired_enable&&manual_level==37&&writes==before);
 advance(.1,750,1);CHECK(last_level==37&&policy.effective);
 before=writes;brightness_hook(fake_screen,1,80);CHECK(writes==before&&desired_enable);
 advance(2,750,1);CHECK(last_level==80);
 advance(4,0,1);CHECK(last_level==5&&manual_level==80);
 /* Display disable restores the saved ceiling and keeps the feature available. */
 cancel_auto();advance(.1,750,1);CHECK(last_level==80&&desired_available);
 brightness_hook(fake_screen,1,37);CHECK(!desired_enable&&manual_level==37&&last_level==37);
 desired_enable=1;advance(4,750,1);CHECK(last_level==37);
 session_end=test_time+.4;advance(1,750,1);CHECK(!desired_enable&&last_level==37);
 session_end=0;desired_enable=1;advance(4,0,1);CHECK(last_level==5);
 test_time+=1;sensor_valid=1;tick(timer_object,0);CHECK(last_level==37&&!policy.effective);
 fake_screen[0x40]=3;before=writes;advance(2,750,1);CHECK(writes==before);
 fake_screen[0x40]=1;desired_enable=1;advance(4,750,1);
 cancel_auto();advance(.2,750,1);CHECK(last_level==37&&!policy.effective);
 CHECK(last_screen==1);
 desired_enable=1;pref_pending=0;serve(0);
 CHECK(!desired_enable&&pref_pending&&!strcmp(GET(reason),"display_control_failed"));
 printf("PASS: real adapter callbacks, rear-only output, idle/fade/off/EVF/suspend, zero, sensor fallback, manual override, expiry\n");
 /* Toolkit master off restores the manual level and clears effective output. */
 PUT(desired_enable,1);master_enabled=1;idle_state=0;
 advance(2,450,1);CHECK(policy.effective);
 master_enabled=0;advance(.1,450,1);
 CHECK(!GET(desired_enable)&&!GET(desired_available)&&!policy.effective&&last_level==manual_level);
 /* Turning the master back on does not re-enable the child. */
 master_enabled=1;advance(.1,450,1);CHECK(!GET(desired_enable));
 struct brightness_policy paced={0};int out=0,previous=100,steps=0,last_tick=-1,max_gap=0;
 brightness_reset(&paced,100,0);
 for(int i=1;i<=250;i++){
  if(brightness_step(&paced,1,1,0,1,100,i*.02,&out)){
   CHECK(out==previous-1);previous=out;steps++;
   if(last_tick>=0&&i-last_tick>max_gap)max_gap=i-last_tick;
   last_tick=i;
  }
 }
 CHECK(steps==95&&previous==5&&max_gap<=3);
 printf("PASS: ceiling edits preserve Auto, disable restores ceiling, master hides feature, dimming has no long tail\n");
 /* The same command handler used by the real HTTP server persists both switches. */
 bridge_ready=1;test_master=1;session_end=0;
 CHECK(command(1,1)&&desired_available&&desired_enable);
 char saved[32];CHECK(read_text(FEATURE,saved,sizeof(saved))&&!strcmp(saved,"1\n"));
 CHECK(read_text(PREF,saved,sizeof(saved))&&!strcmp(saved,"1\n"));
 CHECK(command(0,0)&&desired_available&&!desired_enable);
 CHECK(read_text(FEATURE,saved,sizeof(saved))&&!strcmp(saved,"1\n"));
 CHECK(read_text(PREF,saved,sizeof(saved))&&!strcmp(saved,"0\n"));
 CHECK(command(0,1)&&desired_available&&desired_enable);
 CHECK(command(1,0)&&!desired_available&&!desired_enable);
 CHECK(read_text(FEATURE,saved,sizeof(saved))&&!strcmp(saved,"0\n"));
 CHECK(!command(0,1)&&!desired_enable);
 test_master=0;CHECK(!command(1,1)&&!desired_available&&!desired_enable);
 test_master=1;fail_save=1;CHECK(!command(1,1)&&!desired_available&&!desired_enable);fail_save=0;
 /* Stock inactive writes and the subsequent wake retain the real last output. */
 desired_available=1;desired_enable=1;master_enabled=1;idle_state=2;
 brightness_hook(fake_screen,1,80);CHECK(last_level==80&&policy.applied==80&&desired_enable);
 idle_state=0;advance(.1,0,1);CHECK(last_level>=77&&last_level<=80&&policy.effective);
 bridge_ready=0;before=writes;brightness_hook(fake_screen,1,63);
 CHECK(writes==before+1&&last_level==63&&manual_level==63);
 bridge_ready=1;
 printf("PASS: real feature/Auto command persistence, master refusal, save failure, bridge fallback and stock wake synchronization\n");
 return 0;
}
