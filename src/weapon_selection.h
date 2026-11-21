#pragma once
#include <cstdint>
#include <cstring>
namespace weapon_selection {
constexpr uint32_t CAPABILITY=0x57534c31;
constexpr uint8_t MESSAGE='s', ACK='u', SEED=1;
constexpr uint32_t TIMEOUT=30000, RETRY=400;
constexpr unsigned CMD_WEAPON=6;
inline bool Capability(uint32_t value,uint32_t ticket,bool exact) {return exact&&value==CAPABILITY&&ticket&&ticket<=0x7fffffff;}
inline bool DefinitionMatches(const char* required,const char* game,const char* cgame) {
    return required&&game&&cgame&&!std::strcmp(required,game)&&!std::strcmp(required,cgame);
}
struct Request { uint32_t serial,ticket; uint16_t weapon; uint8_t slot,flags; char name[64]; };
static_assert(sizeof(Request)==76,"bounded selection wire payload");
struct Pending { Request request; uint32_t begun,sent,commandFloor; bool active,queued,completed,ack,commandSeen; };
struct Producer { uint32_t ticket,world,sequence; };
struct Control { Pending host[4],peer; Producer producer[4]; uint32_t serial,acceptedTicket; };
inline bool Newer(uint32_t a,uint32_t b) {return a&&(!b||int32_t(a-b)>0);}
inline bool Name(const char* s) {
    if(!s||!*s)return false;
    unsigned i=0;
    for(;i<64&&s[i];++i) if(!((s[i]>='a'&&s[i]<='z')||(s[i]>='0'&&s[i]<='9')||s[i]=='_'))return false;
    return i>0&&i<64;
}
inline bool Valid(const Request& r,unsigned slot,uint32_t ticket) {
    return r.serial&&slot>0&&slot<4&&r.slot==slot&&r.ticket&&r.ticket==ticket&&r.flags<=SEED&&r.weapon<128&&
        std::memchr(r.name,0,sizeof r.name)&&Name(r.name)&&(r.weapon||r.flags==SEED);
}
inline bool Receive(Pending& p,const Request& r,unsigned slot,uint32_t ticket,uint32_t now) {
    if(!Valid(r,slot,ticket)||(!Newer(r.serial,p.request.serial)&&r.serial!=p.request.serial))return false;
    if(r.serial==p.request.serial) return !std::memcmp(&p.request,&r,sizeof r); // duplicate never requeues a native command
    p={};p.request=r;p.begun=now;p.active=true;return true;
}
inline bool Due(const Pending& p,uint32_t now) {return p.active&&(!p.sent||uint32_t(now-p.sent)>=RETRY);}
inline bool Expired(const Pending& p,uint32_t now) {return p.active&&uint32_t(now-p.begun)>TIMEOUT;}
inline bool Gate(Pending& p,uint8_t* cmd) {
    if(!p.active||p.completed||!cmd)return false;
    uint32_t clock=0;std::memcpy(&clock,cmd,sizeof clock);
    if(cmd[CMD_WEAPON]==p.request.weapon&&int32_t(clock-p.commandFloor)>=0)p.commandSeen=true;
    if(p.ack&&p.commandSeen)return false;
    cmd[CMD_WEAPON]=(uint8_t)p.request.weapon;return true;
}
}
