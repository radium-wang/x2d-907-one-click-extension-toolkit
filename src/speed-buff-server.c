/* Fixed loopback-only transport. No request text becomes a shell command. */
typedef unsigned long size_t;
typedef long ssize_t;
extern int socket(int,int,int),bind(int,const void*,unsigned),listen(int,int),accept(int,void*,void*),close(int),setsockopt(int,int,int,const void*,unsigned);
extern ssize_t read(int,void*,size_t),write(int,const void*,size_t);
extern int open(const char*,int,...),strcmp(const char*,const char*),strncmp(const char*,const char*,size_t),system(const char*);
extern char *getenv(const char*);
extern int unsetenv(const char*),unlink(const char*);
extern void _exit(int);
extern int snprintf(char*,size_t,const char*,...);
struct addr {unsigned short family,port;unsigned int ip;char pad[8];};
struct timeval {long sec,usec;};
static const char *fallback="{\"ready\":false,\"active\":false,\"master\":false,\"message\":\"加速服务拒绝操作，请恢复原状\"}";
static int menu_ack(const char *action) {
 const char *value = !strcmp(action,"menu_ready_11") ? "MENU_ENTRY_READY_11" :
                     !strcmp(action,"menu_ready_12") ? "MENU_ENTRY_READY_12" : 0;
 if(!value){unlink("/tmp/x2d-native-menu-ui.ready");return 0;}
 int f=open("/tmp/x2d-native-menu-ui.ready",1|64|512,0600);if(f<0)return -1;
 int ok=write(f,value,19)==19;close(f);return ok?0:-1;
}
static int run(const char *action) {
 if(!strcmp(action,"status"))return system("/system/bin/sh /system/etc/x2d-speed-buff/worker status");
 if(!strcmp(action,"enable"))return system("/system/bin/sh /system/etc/x2d-speed-buff/worker enable");
 if(!strcmp(action,"disable"))return system("/system/bin/sh /system/etc/x2d-speed-buff/worker disable");
 if(!strcmp(action,"afc_on"))return system("/system/bin/sh /system/etc/x2d-speed-buff/worker afc_on");
 if(!strcmp(action,"afc_off"))return system("/system/bin/sh /system/etc/x2d-speed-buff/worker afc_off");
 if(!strcmp(action,"master_on"))return system("/system/bin/sh /system/etc/x2d-speed-buff/worker master_on");
 if(!strcmp(action,"master_off"))return system("/system/bin/sh /system/etc/x2d-speed-buff/worker master_off");
 return -1;
}
__attribute__((constructor)) static void serve(void) {
 const char *env=getenv("X2D_SPEED_SERVER");if(!env||strcmp(env,"1"))return;
 int s=socket(2,1,0),one=1;if(s<0)_exit(70);
 setsockopt(s,1,2,&one,sizeof(one));
 struct addr a={2,0x4b49,0x0100007f,{0}}; /* 18763, 127.0.0.1 */
 if(bind(s,&a,sizeof(a))||listen(s,4)){close(s);_exit(71);}
 unsetenv("LD_PRELOAD");unsetenv("X2D_SPEED_SERVER");
 unlink("/tmp/x2d-native-menu-ui.ready");
 /* Reapply a saved enabled state only through full original/hash preflight. */
 /* The saved AF-C flag controls availability only. Preserve the stock
  * focus mode selected by the user (AF-S / AF-C / MF) at startup. */
 system("if [ -e /blackbox/x2d-speed-buff.master ] && [ -e /blackbox/x2d-speed-buff.enabled ]; then n=0; while [ $n -lt 30 ]; do /system/bin/sh /system/etc/x2d-speed-buff/worker enable && break; n=$((n+1)); sleep 1; done; fi");
 for(;;){
  int c=accept(s,0,0);if(c<0)continue;
  struct timeval t={3,0};setsockopt(c,1,20,&t,sizeof(t));setsockopt(c,1,21,&t,sizeof(t));
  char req[512]={0};ssize_t n=read(c,req,sizeof(req)-1);const char *action=0;
  if(n>0){
   if(!strncmp(req,"GET /status HTTP/1.",19))action="status";
   else if(!strncmp(req,"POST /menu_ready_11 HTTP/1.",27))action="menu_ready_11";
   else if(!strncmp(req,"POST /menu_ready_12 HTTP/1.",27))action="menu_ready_12";
   else if(!strncmp(req,"POST /menu_unavailable HTTP/1.",30))action="menu_unavailable";
   else if(!strncmp(req,"POST /enable HTTP/1.",20))action="enable";
   else if(!strncmp(req,"POST /disable HTTP/1.",21))action="disable";
   else if(!strncmp(req,"POST /afc_on HTTP/1.",20))action="afc_on";
   else if(!strncmp(req,"POST /afc_off HTTP/1.",21))action="afc_off";
   else if(!strncmp(req,"POST /master_on HTTP/1.",23))action="master_on";
   else if(!strncmp(req,"POST /master_off HTTP/1.",24))action="master_off";
  }
  char body[1024];int len=0;
  int menu_action=action && !strncmp(action,"menu_",5);
  int ok=action && (menu_action ? menu_ack(action) : run(action))==0;
  if(menu_action && ok) len=snprintf(body,sizeof(body),"{\"menuAcknowledged\":true}");
  if(ok && !menu_action){int f=open("/tmp/x2d-speed-buff/ui.json",0);if(f>=0){len=(int)read(f,body,sizeof(body)-1);close(f);}}
  if(len<=0){len=snprintf(body,sizeof(body),"%s",fallback);}
  char header[256];int h=snprintf(header,sizeof(header),"HTTP/1.1 200 OK\r\nContent-Type: application/json; charset=utf-8\r\nAccess-Control-Allow-Origin: *\r\nCache-Control: no-store\r\nContent-Length: %d\r\nConnection: close\r\n\r\n",len);
  write(c,header,h);write(c,body,len);close(c);
 }
}
