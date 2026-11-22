// Owned-window native input injection ONLY; never writes process/game memory.
// Run in the harness's private WINEPREFIX. Exact exe suffix+PID+window title
// binding and foreground verification precede any SendInput event.
#include <windows.h>
#include <tlhelp32.h>
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <string>
struct Target{DWORD pid;HWND window;bool uo;};
static BOOL CALLBACK windowForProcess(HWND w,LPARAM raw){
 auto& t=*reinterpret_cast<Target*>(raw);DWORD pid=0;GetWindowThreadProcessId(w,&pid);
 if(pid!=t.pid||!IsWindowVisible(w))return TRUE;
 char title[256]={};GetWindowTextA(w,title,255);
 char windowClass[256]={};GetClassNameA(w,windowClass,255);
 // Observed native UO caption/class are "CoD:United Offensive", not
 // "Call of Duty". Never target its separate WinConsole or an IME window.
 if(t.uo) {
  if(std::strcmp(windowClass,"CoD:United Offensive")||std::strcmp(title,"CoD:United Offensive"))return TRUE;
 } else if(!std::strstr(title,"Call of Duty")||std::strstr(windowClass,"Console"))return TRUE;
 t.window=w;return FALSE;
}
int main(int argc,char** argv){
 if(argc!=5)return 2;bool uo=!std::strcmp(argv[2],"uo");if(!uo&&std::strcmp(argv[2],"cod1"))return 2;
 char* end=nullptr;long dx=std::strtol(argv[3],&end,10);if(!end||*end||dx<-1000||dx>1000)return 2;
 long dy=std::strtol(argv[4],&end,10);if(!end||*end||dy<-1000||dy>1000)return 2;
 const char* exe=uo?"CoDUOSP.exe":"CoDSP.exe";std::string suffix=std::string(argv[1])+"\\"+exe;
 HANDLE list=CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS,0);PROCESSENTRY32 entry={sizeof(entry)};Target target={};
 if(Process32First(list,&entry))do{
  if(_stricmp(entry.szExeFile,exe))continue;
  HANDLE p=OpenProcess(PROCESS_QUERY_INFORMATION,FALSE,entry.th32ProcessID);if(!p)continue;
  char path[4096]={};DWORD length=4095;bool valid=QueryFullProcessImageNameA(p,0,path,&length)!=0;CloseHandle(p);
  size_t size=std::strlen(path);if(!valid||size<suffix.size()||_stricmp(path+size-suffix.size(),suffix.c_str()))continue;
  target.pid=entry.th32ProcessID;target.uo=uo;EnumWindows(windowForProcess,reinterpret_cast<LPARAM>(&target));if(target.window)break;
 }while(Process32Next(list,&entry));CloseHandle(list);if(!target.window)return 3;
 DWORD before=0,after=0;GetWindowThreadProcessId(GetForegroundWindow(),&before);
 // Attach only this helper to its owned target. Never merge the two game
 // processes' input queues through the currently foreground third thread.
 DWORD thread=GetCurrentThreadId(),targetThread=GetWindowThreadProcessId(target.window,nullptr);
 bool attached=thread!=targetThread&&AttachThreadInput(thread,targetThread,TRUE);
 if(IsIconic(target.window))ShowWindowAsync(target.window,SW_RESTORE);
 SetForegroundWindow(target.window);SetFocus(target.window);
 Sleep(100);HWND active=GetForegroundWindow();GetWindowThreadProcessId(active,&after);
 UINT sent=0;
 if(after==target.pid&&active==target.window){INPUT input={};input.type=INPUT_MOUSE;input.mi.dx=dx;input.mi.dy=dy;input.mi.dwFlags=MOUSEEVENTF_MOVE;sent=SendInput(1,&input,sizeof(input));Sleep(150);}
 if(attached)AttachThreadInput(thread,targetThread,FALSE);
 std::printf("{\"target_pid\":%lu,\"foreground_before\":%lu,\"foreground_after\":%lu,\"dx\":%ld,\"dy\":%ld,\"sent\":%u}\n",target.pid,before,after,dx,dy,sent);
 return after==target.pid&&active==target.window&&sent==1?0:4;
}
