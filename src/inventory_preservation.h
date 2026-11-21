#pragma once
#include <cstdint>
#include <type_traits>
namespace inventory_preservation {
enum Phase:uint8_t {WAIT,FRESH,PRESERVED};
struct Identity {uint64_t session;uint32_t world,ticket;uint8_t slot;};
struct Record {Identity identity;Phase phase;bool freshIssued;};
struct NativeInit {uint64_t session;uint32_t world,serial,committed;char map[64];int intent,nativeWorldId;bool valid,announced,handled,nativeReady;};
struct Store {Record slots[4];NativeInit init;uint32_t serial;bool expectSpawnInit;};
static_assert(std::is_trivial<Store>::value&&std::is_standard_layout<Store>::value,"persistent POD lifecycle ownership");
inline bool Valid(Identity a) {return a.session&&a.world&&a.ticket&&a.ticket<=0x7fffffff&&a.slot<4;}
inline bool Same(Identity a,Identity b) {return Valid(a)&&Valid(b)&&a.session==b.session&&a.world==b.world&&a.ticket==b.ticket&&a.slot==b.slot;}
inline void Begin(Record& r,Identity identity,bool keepFresh=false) {
    bool issued=keepFresh&&Same(r.identity,identity)&&r.freshIssued;
    r={identity,WAIT,issued};
}
inline void Issued(Record& r,Identity identity) {r={identity,WAIT,Valid(identity)};}
inline bool IsFresh(const Record& r,Identity identity) {return Same(r.identity,identity)&&r.freshIssued;}
inline bool Commit(Record& r,Identity identity,Phase phase,bool verified) {
    if(!Same(r.identity,identity)||!verified||(phase!=FRESH&&phase!=PRESERVED)||(phase==FRESH&&!r.freshIssued))return false;
    r.phase=phase;if(phase==PRESERVED)r.freshIssued=false;return true;
}
}
