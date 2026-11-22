#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <cstdio>
#include <cstdlib>
#include <cstdint>
#include <string>
volatile LONG watched=988;
volatile LONG unrelated=0;
DWORD WINAPI WriteLater(void*){Sleep(900);InterlockedExchange(&watched,-16777216);return 0;}
DWORD WINAPI InstallConflict(void*p){HANDLE mainThread=(HANDLE)p;CONTEXT c{};c.ContextFlags=CONTEXT_DEBUG_REGISTERS;if(SuspendThread(mainThread)==(DWORD)-1)return 1;bool ok=GetThreadContext(mainThread,&c)!=0;c.Dr3=(DWORD)(uintptr_t)&unrelated;c.Dr7|=(1u<<6)|(1u<<28)|(3u<<30);ok=ok&&SetThreadContext(mainThread,&c);ResumeThread(mainThread);return ok?0:2;}
int main(int argc,char**argv){
 if(argc!=5){return 2;}int mode=std::atoi(argv[3]);
 if(mode==3){HANDLE mainThread=OpenThread(THREAD_GET_CONTEXT|THREAD_SET_CONTEXT|THREAD_SUSPEND_RESUME,FALSE,GetCurrentThreadId());if(!mainThread)return 3;HANDLE setter=CreateThread(nullptr,0,InstallConflict,mainThread,0,nullptr);if(!setter)return 3;WaitForSingleObject(setter,5000);DWORD rc=3;GetExitCodeThread(setter,&rc);CloseHandle(setter);CloseHandle(mainThread);if(rc)return 3;}
 FILE*f=std::fopen(argv[1],"wb");if(!f)return 2;char path[32768];DWORD n=sizeof path;QueryFullProcessImageNameA(GetCurrentProcess(),0,path,&n);std::fprintf(f,"%lu %08lx\n%s\n",GetCurrentProcessId(),(DWORD)(uintptr_t)&watched,path);std::fclose(f);
 Sleep((DWORD)std::strtoul(argv[2],nullptr,10));
 if(mode==2){HANDLE writer=CreateThread(nullptr,0,WriteLater,nullptr,0,nullptr);if(!writer)return 4;WaitForSingleObject(writer,5000);CloseHandle(writer);}else if(mode==1||mode==3)InterlockedExchange(&watched,-16777216);
 Sleep((DWORD)std::strtoul(argv[4],nullptr,10));f=std::fopen((std::string(argv[1])+".done").c_str(),"wb");if(f){std::fprintf(f,"%ld",watched);std::fclose(f);}return 0;
}
