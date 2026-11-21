#include "../src/weapon_selection.h"
#include <cassert>
#include <initializer_list>
using namespace weapon_selection;
int main() {
    assert(Capability(CAPABILITY,7,true));
    assert(!Capability(0,7,true)&&!Capability(CAPABILITY,0,true)&&!Capability(CAPABILITY,7,false));
    assert(!Capability(CAPABILITY,0x80000000,true)); // legacy/missing/malformed capability fails closed
    assert(DefinitionMatches("springfield","springfield","springfield"));
    assert(!DefinitionMatches("springfield","springfield","bar"));
    assert(!DefinitionMatches("springfield","bar","springfield"));
    assert(!DefinitionMatches("springfield","springfield",nullptr));
    Request r{};r.serial=7;r.ticket=3;r.weapon=98;r.slot=1;strcpy(r.name,"springfield");
    Pending p{};
    assert(!Receive(p,r,2,3,10)&&!Receive(p,r,1,4,10));
    assert(Receive(p,r,1,3,10));assert(p.active&&!p.queued);
    p.queued=true;p.completed=true;p.active=false;
    assert(Receive(p,r,1,3,20)&&p.completed&&p.queued&&!p.active); // duplicate after user's later weapon change never requeues
    auto stale=r;stale.serial=6;assert(!Receive(p,stale,1,3,30));
    auto changed=r;strcpy(changed.name,"bar");assert(!Receive(p,changed,1,3,30));
    r.serial=8;assert(Receive(p,r,1,3,40)&&p.active&&!p.queued&&!p.completed);
    assert(Due(p,40));p.sent=40;assert(!Due(p,41)&&Due(p,441));
    assert(!Expired(p,30040)&&Expired(p,30041));
    unsigned char cmd[44],before[44];for(unsigned i=0;i<sizeof cmd;++i)cmd[i]=(unsigned char)(i+50);
    uint32_t clock=101;std::memcpy(cmd,&clock,4);cmd[6]=0;std::memcpy(before,cmd,sizeof cmd);p.commandFloor=100;
    assert(Gate(p,cmd)&&cmd[6]==98);
    for(unsigned i=0;i<sizeof cmd;++i)if(i!=6)assert(cmd[i]==before[i]); // NEVER overwrite +7, buttons, movement, angles
    p.ack=true;clock=99;std::memcpy(cmd,&clock,4);cmd[6]=98;assert(Gate(p,cmd)&&!p.commandSeen);
    clock=102;std::memcpy(cmd,&clock,4);assert(!Gate(p,cmd)&&p.commandSeen);
    cmd[6]=5;assert(!Gate(p,cmd)&&cmd[6]==5); // normal user switch resumes after actual command + ACK
    for(auto bad:{"springfield;quit","../bar","BAR","bar\nquit",""})assert(!Name(bad));
    char unterminated[64];memset(unterminated,'a',sizeof unterminated);assert(!Name(unterminated));
    r.weapon=0;r.flags=0;assert(!Valid(r,1,3));r.flags=SEED;strcpy(r.name,"none");assert(Valid(r,1,3));
}
