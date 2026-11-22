// Native initial-resource contract. Incremental live-resource updates remain separate.
#include "resource_bootstrap_state.h"
constexpr uint8_t B_REQUEST=0xb0,B_DESCRIPTION=0xb1,B_PART=0xb2,B_ACK=0xb3,B_CANCEL=0xb4;
bool BootEnabled(){return g_api&&S;}
bool BootType(uint8_t type){return type>=B_REQUEST&&type<=B_CANCEL;}
using BootHostPeer=resource_bootstrap_state::HostPeer;
#define g_bootHost (S->bootstrap.host)
#define g_bootSerial (S->bootstrap.serialCounter)
#define g_bootReceiver (S->bootstrap.peer.receiver)
#define g_bootToken (S->bootstrap.peer.token)
#define g_bootCapability (S->bootstrap.peer.capability)
#define g_bootTransferred (S->bootstrap.peer.transferred)
#define g_bootLoading (S->bootstrap.peer.loading)
#define g_bootItemDone (S->bootstrap.peer.itemDone)
#define g_bootEndDone (S->bootstrap.peer.endDone)
#define g_bootNativeReady (S->bootstrap.peer.nativeReady)
#define g_bootFailed (S->bootstrap.peer.failed)
#define g_bootRequestSent (S->bootstrap.peer.requestSent)
#define g_bootReadySent (S->bootstrap.peer.readySent)
#define g_bootNativeMap (S->bootstrap.peer.nativeMap)
#define g_bootRequestNonce (S->bootstrap.peer.requestNonce)
#define g_bootReadyMap (S->bootstrap.peer.readyMap)
uint32_t g_bootParsedSerial;
struct BootCache{resource_bootstrap_flow::Key key{};uint8_t digest[32]{};asset_bootstrap::Resources resources;};BootCache g_bootCache[3];
void BootResetPeer();
asset_bootstrap::Resources g_bootResources; // ephemeral cache; invalidated before DLL shutdown
void* g_bootItemOriginal;uintptr_t g_bootItemCall;uint32_t g_bootItemEpoch;
resource_bootstrap_state::Endpoint BootEndpoint(const sockaddr_in& a){return {a.sin_addr.s_addr,a.sin_port};}
sockaddr_in BootAddress(const BootHostPeer& p){sockaddr_in a{};a.sin_family=AF_INET;a.sin_addr.s_addr=p.endpoint.address;a.sin_port=p.endpoint.port;return a;}
bool BootReserved(const BootHostPeer& p){for(unsigned n=1;n<4;++n)if(peer_inventory::Owner(S->inventories.slots[n],n,S->reloadToken.session,{p.endpoint.address,p.endpoint.port}))return true;return false;}
bool BootActive(const BootHostPeer& p){for(unsigned n=1;n<4;++n)if(S->remote[n].active&&resource_bootstrap_state::Same(p.endpoint,BootEndpoint(S->remote[n].addr)))return true;return false;}
bool BootPeerContext(){return BootEnabled()&&resource_bootstrap_state::Scope(S->bootstrap.peer,BootEndpoint(S->host),S->reloadToken)&&asset_bootstrap::Valid(g_bootReceiver.Header());}
void BootForgetEndpoint(const sockaddr_in& a){if(!S)return;for(auto& p:g_bootHost)if(p.active&&resource_bootstrap_state::Same(p.endpoint,BootEndpoint(a)))p={};}
void BootInvalidatePeer(){if(!S)return;S->bootstrap.peer={};g_bootResources={};g_bootParsedSerial=0;resource_bootstrap_state::Next(S->bootstrap.epoch);}
void BootCancelPeer(){if(!BootPeerContext())return;Writer w(B_CANCEL);w.Put(g_bootRequestNonce);w.Put(g_bootReceiver.Header().serial);for(int i=0;i<3;++i)SendTo(S->host,w.buf,w.len);}
resource_bootstrap_flow::Key BootKey(const BootHostPeer& p) {return {p.token.session,p.token.generation,p.description.serial,p.requestNonce,p.endpoint.address,p.endpoint.port};}
void BootWriteReady(Writer& w) {if(BootEnabled()){w.Put(resource_bootstrap_flow::CAPABILITY);w.Put(resource_bootstrap_flow::VERSION);}}
bool BootAcceptReady(Reader r) {
    if(!BootEnabled())return true;
    unsigned bytes=(unsigned)(r.end-r.p);auto magic=r.Get<uint32_t>();auto version=r.Get<uint16_t>();
    if(!r.Ok()||!resource_bootstrap_flow::Capability(magic,version,bytes)) {
        g_bootCapability={};S->role=NONE;S->compatible=false;
        const char* reason="Host lacks the required resource-bootstrap v2 capability. Update the complete co-op suite.";
        CoopStatus("%s",reason);g::Com_Printf("^1COOP: %s\n",reason);Log("Resource bootstrap: %s",reason);return false;
    }
    if(!reload_delivery::Same(g_bootToken,S->reloadToken)||!resource_bootstrap_state::Same(S->bootstrap.peer.endpoint,BootEndpoint(S->host)))BootResetPeer();
    g_bootCapability=S->reloadToken;return true;
}
void BootWrite(const char* name,const std::string& text) {
    if(!suite::IsQA())return;
    FILE* file=fopen((suite::GameDir()+name).c_str(),"wb");if(!file)return;
    fwrite(text.data(),1,text.size(),file);fclose(file);
}

std::string BootString(const char* p) {
    if(!p)return {};
    MEMORY_BASIC_INFORMATION r{};
    if(!VirtualQuery(p,&r,sizeof r)||r.State!=MEM_COMMIT||(r.Protect&(PAGE_NOACCESS|PAGE_GUARD)))return {};
    size_t available=(uintptr_t)r.BaseAddress+r.RegionSize-(uintptr_t)p,n=0;
    while(n<64&&n<available&&p[n])++n;
    return n&&n<64&&n<available?std::string(p,n):std::string{};
}
std::string BootCgWeaponName(unsigned index) {
    auto module=(uint8_t*)GetModuleHandleA(g::CgameDll());
    if(!module||!index||index>=(unsigned)g::MAX_WEAPONS)return {};
    int count=*(int*)(module+g::A(0xceb88,0x13d474));
    auto defs=*(uint8_t***)(module+g::A(0xceb8c,0x13d478));
    if(count<0||count>=g::MAX_WEAPONS||index>(unsigned)count||!defs||IsBadReadPtr(defs,(count+1)*4)||
       !defs[index]||IsBadReadPtr(defs[index],8))return {};
    auto name=BootString(*(char**)(defs[index]+4));
    return asset_bootstrap::ValidWeaponName(name)?name:std::string{};
}
void BootFailure(const char* reason) {
    if(!g_bootFailed)Log("Resource bootstrap WAIT: %s",reason);
    g_bootFailed=true;CoopStatus("Resource bootstrap WAIT: %s",reason);
}
bool BootRendererCached(const std::string& name) {
    int count=*(int*)g::A(0x15384f8,0x47abb58);
    if(count<1||count>2048)return false;
    auto models=(uint8_t**)g::A(0x15364f8,0x47a9b58);
    for(int i=1;i<count;++i)if(models[i]&&!IsBadReadPtr(models[i],0x60)&&
        !_stricmp(BootString((const char*)models[i]).c_str(),name.c_str())&&*(int*)(models[i]+0x40))return true;
    return false;
}
bool BootStageCurrent(){return BootPeerContext()&&g_bootTransferred&&!g_bootFailed&&g_bootParsedSerial==g_bootReceiver.Header().serial&&g_bootItemEpoch==S->bootstrap.epoch&&S->bootstrap.peer.initSerial==S->preservation.init.serial&&S->bootstrap.peer.gameBase==(uint32_t)(uintptr_t)GetModuleHandleA(g::GameDll())&&!_stricmp(g_bootReceiver.Header().map,g::CvarString("mapname"));}
bool BootContains(const asset_bootstrap::Resources& r,const char* raw){auto name=QASafeModel(raw);return !name.empty()&&std::binary_search(r.models.begin(),r.models.end(),name);}
bool BootPeerModelAllowed(const char* name){if(BootStageCurrent()&&g_bootNativeReady&&g_bootReadyMap==(uint32_t)CvarInt("sv_serverid")&&BootContains(g_bootResources,name))return true;CoopStatus("Resource WAIT: a model is outside the current verified contract; retry after the host prepares this content.");return false;}
bool BootHostObjectAllowed(int slot,const uint8_t* object){
 if(!object)return true;
 for(auto& p:g_bootHost)if(p.active&&resource_bootstrap_state::Same(p.endpoint,BootEndpoint(S->remote[slot].addr))&&reload_delivery::Same(p.token,S->reloadToken)&&!_stricmp(p.description.map,g::CvarString("mapname"))&&p.progress.Allocate(BootKey(p))){
  auto& cache=g_bootCache[&p-g_bootHost];
  if(!resource_bootstrap_flow::Same(cache.key,BootKey(p))||memcmp(cache.digest,p.description.sha256,32)){uint8_t hash[32];if(!suite::Sha256(p.body,p.description.bytes,hash)||memcmp(hash,p.description.sha256,32)||!asset_bootstrap::DecodeResources((const uint8_t*)p.body,p.description.bytes,p.description.names,cache.resources))return false;cache.key=BootKey(p);memcpy(cache.digest,p.description.sha256,32);}
  if(object[0x16]>8)return false;
  for(unsigned k=0;k<object[0x16];++k){auto m=*(uint8_t**)(object+g::DO_MODELS+k*4);if(!m||!BootContains(cache.resources,SafeStr(*(char**)m))){CoopStatus("Resource WAIT: player %d needs media beyond the current initial contract; live resource updates are not approved yet.",slot+1);return false;}}
  return true;
 }
 return false;
}
bool BootExport(asset_bootstrap::Resources& resources) {
    if(g::sv_state!=2||g::cls_state!=2||!g::cgvm||g::currentVM==g::gvm)return false;
    const auto& init=S->preservation.init;
    if(!init.valid||!init.nativeReady||!init.handled||init.session!=S->reloadToken.session||init.world!=S->reloadToken.generation||init.nativeWorldId!=CvarInt("sv_serverid")||_stricmp(init.map,g::CvarString("mapname")))return false;
    uint8_t* game=(uint8_t*)GetModuleHandleA(g::GameDll());if(!game)return false;
    asset_bootstrap::Resources result;std::vector<std::string> resident;
    auto add=[&](const char* raw){auto name=QASafeModel(raw);return !name.empty()&&qa_preload::Add(result.models,name);};
    for(int i=1;i<256;++i)if(*g::ConfigString((int)g::A(31,32)+i)&&!add(g::ConfigString((int)g::A(31,32)+i)))return false;
    for(const auto& entry:g_qaLedger.entries)if(!add(entry.name.c_str()))return false;
    for(int e=0;e<g::sv_numEntities&&e<g::MAX_GENTITIES;++e)if(auto d=g::ServerDObj(e)) {
        if(IsBadReadPtr(d,g::DO_MODELS+32)||d[0x16]>8)return false;
        for(int k=0;k<d[0x16];++k) {
            auto model=*(uint8_t**)(d+g::DO_MODELS+k*4);
            if(!model||IsBadReadPtr(model,4)||!add(*(char**)model))return false;resident.push_back(QASafeModel(*(char**)model));
        }
    }
    int count=*(int*)(game+g::G_NUMWEAPONS);
    auto definitions=*(uint8_t***)(game+g::G_WEAPONDEFS);
    auto flags=(int*)(game+g::G_ITEMREGISTERED);
    if(count<0||count>=g::MAX_WEAPONS||!definitions||IsBadReadPtr(definitions,(count+1)*4))return false;
    for(int w=1;w<=count;++w) {
        if(!definitions[w]||IsBadReadPtr(definitions[w],g::uo?0x388:0x320))return false;
        auto name=BootString(*(char**)(definitions[w]+4));
        if(!asset_bootstrap::ValidWeaponName(name))return false;
        result.weapons.push_back({(uint8_t)w,name,flags[w]!=0});
        const std::vector<int> fields=g::uo?std::vector<int>{0x10,0x14,0x1c8,0x1cc,0x384}:std::vector<int>{0x10,0x14,0x188,0x31c};
        if(flags[w])for(int offset:fields) {
            const char* raw=*(char**)(definitions[w]+offset);
            if(raw) {auto text=BootString(raw);if(!text.empty()&&!add(text.c_str()))return false;}
        }
    }
    // Include every already loaded XModel renderer entry, including unused startup media.
    int cachedCount=*(int*)g::A(0x15384f8,0x47abb58);auto cached=(uint8_t**)g::A(0x15364f8,0x47a9b58);
    if(cachedCount<1||cachedCount>2048)return false;
    for(int i=1;i<cachedCount;++i)if(cached[i]&&!IsBadReadPtr(cached[i],0x60)&&*(int*)(cached[i]+0x40)){
        auto name=BootString((const char*)cached[i]);
        if(name.compare(0,7,"xmodel/")==0){if(!add(name.c_str()))return false;}
        else if(!name.empty()&&name[0]=='*'&&name.size()>1&&name.find_first_not_of("0123456789",1)==std::string::npos){} // inline brush media comes from the identical native BSP
        else {Log("Resource bootstrap: unsupported renderer class/name %s",name.c_str());return false;}
    }
    for(const auto& name:result.models)if(!BootRendererCached(name)&&std::find(resident.begin(),resident.end(),name)==resident.end()) {
        Log("Resource bootstrap host cache missing: %s",name.c_str());return false;
    }
    resources=std::move(result);return true;
}
void BootSendAck(uint8_t phase) {
    const auto& d=g_bootReceiver.Header();
    Writer w(B_ACK);w.Put(d.serial);w.Put(g_bootRequestNonce);w.Put<uint8_t>(phase);w.Put(d.sha256,32);SendTo(S->host,w.buf,w.len);
}
void BootResetPeer() {
    g_bootReceiver.Reset();g_bootResources={};g_bootParsedSerial=0;g_bootToken=S->reloadToken;
    g_bootTransferred=g_bootLoading=g_bootItemDone=g_bootEndDone=g_bootNativeReady=g_bootFailed=false;
    g_bootRequestSent=g_bootReadySent=0;g_bootNativeMap=0;
    g_bootRequestNonce=resource_bootstrap_state::Next(S->bootstrap.nonceCounter);S->bootstrap.peer.endpoint=BootEndpoint(S->host);resource_bootstrap_state::Next(S->bootstrap.epoch);
}
void BootRequest() {
    if(!reload_delivery::Same(g_bootCapability,S->reloadToken)) {S->compatible=false;JoinerSendJoin();return;}
    if(!reload_delivery::Same(g_bootToken,S->reloadToken))BootResetPeer();
    Writer w(B_REQUEST);w.Put(g_bootRequestNonce);SendTo(S->host,w.buf,w.len);g_bootRequestSent=GetTickCount();
}
bool BootPeerJoinAllowed() {
    if(!BootEnabled())return true;
    if(!reload_delivery::Same(g_bootToken,S->reloadToken))BootResetPeer();
    if(g_bootNativeReady&&BootStageCurrent()&&S->bootstrap.peer.cgBase==(uint32_t)(uintptr_t)GetModuleHandleA(g::CgameDll())&&g::sv_state==2&&g::cls_state==2&&g::cgvm&&g_bootReadyMap==CvarInt("sv_serverid")&&
        !_stricmp(g_bootReceiver.Header().map,g::CvarString("mapname")))return true;
    if(g_bootNativeReady)BootResetPeer();
    if(GetTickCount()-g_bootRequestSent>=750)BootRequest(); // keeps stale-world and lost-M_MAP recovery live after byte ACK too
    return false;
}
bool BootInterceptMap(const char* map) {
    if(!BootEnabled())return false;
    if(!BootPeerContext()||!g_bootTransferred||_stricmp(map,g_bootReceiver.Header().map)) {
        S->role=JOINER; // a host transition waits for transfer, not for native map loading yet
        // A separately authenticated map disagrees with this description. Retire
        // the transfer nonce so retry cannot keep accepting the same descriptor.
        if(BootPeerContext()&&g_bootTransferred)BootResetPeer();
        BootRequest();return true;
    }
    if(g_bootNativeReady&&BootStageCurrent()&&g::cls_state==2&&g_bootReadyMap==(uint32_t)CvarInt("sv_serverid"))return true; // delayed identical M_MAP must not reload a ready native world
    if(!g_gameLifecycleReady||!g_qaEndEnabled){BootFailure("required native lifecycle/renderer hook unavailable");return true;}
    if(g_bootLoading&&!g_bootNativeReady)return true; // retransmitted M_MAP
    g_bootLoading=true;g_bootNativeReady=g_bootItemDone=g_bootEndDone=false;g_bootFailed=false;
    g_bootNativeMap=CvarInt("sv_serverid");S->bootstrap.peer.requireMapChange=true;
    Log("Resource bootstrap: verified transfer permits native map %s serial=%u",map,g_bootReceiver.Header().serial);
    return false;
}
bool BootHostJoinAllowed(const sockaddr_in& from) {
    if(!BootEnabled())return true;
    for(const auto& peer:g_bootHost)if(peer.active&&peer.progress.Allocate(BootKey(peer))&&
        peer.endpoint.address==from.sin_addr.s_addr&&peer.endpoint.port==from.sin_port&&
        reload_delivery::Same(peer.token,S->reloadToken)&&!_stricmp(peer.description.map,g::CvarString("mapname")))return true;
    for(const auto& p:g_bootHost)if(p.active&&p.endpoint.address==from.sin_addr.s_addr&&p.endpoint.port==from.sin_port)return false;
    Writer reject(suite::REJECT);const char* reason="This host requires verified native resources before joining. Update or retry the complete co-op suite.";
    reject.Put(reason,(int)strlen(reason)+1);SendTo(from,reject.buf,reject.len);return false;
}
void BootSendHost(BootHostPeer& peer) {
    if(!peer.active||peer.progress.ready||!reload_delivery::Same(peer.token,S->reloadToken))return;
    Writer w(B_DESCRIPTION);w.Put(peer.requestNonce);w.Put(peer.description);SendTo(BootAddress(peer),w.buf,w.len);
    if(peer.progress.transferred) {
        Writer map(M_MAP);map.Put(peer.description.map,(int)strlen(peer.description.map)+1);SendTo(BootAddress(peer),map.buf,map.len);
    } else for(unsigned part=0;part<peer.description.parts;++part) {
        unsigned offset=part*asset_bootstrap::PART_BYTES,n=std::min(asset_bootstrap::PART_BYTES,peer.description.bytes-offset);
        Writer body(B_PART);body.Put(peer.description.serial);body.Put<uint16_t>((uint16_t)part);
        body.Put(peer.body+offset,n);SendTo(BootAddress(peer),body.buf,body.len);
    }
    peer.sent=GetTickCount();
}
bool BootControl(uint8_t type,Reader r,const sockaddr_in& from) {
    if(!BootEnabled()||!BootType(type))return false;
    if(S->role==HOST) {
        BootHostPeer* peer=nullptr;DWORD now=GetTickCount();
        for(auto& p:g_bootHost)if(p.active&&p.endpoint.address==from.sin_addr.s_addr&&p.endpoint.port==from.sin_port)peer=&p;
        if(type==B_REQUEST) {
            uint32_t nonce=r.Get<uint32_t>();if(!nonce||!r.Ok()||r.p!=r.end)return true;
            if(g::sv_state!=2||g::cls_state!=2||g::currentVM==g::gvm)return true;
            if(peer&&!resource_bootstrap_state::AcceptNonce(*peer,nonce))return true;
            if(peer&&peer->requestNonce!=nonce&&BootActive(*peer)){for(int n=1;n<4;++n)if(S->remote[n].active&&resource_bootstrap_state::Same(peer->endpoint,BootEndpoint(S->remote[n].addr))){HostDropRemote(n,false);break;}}
            if(peer&&peer->requestNonce==nonce&&reload_delivery::Same(peer->token,S->reloadToken)) {peer->last=now;BootSendHost(*peer);return true;}
            if(!peer)for(auto& p:g_bootHost)if(!p.active||resource_bootstrap_state::Expired(p,now,BootReserved(p)||BootActive(p))){peer=&p;break;}
            if(!peer)return true;
            asset_bootstrap::Resources resources;std::string body;uint16_t names=0;
            if(!BootExport(resources)||!asset_bootstrap::EncodeResources(resources,body,names)) {
                CoopStatus("Resource bootstrap WAIT: current native model/weapon closure is incomplete.");return true;
            }
            asset_bootstrap::Description d{};
            resource_bootstrap_state::Next(g_bootSerial);
            d.serial=g_bootSerial;d.bytes=(uint32_t)body.size();d.names=names;d.parts=(d.bytes+1023)/1024;
            snprintf(d.map,sizeof d.map,"%s",g::CvarString("mapname"));
            if(!suite::Sha256(body.data(),body.size(),d.sha256)||!asset_bootstrap::Valid(d))return true;
            BootWrite("qa-network-sent.txt",body);
            *peer={};peer->active=true;peer->endpoint=BootEndpoint(from);peer->token=S->reloadToken;peer->description=d;memcpy(peer->body,body.data(),body.size());peer->last=now;peer->requestNonce=nonce;
            peer->progress.Reset(BootKey(*peer));
            auto cacheIndex=peer-g_bootHost;auto& cache=g_bootCache[cacheIndex];
            if(!asset_bootstrap::DecodeResources((const uint8_t*)body.data(),(unsigned)body.size(),names,cache.resources)){*peer={};return true;}
            cache.key=BootKey(*peer);memcpy(cache.digest,d.sha256,32);
            Log("Resource bootstrap: exported serial=%u models=%u weapons=%u bytes=%u before slot allocation",d.serial,(unsigned)resources.models.size(),(unsigned)resources.weapons.size(),d.bytes);
            BootSendHost(*peer);
        } else if(type==B_CANCEL&&peer&&reload_delivery::Same(peer->token,S->reloadToken)) {
            auto nonce=r.Get<uint32_t>(),serial=r.Get<uint32_t>();
            if(r.Ok()&&r.p==r.end&&nonce==peer->requestNonce&&serial==peer->description.serial&&!BootReserved(*peer)&&!BootActive(*peer)){Log("Resource bootstrap: pending endpoint cancelled serial=%u",serial);*peer={};}
        } else if(type==B_ACK&&peer&&reload_delivery::Same(peer->token,S->reloadToken)) {
            uint32_t serial=r.Get<uint32_t>(),nonce=r.Get<uint32_t>();uint8_t phase=r.Get<uint8_t>();
            auto incoming=BootKey(*peer);incoming.serial=serial;incoming.nonce=nonce;
            bool advanced=false;
            if(!r.Ok()||r.end-r.p!=32||!peer->progress.Ack(incoming,phase,!memcmp(r.p,peer->description.sha256,32),&advanced))return true;
            peer->last=now;
            // Repeated descriptions elicit repeated ACKs. Only an actual
            // phase transition may trigger an immediate response; retries
            // continue on the bounded timer instead of creating a feedback loop.
            if(advanced&&phase==1)BootSendHost(*peer);
            else if(advanced)Log("Resource bootstrap: native ready ACK serial=%u; slot now permitted",serial);
        }
    } else if(S->role==JOINER) {
        if(!reload_delivery::Same(g_bootCapability,S->reloadToken))return true;
        if(from.sin_addr.s_addr!=S->host.sin_addr.s_addr||from.sin_port!=S->host.sin_port)return true;
        if(type==B_DESCRIPTION) {
            auto nonce=r.Get<uint32_t>();if(nonce!=g_bootRequestNonce)return true;
            auto d=r.Get<asset_bootstrap::Description>();
            if(!r.Ok()||r.p!=r.end)return true;
            if(!reload_delivery::Same(g_bootToken,S->reloadToken))BootResetPeer();
            if(S->joined&&d.serial!=g_bootReceiver.Header().serial)return true; // no unsolicited active-party serial replacement
            auto prior=g_bootReceiver.Header().serial;
            if(g_bootReceiver.Start(d)){
                if(prior!=d.serial){g_bootResources={};g_bootParsedSerial=0;g_bootTransferred=g_bootLoading=g_bootItemDone=g_bootEndDone=g_bootNativeReady=g_bootFailed=false;resource_bootstrap_state::Next(S->bootstrap.epoch);}
                else if(g_bootTransferred&&!g_bootFailed)BootSendAck(g_bootNativeReady?2:1);
            }
        } else if(type==B_PART) {
            auto serial=r.Get<uint32_t>();auto part=r.Get<uint16_t>();if(!r.Ok())return true;
            if(!g_bootReceiver.Add(serial,part,r.p,(unsigned)(r.end-r.p)))return true;
            if(g_bootTransferred) {if(!g_bootFailed)BootSendAck(g_bootNativeReady?2:1);return true;}
            bool complete=g_bootReceiver.Ready();
            if(g_bootReceiver.FinishResources(g_bootResources,[](const uint8_t* data,unsigned n,const uint8_t* expected){uint8_t hash[32];return suite::Sha256(data,n,hash)&&!memcmp(hash,expected,32);})) {
                g_bootParsedSerial=serial;g_bootTransferred=true;g_bootFailed=false;
                std::string canonical;uint16_t entries=0;
                if(asset_bootstrap::EncodeResources(g_bootResources,canonical,entries))BootWrite("qa-network-received.txt",canonical);
                Log("Resource bootstrap: SHA verified serial=%u models=%u weapons=%u BEFORE native map load",serial,(unsigned)g_bootResources.models.size(),(unsigned)g_bootResources.weapons.size());BootSendAck(1);
            } else if(complete){Log("Resource bootstrap: rejected digest/canonical payload; requesting a new nonce");BootResetPeer();CoopStatus("Resource data failed validation; requesting a clean retransmission.");}

        }
    }
    return true;
}
bool BootQAAllWeaponMedia() {
    char flag[8]{};
    return suite::IsQA()&&g_qaDeferredEnabled&&g::uo&&S&&g_identity.variant==4&&
        GetEnvironmentVariableA("CODCOOP_QA_ALL_WEAPON_MEDIA",flag,sizeof flag)==1&&flag[0]=='1';
}
void BootNativeItems() {
    auto live=(uintptr_t)GetModuleHandleA(g::GameDll());
    const uint8_t nativeStage[]={0x51,0x53,0x55,0x56,0x57,0x83,0xcb,0xff};
    if(!live||g_bootItemOriginal!=(void*)(live+g::A(0x3e5a0,0x421f0))||memcmp(g_bootItemOriginal,nativeStage,sizeof nativeStage))return;
    ((void(__cdecl*)())g_bootItemOriginal)();
    if(BootQAAllWeaponMedia()) {
        auto game=(uint8_t*)live;int count=*(int*)(game+g::G_NUMWEAPONS);
        auto definitions=*(uint8_t***)(game+g::G_WEAPONDEFS);
        if(!*(int*)(game+g::A(0x2db248,0x307f28))||count<1||count>=g::MAX_WEAPONS||
            !definitions||IsBadReadPtr(definitions,(count+1)*4)) {
            BootFailure("QA full native weapon media stage is invalid");return;
        }
        for(int w=1;w<=count;++w)if(!definitions[w]||IsBadReadPtr(definitions[w],g::uo?0x388:0x320)||
            !asset_bootstrap::ValidWeaponName(BootString(*(char**)(definitions[w]+4)))) {
            BootFailure("QA full native weapon table has an invalid definition");return;
        }
        void* native=game+0x1e700;
        for(int w=1;w<=count;++w) {
            int index=w;
            asm volatile("push $1; call *%1; add $4,%%esp":"+D"(index):"r"(native):"eax","ecx","edx","memory","cc");
        }
        for(int w=1;w<=count;++w)if(!*(int*)(game+g::G_ITEMREGISTERED+w*4)) {
            BootFailure("QA full native weapon registration did not complete");return;
        }
        Log("QA full native weapon media: registered all %d existing definitions before GSC; no inventory granted",count);
    }
    if(!g_api||!BootStageCurrent()||!g_bootLoading||!g_bootTransferred||g_bootFailed)return;
    uint8_t* game=(uint8_t*)GetModuleHandleA(g::GameDll());
    int count=game?*(int*)(game+g::G_NUMWEAPONS):-1;
    auto defs=game?*(uint8_t***)(game+g::G_WEAPONDEFS):nullptr;
    if(!game||!*(int*)(game+g::A(0x2db248,0x307f28))||count!=(int)g_bootResources.weapons.size()||!defs) {BootFailure("native item stage/definition count mismatch");return;}
    for(const auto& w:g_bootResources.weapons)if(!defs[w.index]||BootString(*(char**)(defs[w.index]+4))!=w.name) {BootFailure("native weapon index/name order mismatch before item registration");return;}
    void* native=game+g::A(0x1c490,0x1e700);
    for(const auto& w:g_bootResources.weapons)if(w.registered) {
        int index=w.index;
        if(g::uo)asm volatile("push $1; call *%1; add $4,%%esp":"+D"(index):"r"(native):"eax","ecx","edx","memory","cc");
        else asm volatile("push $1; call *%1; add $4,%%esp":"+b"(index):"r"(native):"eax","ecx","edx","memory","cc");
    }
    g_bootItemDone=true;Log("Resource bootstrap: native item/alt registration completed before GSC start serial=%u",g_bootReceiver.Header().serial);
}
void BootPreInit() {
    if(!BootEnabled())return;
    bool peerStage=g_bootLoading&&g_bootTransferred;
    if(!peerStage&&!BootQAAllWeaponMedia())return;
    if(peerStage) {
        if(!BootPeerContext()||g_bootParsedSerial!=g_bootReceiver.Header().serial||_stricmp(g::CvarString("mapname"),g_bootReceiver.Header().map)){BootFailure("native init does not match current approved resource context");return;}
        S->bootstrap.peer.initSerial=S->preservation.init.serial;S->bootstrap.peer.gameBase=(uint32_t)(uintptr_t)GetModuleHandleA(g::GameDll());g_bootItemEpoch=S->bootstrap.epoch;
        g_bootItemDone=g_bootEndDone=g_bootNativeReady=false;
    }
    if(!g_qaEndEnabled){BootFailure("native EndRegistration hook is unavailable");return;}
    auto base=(uintptr_t)GetModuleHandleA(g::GameDll());if(!base)return;
    uintptr_t call=base+g::A(0x1e3d9,0x2095a),original=base+g::A(0x3e5a0,0x421f0),item=base+g::A(0x1c490,0x1e700);
    auto code=(uint8_t*)call;
    const uint8_t stage[]={0x51,0x53,0x55,0x56,0x57,0x83,0xcb,0xff};
    const uint8_t itemTail[]={0x85,0xc0,0x0f,0x85};
    if(memcmp((void*)original,stage,sizeof stage)||*(uint8_t*)item!=0x8b||
       *(uint16_t*)(item+1)!=(g::uo?0xbd04:0x9d04)||*(uint32_t*)(item+3)!=(uint32_t)(base+g::G_ITEMREGISTERED)||
       memcmp((void*)(item+7),itemTail,sizeof itemTail)) {BootFailure("native item function ABI fingerprint mismatch");return;}
    if(code[0]!=0xe8){BootFailure("native item stage callsite signature mismatch");return;}
    uintptr_t target=call+5+*(int32_t*)(code+1);
    if(target!=(uintptr_t)BootNativeItems&&target!=original){BootFailure("foreign item stage wrapper");return;}
    if(target==original) {g_bootItemOriginal=(void*)original;g_bootItemCall=call;hook::PatchRel32(call,(void*)BootNativeItems);}
    if(call+5+*(int32_t*)(code+1)!=(uintptr_t)BootNativeItems){BootFailure("native item-stage patch failed");return;}
    if(peerStage&&g_qaDeferredEnabled)for(const auto& model:g_bootResources.models)if(!g_qaLedger.Approve(model)){BootFailure("approved native model ledger full");return;}
}
void BootBeforeEnd() {
    if(!g_api||!BootStageCurrent()||!g_bootLoading||!g_bootTransferred||g_bootFailed)return;
    if(g_bootNativeReady)S->bootstrap.peer.requireMapChange=false; // local graphics restart revalidates without resetting the party
    g_bootNativeReady=g_bootEndDone=false;S->bootstrap.peer.cgBase=0;
    if(!g_bootItemDone||CvarInt("r_errorOnConflicts")!=1||(*(int*)g::A(0x1535b44,0x47a91a4)&&*(int*)g::A(0x1535b40,0x47a91a0)<=0)) {BootFailure("native pre-EndRegistration stage unavailable");return;}
    int before=QAModelCount();
    for(const auto& model:g_bootResources.models) {
        int handle=((int(__cdecl*)(const char*,int))g::A(0x4f8930,0x4fda70))(model.c_str(),7);
        if(handle<=0||handle>=2048){BootFailure("normal renderer registration failed");return;}
    }
    if(before!=QAModelCount()){BootFailure("renderer preload unexpectedly changed native model CS");return;}
    g_bootEndDone=true;Log("Resource bootstrap: renderer media preloaded before EndRegistration models=%u gameCS=%d unchanged",(unsigned)g_bootResources.models.size(),before);
}
void BootTick() {
    if(!BootEnabled())return;
    DWORD now=GetTickCount();
    if(S->role==HOST) {for(auto& p:g_bootHost)if(p.active){
        if(!reload_delivery::Same(p.token,S->reloadToken)||resource_bootstrap_state::Expired(p,now,BootReserved(p)||BootActive(p))){p={};continue;}
        p.allocated=BootActive(p)||BootReserved(p);if(now-p.sent>=500)BootSendHost(p);
    }return;}
    if(!S->host.sin_port||!reload_delivery::Same(g_bootToken,S->reloadToken)) {
        if(g_bootLoading||g_bootTransferred||g_bootNativeReady)BootResetPeer();
        return;
    }
    if(g_bootNativeReady&&S->bootstrap.peer.cgBase!=(uint32_t)(uintptr_t)GetModuleHandleA(g::CgameDll())){g_bootNativeReady=g_bootEndDone=false;S->bootstrap.peer.requireMapChange=false;}
    if(BootStageCurrent()&&g_bootLoading&&!g_bootNativeReady&&!g_bootFailed&&g_bootItemDone&&g_bootEndDone&&g::sv_state==2&&g::cls_state==2&&g::cgvm&&
        (!S->bootstrap.peer.requireMapChange||CvarInt("sv_serverid")!=(int)g_bootNativeMap)&&!_stricmp(g::CvarString("mapname"),g_bootReceiver.Header().map)) {
        auto game=(uint8_t*)GetModuleHandleA(g::GameDll());int count=game?*(int*)(game+g::G_NUMWEAPONS):-1;
        auto defs=game?*(uint8_t***)(game+g::G_WEAPONDEFS):nullptr;
        bool match=game&&asset_bootstrap::MatchWeapons(g_bootResources,count,g::MAX_WEAPONS,
            [&](unsigned n){return defs&&defs[n]?BootString(*(char**)(defs[n]+4)):std::string{};},
            [&](unsigned n){return *(int*)(game+g::G_ITEMREGISTERED+n*4)!=0;});
        std::string audit="index\texpected_name\texpected_registered\tgame_name\tgame_registered\tcgame_name\n";
        for(const auto& weapon:g_bootResources.weapons) {
            auto name=BootCgWeaponName(weapon.index);
            if(weapon.name!=name)match=false;
            std::string local=defs&&weapon.index<=count&&defs[weapon.index]?BootString(*(char**)(defs[weapon.index]+4)):"<missing>";
            if(!asset_bootstrap::ValidWeaponName(local))local="<invalid>";
            int flag=game&&weapon.index<=count?*(int*)(game+g::G_ITEMREGISTERED+weapon.index*4):0;
            char prefix[32];snprintf(prefix,sizeof prefix,"%u\t",weapon.index);
            audit+=prefix+weapon.name+'\t'+(weapon.registered?"1":"0")+'\t'+local+'\t'+(flag?"1":"0")+'\t'+(name.empty()?"<missing>":name)+'\n';
        }
        BootWrite("qa-network-mapping.tsv",audit);
        if(!match){BootFailure("completed Game/CG weapon index/name/registered mapping differs");return;}
        g_bootNativeReady=true;g_bootReadyMap=CvarInt("sv_serverid");S->bootstrap.peer.cgBase=(uint32_t)(uintptr_t)GetModuleHandleA(g::CgameDll());BootSendAck(2);g_bootReadySent=now;
        Log("Resource bootstrap: completed native Game/CG mapping verified serial=%u BEFORE requesting slot",g_bootReceiver.Header().serial);
    }
    if(g_bootNativeReady&&!S->joined&&now-g_bootReadySent>=500) {BootSendAck(2);g_bootReadySent=now;}
}
void BootShutdown() {
    if(!g_bootItemCall)return;
    auto game=(uintptr_t)GetModuleHandleA(g::GameDll());
    if(!game||g_bootItemCall!=game+g::A(0x1e3d9,0x2095a)){g_bootItemCall=0;g_bootItemOriginal=nullptr;return;}
    auto bytes=(uint8_t*)g_bootItemCall;
    if(bytes[0]==0xe8&&g_bootItemCall+5+*(int32_t*)(bytes+1)==(uintptr_t)BootNativeItems) {
        hook::PatchRel32(g_bootItemCall,g_bootItemOriginal);
        if(g_bootItemCall+5+*(int32_t*)(bytes+1)==(uintptr_t)g_bootItemOriginal){g_bootItemCall=0;g_bootItemOriginal=nullptr;return;}
    }
    HMODULE retained=nullptr;
    GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_PIN,reinterpret_cast<LPCSTR>(&BootNativeItems),&retained);
    Log("Resource bootstrap: retained native item wrapper; pinned=%d",retained!=nullptr);
}

void BootStop(){
 if(!BootEnabled())return;
 bool interrupted=S->role!=NONE||S->waitingForMap;
 if(S->role==HOST){Writer close(M_BYE);close.Put<uint8_t>(1);close.Put(S->reloadToken);for(const auto& p:g_bootHost)if(p.active&&p.token.session==S->reloadToken.session)for(int n=0;n<3;++n)SendTo(BootAddress(p),close.buf,close.len);}
 if(S->role!=NONE)Cmd_CoopLeave();else if(S->waitingForMap)JoinerLeave("Resource validation stopped for a core update.");
 resource_bootstrap_state::Clear(S->bootstrap);g_bootParsedSerial=0;g_bootResources={};for(auto& c:g_bootCache)c={};
 S->waitingForMap=false;S->compatible=false;S->reloadToken={};
 if(interrupted){CoopStatus("Co-op stopped for a core update. Start or join again to verify the new resource contract.");Log("Resource bootstrap: core reload ended session; fresh handshake required");}
}
