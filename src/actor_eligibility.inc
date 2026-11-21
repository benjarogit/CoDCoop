// Derived, host-authoritative script view. No script receipt grants eligibility.
// No new persistent state: every publication binds the current native owner and
// world, including after Core hot reload, connection loss and native save load.
void PublishActorEligibility(int only)
{
    if(!S)return;
    const char* mode=S->role==HOST?"HOST":S->role==JOINER?"JOINER":"SOLO";
    SetCoopCvarChanged("coop_actor_mode",mode);
    bool ready=g::sv_state==2&&g::svs_clients&&g::sv_gameClients;
    for(int n=0;n<g::MAX_CLIENTS;++n) {
        if(only>=0&&n!=only)continue;
        actor_eligibility::View view{};
        view.worldReady=ready;view.remoteReady=n==0;
        std::string identity;
        if(S->role==HOST) {
            auto owner=PreservationIdentity(n);
            const auto& record=S->preservation.slots[n];
            view.authoritative=true;
            view.ownerReady=inventory_preservation::Same(owner,record.identity)&&record.phase!=inventory_preservation::WAIT;
            if(inventory_preservation::Valid(owner)) {
                auto parts=spawn_ticket::Split(owner.session);char text[128];
                snprintf(text,sizeof text,"%u|%u|%u|%d|%u|%u",parts.a,parts.b,parts.c,n,owner.ticket,owner.world);
                identity=text;
            }
            if(n)view.remoteReady=S->remote[n].active&&S->remote[n].worldReady;
            view.downed=S->downed[n];
        } else if(S->role==NONE&&n==0) {
            view.authoritative=true;view.ownerReady=true;
            identity=std::string("solo|")+g::CvarString("sv_serverid")+"|0";
        }
        if(ready&&PlayerInGame(n)) {
            view.connected=true;
            view.health=*(int*)(g::Entity(n)+g::GE_HEALTH);
        }
        char key[64];snprintf(key,sizeof key,"coop_actor_%d_identity",n);
        if(strcmp(g::CvarString(key),identity.c_str())) {
            char stateKey[64];snprintf(stateKey,sizeof stateKey,"coop_actor_%d_state",n);
            SetCoopCvarChanged(stateKey,"WAIT"); // never grant under an old tuple
            SetCoopCvarChanged(key,identity.c_str());
        }
        snprintf(key,sizeof key,"coop_actor_%d_state",n);
        SetCoopCvarChanged(key,actor_eligibility::Name(actor_eligibility::Evaluate(view)));
    }
    SetCoopCvarChanged("coop_actor_api","1");
}
