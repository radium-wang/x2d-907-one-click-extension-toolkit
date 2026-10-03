/* Windows x64 launcher, no CRT; the embedded Python provides the native UI. */
typedef unsigned short WCHAR;
typedef unsigned long DWORD;
typedef int BOOL;
typedef void *HANDLE;
typedef struct { DWORD cb; WCHAR *reserved,*desktop,*title; DWORD x,y,w,h,cx,cy,fill,flags;
 unsigned short show,reserved2; unsigned char *reservedBytes; HANDLE in,out,err; } STARTUP;
typedef struct { HANDLE process,thread; DWORD processId,threadId; } PROCESS;
__declspec(dllimport) DWORD __stdcall GetModuleFileNameW(HANDLE,WCHAR*,DWORD);
__declspec(dllimport) BOOL __stdcall CreateProcessW(const WCHAR*,WCHAR*,void*,void*,BOOL,DWORD,void*,const WCHAR*,STARTUP*,PROCESS*);
__declspec(dllimport) BOOL __stdcall CloseHandle(HANDLE);
__declspec(dllimport) void __stdcall ExitProcess(DWORD);
__declspec(dllimport) int __stdcall MessageBoxW(HANDLE,const WCHAR*,const WCHAR*,unsigned int);
static WCHAR directory[32768], executable[32768], command[65536];
static int add(WCHAR *to,int offset,const WCHAR *from,int limit) {
 while (*from && offset < limit-1) to[offset++]=*from++;
 to[offset]=0; return *from ? -1 : offset;
}
void mainCRTStartup(void) {
 DWORD length=GetModuleFileNameW(0,directory,32768);
 if (!length || length>=32768) goto fail;
 while (length && directory[length-1]!='\\') length--;
 if (!length) goto fail;
 directory[length]=0;
 int pos=add(executable,0,directory,32768);
 if (pos<0 || add(executable,pos,L"runtime\\pythonw.exe",32768)<0) goto fail;
 pos=add(command,0,L"\"",65536);
 pos=add(command,pos,executable,65536);
 pos=add(command,pos,L"\" -X utf8 -B -u \"",65536);
 pos=add(command,pos,directory,65536);
 if (pos<0 || add(command,pos,L"windows_app.py\"",65536)<0) goto fail;
 STARTUP startup={0}; PROCESS process={0}; startup.cb=sizeof(startup);
 if (!CreateProcessW(executable,command,0,0,0,0x08000000,0,directory,&startup,&process)) goto fail;
 CloseHandle(process.thread); CloseHandle(process.process); ExitProcess(0);
fail:
 MessageBoxW(0,L"应用未能启动，请解压完整安装包后再打开，勿单独移动 EXE 文件。\nApp could not start. Extract the complete package; do not move the EXE by itself.",L"x2d/907一键扩展功能-工具包 / X2D/907 One-Click Extension Toolkit",0x10);
 ExitProcess(1);
}
