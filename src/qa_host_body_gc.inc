#include "host_body_ownership.h"
bool QAHostBodyGCEnabled()
{
    return g::uo&&S&&S->memoryRequired&&S->memoryReady&&qa_mt_epoch::enabled;
}
void QATrackHostBody(int player,uint8_t* tree)
{
    if (!QAHostBodyGCEnabled() || !tree) return;
    auto* xanim = *(uint8_t**)tree;
    unsigned nodes = *(unsigned*)(xanim+4);
    host_body_owner::Record record{(uintptr_t)tree,(uintptr_t)xanim,qa_mt_epoch::counter.value,
        0,nodes*8+14,nodes,player,1};
    if (!host_body_owner::Valid(record)) { BodyMemoryFailure("Invalid player-body allocation provenance; restart from launcher.");return; }
    for(unsigned i=0;i<S->hostBodies.count;++i) {
        const auto& old=S->hostBodies.records[i];
        if(old.tree==record.tree&&old.epoch==record.epoch) {
            BodyMemoryFailure("Duplicate player-body ownership record; restart from launcher.");return;
        }
    }
    if(!S->hostBodies.Append(record)) {
        BodyMemoryFailure("Player-body ownership ledger is full; restart from CoDCoop Launcher.");return;
    }
    Log("body memory: track player=%d index=%u bytes=%u epoch=%u",player,record.index,record.bytes,record.epoch);
}
bool QAHostBodyReferenced(uintptr_t tree)
{
    for(int side=0;side<2;++side) {
        auto* map = side ? (int16_t*)0x8ae2c8 : g::serverObjMap;
        for(int e=0;e<g::MAX_GENTITIES;++e) {
            int index=map[e];
            if (!index) continue;
            if(index<0||index>=1024) return true; // uncertain ownership cannot authorize a free
            if(*(uintptr_t*)(g::dobjPool+index*g::DOBJ_SIZE)==tree) return true;
        }
    }
    return false;
}
void QAClearTreeBothSides(uint8_t* tree)
{
    asm volatile("call *%1" : "+b"(tree) : "r"((void*)0x4826b0) : "eax","ecx","edx","memory");
}
void QAHostBodySweep(bool beforeInit,const char* reason)
{
    if(!QAHostBodyGCEnabled()) return;
    if(S->hostBodies.count>host_body_owner::MAX_RECORDS) {BodyMemoryFailure("Invalid player-body ownership state; restart from launcher.");return;}
    for(unsigned i=0;i<S->hostBodies.count;) {
        const auto record=S->hostBodies.records[i];
        if(record.player<0||record.player>=g::MAX_CLIENTS) {BodyMemoryFailure("Invalid player-body owner; restart from launcher.");return;}
        bool current=S->bodyTree[record.player]==(uint8_t*)record.tree;
        bool validEpoch=record.epoch==qa_mt_epoch::counter.value;
        if(current&&validEpoch&&!beforeInit&&S->role==HOST) {++i;continue;}
        bool animationValid=false;
        if(validEpoch&&host_body_owner::Valid(record)&&!IsBadReadPtr((void*)record.tree,12)&&
            !IsBadReadPtr((void*)record.xanim,8)&&XAnimLoaded((uint8_t*)record.xanim))
            animationValid=*(uintptr_t*)record.tree==record.xanim&&*(unsigned*)(record.xanim+4)==record.nodes;
        bool referenced=validEpoch&&QAHostBodyReferenced(record.tree);
        auto decision=host_body_owner::Release(record,qa_mt_epoch::counter.value,referenced,animationValid,
            [&](const host_body_owner::Record& owned){
                // Bloque propio en el heap: no entra en la memoria de los scripts ni en su asignador.
                QAClearTreeBothSides((uint8_t*)owned.tree);
                if (owned.heap) FreeOwnTree((uint8_t*)owned.tree);
                else g::UO_FreeTreeBlock(owned.index,owned.bytes);
                ++S->hostBodies.freed;
                Log("body memory: free player=%d index=%u bytes=%u epoch=%u heap=%u reason=%s",owned.player,owned.index,owned.bytes,owned.epoch,(unsigned)owned.heap,reason);
            });
        if(decision==host_body_owner::Decision::Hold) { ++i; continue; }
        if(decision==host_body_owner::Decision::Forget) {
            ++S->hostBodies.forgotten;
            Log("body memory: forget player=%d index=%u epoch=%u current=%u",record.player,record.index,record.epoch,qa_mt_epoch::counter.value);
        }
        if(current) S->bodyTree[record.player]=nullptr;
        S->hostBodies.Erase(i);
    }
}
void QAPreGameInitHostBodies()
{
    if(S) QAHostBodySweep(true,"before native GAME_INIT");
}
bool QAFreeHostBody(int player)
{
    if(!QAHostBodyGCEnabled()) return false;
    uint8_t* tree=S->bodyTree[player];
    bool known=false;
    for(unsigned i=0;i<S->hostBodies.count;++i)
        if(S->hostBodies.records[i].tree==(uintptr_t)tree&&S->hostBodies.records[i].player==player) known=true;
    if(!known) { BodyMemoryFailure("Untracked player-body memory; restart from CoDCoop Launcher.");return true; }
    // Detach only the exact object we created; never a replacement Game object.
    auto* object=g::ServerDObj(player);
    if(object&&*(uint8_t**)object==tree) g::Com_ServerDObjFree(player,true);
    g::Com_SyncClientDObjs();
    S->bodyTree[player]=nullptr;
    QAHostBodySweep(false,"normal body replacement");
    return true;
}
