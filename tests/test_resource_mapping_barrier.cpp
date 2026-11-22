#include "../src/resource_mapping_barrier.h"
#include <cassert>
int main(){
 const uint8_t cod[]={0x0f,0xbf,0x04,0x4d,0x10,0x6f,0x88,0x00};
 uint8_t uo[]={0x0f,0xbf,0x04,0x4d,0x50,0x45,0x89,0x00};
 const uint8_t sync[]={0x53,0x56,0x57,0x33,0xff};
 assert(resource_mapping_barrier::Signature(false,cod,sync));
 assert(resource_mapping_barrier::Signature(true,uo,sync));
 assert(!resource_mapping_barrier::Signature(false,uo,sync));
 uo[0]=0xe9;assert(!resource_mapping_barrier::Signature(true,uo,sync));
 assert(!resource_mapping_barrier::Signature(true,nullptr,sync));
 unsigned nativeOwners[]={13,29,41},maps[]={1,0,3},calls=0,syncs=0;
 auto has=[&](unsigned n){return maps[n]!=0;};
 auto detach=[&](unsigned n,bool clear){assert(clear&&maps[n]);maps[n]=0;++calls;};
 auto publish=[&]{++syncs;};
 assert(!resource_mapping_barrier::Run(false,3,has,detach,publish).ran);
 assert(!resource_mapping_barrier::Run(true,2049,has,detach,publish).ran);
 assert(!calls&&!syncs);
 auto result=resource_mapping_barrier::Run(true,3,has,detach,publish);
 assert(result.ran&&result.detached==2&&calls==2&&syncs==1);
 assert(!maps[0]&&!maps[2]&&nativeOwners[0]==13&&nativeOwners[1]==29&&nativeOwners[2]==41);
}
