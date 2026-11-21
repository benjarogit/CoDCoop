#include "../src/tree_ownership.h"
#include <cassert>
#include <initializer_list>
int main() {
    using namespace tree_owner;
    Reference native{0x1234,7,Owner::Native}, core{0x5678,7,Owner::Core};
    assert(OnRelease(native,7,true,true)==Release::Detach);
    assert(OnRelease(native,7,false,true)==Release::Forget);
    assert(OnRelease(native,8,true,true)==Release::Forget);
    assert(OnRelease(native,7,true,false)==Release::Forget);
    assert(OnRelease(core,7,false,true)==Release::FreeCore);
    assert(OnRelease(core,8,false,true)==Release::Forget);
    assert(OnRelease(core,7,false,false)==Release::Forget);
    for (unsigned world=0;world<20;++world) for (bool owns:{false,true}) for(bool valid:{false,true})
        assert(OnRelease(native,world,owns,valid)!=Release::FreeCore);
    unsigned frees = 0;
    auto free = [&](uintptr_t) { ++frees; };
    ReleaseReference(native,7,true,true,free);
    ReleaseReference(native,8,true,true,free);
    ReleaseReference(native,7,false,true,free);
    ReleaseReference(core,8,false,true,free);
    assert(frees == 0); // native and stale references must never reach MT_Free
    ReleaseReference(core,7,false,true,free); assert(frees == 1);
    assert(CanBorrow(0x1234,7,true,true,false));
    assert(!CanBorrow(0,7,true,true,false)); assert(!CanBorrow(0x1234,0,true,true,false));
    assert(!CanBorrow(0x1234,7,false,true,false)); assert(!CanBorrow(0x1234,7,true,false,false));
    assert(!CanBorrow(0x1234,7,true,true,true));
}
