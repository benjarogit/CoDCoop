#pragma once
#include <cstdint>
#include <cstring>
namespace saved_ghost_cleanup {
inline bool ValidBranch(const uint8_t* code,uintptr_t base,bool uo) {
    if(!code||code[0]!=0x83||code[1]!=0xbe||code[6]!=2||code[7]!=0x75||code[8]!=7||
       code[9]!=0x8b||code[10]!=0xc7||code[11]!=0xe8)return false;
    uint32_t connected=0;int32_t relative=0;
    std::memcpy(&connected,code+2,4);std::memcpy(&relative,code+12,4);
    return connected==(uo?0x8228u:0x73e0u)&&
        base+(uo?0x1689fu:0x14cbfu)+16+relative==base+(uo?0x1a630u:0x184f0u);
}
inline int Connection(unsigned slot,bool active,int engineState,int savedState) {
    // A restored ghost has no engine client. Native state2 would toss its
    // held weapon into the restored world before freeing it. Use the native
    // partial-connection cleanup path instead; never alter a real player.
    return slot>0&&slot<4&&!active&&engineState==0&&savedState==2?1:savedState;
}
}
