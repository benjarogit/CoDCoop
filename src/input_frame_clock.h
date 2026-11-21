#pragma once
#include <cstdint>
#include <cstring>
namespace input_frame_clock {
inline bool ValidSetter(const uint8_t* code,uint32_t input,uint32_t remainder) {
    if(!code||code[0]!=0xa3||code[5]!=0x89||code[6]!=0x0d||code[11]!=0xc3)return false;
    uint32_t a=0,b=0;std::memcpy(&a,code+1,4);std::memcpy(&b,code+7,4);
    return a==input&&b==remainder;
}
inline void Publish(int& input,int& remainder,int localMsec) {
    // Native SV_Frame's no-local-server path publishes real client input time
    // and zero server interpolation residue. Do not use host snapshot delta:
    // a stationary/paused host world must not disable local camera controls.
    input=localMsec<0?0:localMsec;
    remainder=0;
}
}
