// Read-only observer for owned Wine game instances. Never executes or writes game code.
#include <windows.h>
#include <tlhelp32.h>
#include <cstdio>
#include <cstring>
#include <cstdint>
#include <map>
#include <set>
static bool Read(HANDLE p, uintptr_t a, void* out, SIZE_T size) { SIZE_T got=0;return ReadProcessMemory(p,(void*)a,out,size,&got)&&got==size; }
static unsigned U32(HANDLE p,uintptr_t a){unsigned v=0;Read(p,a,&v,4);return v;}
struct Tree{unsigned pointer=0,anims=0,nodes=0,bytes=0,infos=0;};
static Tree Inspect(HANDLE p,unsigned ptr) {
 Tree t{};unsigned h[3]={};if(!ptr||!Read(p,ptr,h,12)||!h[0])return t;
 unsigned n=U32(p,h[0]+4);if(!n||n>4096)return t;
 t={ptr,h[0],n,n*8+14,0};
 unsigned short infos[4096]={};if(!Read(p,ptr+12,infos,n*2))return Tree{};for(unsigned i=0;i<n;++i)if(infos[i])++t.infos;
 return t;
}
int main(int argc,char**argv){
 if(argc!=2)return 2;HANDLE snap=CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS,0);PROCESSENTRY32 pe={sizeof(pe)};
 if(Process32First(snap,&pe))do{
  if(_stricmp(pe.szExeFile,"CoDUOSP.exe"))continue;HANDLE p=OpenProcess(PROCESS_QUERY_INFORMATION|PROCESS_VM_READ,FALSE,pe.th32ProcessID);if(!p)continue;
  char path[4096]={};DWORD len=4095;QueryFullProcessImageNameA(p,0,path,&len);if(!strstr(path,argv[1])){CloseHandle(p);continue;}
  unsigned base=0;HANDLE ms=CreateToolhelp32Snapshot(TH32CS_SNAPMODULE,pe.th32ProcessID);MODULEENTRY32 me={sizeof(me)};
  if(Module32First(ms,&me))do{if(!_stricmp(me.szModule,"uo_gamex86.dll"))base=(uintptr_t)me.modBaseAddr;}while(Module32Next(ms,&me));CloseHandle(ms);if(!base)return 3;
  std::map<unsigned,Tree> native,objects;std::map<unsigned,unsigned> owner;
  auto add=[&](unsigned ptr){Tree t=Inspect(p,ptr);if(t.pointer)native.emplace(ptr,t);};
  for(unsigned e=0;e<2048;++e){unsigned char used=0;Read(p,base+0x1549c0+e*0x2d0+0x11c,&used,1);if(!used)continue;unsigned address=base+0x1549c0+e*0x2d0; unsigned char type=0; Read(p,address,&type,1);
   unsigned ptr=U32(p,address+0x2c8);
   if(type==11){unsigned actor=U32(p,address+0x10c),start=U32(p,base+0x307f1c);if(actor>=start&&(actor-start)%4656==0&&(actor-start)/4656<32)ptr=U32(p,base+0x153850+4*((actor-start)/4656));else ptr=0;}
   else if(type==13){unsigned short number=0;Read(p,address+6,&number,2);ptr=0;for(unsigned index=0;index<64;++index)if(U32(p,base+0x1538d4+index*32)==number){ptr=U32(p,base+0x1538d0+index*32);break;}}
   Tree t=Inspect(p,ptr);if(t.pointer){native.emplace(ptr,t);owner.emplace(e,ptr);}}
  unsigned deferred=U32(p,base+0x30a2ac);if(deferred<=1024)for(unsigned i=0;i<deferred;++i)add(U32(p,base+0x30a2b0+4*i));
  for(unsigned i=0;i<32;++i)add(U32(p,base+0x153850+4*i));
  for(unsigned i=0;i<64;++i)add(U32(p,base+0x1538d0+32*i));
  printf("{\"render_resolver\":%u,\"mt_init_prefix\":%u}\n",U32(p,0x47bcce8),U32(p,0x45fab0));
  unsigned detached=0,mismatches=0;bool comma=false;printf("{\"pid\":%lu,\"server_time\":%u,\"cls_state\":%u,\"deferred_free_count\":%u,\"entities\":[",pe.th32ProcessID,U32(p,0x4801c90),U32(p,0x4842100),deferred);
  for(unsigned e=0;e<2048;++e){short id=0;Read(p,0x894550+e*2,&id,2);Tree t{};if(id>0&&id<1024)t=Inspect(p,U32(p,0x895660+id*0x5c));if(t.pointer)objects.emplace(t.pointer,t);
   if(id>0&&id<1024)for(unsigned k=0;k<8;++k){unsigned char count=0;Read(p,0x895660+id*0x5c+0x16,&count,1);if(k>=count)break;
    short flag=0;Read(p,0x895660+id*0x5c+0x3c+2*k,&flag,2);if(flag>=0||flag<=-256)continue;
    unsigned model=U32(p,0x895660+id*0x5c+0x1c+4*k);char modelname[128]={},cs[128]={},full[136]={};unsigned short h=0;
    if(model)Read(p,U32(p,model),modelname,127);Read(p,0x48362d0+2*(32-flag),&h,2);if(h)Read(p,U32(p,0x8f72f0)+8*h+4,cs,127);
    if(!_strnicmp(modelname,"xmodel/",7))snprintf(full,sizeof full,"%s",modelname);else snprintf(full,sizeof full,"xmodel/%s",modelname);
    if(*modelname&&_stricmp(full,cs))++mismatches;
   }
   unsigned local=owner.count(e)?owner[e]:0;if(local&&local!=t.pointer)++detached;if(!local&&!t.pointer)continue;
   printf("%s{\"entity\":%u,\"native_owner_tree\":%u,\"server_dobj_tree\":%u,\"anims\":%u,\"nodes\":%u,\"bytes\":%u,\"infos\":%u}",comma?",":"",e,local,t.pointer,t.anims,t.nodes,t.bytes,t.infos);comma=true;}
  unsigned nb=0,ob=0,extra=0,extraBytes=0;for(auto&x:native)nb+=x.second.bytes;for(auto&x:objects){ob+=x.second.bytes;if(!native.count(x.first)){++extra;extraBytes+=x.second.bytes;}}
  printf("],\"model_mapping_mismatches\":%u,\"native_owned_unique\":%u,\"native_owned_bytes\":%u,\"server_dobj_unique\":%u,\"server_dobj_bytes\":%u,\"detached_entity_owner_count\":%u,\"additional_dobj_tree_count\":%u,\"additional_dobj_tree_bytes\":%u}\n",mismatches,(unsigned)native.size(),nb,(unsigned)objects.size(),ob,detached,extra,extraBytes);
  CloseHandle(p);CloseHandle(snap);return 0;
 }while(Process32Next(snap,&pe));CloseHandle(snap);return 4;
}
