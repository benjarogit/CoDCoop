// Native proof of numeric ownership; script receipts never authorize this state.
inventory_preservation::Identity PreservationIdentity(int n)
{return {S->reloadToken.session,S->reloadToken.generation,S->spawnTicket[n],(uint8_t)n};}

void PreservationPublish(int n)
{
    char key[64],value[128];auto& r=S->preservation.slots[n];
    snprintf(key,sizeof key,"coop_inventory_%d_state",n);SetCoopCvarChanged(key,"WAIT");
    auto id=PreservationIdentity(n);value[0]=0;
    if(inventory_preservation::Same(r.identity,id)) {
        auto parts=spawn_ticket::Split(id.session);
        snprintf(value,sizeof value,"%u|%u|%u|%d|%u|%u",parts.a,parts.b,parts.c,n,id.ticket,id.world);
    }
    snprintf(key,sizeof key,"coop_inventory_%d_identity",n);SetCoopCvarChanged(key,value);
    snprintf(key,sizeof key,"coop_inventory_%d_state",n);
    bool current=inventory_preservation::Same(r.identity,id);
    SetCoopCvarChanged(key,current&&r.phase==inventory_preservation::PRESERVED?"PRESERVED":current&&r.phase==inventory_preservation::FRESH?"FRESH":"WAIT");
    PublishActorEligibility(n);
}
void PreservationIssued(int n)
{inventory_preservation::Issued(S->preservation.slots[n],PreservationIdentity(n));PreservationPublish(n);}
void PreservationWait(int n,bool keepFresh)
{inventory_preservation::Begin(S->preservation.slots[n],PreservationIdentity(n),keepFresh);PreservationPublish(n);}
bool PreservationFresh(int n)
{return inventory_preservation::IsFresh(S->preservation.slots[n],PreservationIdentity(n));}
void PreservationCommit(int n,bool preserved)
{
    if(inventory_preservation::Commit(S->preservation.slots[n],PreservationIdentity(n),preserved?inventory_preservation::PRESERVED:inventory_preservation::FRESH,true)) {
        PreservationPublish(n);Log("inventory: disposition slot=%d state=%s ticket=%u world=%u",n,preserved?"PRESERVED":"FRESH",S->spawnTicket[n],S->reloadToken.generation);
    }
}
void PreservationBeforeInit(int intent)
{
    if(!S)return;
    auto& store=S->preservation;auto& init=store.init;
    if(!++store.serial)++store.serial;
    init={};init.serial=store.serial;init.session=S->reloadToken.session;init.world=S->reloadToken.generation;
    init.intent=intent;init.valid=true;init.announced=store.expectSpawnInit;store.expectSpawnInit=false;
    init.nativeWorldId=CvarInt("sv_serverid");
    snprintf(init.map,sizeof init.map,"%s",g::CvarString("mapname"));
    Log("inventory: observed native init serial=%u intent=%d map=%s native_world=%d hosting=%d",init.serial,intent,init.map,init.nativeWorldId,S->role==HOST);
    // The shipped launcher can load a map before executing coophost. Retain
    // the observed native intent without granting any equipment in solo mode.
    if(S->role!=HOST) {
        init.session=0;init.world=0;init.announced=false;
        // A previous session can leave non-archived receipt CVars alive in
        // this process. They must not authorize scripts in a new solo world.
        for(int n=0;n<g::MAX_CLIENTS;++n)PreservationWait(n);
        return;
    }
    for(int n=0;n<g::MAX_CLIENTS;++n) {
        PreservationWait(n);
        if(intent==0&&(n==0||S->inventories.slots[n].reserved))FreshSpawnTicket(n);
    }
    if(intent!=0&&intent!=1) {
        Log("inventory: unsupported native GAME_INIT intent %d; disposition WAIT",intent);
        CoopStatus("Unrecognized native save intent. Player equipment is waiting for verified ownership.");
    }
}
void PreservationObserveReady()
{
    if(!S)return;
    auto& init=S->preservation.init;
    if(!init.valid||init.nativeReady||g::currentVM==g::gvm||g::sv_state!=2||!g::svs_clients||!g::sv_gameClients||
        _stricmp(init.map,g::CvarString("mapname")))return;
    // Fast restart updates sv_serverid AFTER returning from GAME_INIT.
    // Bind the completed server, never the intermediate pre-init CVar value.
    init.nativeWorldId=CvarInt("sv_serverid");init.nativeReady=true;
    Log("inventory: completed native init serial=%u native_world=%d",init.serial,init.nativeWorldId);
}
void PreservationWorld(const char* map)
{
    auto& init=S->preservation.init;
    bool current=init.valid&&!init.handled&&init.session==S->reloadToken.session&&!_stricmp(init.map,map);
    for(int n=0;n<g::MAX_CLIENTS;++n) {
        bool fresh=current&&init.intent==0&&S->preservation.slots[n].freshIssued&&S->preservation.slots[n].identity.ticket==S->spawnTicket[n];
        PreservationWait(n);
        if(fresh)PreservationIssued(n);
    }
    if(current)init.world=S->reloadToken.generation;
}
void PreservationTick()
{
    if(!S||S->role!=HOST||!SavedRemoteLoadReady())return;
    auto& init=S->preservation.init;
    if(!init.valid||!init.nativeReady||!init.handled||init.committed==init.serial||init.session!=S->reloadToken.session||init.world!=S->reloadToken.generation||
       init.nativeWorldId!=CvarInt("sv_serverid")||_stricmp(init.map,g::CvarString("mapname"))||g::currentVM==g::gvm||g::sv_state!=2||g::cls_state!=2||!g::sv_gameClients)return;
    uint8_t* ps=g::PlayerState(0);
    if(!ps||!*(int*)(ps+g::GC_CONNECTED)||init.intent<0||init.intent>1)return;
    PreservationCommit(0,init.intent==1);init.committed=init.serial;
}
