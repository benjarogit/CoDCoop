// Read-only owned-process observer. Native CoD1/UO offsets are shared with
// src/game.h; actual CG snapshot/definitions match src/weapon_selection.inc.
// CoD1 desired FE24C and predicted11E154: native commandAC80/AC9E/ACD5,
// prediction1ED7B/1ED82 and1EFB4/1EFBB (independent YAP-agent static RE).
// UO equivalents24AECC/26DAAC were independently used by the UF kit probes.
#include <windows.h>
#include <tlhelp32.h>
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <cstdint>
#include <vector>
static bool read(HANDLE p,uintptr_t a,void* v,SIZE_T n){SIZE_T got=0;return ReadProcessMemory(p,(void*)a,v,n,&got)&&got==n;}
static unsigned u32(HANDLE p,uintptr_t a){unsigned v=0;read(p,a,&v,4);return v;}
static void name(HANDLE p,unsigned defs,unsigned id,char* out){
 out[0]=0;if(!id||id>=256)return;unsigned d=u32(p,defs+id*4),s=d?u32(p,d+4):0;
 if(s)read(p,s,out,127);out[127]=0;
}
static void weapon(HANDLE p,unsigned defs,unsigned id){char s[128]={};name(p,defs,id,s);std::printf("{\"id\":%u,\"name\":\"%s\"}",id,*s?s:"none");}
int main(int argc,char** argv){
 if(argc!=4)return 2;bool uo=!std::strcmp(argv[3],"uo");if(!uo&&std::strcmp(argv[3],"cod1"))return 2;
 unsigned slot=std::strtoul(argv[2],nullptr,10);if(slot>3)return 2;
 HANDLE list=CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS,0);PROCESSENTRY32 entry={sizeof(entry)};
 if(Process32First(list,&entry))do{
  if(_stricmp(entry.szExeFile,uo?"CoDUOSP.exe":"CoDSP.exe"))continue;
  HANDLE p=OpenProcess(PROCESS_QUERY_INFORMATION|PROCESS_VM_READ,FALSE,entry.th32ProcessID);if(!p)continue;
  char path[4096]={};DWORD size=4095;QueryFullProcessImageNameA(p,0,path,&size);
  if(!std::strstr(path,argv[1])){CloseHandle(p);continue;}
  unsigned game=0,cg=0;HANDLE modules=CreateToolhelp32Snapshot(TH32CS_SNAPMODULE,entry.th32ProcessID);MODULEENTRY32 me={sizeof(me)};
  if(Module32First(modules,&me))do{
   if(!_stricmp(me.szModule,uo?"uo_gamex86.dll":"gamex86.dll"))game=(uintptr_t)me.modBaseAddr;
   if(!_stricmp(me.szModule,uo?"uo_cgamex86.dll":"cgamex86.dll"))cg=(uintptr_t)me.modBaseAddr;
  }while(Module32Next(modules,&me));CloseHandle(modules);
  unsigned clients=u32(p,uo?0x47fefc4:0x152bc64),stride=u32(p,uo?0x47fefc8:0x152bc68),ps=clients+slot*stride;
  unsigned off=uo?0x28:0,ammo=uo?0x11c:0xf4,clip=uo?0x31c:0x1f4,count=uo?128:64;
  unsigned own=u32(p,ps+0x9c+off),defs=game?u32(p,game+(uo?0x151f34:0x125650)):0;
  if(!clients||stride<0x1000||stride>0x10000||own!=slot||!defs||!cg){CloseHandle(p);CloseHandle(list);return 3;}
  float position[3]={},angles[3]={};read(p,ps+0x14,position,12);read(p,ps+0xb0+off,angles,12);
  DWORD foreground=0;GetWindowThreadProcessId(GetForegroundWindow(),&foreground);
  std::printf("{\"pid\":%lu,\"foreground_pid\":%lu,\"slot\":%u,\"clientnum\":%u,\"command_time\":%u,\"position\":[%.5f,%.5f,%.5f],\"viewangles\":[%.5f,%.5f,%.5f],\"selected\":",entry.th32ProcessID,foreground,slot,own,u32(p,ps),position[0],position[1],position[2],angles[0],angles[1],angles[2]);
  weapon(p,defs,u32(p,ps+0xa0+off));
  std::printf(",\"stock\":[");for(unsigned i=0;i<count;i++)std::printf("%s%u",i?",":"",u32(p,ps+ammo+i*4));
  std::printf("],\"clip\":[");for(unsigned i=0;i<count;i++)std::printf("%s%u",i?",":"",u32(p,ps+clip+i*4));
  unsigned slots=uo?0x52d:0x2fd;const char* labels[]={"primary","primaryb","pistol","grenade"};
  std::printf("],\"inventory\":{");for(unsigned i=0;i<4;i++){unsigned char id=0;read(p,ps+slots+i,&id,1);std::printf("%s\"%s\":",i?",":"",labels[i]);weapon(p,defs,id);}std::printf("}");
  // CoD1 actual getweaponslotammo16620/clip16890: def1A0/1A8,
  // stockPSF4/clipPS1F4; special def2D4 uses clip as slot ammo.
  // UO native ammo readersC413/C43E prove def1E8/1F0 and PS11C/31C.
  std::printf(",\"slot_ammo\":{");for(unsigned i=0;i<4;i++){
   unsigned char id=0;read(p,ps+slots+i,&id,1);unsigned def=id?u32(p,defs+id*4):0;
   unsigned ai=def?u32(p,def+(uo?0x1e8:0x1a0)):0,ci=def?u32(p,def+(uo?0x1f0:0x1a8)):0;
   unsigned stock=ai<count?u32(p,ps+ammo+ai*4):0,clips=ci&&ci<count?u32(p,ps+clip+ci*4):0;
   std::printf("%s\"%s\":{\"stock_index\":%u,\"clip_index\":%u,\"stock\":%u,\"clip\":%u}",i?",":"",labels[i],ai,ci,stock,clips);
  }std::printf("}");
  unsigned cdefs=u32(p,cg+(uo?0x13d478:0xceb8c)),snap=u32(p,cg+(uo?0x259548:0x10b8a8));
  std::printf(",\"cgame\":{\"snapshot_client\":%u,\"snapshot_time\":%u,\"snapshot\":",snap?u32(p,snap+8+0x9c+off):999,snap?u32(p,snap+4):0);
  weapon(p,cdefs,snap?u32(p,snap+8+0xa0+off):0);
  std::printf(",\"desired\":");weapon(p,cdefs,u32(p,cg+(uo?0x24aecc:0xfe24c)));
  std::printf(",\"predicted\":");weapon(p,cdefs,u32(p,cg+(uo?0x26daac:0x11e154)));
  float predictedAngles[3]={};read(p,cg+(uo?0x26d9e4:0x11e0b4)+0xb0+off,predictedAngles,12);
  float predictedPosition[3]={},snapshotPosition[3]={};
  read(p,cg+(uo?0x26d9e4:0x11e0b4)+0x14,predictedPosition,12);
  if(snap)read(p,snap+8+0x14,snapshotPosition,12);
  std::printf(",\"predicted_angles\":[%.5f,%.5f,%.5f],\"predicted_position\":[%.5f,%.5f,%.5f],\"snapshot_position\":[%.5f,%.5f,%.5f]}",predictedAngles[0],predictedAngles[1],predictedAngles[2],predictedPosition[0],predictedPosition[1],predictedPosition[2],snapshotPosition[0],snapshotPosition[1],snapshotPosition[2]);
  // Read-only field mapping in notes/uo_playerstate.txt: proneDirection,
  // proneDirectionPitch, proneTorsoPitch. No clamp or restore assumption.
  float nativeProne[3]={},snapshotProne[3]={},predictedProne[3]={};
  unsigned proneOffset=uo?0x58c:0x350;
  read(p,ps+proneOffset,nativeProne,12);
  if(snap)read(p,snap+8+proneOffset,snapshotProne,12);
  read(p,cg+(uo?0x26d9e4:0x11e0b4)+proneOffset,predictedProne,12);
  unsigned delta=uo?0x4c:0x48;
  std::printf(",\"prone_basis\":{\"native\":[%.5f,%.5f,%.5f],\"current_snapshot\":[%.5f,%.5f,%.5f],\"predicted\":[%.5f,%.5f,%.5f]},\"delta_angles\":[%d,%d,%d]",nativeProne[0],nativeProne[1],nativeProne[2],snapshotProne[0],snapshotProne[1],snapshotProne[2],predictedProne[0],predictedProne[1],predictedProne[2],(int32_t)u32(p,ps+delta),(int32_t)u32(p,ps+delta+4),(int32_t)u32(p,ps+delta+8));
  std::printf(",\"pm_flags\":%u,\"cmd_angles\":[%u,%u,%u]",u32(p,ps+0xc),u32(p,ps+(uo?0x822c:0x73e4)+8),u32(p,ps+(uo?0x822c:0x73e4)+12),u32(p,ps+(uo?0x822c:0x73e4)+16));
  unsigned playerEntities=u32(p,uo?0x47fefb8:0x152bc58),playerEntitySize=u32(p,uo?0x47fefbc:0x152bc5c);
  bool linked=playerEntities&&u32(p,playerEntities+slot*playerEntitySize+(uo?0x29c:0x294));
  // Native PS_HEALTH/GE_HEALTH (game.h, verified Damage/ClientSpawn paths).
  std::printf(",\"pm_type\":%u,\"linked\":%s,\"health\":%u,\"entity_health\":%u",u32(p,ps+4),linked?"true":"false",u32(p,ps+(uo?0x10c:0xe4)),u32(p,playerEntities+slot*playerEntitySize+(uo?0x1e0:0x1d8)));
  if(uo){
   // Independently verified UO native40F110 setter / SV_Frame branches.
   std::printf(",\"native_input\":{\"frame_msec\":%u,\"server_residue\":%u}",u32(p,0x4842220),u32(p,0x4842224));
  }else{
   // Engine40A5B0 consumes key86CDA8/+10 and strafe86CE68/+10,
   // frame msec1439380 and yaw CVar1423C54; writes CL angles142F304.
   float view[3]={};read(p,0x142f304,view,12);
   std::printf(",\"native_input\":{\"left\":%u,\"strafe\":%u,\"frame_msec\":%u,\"cl_angles\":[%.5f,%.5f,%.5f]}",u32(p,0x86cdb8),u32(p,0x86ce78),u32(p,0x1439380),view[0],view[1],view[2]);
   // Verified CoD1 InitGentity45F30 sets inuse118; SpawnItem1B980
   // sets typebyte0=2, weaponwordC, classnameString12E, itemPtr240.
   unsigned entities=u32(p,0x152bc58),entitySize=u32(p,0x152bc5c),entityCount=u32(p,0x152bc60),pool=u32(p,0x8d8bf8);
   bool valid=entities&&entitySize==0x2c8&&entityCount<=2048&&pool;
   std::vector<unsigned char> data(valid?entitySize*entityCount:0);
   valid=valid&&read(p,entities,data.data(),data.size());
   std::printf(",\"world_items_complete\":%s,\"world_items\":[",valid?"true":"false");bool comma=false;
   if(valid)for(unsigned i=0;i<entityCount;i++){
    const unsigned char* e=data.data()+i*entitySize;if(!e[0x118]||e[0]!=2)continue;
    unsigned short classId=0,weaponId=0;std::memcpy(&classId,e+0x12e,2);std::memcpy(&weaponId,e+0xc,2);
    char classname[128]={};if(classId)read(p,pool+classId*8+4,classname,127);classname[127]=0;
    float position[3]={};std::memcpy(position,e+0xe0,12);
    std::printf("%s{\"entity\":%u,\"weapon_id\":%u,\"classname\":\"",comma?",":"",i,weaponId);
    for(const char* c=classname;*c;c++){if(*c=='\\'||*c=='\"')std::putchar('\\');if((unsigned char)*c>=32)std::putchar(*c);}
    std::printf("\",\"position\":[%.5f,%.5f,%.5f]}",position[0],position[1],position[2]);comma=true;
   }std::printf("]");
  }
  std::printf("}\n");CloseHandle(p);CloseHandle(list);return 0;
 }while(Process32Next(list,&entry));CloseHandle(list);return 4;
}
