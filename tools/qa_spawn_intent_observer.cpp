// Read-only 32-bit native observer. No process writes, breakpoints or suspension.
// Stack words are explicitly reported as candidates, together with loading/VM
// state; the static call-chain evidence determines their native ABI meaning.
#include <windows.h>
#include <tlhelp32.h>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>
#include <set>
struct BasicThread { LONG status; void* teb; DWORD process,thread,affinity; LONG priority,basePriority; };
using QueryThread=LONG(WINAPI*)(HANDLE,ULONG,void*,ULONG,ULONG*);
static bool Read(HANDLE p,uintptr_t address,void* out,SIZE_T size) {
    SIZE_T got=0;return ReadProcessMemory(p,(void*)address,out,size,&got)&&got==size;
}
static uint32_t U32(HANDLE p,uintptr_t address) {uint32_t value=0;Read(p,address,&value,4);return value;}
static std::string Map(HANDLE p,uint32_t address) {
    char name[64]{};if(!address||!Read(p,address,name,sizeof name))return {};
    for(unsigned i=0;i<sizeof name;++i) {
        unsigned char c=name[i];if(!c)return i?std::string(name):std::string();
        if(!((c>='a'&&c<='z')||(c>='A'&&c<='Z')||(c>='0'&&c<='9')||c=='_'||c=='-'))return {};
    }return {};
}
int main(int argc,char** argv) {
    if(argc!=3)return 2;
    unsigned seconds=std::strtoul(argv[2],nullptr,10);if(!seconds||seconds>120)return 2;
    QueryThread query=(QueryThread)GetProcAddress(GetModuleHandleA("ntdll.dll"),"NtQueryInformationThread");if(!query)return 3;
    std::set<std::string> reported;
    DWORD begun=GetTickCount();unsigned count=0;
    while(GetTickCount()-begun<seconds*1000) {
        HANDLE processes=CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS,0);PROCESSENTRY32 process={sizeof process};
        if(Process32First(processes,&process))do {
            bool uo=!_stricmp(process.szExeFile,"CoDUOSP.exe");if(!uo&&_stricmp(process.szExeFile,"CoDSP.exe"))continue;
            HANDLE p=OpenProcess(PROCESS_QUERY_INFORMATION|PROCESS_VM_READ,FALSE,process.th32ProcessID);if(!p)continue;
            char path[4096]{};DWORD length=sizeof path-1;QueryFullProcessImageNameA(p,0,path,&length);
            if(!strstr(path,argv[1])){CloseHandle(p);continue;}
            uint32_t state=U32(p,uo?0x47c7ba0:0x14f4840);
            if(state!=1){CloseHandle(p);continue;}
            uint32_t gvm=U32(p,uo?0x37c07a4:0x13f9db8),current=U32(p,uo?0x37c07ac:0x13f9db4);
            HANDLE threads=CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD,0);THREADENTRY32 thread={sizeof thread};
            if(Thread32First(threads,&thread))do {
                if(thread.th32OwnerProcessID!=process.th32ProcessID)continue;
                HANDLE handle=OpenThread(THREAD_QUERY_INFORMATION,FALSE,thread.th32ThreadID);if(!handle)continue;
                BasicThread info{};LONG result=query(handle,0,&info,sizeof info,nullptr);CloseHandle(handle);if(result<0||!info.teb)continue;
                uint32_t tib[3]{};if(!Read(p,(uintptr_t)info.teb,tib,sizeof tib))continue;
                uint32_t base=tib[1],limit=tib[2];if(base<=limit||base-limit>2*1024*1024)continue;
                std::vector<uint32_t> stack((base-limit)/4);
                if(!Read(p,limit,stack.data(),stack.size()*4))continue;
                uint32_t vmIntent=0xffffffff,vmAddress=0;
                if(gvm&&gvm==current)for(unsigned i=0;i+5<stack.size();++i)
                    if(stack[i]==(uo?0x4515c0u:0x44f2c0u)&&stack[i+1]==0&&stack[i+4]<=1) {vmIntent=stack[i+4];vmAddress=limit+i*4;}
                for(unsigned i=0;i+2<stack.size();++i) {
                    if(stack[i]!=(uo?0x44a43eu:0x44824bu)||stack[i+2]>1)continue;
                    auto map=Map(p,stack[i+1]);if(map.empty())continue;
                    std::string key=std::to_string(process.th32ProcessID)+":"+std::to_string(thread.th32ThreadID)+":"+map+":"+std::to_string(stack[i+2])+":"+std::to_string(vmIntent);
                    if(!reported.insert(key).second)continue;
                    printf("{\"kind\":\"readonly_loading_stack_candidate\",\"pid\":%lu,\"thread\":%lu,\"elapsed_ms\":%lu,\"engine\":\"%s\",\"sv_state\":%u,\"gvm\":%u,\"current_vm\":%u,\"map\":\"%s\",\"spawn_x\":%u,\"map_return_frame\":%u,\"vm_init_intent\":%u,\"vm_return_frame\":%u,\"no_suspension\":true}\n",
                        process.th32ProcessID,thread.th32ThreadID,GetTickCount()-begun,uo?"uo":"cod1",state,gvm,current,map.c_str(),stack[i+2],limit+i*4,vmIntent,vmAddress);
                    fflush(stdout);++count;
                }
            }while(Thread32Next(threads,&thread));
            CloseHandle(threads);CloseHandle(p);
        }while(Process32Next(processes,&process));
        CloseHandle(processes);Sleep(20);
    }
    return count?0:4;
}
