// Standalone32bit debugger: no code/data patches; one exact owned-process DR0 write watchpoint.
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <tlhelp32.h>
#include <cstdio>
#include <cstdlib>
#include <cstdint>
#include <cstring>
#include <string>
#include <vector>
struct Saved {DWORD tid;HANDLE thread;CONTEXT original;bool armed;};
static volatile LONG interrupted=0;
BOOL WINAPI Interrupt(DWORD){InterlockedExchange(&interrupted,1);return TRUE;}
static std::string escaped(const char*s){std::string out;for(;*s;++s){unsigned char c=*s;if(c=='\\'||c=='"'){out+='\\';out+=(char)c;}else if(c<32){char b[8];std::snprintf(b,sizeof b,"\\u%04x",c);out+=b;}else out+=(char)c;}return out;}
static void event(FILE*f,const char*status,const char*reason){std::fprintf(f,"{\"status\":\"%s\",\"reason\":\"%s\",\"winerror\":%lu}\n",status,escaped(reason).c_str(),GetLastError());std::fflush(f);}
static bool identity(HANDLE process,const char*expected){char name[32768];DWORD n=sizeof name;return QueryFullProcessImageNameA(process,0,name,&n)&&!_stricmp(name,expected);}
static bool read(HANDLE p,uintptr_t address,void*out,size_t n){SIZE_T got=0;return ReadProcessMemory(p,(void*)address,out,n,&got)&&got==n;}
static bool context(HANDLE thread,CONTEXT&c,bool set){
 if(SuspendThread(thread)==(DWORD)-1)return false;
 BOOL ok=set?SetThreadContext(thread,&c):GetThreadContext(thread,&c);DWORD err=GetLastError();
 bool resumed=ResumeThread(thread)!=(DWORD)-1;SetLastError(err);return ok&&resumed;
}
static bool saveThread(std::vector<Saved>&saved,DWORD tid){
 for(const auto&s:saved)if(s.tid==tid)return true;
 HANDLE thread=OpenThread(THREAD_GET_CONTEXT|THREAD_SET_CONTEXT|THREAD_SUSPEND_RESUME|THREAD_QUERY_INFORMATION|SYNCHRONIZE,FALSE,tid);if(!thread)return false;
 CONTEXT c{};c.ContextFlags=CONTEXT_DEBUG_REGISTERS;
 if(!context(thread,c,false)){CloseHandle(thread);return false;}
 if(c.Dr0||c.Dr1||c.Dr2||c.Dr3||(c.Dr7&0xff)){CloseHandle(thread);SetLastError(ERROR_BUSY);return false;}
 saved.push_back({tid,thread,c,false});return true;
}
static bool arm(Saved&s,uintptr_t address){CONTEXT c=s.original;c.ContextFlags=CONTEXT_DEBUG_REGISTERS;c.Dr0=(DWORD)address;c.Dr6&=~15u;c.Dr7=(c.Dr7&~0x000f0003u)|1u|(1u<<16)|(3u<<18);s.armed=true;if(!context(s.thread,c,true))return false;return true;}
static bool collect(std::vector<Saved>&saved,DWORD pid){
 HANDLE snap=CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD,0);if(snap==INVALID_HANDLE_VALUE)return false;
 THREADENTRY32 t{};t.dwSize=sizeof t;BOOL more=Thread32First(snap,&t);bool ok=true;unsigned count=0;
 for(;more;more=Thread32Next(snap,&t))if(t.th32OwnerProcessID==pid){if(++count>256||!saveThread(saved,t.th32ThreadID)){ok=false;break;}}
 CloseHandle(snap);return ok&&count;
}
static bool restore(std::vector<Saved>&saved){bool ok=true;for(auto&s:saved){if(s.armed&&WaitForSingleObject(s.thread,0)!=WAIT_OBJECT_0){CONTEXT c=s.original;c.ContextFlags=CONTEXT_DEBUG_REGISTERS;if(!context(s.thread,c,true))ok=false;
 CONTEXT check{};check.ContextFlags=CONTEXT_DEBUG_REGISTERS;
 if(!context(s.thread,check,false)||check.Dr0!=c.Dr0||check.Dr1!=c.Dr1||check.Dr2!=c.Dr2||check.Dr3!=c.Dr3||check.Dr6!=c.Dr6||check.Dr7!=c.Dr7)ok=false;}CloseHandle(s.thread);}saved.clear();return ok;}
static void capture(FILE*f,HANDLE process,DWORD pid,DWORD tid,uintptr_t address){
 HANDLE thread=OpenThread(THREAD_GET_CONTEXT|THREAD_SUSPEND_RESUME,FALSE,tid);CONTEXT c{};c.ContextFlags=CONTEXT_FULL|CONTEXT_DEBUG_REGISTERS;bool got=thread&&context(thread,c,false);if(thread)CloseHandle(thread);
 uint32_t value=0;bool valueOK=read(process,address,&value,4);char module[MAX_PATH]="<unknown>";uintptr_t base=0;
 HANDLE modules=CreateToolhelp32Snapshot(TH32CS_SNAPMODULE|TH32CS_SNAPMODULE32,pid);MODULEENTRY32 m{};m.dwSize=sizeof m;
 if(modules!=INVALID_HANDLE_VALUE){for(BOOL more=Module32First(modules,&m);more;more=Module32Next(modules,&m))if(c.Eip>=(uintptr_t)m.modBaseAddr&&c.Eip-(uintptr_t)m.modBaseAddr<m.modBaseSize){std::snprintf(module,sizeof module,"%s",m.szExePath);base=(uintptr_t)m.modBaseAddr;break;}CloseHandle(modules);}
 uint32_t stack[16]={};uint8_t code[48]={};bool stackOK=got&&read(process,c.Esp,stack,sizeof stack);bool codeOK=got&&c.Eip>=16&&read(process,c.Eip-16,code,sizeof code);
 std::fprintf(f,"{\"status\":\"WRITE\",\"pid\":%lu,\"tid\":%lu,\"address\":%lu,\"value_read\":%s,\"new_value\":%lu,\"context_read\":%s,\"ip_after_write\":%lu,\"module\":\"%s\",\"module_base\":%lu,\"module_rva_after_write\":%lu,\"eax\":%lu,\"ebx\":%lu,\"ecx\":%lu,\"edx\":%lu,\"esi\":%lu,\"edi\":%lu,\"esp\":%lu,\"ebp\":%lu,\"eflags\":%lu,\"dr6\":%lu,\"stack_read\":%s,\"stack\":[",pid,tid,(DWORD)address,valueOK?"true":"false",(DWORD)value,got?"true":"false",c.Eip,escaped(module).c_str(),(DWORD)base,(DWORD)(c.Eip-base),c.Eax,c.Ebx,c.Ecx,c.Edx,c.Esi,c.Edi,c.Esp,c.Ebp,c.EFlags,c.Dr6,stackOK?"true":"false");
 for(unsigned i=0;i<16;++i){std::fprintf(f,"%s%lu",i?",":"",(DWORD)stack[i]);}std::fprintf(f,"],\"code_read\":%s,\"code_start\":%lu,\"code_hex\":\"",codeOK?"true":"false",c.Eip-16);
 for(auto b:code){std::fprintf(f,"%02x",b);}std::fprintf(f,"\"}\n");std::fflush(f);
}
int main(int argc,char**argv){
 if(argc<3||argc%2==0){std::fprintf(stderr,"--pid N --exe EXACT_PATH (--address HEX | --module NAME --rva HEX) --expected N --timeout-ms N --output PATH\n");return 2;}
 const char*expectedPath=nullptr,*output=nullptr,*moduleName=nullptr;DWORD pid=0,expectedValue=0,timeout=0;uintptr_t address=0,rva=0;bool hasAddress=false,hasRva=false;
 for(int i=1;i<argc;i+=2){char*end=nullptr;const char*key=argv[i];const char*value=argv[i+1];if(!std::strcmp(key,"--exe")){expectedPath=value;continue;}if(!std::strcmp(key,"--output")){output=value;continue;}if(!std::strcmp(key,"--module")){moduleName=value;continue;}unsigned long n=std::strtoul(value,&end,!std::strcmp(key,"--address")||!std::strcmp(key,"--rva")?16:10);if(!*value||!end||*end)return 2;if(!std::strcmp(key,"--pid"))pid=n;else if(!std::strcmp(key,"--address")){address=n;hasAddress=true;}else if(!std::strcmp(key,"--rva")){rva=n;hasRva=true;}else if(!std::strcmp(key,"--expected"))expectedValue=n;else if(!std::strcmp(key,"--timeout-ms"))timeout=n;else return 2;}
 if(!pid||pid==GetCurrentProcessId()||!expectedPath||!output||hasAddress==hasRva||!timeout||timeout>120000)return 2;
 if(hasRva&&(!moduleName||!*moduleName||(rva&3)))return 2;
 FILE*f=std::fopen(output,"wb");if(!f)return 2;SetConsoleCtrlHandler(Interrupt,TRUE);
 if(hasRva){
  HANDLE modules=CreateToolhelp32Snapshot(TH32CS_SNAPMODULE|TH32CS_SNAPMODULE32,pid);MODULEENTRY32 m{};m.dwSize=sizeof m;uintptr_t base=0;DWORD size=0;
  if(modules!=INVALID_HANDLE_VALUE){for(BOOL more=Module32First(modules,&m);more;more=Module32Next(modules,&m))if(!_stricmp(m.szModule,moduleName)){base=(uintptr_t)m.modBaseAddr;size=m.modBaseSize;break;}CloseHandle(modules);}
  if(!base||rva+4>size){event(f,"REJECTED","module/rva resolution failed");std::fclose(f);return 3;}
  address=base+rva;
  std::fprintf(f,"{\"status\":\"RESOLVED\",\"module\":\"%s\",\"module_base\":%lu,\"module_rva\":%lu,\"address\":%lu}\n",escaped(moduleName).c_str(),(DWORD)base,(DWORD)rva,(DWORD)address);std::fflush(f);
 }
 if(address<0x10000||(address&3)){event(f,"REJECTED","address invalid");std::fclose(f);return 2;}
 HANDLE process=OpenProcess(PROCESS_QUERY_INFORMATION|PROCESS_VM_READ|SYNCHRONIZE,FALSE,pid);BOOL debugged=FALSE;uint32_t initial=0;MEMORY_BASIC_INFORMATION mbi{};
 bool valid=process&&identity(process,expectedPath)&&CheckRemoteDebuggerPresent(process,&debugged)&&!debugged&&VirtualQueryEx(process,(void*)address,&mbi,sizeof mbi)==sizeof mbi&&mbi.State==MEM_COMMIT&&!(mbi.Protect&(PAGE_GUARD|PAGE_NOACCESS))&&read(process,address,&initial,4)&&initial==expectedValue;
 if(!valid){event(f,"REJECTED","PID/path/debugger/address/initial-value verification failed");if(process)CloseHandle(process);std::fclose(f);return 3;}
 if(!DebugActiveProcess(pid)){event(f,"REJECTED","debug attach failed");CloseHandle(process);std::fclose(f);return 3;}
 if(!DebugSetProcessKillOnExit(FALSE)){event(f,"ERROR","cannot disable debug kill-on-exit");DebugActiveProcessStop(pid);CloseHandle(process);std::fclose(f);return 5;}std::vector<Saved> saved;bool initialBreak=false,armed=false,hit=false,terminated=false,failed=false,rejected=false,pending=false;DEBUG_EVENT e{};DWORD continuation=DBG_CONTINUE;ULONGLONG deadline=GetTickCount64()+timeout;
 event(f,"ATTACHED","verified exact process; code/data untouched");
 while(GetTickCount64()<deadline&&!interrupted){
  if(!WaitForDebugEvent(&e,100)){if(GetLastError()==ERROR_SEM_TIMEOUT)continue;failed=true;event(f,"ERROR","WaitForDebugEvent failed");break;}pending=true;continuation=DBG_CONTINUE;
  if(e.dwDebugEventCode==CREATE_PROCESS_DEBUG_EVENT){if(e.u.CreateProcessInfo.hFile)CloseHandle(e.u.CreateProcessInfo.hFile);if(e.u.CreateProcessInfo.hProcess)CloseHandle(e.u.CreateProcessInfo.hProcess);if(e.u.CreateProcessInfo.hThread)CloseHandle(e.u.CreateProcessInfo.hThread);}
  else if(e.dwDebugEventCode==LOAD_DLL_DEBUG_EVENT){if(e.u.LoadDll.hFile)CloseHandle(e.u.LoadDll.hFile);}
  else if(e.dwDebugEventCode==CREATE_THREAD_DEBUG_EVENT){if(e.u.CreateThread.hThread)CloseHandle(e.u.CreateThread.hThread);if(armed){bool ok=saveThread(saved,e.dwThreadId);if(ok)for(auto&thread:saved)if(thread.tid==e.dwThreadId){ok=arm(thread,address);break;}if(!ok){failed=true;event(f,"ERROR","new thread has conflicting/unavailable debug registers");break;}}}
  else if(e.dwDebugEventCode==EXIT_THREAD_DEBUG_EVENT){for(auto it=saved.begin();it!=saved.end();++it)if(it->tid==e.dwThreadId){CloseHandle(it->thread);saved.erase(it);break;}}
  else if(e.dwDebugEventCode==EXIT_PROCESS_DEBUG_EVENT){terminated=true;break;}
  else if(e.dwDebugEventCode==EXCEPTION_DEBUG_EVENT){DWORD code=e.u.Exception.ExceptionRecord.ExceptionCode;
   if(code==EXCEPTION_BREAKPOINT&&!initialBreak){initialBreak=true;
    // Debug event has all target threads stopped; reject conflicts BEFORE any arm.
    if(!identity(process,expectedPath)||!read(process,address,&initial,4)||initial!=expectedValue||!collect(saved,pid)){failed=true;rejected=true;event(f,"REJECTED","stopped-process identity/initial-value/thread-register verification failed");break;}
    for(auto&s:saved)if(!arm(s,address)){failed=true;break;}
    if(failed){event(f,"ERROR","SetThreadContext failed");break;}armed=true;event(f,"ARMED","DR0 write4; original debug registers preserved");
   }else if(code==EXCEPTION_SINGLE_STEP&&armed){HANDLE t=OpenThread(THREAD_GET_CONTEXT|THREAD_SUSPEND_RESUME,FALSE,e.dwThreadId);CONTEXT c{};c.ContextFlags=CONTEXT_DEBUG_REGISTERS;bool ours=t&&context(t,c,false)&&(c.Dr6&1);if(t)CloseHandle(t);if(ours){capture(f,process,pid,e.dwThreadId,address);hit=true;break;}continuation=DBG_EXCEPTION_NOT_HANDLED;
   }else continuation=DBG_EXCEPTION_NOT_HANDLED;
  }
  if(!ContinueDebugEvent(e.dwProcessId,e.dwThreadId,continuation)){failed=true;event(f,"ERROR","ContinueDebugEvent failed");break;}pending=false;
 }
 bool restored=restore(saved);if(pending){if(!ContinueDebugEvent(e.dwProcessId,e.dwThreadId,continuation))restored=false;pending=false;}
 bool detached=DebugActiveProcessStop(pid)!=0;if(terminated)detached=true;
 std::fprintf(f,"{\"status\":\"CLEANUP\",\"restored\":%s,\"detached\":%s,\"hit\":%s,\"armed\":%s,\"target_exited\":%s,\"interrupted\":%s}\n",restored?"true":"false",detached?"true":"false",hit?"true":"false",armed?"true":"false",terminated?"true":"false",interrupted?"true":"false");
 CloseHandle(process);std::fclose(f);return restored&&detached?(rejected?3:failed?5:hit?0:4):5;
}
