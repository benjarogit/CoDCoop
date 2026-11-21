#include "../src/saved_remote_patch.h"
#include <cassert>
#include <initializer_list>
int main(){
    // Exact shipped CoD1 1.5 / UO 1.51 bytes from the independently decoded
    // connected-client check, not generated from the validator's offsets.
    const uint8_t cod1[]={0x75,0x0d,0x68,0xa0,0x44,0x09,0x20,0xe8,0x05,0xf2,0xfe,0xff,0x83,0xc4,0x04};
    const uint8_t uo151[]={0x75,0x0d,0x68,0x88,0x77,0x09,0x20,0xe8,0xb0,0xe7,0xfe,0xff,0x83,0xc4,0x04};
    assert(saved_remote_patch::Valid(cod1,0x20000000,false));
    assert(saved_remote_patch::Valid(uo151,0x20000000,true));
    assert(!saved_remote_patch::Valid(cod1,0x21000000,false));
    assert(!saved_remote_patch::Valid(uo151,0x20000000,false));
    for(bool uo:{false,true}) {
        uint8_t b[15]={0x75,0x0d,0x68,0,0,0,0,0xe8,0,0,0,0,0x83,0xc4,4};
        uintptr_t base=0x20000000;uint32_t msg=(uint32_t)base+(uo?0x97788:0x944a0);
        int32_t rel=(uo?0x1f330:0x1d080)-saved_remote_patch::Offset(uo)-12;
        std::memcpy(b+3,&msg,4);std::memcpy(b+8,&rel,4);
        assert(saved_remote_patch::Valid(b,base,uo));
        saved_remote_patch::Ownership foreign{};b[0]=0xeb;
        assert(!saved_remote_patch::CanRestore(foreign,b,base,uo));
        saved_remote_patch::Ownership own{(uintptr_t)b,true};
        assert(saved_remote_patch::CanRestore(own,b,base,uo));
        own.branch++;assert(!saved_remote_patch::CanRestore(own,b,base,uo));
        b[8]^=1;assert(!saved_remote_patch::Valid(b,base,uo));b[8]^=1;
        b[3]^=1;assert(!saved_remote_patch::Valid(b,base,uo));b[3]^=1;
        b[0]=0x90;assert(!saved_remote_patch::Valid(b,base,uo));
    }
}
