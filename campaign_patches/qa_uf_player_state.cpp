// Test observer only. Reads owned UO processes; never writes process memory.
// UO 1.51 BG weapon-animation diagnostics at game RVA F170 read pmove.ps+614;
// table F2F0 maps animation19 to deploy and20 to breakdown. Completion
// uses actual ADS fraction+pm_flags, since the UO idle path returns animation0.
#include <windows.h>
#include <tlhelp32.h>
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <vector>
static bool read32(HANDLE process, uintptr_t address, unsigned& value) {
    SIZE_T count = 0;
    return ReadProcessMemory(process, reinterpret_cast<void*>(address), &value, 4, &count) && count == 4;
}
static void weaponName(HANDLE process, unsigned definitions, unsigned index, char* name, SIZE_T size) {
    unsigned definition=0, pointer=0; SIZE_T count=0; name[0]=0;
    if (index && index<256 && definitions && read32(process,definitions+index*4,definition) && definition && read32(process,definition+4,pointer) && pointer)
        ReadProcessMemory(process,reinterpret_cast<void*>(pointer),name,size-1,&count);
    name[size-1]=0;
}
static void modelName(HANDLE process,unsigned index,char* name,SIZE_T size,uintptr_t table=0x47c7fb4) {
    name[0]=0;unsigned pool=0;unsigned short handle=0;SIZE_T got=0;
    if(index>0&&index<256&&read32(process,0x8f72f0,pool)&&pool&&
       ReadProcessMemory(process,reinterpret_cast<void*>(table+(32+index)*2),&handle,2,&got)&&got==2&&handle)
        ReadProcessMemory(process,reinterpret_cast<void*>(pool+handle*8+4),name,size-1,&got);
    name[size-1]=0;
}
int main(int argc, char** argv) {
    if (argc < 3 || argc > 4) return 2;
    unsigned slot = std::strtoul(argv[2], nullptr, 10);
    if (slot > 3) return 2;
    HANDLE snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
    PROCESSENTRY32 entry = {sizeof(entry)};
    if (Process32First(snapshot, &entry)) do {
        if (_stricmp(entry.szExeFile, "CoDUOSP.exe")) continue;
        HANDLE process = OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, FALSE, entry.th32ProcessID);
        if (!process) continue;
        char path[4096] = {}; DWORD length = sizeof(path)-1;
        QueryFullProcessImageNameA(process, 0, path, &length);
        if (!strstr(path, argv[1])) { CloseHandle(process); continue; }
        uintptr_t module = 0, cgame = 0;
        HANDLE modules = CreateToolhelp32Snapshot(TH32CS_SNAPMODULE, entry.th32ProcessID);
        MODULEENTRY32 me = {sizeof(me)};
        if (Module32First(modules, &me)) do {
            if (!_stricmp(me.szModule, "uo_gamex86.dll")) module = reinterpret_cast<uintptr_t>(me.modBaseAddr);
            if (!_stricmp(me.szModule, "uo_cgamex86.dll")) cgame = reinterpret_cast<uintptr_t>(me.modBaseAddr);
        } while (Module32Next(modules, &me));
        CloseHandle(modules);
        unsigned client=0, state=0, weaponstate=0, clientnum=999, weapon=0, viewmodel=0, flags=0, ads=0, hint=0, buttons=0;
        bool valid = module && read32(process, module+0x1549c0+slot*0x2d0+0x108, client) && client &&
            read32(process, client+0x614, state) && read32(process, client+0xcc, weaponstate) && read32(process, client+0xc4, clientnum) &&
            read32(process, client+0xc8, weapon) && read32(process, client+0xd4, viewmodel);
        if (valid) {
            read32(process, client+0xc, flags); read32(process, client+0xd0, ads);
            read32(process, client+0x5b8, hint); read32(process, client+0x8230, buttons);
        }
        float fraction=0; std::memcpy(&fraction, &ads, sizeof(fraction));
        if (valid) {
            std::printf("{\"pid\":%lu,\"slot\":%u,\"clientnum\":%u,\"weapon\":%u,\"viewmodel\":%u,\"weapon_state\":%u,\"raw_weapon_anim\":%u,\"weapon_anim\":%u,\"pm_flags\":%u,\"ads_fraction\":%.5f,\"cursor_hint\":%u,\"buttons\":%u",
                entry.th32ProcessID, slot, clientnum, weapon, viewmodel, weaponstate, state, state & ~0x200u, flags, fraction, hint, buttons);
            unsigned definitions=0; read32(process, module+0x151f34, definitions);
            unsigned selecteddef=0, selectednameptr=0; char selectedname[128]={}; SIZE_T selectedread=0;
            if (weapon && definitions && read32(process,definitions+weapon*4,selecteddef) && selecteddef && read32(process,selecteddef+4,selectednameptr) && selectednameptr)
                ReadProcessMemory(process,reinterpret_cast<void*>(selectednameptr),selectedname,127,&selectedread);
            std::printf(",\"selected_weapon_name\":\"%s\"",*selectedname?selectedname:"none");
            // UO game.h/native weapon registration: WD worldModel+1C8.
            unsigned worldptr=0;char worldname[256]={};SIZE_T worldread=0;
            if(selecteddef&&read32(process,selecteddef+0x1c8,worldptr)&&worldptr)
                ReadProcessMemory(process,reinterpret_cast<void*>(worldptr),worldname,255,&worldread);
            std::printf(",\"selected_world_model\":\"%s\"",worldname);
            unsigned modelpool=0; unsigned short modelhandle=0; char viewname[256]={}; SIZE_T modelread=0;
            if (viewmodel && viewmodel<256 && read32(process,0x8f72f0,modelpool) && modelpool &&
                ReadProcessMemory(process,reinterpret_cast<void*>(0x47c7fb4+(32+viewmodel)*2),&modelhandle,2,&modelread) && modelhandle)
                ReadProcessMemory(process,reinterpret_cast<void*>(modelpool+modelhandle*8+4),viewname,255,&modelread);
            std::printf(",\"viewmodel_name\":\"%s\"",*viewname?viewname:"none");
            if (cgame) {
                // CG weaponslot34460 and BG lookupB190 verify predictedPS
                // base26D9E4, defs13D478/+4names; current snap used by
                // weapon drawing22ECA is259548, snapshotPS starts+8.
                unsigned selection=0, predicted=0, cgdefs=0, snap=0, snapweapon=0, snapclient=999, snaptime=0;
                read32(process,cgame+0x24aecc,selection);
                read32(process,cgame+0x26daac,predicted);
                read32(process,cgame+0x13d478,cgdefs);
                read32(process,cgame+0x259548,snap);
                if (snap) { read32(process,snap+0xd0,snapweapon);read32(process,snap+0xcc,snapclient);read32(process,snap+4,snaptime); }
                char selectionname[128]={}, predictedname[128]={}, snapshotname[128]={};
                weaponName(process,cgdefs,selection,selectionname,sizeof(selectionname));
                weaponName(process,cgdefs,predicted,predictedname,sizeof(predictedname));
                weaponName(process,cgdefs,snapweapon,snapshotname,sizeof(snapshotname));
                std::printf(",\"cgame\":{\"desired_weapon\":%u,\"desired_name\":\"%s\",\"predicted_weapon\":%u,\"predicted_name\":\"%s\",\"snapshot_weapon\":%u,\"snapshot_name\":\"%s\",\"snapshot_clientnum\":%u,\"snapshot_server_time\":%u}",selection,*selectionname?selectionname:"none",predicted,*predictedname?predictedname:"none",snapweapon,*snapshotname?snapshotname:"none",snapclient,snaptime);
            }
            std::printf(",\"inventory\":{");
            const char* slots[]={"primary","primaryb","pistol","grenade","smokegrenade"};
            for (unsigned index=0; index<5; ++index) {
                unsigned char id=0; SIZE_T count=0;
                ReadProcessMemory(process, reinterpret_cast<void*>(client+0x52d+index), &id, 1, &count);
                unsigned definition=0, nameptr=0; char name[128]={};
                if (id && definitions) {
                    read32(process, definitions+id*4, definition);
                    if (definition) read32(process, definition+4, nameptr);
                    if (nameptr) ReadProcessMemory(process, reinterpret_cast<void*>(nameptr), name, 127, &count);
                }
                std::printf("%s\"%s\":\"%s\"",index?",":"",slots[index],*name?name:"none");
            }
            std::printf("}");
            // UO native BG ammo reader C413/C416/C41C: weaponDef+1F0
            // indexes PSclip+31C; C43E/C441/C447 uses+1E8 ->stock+11C.
            std::printf(",\"slot_ammo\":{");
            for (unsigned index=0; index<5; ++index) {
                unsigned char id=0; SIZE_T got=0; unsigned definition=0, ammoindex=0, clipindex=0, stock=0, clip=0;
                ReadProcessMemory(process,reinterpret_cast<void*>(client+0x52d+index),&id,1,&got);
                if (id && definitions && read32(process,definitions+id*4,definition) && definition) {
                    if (read32(process,definition+0x1e8,ammoindex) && ammoindex<128) read32(process,client+0x11c+ammoindex*4,stock);
                    if (read32(process,definition+0x1f0,clipindex) && clipindex<128) read32(process,client+0x31c+clipindex*4,clip);
                }
                std::printf("%s\"%s\":{\"weapon_id\":%u,\"stock\":%u,\"clip\":%u}",index?",":"",slots[index],id,stock,clip);
            }
            std::printf("}");
            const bool references = argc == 4 && !std::strcmp(argv[3], "--model-references");
            if (references || (argc == 4 && !std::strcmp(argv[3], "--models"))) {
                unsigned pool=0; read32(process, 0x8f72f0, pool);
                std::printf(",\"models\":[");
                bool comma=false;
                for (unsigned index=1; index<256; ++index) {
                    unsigned short handle=0; SIZE_T count=0;
                    if (!ReadProcessMemory(process, reinterpret_cast<void*>(0x47c7fb4+(32+index)*2), &handle, 2, &count) || !handle) break;
                    char name[256]={};
                    if (!ReadProcessMemory(process, reinterpret_cast<void*>(pool+handle*8+4), name, 255, &count)) break;
                    if (!*name) break;
                    std::printf("%s{\"index\":%u,\"name\":\"", comma?",":"", index);
                    for (const char* c=name; *c; ++c) {
                        if (*c=='\\' || *c=='\"') std::putchar('\\');
                        if (static_cast<unsigned char>(*c)>=32) std::putchar(*c);
                    }
                    std::printf("\"}"); comma=true;
                }
                std::printf("]");
            }
            if (references) {
                // Read all byte IDs, including holes: actual client CS can
                // advance while the frozen server shadow remains empty.
                // Native UO G_ModelIndex cache is game RVA D2E70[256].
                std::printf(",\"native_model_slots\":[");
                for(unsigned id=1;id<256;++id) {
                    char svname[256]={},clientname[256]={},cachedname[256]={};unsigned cached=0,pointer=0;SIZE_T got=0;
                    modelName(process,id,svname,sizeof svname);
                    modelName(process,id,clientname,sizeof clientname,0x48362d0);
                    if(read32(process,module+0xd2e70+id*4,cached)&&cached&&read32(process,cached,pointer)&&pointer)
                        ReadProcessMemory(process,reinterpret_cast<void*>(pointer),cachedname,255,&got);
                    std::printf("%s{\"index\":%u,\"server_cs\":\"",id>1?",":"",id);
                    for(const char* c=svname;*c;++c){if(*c=='\\'||*c=='\"')std::putchar('\\');if(static_cast<unsigned char>(*c)>=32)std::putchar(*c);}
                    std::printf("\",\"client_cs\":\"");
                    for(const char* c=clientname;*c;++c){if(*c=='\\'||*c=='\"')std::putchar('\\');if(static_cast<unsigned char>(*c)>=32)std::putchar(*c);}
                    std::printf("\",\"cache_name\":\"");
                    for(const char* c=cachedname;*c;++c){if(*c=='\\'||*c=='\"')std::putchar('\\');if(static_cast<unsigned char>(*c)>=32)std::putchar(*c);}
                    std::printf("\"}");
                }
                std::printf("]");
                // Verified UO 1.51 lifecycle: G_InitGentity RVA49FD0 sets
                // +11C=1; G_FreeEntity RVA4A2C0 zeroes all2D0 bytes at4A534.
                // G_DObjUpdate48900 resolves body+131 and seven+2A8 bytes,
                // emits their NEGATED CS IDs as ModelEntry u16 flags.
                // Engine432E60/432F80 owns server/client maps;432D80 bounds
                // the shared5C-byte pool to1024 slots;47B550 copies8 flags+3C.
                std::vector<unsigned char> entities(2048*0x2d0);
                short server[2048]={}, clientmap[2048]={};
                unsigned char objects[1024*0x5c]={}, ownership[256]={}; SIZE_T got=0;
                bool complete = ReadProcessMemory(process, reinterpret_cast<void*>(module+0x1549c0), entities.data(), entities.size(), &got) && got==entities.size();
                complete = complete && ReadProcessMemory(process, reinterpret_cast<void*>(0x894550), server, sizeof(server), &got) && got==sizeof(server);
                complete = complete && ReadProcessMemory(process, reinterpret_cast<void*>(0x8ae2c8), clientmap, sizeof(clientmap), &got) && got==sizeof(clientmap);
                complete = complete && ReadProcessMemory(process, reinterpret_cast<void*>(0x895660), objects, sizeof(objects), &got) && got==sizeof(objects);
                complete = complete && ReadProcessMemory(process, reinterpret_cast<void*>(0x895550), ownership, sizeof(ownership), &got) && got==sizeof(ownership);
                std::printf(",\"references_complete\":%s,\"model_references\":[", complete?"true":"false");
                bool comma=false;
                auto emit = [&](const char* kind, unsigned entity, unsigned index) {
                    if (!index) return;
                    std::printf("%s{\"kind\":\"%s\",\"entity\":%u,\"index\":%u}",comma?",":"",kind,entity,index); comma=true;
                };
                if (complete) for (unsigned index=0; index<2048; ++index) {
                    const auto* entity=entities.data()+index*0x2d0;
                    if (!entity[0x11c]) continue;
                    emit("entity_body",index,entity[0x131]);
                    for (unsigned attach=0; attach<7; ++attach) emit("entity_attachment",index,entity[0x2a8+attach]);
                    if (index<4) {
                        unsigned ps=0, id=0, num=999;
                        std::memcpy(&ps,entity+0x108,4);
                        if (ps && read32(process,ps+0xc4,num) && num==index && read32(process,ps+0xd4,id)) emit("player_viewmodel",index,id);
                    }
                }
                std::printf("],\"live_dobjs\":["); comma=false;
                if (complete) for (unsigned side=0; side<2; ++side) for (unsigned entity=0; entity<2048; ++entity) {
                    const int object=(side?clientmap:server)[entity];
                    if (!object) continue;
                    if (object<0 || object>=1024) { complete=false; continue; }
                    const auto* data=objects+object*0x5c;
                    const unsigned count=data[0x16], mask=(ownership[object/4]>>((object%4)*2))&3;
                    std::printf("%s{\"side\":\"%s\",\"entity\":%u,\"pool_slot\":%d,\"ownership_mask\":%u,\"model_count\":%u,\"raw_model_flags\":[",comma?",":"",side?"client":"server",entity,object,mask,count);
                    for (unsigned i=0;i<count && i<8;++i) {
                        short flag=0; std::memcpy(&flag,data+0x3c+i*2,2);
                        std::printf("%s%d",i?",":"",static_cast<int>(flag));
                    }
                    std::printf("],\"model_names\":[");
                    for(unsigned i=0;i<count&&i<8;++i) {
                        unsigned model=0,pointer=0;std::memcpy(&model,data+0x1c+i*4,4);char name[256]={};SIZE_T got=0;
                        if(model&&read32(process,model,pointer)&&pointer)ReadProcessMemory(process,reinterpret_cast<void*>(pointer),name,255,&got);
                        std::printf("%s\"",i?",":"");
                        for(const char* c=name;*c;++c){if(*c=='\\'||*c=='\"')std::putchar('\\');if(static_cast<unsigned char>(*c)>=32)std::putchar(*c);}
                        std::printf("\"");
                    }
                    std::printf("],\"cs_model_names\":[");
                    for(unsigned i=0;i<count&&i<8;++i) {
                        short flag=0;std::memcpy(&flag,data+0x3c+i*2,2);char name[256]={};
                        if(flag<0)modelName(process,static_cast<unsigned>(-flag),name,sizeof name);
                        std::printf("%s\"",i?",":"");
                        for(const char* c=name;*c;++c){if(*c=='\\'||*c=='\"')std::putchar('\\');if(static_cast<unsigned char>(*c)>=32)std::putchar(*c);}
                        std::printf("\"");
                    }
                    std::printf("],\"client_cs_model_names\":[");
                    for(unsigned i=0;i<count&&i<8;++i) {
                        short flag=0;std::memcpy(&flag,data+0x3c+i*2,2);char name[256]={};
                        if(flag<0)modelName(process,static_cast<unsigned>(-flag),name,sizeof name,0x48362d0);
                        std::printf("%s\"",i?",":"");
                        for(const char* c=name;*c;++c){if(*c=='\\'||*c=='\"')std::putchar('\\');if(static_cast<unsigned char>(*c)>=32)std::putchar(*c);}
                        std::printf("\"");
                    }
                    std::printf("]}"); comma=true;
                    if (count>8 || !(mask&(side?1:2))) complete=false;
                }
                std::printf("],\"reference_layout_valid\":%s",complete?"true":"false");
            }
            if (argc == 4 && !std::strcmp(argv[3], "--missiles")) {
                std::vector<unsigned char> entities(2048*0x2d0); SIZE_T read=0;
                bool loaded = ReadProcessMemory(process, reinterpret_cast<void*>(module+0x1549c0), entities.data(), entities.size(), &read);
                std::printf(",\"missiles\":["); bool comma=false;
                if (loaded && read==entities.size()) for (unsigned index=0; index<2048; ++index) {
                    const auto* entity=entities.data()+index*0x2d0;
                    if (entity[0]!=3) continue;
                    unsigned owner=0, pointer=0; std::memcpy(&owner, entity+0xfc, 4); std::memcpy(&pointer, entity+0x14c, 4);
                    if (owner>3 || pointer!=module+0x1549c0+owner*0x2d0) continue;
                    float position[3]={}; std::memcpy(position, entity+0xe4, sizeof(position));
                    std::printf("%s{\"entity\":%u,\"owner\":%u,\"position\":[%.3f,%.3f,%.3f]}", comma?",":"", index, owner, position[0], position[1], position[2]); comma=true;
                }
                std::printf("]");
            }
            std::printf("}\n");
        }
        CloseHandle(process); CloseHandle(snapshot); return valid ? 0 : 3;
    } while (Process32Next(snapshot, &entry));
    CloseHandle(snapshot); return 4;
}
