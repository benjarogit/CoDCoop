// Optional read-only native/GSC witness diagnostics. This is not a party or
// equipment capability. No gameplay rule, actor or mission state is written.
struct QUFWorldEpoch {
    uint64_t session;
    uint32_t serial,world;
    int preinitWorld;
    uintptr_t game,vm;
    char map[64],epoch[65];
    bool requested,active;
} g_qufWorld;

bool QUFWorldRequested()
{
    char value[8]{};
    return suite::IsQA()&&GetEnvironmentVariableA("CODCOOP_QA_UF_WORLD_OBSERVER",value,sizeof value)&&!strcmp(value,"1");
}

void QUFWorldStop()
{
    g_qufWorld={};
    SetCoopCvarChanged("coop_uf_native_api","0");
    SetCoopCvarChanged("coop_uf_native_mode","NONE");
}

void QUFWorldBeforeInit(int intent)
{
    QUFWorldStop();
    g_qufWorld.requested=QUFWorldRequested();
    if(!g_qufWorld.requested)return;
    SetCoopCvarChanged("coop_uf_world_status","WAIT");
    if(!S||S->role!=HOST||!g::uo||g_identity.variant!=4||intent!=0)return;
    const auto& init=S->preservation.init;
    if(!init.valid||!init.serial||!reload_delivery::Valid(S->reloadToken))return;
    const char* map=g::CvarString("mapname");
    size_t length=strlen(map);
    if(!length||length>=sizeof g_qufWorld.map||strspn(map,"abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")!=length)return;
    HCRYPTPROV provider=0;uint8_t random[32]{};
    bool ok=CryptAcquireContextA(&provider,nullptr,nullptr,PROV_RSA_AES,CRYPT_VERIFYCONTEXT)&&CryptGenRandom(provider,sizeof random,random);
    if(provider)CryptReleaseContext(provider,0);
    bool nonzero=false;for(auto value:random)nonzero|=value!=0;
    if(!ok||!nonzero){Log("QA UF witness: nonce generation failed; observation unavailable");return;}
    auto& context=g_qufWorld;
    context.session=S->reloadToken.session;context.world=S->reloadToken.generation;
    context.serial=init.serial;context.preinitWorld=CvarInt("sv_serverid");
    context.game=(uintptr_t)GetModuleHandleA(g::GameDll());context.vm=(uintptr_t)g::gvm;
    strcpy(context.map,map);
    for(unsigned k=0;k<sizeof random;++k)snprintf(context.epoch+k*2,3,"%02x",random[k]);
    if(!context.game||!context.vm)return;
    char number[32];
    SetCoopCvarChanged("coop_uf_native_map",context.map);
    snprintf(number,sizeof number,"%u",context.serial);SetCoopCvarChanged("coop_uf_native_init",number);
    snprintf(number,sizeof number,"%d",context.preinitWorld);SetCoopCvarChanged("coop_uf_native_preinit_world",number);
    SetCoopCvarChanged("coop_uf_native_epoch",context.epoch);
    SetCoopCvarChanged("coop_uf_native_intent","0");
    SetCoopCvarChanged("coop_uf_native_mode","HOST");
    context.active=true;
    SetCoopCvarChanged("coop_uf_native_api","1"); // publish last
    Log("QA UF witness: fresh native epoch published init=%u preinit_world=%d map=%s",context.serial,context.preinitWorld,context.map);
}

void QUFWorldTick()
{
    if(!g_qufWorld.requested||!S||g::currentVM==g::gvm)return;
    static DWORD previous;DWORD now=GetTickCount();if(now-previous<250)return;previous=now;
    using V=party_native_json::Value;V root=V::Dict(),fields=V::Dict();
    const auto& c=g_qufWorld;const auto& init=S->preservation.init;
    bool lifecycle=c.active&&S->role==HOST&&init.valid&&init.intent==0&&init.serial==c.serial&&
        init.session==c.session&&S->reloadToken.session==c.session&&!strcmp(init.map,c.map)&&
        !_stricmp(g::CvarString("mapname"),c.map)&&c.game==(uintptr_t)GetModuleHandleA(g::GameDll())&&c.vm==(uintptr_t)g::gvm;
    root.object["scope"]=V::Text("QA_READONLY_NATIVE_UF_WORLD_WITNESS_NOT_READINESS");
    root.object["runtime_ready"]=V::Bool(false);root.object["lifecycle_match"]=V::Bool(lifecycle);
    root.object["native_init_serial"]=V::Number(c.serial);
    root.object["native_init_complete"]=V::Bool(init.nativeReady);
    root.object["native_preinit_world"]=V::Text(std::to_string(c.preinitWorld));
    root.object["native_completed_world"]=V::Text(std::to_string(init.nativeWorldId));
    root.object["native_epoch"]=V::Text(c.epoch);root.object["native_map"]=V::Text(c.map);
    root.object["server_time"]=V::Text(std::to_string(g::sv_time));
    const char* names[]={"coop_uf_world_status","coop_uf_world_epoch","coop_uf_world_map","coop_uf_world_preinit_world",
        "coop_uf_world_init_serial","coop_uf_world_graph","coop_uf_world_campaign_count","coop_uf_world_last_index","coop_uf_world_last_class",
        "coop_uf_world_climate_count","coop_uf_world_winter","coop_uf_world_winter_index","coop_uf_world_winter_class",
        "coop_uf_world_campaign_seen","coop_uf_world_climate_seen","coop_uf_world_cvars_seen","coop_uf_world_input_loadgame",
        "coop_uf_world_campaign_world","coop_uf_world_climate_world","coop_uf_world_year_world","coop_uf_world_cmp_campaign",
        "coop_uf_world_cmp_climate","coop_uf_world_cmp_year","coop_uf_world_cmp_ally_nation","coop_uf_world_cmp_axis_nation",
        "sp_ally","sp_axis","sp_ally_nation","sp_axis_nation","sp_year","sp_climate","sp_loadgame","sp_forceweapons","sp_campaign",
        "sp_ammo","sp_history","sp_order","cg_norender","cl_paused"};
    for(auto name:names) {
        const char* value=g::CvarString(name);size_t n=0;while(n<1024&&value[n])++n;
        fields.object[name]=V::Text(n<1024?std::string(value,n):"<oversized>");
    }
    root.object["fields"]=std::move(fields);std::string text;
    if(!party_native_json::Canonical(root,text))return;
    auto base=suite::GameDir();auto temporary=base+"qa-uf-world-context.tmp";
    FILE* file=fopen(temporary.c_str(),"wb");if(!file)return;
    bool ok=fwrite(text.data(),1,text.size(),file)==text.size();ok=fclose(file)==0&&ok;
    if(ok)MoveFileExA(temporary.c_str(),(base+"qa-uf-world-context.json").c_str(),MOVEFILE_REPLACE_EXISTING);
}
