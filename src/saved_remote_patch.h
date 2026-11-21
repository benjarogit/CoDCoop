#pragma once
#include <cstdint>
#include <cstring>
namespace saved_remote_patch {
inline unsigned Offset(bool uo){return uo?0x30b74:0x2de6f;}
inline bool Valid(const uint8_t* branch,uintptr_t base,bool uo) {
    if(!branch||(branch[0]!=0x75&&branch[0]!=0xeb)||branch[1]!=0x0d||branch[2]!=0x68||branch[7]!=0xe8||
       branch[12]!=0x83||branch[13]!=0xc4||branch[14]!=0x04)return false;
    uint32_t message;int32_t relative;std::memcpy(&message,branch+3,4);std::memcpy(&relative,branch+8,4);
    return message==(uint32_t)(base+(uo?0x97788:0x944a0))&&
        (uint32_t)(Offset(uo)+12+relative)==(uo?0x1f330u:0x1d080u);
}
struct Ownership {uintptr_t branch;bool written;};
inline bool CanRestore(const Ownership& owner,const uint8_t* branch,uintptr_t base,bool uo)
{return owner.written&&owner.branch==(uintptr_t)branch&&Valid(branch,base,uo)&&branch[0]==0xeb;}
}
