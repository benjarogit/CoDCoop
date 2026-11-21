#include "../src/input_frame_clock.h"
#include <cassert>
int main() {
    const uint8_t cod1[]={0xa3,0x80,0x93,0x43,0x01,0x89,0x0d,0x84,0x93,0x43,0x01,0xc3};
    const uint8_t uo[]={0xa3,0x20,0x22,0x84,0x04,0x89,0x0d,0x24,0x22,0x84,0x04,0xc3};
    assert(input_frame_clock::ValidSetter(cod1,0x1439380,0x1439384));
    assert(input_frame_clock::ValidSetter(uo,0x4842220,0x4842224));
    assert(!input_frame_clock::ValidSetter(uo,0x1439380,0x1439384));
    for(unsigned i=0;i<sizeof cod1;++i) {uint8_t changed[12];std::memcpy(changed,cod1,12);changed[i]^=1;assert(!input_frame_clock::ValidSetter(changed,0x1439380,0x1439384));}
    int input=0,residue=19;
    input_frame_clock::Publish(input,residue,12);assert(input==12&&residue==0);
    input_frame_clock::Publish(input,residue,0);assert(input==0&&residue==0);
    input_frame_clock::Publish(input,residue,500);assert(input==500&&residue==0);
    input_frame_clock::Publish(input,residue,-1);assert(input==0&&residue==0);
}
