// Read-only UO1.51 QA observer; actual engine commands remain in Python harness.
#include <windows.h>
#include <tlhelp32.h>
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <cstdint>
static bool Read(HANDLE p,uintptr_t address,void* value,SIZE_T bytes){SIZE_T got=0;return ReadProcessMemory(p,(void*)address,value,bytes,&got)&&got==bytes;}
static unsigned U32(HANDLE p,uintptr_t a){unsigned v=0;Read(p,a,&v,4);return v;}
int main(int argc,char**argv){
 if(argc!=3)return 2;unsigned slot=std::strtoul(argv[2],nullptr,10);if(slot>3)return 2;
 HANDLE snap=CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS,0);PROCESSENTRY32 entry={sizeof(entry)};
 if(Process32First(snap,&entry))do{
  if(_stricmp(entry.szExeFile,"CoDUOSP.exe"))continue;HANDLE p=OpenProcess(PROCESS_QUERY_INFORMATION|PROCESS_VM_READ,FALSE,entry.th32ProcessID);if(!p)continue;
  char path[4096]={};DWORD len=4095;QueryFullProcessImageNameA(p,0,path,&len);if(!strstr(path,argv[1])){CloseHandle(p);continue;}
  unsigned module=0;HANDLE ms=CreateToolhelp32Snapshot(TH32CS_SNAPMODULE,entry.th32ProcessID);MODULEENTRY32 me={sizeof(me)};
  if(Module32First(ms,&me))do{if(!_stricmp(me.szModule,"uo_gamex86.dll"))module=(uintptr_t)me.modBaseAddr;}while(Module32Next(ms,&me));CloseHandle(ms);
  unsigned ps=module?U32(p,module+0x1549c0+slot*0x2d0+0x108):0;
  int clips[128]={};bool valid=ps&&U32(p,ps+0xc4)==slot&&Read(p,ps+0x31c,clips,sizeof(clips));
  if(valid){printf("{\"pid\":%lu,\"slot\":%u,\"command_time\":%u,\"weapon\":%u,\"weapon_state\":%u,\"buttons\":%u,\"clips\":[",entry.th32ProcessID,slot,U32(p,ps),U32(p,ps+0xc8),U32(p,ps+0xcc),U32(p,ps+0x8230));for(unsigned i=0;i<128;++i)printf("%s%d",i?",":"",clips[i]);printf("]}\n");}
  CloseHandle(p);CloseHandle(snap);return valid?0:3;
 }while(Process32Next(snap,&entry));CloseHandle(snap);return 4;
}
