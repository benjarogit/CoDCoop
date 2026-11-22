#pragma once
#include <cmath>
#include <cstdint>
#include <cstring>
#include <type_traits>

namespace peer_pose {
// Trusted native, plain-player pose only. The containing inventory owner binds
// slot, lease, session, world and map; no link pointers or complete PS are copied.
struct Saved {
    bool valid,pending,hasProneBasis;
    uint32_t commandFloor;
    float origin[3],angles[3],proneBasis[3];
};
static_assert(std::is_trivial<Saved>::value && std::is_standard_layout<Saved>::value,
              "saved pose must survive DLL reload as plain data");
inline bool Capture(Saved& saved,const float* origin,const float* angles,bool plain,const float* prone=nullptr) {
    saved={};
    if(!plain||!origin||!angles)return false;
    for(unsigned k=0;k<3;++k)if(!std::isfinite(origin[k])||!std::isfinite(angles[k]))return false;
    if(prone)for(unsigned k=0;k<3;++k)if(!std::isfinite(prone[k]))return false;
    std::memcpy(saved.origin,origin,sizeof saved.origin);
    std::memcpy(saved.angles,angles,sizeof saved.angles);
    if(prone){std::memcpy(saved.proneBasis,prone,sizeof saved.proneBasis);saved.hasProneBasis=true;}
    saved.valid=true;return true;
}
inline uint32_t Delta(float angle,uint32_t raw) {
    double normalized=std::fmod((double)angle,360.0);
    if(normalized<0)normalized+=360.0;
    uint32_t desired=(uint32_t)(normalized*(65536.0/360.0))&0xffffu;
    return desired-raw; // Native short-angle arithmetic wraps; never signed overflow.
}
inline bool CommandReady(const Saved& saved,uint32_t command) {
    return saved.valid&&saved.pending&&command&&int32_t(command-saved.commandFloor)>=0;
}
}
