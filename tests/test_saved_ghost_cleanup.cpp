#include "../src/saved_ghost_cleanup.h"
#include <cassert>
int main() {
    const uint8_t cod1[]={0x83,0xbe,0xe0,0x73,0,0,2,0x75,7,0x8b,0xc7,0xe8,0x21,0x38,0,0};
    const uint8_t uo[]={0x83,0xbe,0x28,0x82,0,0,2,0x75,7,0x8b,0xc7,0xe8,0x81,0x3d,0,0};
    assert(saved_ghost_cleanup::ValidBranch(cod1,0x20000000,false));
    assert(saved_ghost_cleanup::ValidBranch(uo,0x20000000,true));
    assert(!saved_ghost_cleanup::ValidBranch(cod1,0x20000000,true));
    for(unsigned i=0;i<16;++i){uint8_t changed[16];std::memcpy(changed,cod1,16);changed[i]^=1;assert(!saved_ghost_cleanup::ValidBranch(changed,0x20000000,false));}
    assert(saved_ghost_cleanup::Connection(1,false,0,2)==1);
    assert(saved_ghost_cleanup::Connection(0,false,0,2)==2);
    assert(saved_ghost_cleanup::Connection(4,false,0,2)==2);
    assert(saved_ghost_cleanup::Connection(1,true,0,2)==2);
    assert(saved_ghost_cleanup::Connection(1,false,1,2)==2);
    assert(saved_ghost_cleanup::Connection(1,false,0,1)==1);
    assert(saved_ghost_cleanup::Connection(1,false,0,0)==0);
}
