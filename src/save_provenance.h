#pragma once
#include "peer_inventory.h"
#include <string>
namespace save_provenance {
constexpr uint32_t MAGIC=0x43535049, VERSION=1;
struct Owner { uint64_t lease; uint32_t address; uint16_t port; };
struct Metadata {
    uint32_t magic,version;
    uint64_t session;
    uint8_t engine,variant;
    char map[64],sha256[65];
    Owner owners[4];
};
static_assert(std::is_trivial<Metadata>::value,"binary bounded sidecar");
inline bool Path(const char* input,std::string& out) {
    out.clear(); if(!input) return false;
    for(unsigned i=0;input[i];++i) {
        unsigned char c=input[i]; if(i>=190) return false;
        if(c=='\\') c='/';
        if(!((c>='a'&&c<='z')||(c>='A'&&c<='Z')||(c>='0'&&c<='9')||c=='_'||c=='-'||c=='.'||c=='/')) return false;
        out.push_back(c);
    }
    if(out.size()<10||out.compare(0,5,"save/")||out.compare(out.size()-4,4,".svg")||
       out.find("..")!=std::string::npos||out.find("//")!=std::string::npos) return false;
    return true;
}
inline bool Valid(const Metadata& m,uint8_t engine,uint8_t variant,const char* map,const char* hash,uint64_t session) {
    return m.magic==MAGIC&&m.version==VERSION&&m.session==session&&session&&m.engine==engine&&m.variant==variant&&
        std::memchr(m.map,0,sizeof m.map)&&std::memchr(m.sha256,0,sizeof m.sha256)&&
        map&&hash&&!std::strcmp(m.map,map)&&!std::strcmp(m.sha256,hash);
}
inline bool Owns(const Metadata& m,unsigned slot,const peer_inventory::Record& record) {
    if(slot==0||slot>=4||record.slot!=slot||!record.reserved) return false;
    const auto& o=m.owners[slot];
    return o.lease&&o.lease==record.lease&&m.session==record.world.session&&
        o.address==record.endpoint.address&&o.port==record.endpoint.port;
}
}
