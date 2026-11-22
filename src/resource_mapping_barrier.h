#pragma once
#include <cstdint>
#include <cstring>
namespace resource_mapping_barrier {
// Native server/client DObjs carry model IDs belonging to the old local CS.
// Detach/sync those representations before replacing CS. Native actor/tree
// owners remain intact; this API exposes no allocator or owner-block free.
inline bool Signature(bool uo,const uint8_t* freeEntry,const uint8_t* syncEntry){
 const uint8_t freeCoD[]={0x0f,0xbf,0x04,0x4d,0x10,0x6f,0x88,0x00};
 const uint8_t freeUO[]={0x0f,0xbf,0x04,0x4d,0x50,0x45,0x89,0x00};
 const uint8_t sync[]={0x53,0x56,0x57,0x33,0xff};
 return freeEntry&&syncEntry&&!std::memcmp(freeEntry,uo?freeUO:freeCoD,8)&&!std::memcmp(syncEntry,sync,5);
}
struct Result {bool ran;unsigned detached;};
template<class Has,class Detach,class Sync>
Result Run(bool ready,unsigned limit,Has has,Detach detach,Sync sync){
 if(!ready||!limit||limit>2048)return {};
 Result result{true,0};
 for(unsigned e=0;e<limit;++e)if(has(e)){detach(e,true);++result.detached;}
 sync();return result;
}
}
