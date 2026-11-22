// Read-only owned UO camera observer; all addresses verified against native 1.51 CGame.
#include <windows.h>
#include <tlhelp32.h>
#include <cstdio>
#include <cstring>
int main(int argc,char**argv){
 if(argc!=2)return 2;
 HANDLE snap=CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS,0); PROCESSENTRY32 p={sizeof(p)};
 if(Process32First(snap,&p))do{
  if(_stricmp(p.szExeFile,"CoDUOSP.exe"))continue;
  HANDLE h=OpenProcess(PROCESS_QUERY_INFORMATION|PROCESS_VM_READ,FALSE,p.th32ProcessID); if(!h)continue;
  char path[4096]={};DWORD len=4095;QueryFullProcessImageNameA(h,0,path,&len);
  if(!strstr(path,argv[1])){CloseHandle(h);continue;}
  HANDLE ms=CreateToolhelp32Snapshot(TH32CS_SNAPMODULE,p.th32ProcessID);MODULEENTRY32 m={sizeof(m)};uintptr_t cg=0;
  if(Module32First(ms,&m))do{if(!_stricmp(m.szModule,"uo_cgamex86.dll"))cg=(uintptr_t)m.modBaseAddr;}while(Module32Next(ms,&m));CloseHandle(ms);
  float camera[3]={},predicted[3]={};unsigned pm=999,flags=0,render=0;SIZE_T n=0;
  bool ok=cg&&ReadProcessMemory(h,(void*)(cg+0x275ec8),camera,12,&n)&&n==12&&ReadProcessMemory(h,(void*)(cg+0x26d9f8),predicted,12,&n)&&n==12;
  ReadProcessMemory(h,(void*)(cg+0x26d9e8),&pm,4,&n);ReadProcessMemory(h,(void*)(cg+0x275efc),&flags,4,&n);
  ReadProcessMemory(h,(void*)0x482dfec,&render,4,&n);
  if(ok)printf("{\"pid\":%lu,\"camera\":[%.5f,%.5f,%.5f],\"predicted_origin\":[%.5f,%.5f,%.5f],\"pm_type\":%u,\"ref_flags\":%u,\"render_scene_address\":%u}\n",p.th32ProcessID,camera[0],camera[1],camera[2],predicted[0],predicted[1],predicted[2],pm,flags,render);
  CloseHandle(h);CloseHandle(snap);return ok?0:1;
 }while(Process32Next(snap,&p));CloseHandle(snap);return 1;
}
