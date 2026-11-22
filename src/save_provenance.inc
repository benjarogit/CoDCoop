// Native game FS calls retain all original behavior. Only completed save bytes
// acquire a separate, bounded ownership sidecar; the .svg format is unchanged.
struct InventorySaveOpen { int handle; char relative[192]; save_provenance::Metadata metadata; };
InventorySaveOpen g_inventoryOpen[8]{};

bool InventoryFileHash(const std::string& path,char out[65])
{
    HANDLE file=CreateFileA(path.c_str(),GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,nullptr);
    if(file==INVALID_HANDLE_VALUE) return false;
    LARGE_INTEGER size{};
    bool ok=GetFileType(file)==FILE_TYPE_DISK&&GetFileSizeEx(file,&size)&&size.QuadPart>=16&&size.QuadPart<=64*1024*1024;
    HCRYPTPROV provider=0;HCRYPTHASH hash=0;
    ok=ok&&CryptAcquireContextA(&provider,nullptr,nullptr,PROV_RSA_AES,CRYPT_VERIFYCONTEXT)&&CryptCreateHash(provider,CALG_SHA_256,0,0,&hash);
    uint8_t bytes[65536],digest[32];DWORD remaining=ok?(DWORD)size.QuadPart:0;
    while(ok&&remaining) {
        DWORD wanted=remaining<sizeof bytes?remaining:(DWORD)sizeof bytes,got=0;
        ok=ReadFile(file,bytes,wanted,&got,nullptr)&&got==wanted&&CryptHashData(hash,bytes,got,0);
        remaining-=got;
    }
    DWORD length=sizeof digest;
    ok=ok&&CryptGetHashParam(hash,HP_HASHVAL,digest,&length,0);
    if(ok) for(unsigned i=0;i<32;++i) snprintf(out+i*2,3,"%02x",digest[i]);
    if(hash)CryptDestroyHash(hash);if(provider)CryptReleaseContext(provider,0);CloseHandle(file);return ok;
}

std::string InventorySavePath(const std::string& relative)
{
    std::string home=g::CvarString("fs_homepath");
    if(home.empty()) home=suite::GameDir();
    if(home.back()!='/'&&home.back()!='\\') home+='\\';
    const char* mod=g::CvarString("fs_game");
    // Variant paths are registered locally, never supplied by a peer/file.
    const char* root=*mod?mod:(g::uo?"uo":"Main");
    if(strcmp(root,"uo")&&strcmp(root,"Main")&&strcmp(root,"sp_improved")&&strcmp(root,"UnitedFronts")) return {};
    std::string path=home+root+"\\"+relative;
    return path.size()<MAX_PATH-32?path:std::string();
}

bool ReadInventoryMetadata(const std::string& path,save_provenance::Metadata& metadata)
{
    uint8_t bytes[sizeof metadata];FILE* f=fopen((path+".coopowners").c_str(),"rb");
    if(!f)return false;
    size_t got=fread(bytes,1,sizeof bytes,f);bool ended=fgetc(f)==EOF;fclose(f);
    return ended&&save_provenance::Decode(bytes,got,metadata);
}

void ClearLoadedSavedRoles()
{
    memset(S->loadedSavedRoles,0,sizeof S->loadedSavedRoles);
    S->loadedSavedRoleWorld=0;S->hostSavedRoleApplied=false;
}

void InventoryLoadProvenance(const std::string& relative)
{
    memset(S->loadedInventoryLease,0,sizeof S->loadedInventoryLease);
    ClearLoadedSavedRoles();
    std::string path=InventorySavePath(relative); char hash[65]{};
    save_provenance::Metadata metadata{};
    bool valid=!path.empty()&&ReadInventoryMetadata(path,metadata);
    valid=valid&&InventoryFileHash(path,hash)&&save_provenance::Valid(metadata,g_identity.engine,g_identity.variant,
        g::CvarString("mapname"),hash,S->reloadToken.session);
    if(!valid) { Log("inventory: native save ownership unavailable/unverified: %s",relative.c_str()); return; }
    if(metadata.version==save_provenance::VERSION) {
        S->loadedSavedRoleWorld=S->reloadToken.generation;S->loadedSavedRoles[0]=metadata.roles[0];
    }
    for(unsigned n=1;n<g::MAX_CLIENTS;++n)
        if(save_provenance::Owns(metadata,n,S->inventories.slots[n])) {
            S->loadedInventoryLease[n]=metadata.owners[n].lease;
            S->loadedSavedRoles[n]=metadata.roles[n];
        }
    Log("inventory: loaded saved roles version=%u flags=%u/%u/%u/%u",metadata.version,
        S->loadedSavedRoles[0],S->loadedSavedRoles[1],S->loadedSavedRoles[2],S->loadedSavedRoles[3]);
    Log("inventory: native save ownership verified: %s leases=%llu/%llu/%llu",relative.c_str(),
        (unsigned long long)S->loadedInventoryLease[1],(unsigned long long)S->loadedInventoryLease[2],(unsigned long long)S->loadedInventoryLease[3]);
}

bool WriteInventoryMetadata(const std::string& path,const save_provenance::Metadata& metadata)
{
    std::string target=path+".coopowners",temporary=target+".pending";
    FILE* f=fopen(temporary.c_str(),"wb");
    size_t bytes=save_provenance::Bytes(metadata);
    bool ok=f&&bytes&&fwrite(&metadata,1,bytes,f)==bytes;
    if(f) ok=fclose(f)==0&&ok;
    if(ok) ok=MoveFileExA(temporary.c_str(),target.c_str(),MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH)!=FALSE;
    if(!ok) {DeleteFileA(temporary.c_str());DeleteFileA(target.c_str());}
    return ok;
}

void InventoryFSObserver(const intptr_t* args,intptr_t result,bool after)
{
    if(!after||!args||!S||S->role!=HOST) return;
    if(args[0]==0x15) {
        std::string relative;
        if(!args[2]||result<0) return;
        int handle=*reinterpret_cast<const int*>(args[2]),mode=(int)args[3];
        if(handle<=0||handle>=256) return;
        // An aborted VM call may leave a tracked descriptor behind. Native
        // descriptor reuse must never associate an unrelated close with it.
        for(auto& old:g_inventoryOpen) if(old.handle==handle) old={};
        if(!save_provenance::Path(reinterpret_cast<const char*>(args[1]),relative)) return;
        if(mode==0) { if(S->inventoryLoading) InventoryLoadProvenance(relative); return; }
        if(mode!=1) return;
        InventorySaveOpen* entry=nullptr;
        for(auto& candidate:g_inventoryOpen) if(candidate.handle==handle) {entry=&candidate;break;}
        if(!entry) for(auto& candidate:g_inventoryOpen) if(!candidate.handle) {entry=&candidate;break;}
        if(!entry) { Log("inventory: too many simultaneous save writers; provenance not recorded"); return; }
        *entry={};entry->handle=handle;strcpy(entry->relative,relative.c_str());
        auto& m=entry->metadata;m.magic=save_provenance::MAGIC;m.version=save_provenance::VERSION;
        m.session=S->reloadToken.session;m.engine=g_identity.engine;m.variant=g_identity.variant;
        m.roles[0]=S->downed[0]?saved_role::Downed:saved_role::Alive;
        snprintf(m.map,sizeof m.map,"%s",g::CvarString("mapname"));
        for(unsigned n=1;n<g::MAX_CLIENTS;++n) {
            const auto& record=S->inventories.slots[n];
            if(S->remote[n].active&&peer_inventory::Current(record,n,S->reloadToken,InventoryEndpoint(S->remote[n].addr),m.map)) {
                m.owners[n]={record.lease,record.endpoint.address,record.endpoint.port};
                m.roles[n]=S->downed[n]?saved_role::Downed:saved_role::Alive;
            }
        }
    } else if(args[0]==0x25) {
        for(auto& entry:g_inventoryOpen) if(entry.handle&&entry.handle==args[1]) {
            entry.handle=0;
            std::string path=InventorySavePath(entry.relative);if(path.empty()) break;
            if(!InventoryFileHash(path,entry.metadata.sha256)) {Log("inventory: could not hash completed save %s",entry.relative);break;}
            bool ok=WriteInventoryMetadata(path,entry.metadata);
            if(!ok) Log("inventory: save ownership write failed: %s",entry.relative);
            else Log("inventory: completed native save ownership recorded: %s",entry.relative);
            break;
        }
    } else if(args[0]==0x24) {
        // Both native games finish a save by copying verified save/temp.svg
        // to its actual manual/autosave name (UO callsite game+2feb9).
        std::string from,to;
        if(!save_provenance::Path(reinterpret_cast<const char*>(args[1]),from)||
           !save_provenance::Path(reinterpret_cast<const char*>(args[2]),to)) return;
        std::string source=InventorySavePath(from),target=InventorySavePath(to);
        if(source.empty()||target.empty()) return;
        save_provenance::Metadata metadata{};char hash[65]{};
        bool ok=ReadInventoryMetadata(source,metadata);
        ok=ok&&InventoryFileHash(target,hash)&&save_provenance::Valid(metadata,g_identity.engine,g_identity.variant,
            g::CvarString("mapname"),hash,S->reloadToken.session);
        if(ok) ok=WriteInventoryMetadata(target,metadata);
        if(!ok) DeleteFileA((target+".coopowners").c_str());
        Log("inventory: native save copy ownership %s: %s -> %s",ok?"recorded":"unverified",from.c_str(),to.c_str());
    } else if(args[0]==0x27) {
        std::string relative;
        if(save_provenance::Path(reinterpret_cast<const char*>(args[1]),relative)) {
            std::string path=InventorySavePath(relative);
            if(!path.empty()) DeleteFileA((path+".coopowners").c_str());
        }
    }
}

void PrepareInventoryGameInit()
{
    if(!S||S->role!=HOST) return;
    S->inventoryLoading=true;
    memset(S->loadedInventoryLease,0,sizeof S->loadedInventoryLease);
    ClearLoadedSavedRoles();
    memset(g_inventoryOpen,0,sizeof g_inventoryOpen);
    campaign_cinematics::observer=InventoryFSObserver;
    if(!campaign_cinematics::Sync(g::gvm,true,HostScriptMovie)) Log("inventory: could not observe native load ownership; restored guests require fresh roles");
}
