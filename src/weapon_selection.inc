std::string SelectionField(int slot,const char* field)
{char key[64];snprintf(key,sizeof key,"coop_select_%d_%s",slot,field);return g::CvarString(key);}
void SelectionStatus(int slot,const char* status,uint32_t sequence=0)
{
    char key[64],value[24];snprintf(key,sizeof key,"coop_select_%d_status",slot);SetCoopCvarChanged(key,status);
    if(sequence) {
        auto session=spawn_ticket::Split(S->reloadToken.session);
        const char* fields[]={"ack_ticket","ack_world","ack_session_a","ack_session_b","ack_session_c","ack_seq"};
        const uint32_t values[]={S->spawnTicket[slot],S->reloadToken.generation,session.a,session.b,session.c,sequence};
        for(unsigned i=0;i<6;++i){snprintf(key,sizeof key,"coop_select_%d_%s",slot,fields[i]);snprintf(value,sizeof value,"%u",values[i]);SetCoopCvarChanged(key,value);}
    }
}
void SelectionResetStatus(int slot)
{SelectionStatus(slot,"IDLE");char key[64];snprintf(key,sizeof key,"coop_select_%d_ack_seq",slot);SetCoopCvarChanged(key,"0");}
bool SelectionNumber(const std::string& text,uint32_t& value,uint32_t maximum=0x7fffffff)
{
    if(text.empty()||(text.size()>1&&text[0]=='0'))return false;
    uint64_t n=0;for(char c:text) {if(c<'0'||c>'9')return false;n=n*10+(c-'0');if(n>maximum)return false;}
    value=(uint32_t)n;return true;
}
const char* SelectionWeaponName(int weapon,bool registered=true)
{
    uint8_t* game=(uint8_t*)GetModuleHandleA(g::GameDll());
    if(!game||weapon<=0||weapon>=g::MAX_WEAPONS||weapon>*(int*)(game+g::G_NUMWEAPONS))return nullptr;
    uint8_t** defs=*(uint8_t***)(game+g::G_WEAPONDEFS);
    if(!defs||!defs[weapon]||(registered&&!*(int*)(game+g::G_ITEMREGISTERED+weapon*4)))return nullptr;
    const char* name=SafeStr(*(char**)(defs[weapon]+4));
    return weapon_selection::Name(name)?name:nullptr;
}
bool SelectionOwned(const uint8_t* ps,unsigned weapon)
{return ps&&weapon<(unsigned)g::MAX_WEAPONS&&(!weapon||(*(const uint32_t*)(ps+g::PS_WEAPONS+(weapon/32)*4)&(1u<<(weapon%32))));}
const char* SelectionCgWeaponName(uint8_t* cg,unsigned weapon)
{
    if(!cg||weapon==0||weapon>=(unsigned)g::MAX_WEAPONS)return nullptr;
    // Native `weapon` name lookup: CoD1 A490, UO B190. These are
    // CGame's own tables, independently of the local Game bootstrap table.
    int count=*(int*)(cg+g::A(0xceb88,0x13d474));
    uint8_t** definitions=*(uint8_t***)(cg+g::A(0xceb8c,0x13d478));
    if(count<0||count>=g::MAX_WEAPONS||weapon>(unsigned)count||!definitions||!definitions[weapon])return nullptr;
    const char* name=SafeStr(*(char**)(definitions[weapon]+4));
    return weapon_selection::Name(name)?name:nullptr;
}
void QueueWeaponSelection(int n,int weapon,bool seed)
{
    if(n<=0||n>=g::MAX_CLIENTS||!S->remote[n].active||!S->spawnTicket[n])return;
    const char* name=weapon?SelectionWeaponName(weapon):"none";
    if(!name||!SelectionOwned(g::PlayerState(n),weapon)) {SelectionStatus(n,"WAIT_DEFINITION");Log("selection: cannot register owned weapon slot=%d weapon=%d",n,weapon);return;}
    auto& p=S->selection.host[n];p={};p.active=true;p.begun=GetTickCount();
    p.commandFloor=*(uint32_t*)g::PlayerState(n);
    if(!++S->selection.serial)++S->selection.serial;
    p.request.serial=S->selection.serial;p.request.ticket=S->spawnTicket[n];p.request.slot=(uint8_t)n;
    p.request.weapon=(uint16_t)weapon;p.request.flags=seed?weapon_selection::SEED:0;
    snprintf(p.request.name,sizeof p.request.name,"%s",name);
    SelectionStatus(n,"QUEUED");
    Log("selection: queued slot=%d serial=%u ticket=%u weapon=%d seed=%d",n,p.request.serial,p.request.ticket,weapon,seed);
}
void SelectionAck(uint8_t status)
{
    const auto& p=S->selection.peer;
    Writer w(weapon_selection::ACK);w.Put(p.request.serial);w.Put(p.request.ticket);w.Put(status);SendTo(S->host,w.buf,w.len);
}
void SelectionPeerMessage(Reader r)
{
    auto request=r.Get<weapon_selection::Request>();
    if(!r.Ok()||r.p!=r.end||!weapon_selection::Receive(S->selection.peer,request,S->slot,S->selection.acceptedTicket,GetTickCount()))return;
    if(S->selection.peer.completed)SelectionAck(0);
}
void SelectionUsercmd(int n,uint8_t* cmd,bool local)
{
    if(!cmd)return;
    if(!local) {weapon_selection::Gate(S->selection.host[n],cmd);return;}
    auto& p=S->selection.peer;
    if(!p.active||!p.queued||p.completed||cmd[weapon_selection::CMD_WEAPON]!=p.request.weapon||int32_t(*(uint32_t*)cmd-p.commandFloor)<0)return;
    p.completed=true;p.active=false;SelectionAck(0);
    Log("selection: native command observed serial=%u weapon=%u",p.request.serial,p.request.weapon);
}
void WeaponSelectionTick()
{
    DWORD now=GetTickCount();
    if(S->role==HOST) {
        bool ready=g_getUsercmdTramp&&patch_owner::JumpTargets((uint8_t*)SV_GET_USERCMD,(uintptr_t)Hook_GetUsercmd);
        SetCoopCvarChanged("coop_select_api",ready?"1":"0");PublishSpawnTickets();
        for(int n=1;n<g::MAX_CLIENTS;++n) {
            if(!S->remote[n].active)continue;
            auto& source=S->selection.producer[n];
            if(source.ticket!=S->spawnTicket[n]||source.world!=S->reloadToken.generation)source={S->spawnTicket[n],S->reloadToken.generation,0};
            uint32_t seq=0;
            if(ready&&SelectionNumber(SelectionField(n,"seq"),seq)&&seq>source.sequence) {
                // Commit is read twice around the fixed fields. No peer chooses
                // console-variable names, command text or a player pointer.
                uint32_t ticket=0,world=0,a=0,b=0,c=0;
                auto session=spawn_ticket::Split(S->reloadToken.session);
                std::string name=SelectionField(n,"name"),epoch=SelectionField(n,"epoch");
                bool valid=UFPlannedSlot(n)&&SelectionNumber(SelectionField(n,"ticket"),ticket)&&ticket==S->spawnTicket[n]&&
                    SelectionNumber(SelectionField(n,"world"),world,0xffffffff)&&world==S->reloadToken.generation&&
                    SelectionNumber(SelectionField(n,"session_a"),a)&&a==session.a&&SelectionNumber(SelectionField(n,"session_b"),b)&&b==session.b&&
                    SelectionNumber(SelectionField(n,"session_c"),c)&&c==session.c&&epoch==g::CvarString("coop_qa_kit_verified_epoch")&&
                    weapon_selection::Name(name.c_str())&&SelectionField(n,"seq")==std::to_string(seq);
                if(valid)source.sequence=seq;
                int weapon=0;
                if(valid)for(int w=1;w<g::MAX_WEAPONS;++w)if(const char* found=SelectionWeaponName(w))
                    if(name==found&&SelectionOwned(g::PlayerState(n),w)){weapon=w;break;}
                if(weapon)QueueWeaponSelection(n,weapon,false);
                else SelectionStatus(n,"REJECTED",seq);
            }
            auto& p=S->selection.host[n];
            if(!p.active)continue;
            if(p.request.ticket!=S->spawnTicket[n]){p={};continue;}
            if(p.sent&&weapon_selection::Expired(p,now)) {
                SelectionStatus(n,"FAILED_TIMEOUT");Log("selection: native selection timed out slot=%d serial=%u",n,p.request.serial);
                CoopStatus("Player %d could not select the required weapon. Repair missing content and retry.",n+1);
                p={};HostDropRemote(n);continue;
            }
            if(S->remote[n].worldReady&&weapon_selection::Due(p,now)) {
                if(!p.sent)p.begun=now; // native map loading is not a failed selection timeout
                Writer w(weapon_selection::MESSAGE);w.Put(p.request);SendTo(S->remote[n].addr,w.buf,w.len);p.sent=now;
            }
            if(p.ack&&p.commandSeen){p.active=false;p.completed=true;SelectionStatus(n,"APPLIED",source.sequence);}
        }
    } else if(S->role==JOINER&&S->joined&&!S->movieWorldSuspended&&g::cls_state==2&&g::cgvm) {
        auto& p=S->selection.peer;
        if(!p.active||p.completed)return;
        if(weapon_selection::Expired(p,now)) {SelectionAck(2);JoinerLeave("Required weapon selection was unavailable. Repair missing content and retry joining.");return;}
        uint8_t* cg=(uint8_t*)GetModuleHandleA(g::CgameDll());
        uint8_t* snap=cg?*(uint8_t**)(cg+g::A(0x10b8a8,0x259548)):nullptr;
        const uint8_t* ps=snap?snap+8:nullptr; // actual native HOST snapshot, not local bootstrap PS
        bool own=ps&&*(int*)(snap+4)>0&&*(int*)(ps+g::PS_CLIENTNUM)==S->slot&&SelectionOwned(ps,p.request.weapon);
        const char* name=p.request.weapon?SelectionWeaponName(p.request.weapon):"none";
        const char* cgName=p.request.weapon?SelectionCgWeaponName(cg,p.request.weapon):"none";
        if(!own||!weapon_selection::DefinitionMatches(p.request.name,name,cgName)) {if(weapon_selection::Due(p,now)){SelectionAck(1);p.sent=now;CoopStatus("Waiting for the host-owned weapon snapshot and matching local weapon content.");}return;}
        if(!p.queued) {
            p.commandFloor=*(const uint32_t*)ps;
            if(p.request.weapon) {char command[96];snprintf(command,sizeof command,"weapon %s\n",p.request.name);g::Cbuf_AddText(command);}
            p.queued=true;
            Log("selection: queued native weapon command serial=%u weapon=%u",p.request.serial,p.request.weapon);
        }
    }
}
