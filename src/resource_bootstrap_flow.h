#pragma once
#include <cstdint>
namespace resource_bootstrap_flow {
constexpr uint32_t CAPABILITY=0x41534554;constexpr uint16_t VERSION=2;
inline bool Capability(uint32_t magic,uint16_t version,unsigned bytes){return bytes==6&&magic==CAPABILITY&&version==VERSION;}
struct Key {uint64_t session;uint32_t world,serial,nonce,address;uint16_t port;};
inline bool Valid(Key k){return k.session&&k.world&&k.serial&&k.nonce&&k.port;}
inline bool Same(Key a,Key b){return Valid(a)&&Valid(b)&&a.session==b.session&&a.world==b.world&&a.serial==b.serial&&a.nonce==b.nonce&&a.address==b.address&&a.port==b.port;}
struct Progress {
    Key key;bool transferred,ready;
    void Reset(Key next){key=next;transferred=ready=false;}
    bool Ack(Key incoming,uint8_t phase,bool digestMatches){
        if(!Same(key,incoming)||!digestMatches||phase<1||phase>2)return false;
        if(phase==1)transferred=true;
        else {if(!transferred)return false;ready=true;}
        return true;
    }
    bool Allocate(Key current)const{return ready&&transferred&&Same(key,current);}
};
}
