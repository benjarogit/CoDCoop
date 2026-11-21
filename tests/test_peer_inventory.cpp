#include "../src/peer_inventory.h"
#include <cassert>
#include <cstring>
using namespace peer_inventory;
int main() {
    Store store{};
    const reload_delivery::Token a{0x123456789ULL,7}, newer{a.session,8}, stranger{77,7};
    Endpoint alice{1,1100},bob{1,1200};
    auto& r=store.slots[2]; Reserve(r,2,a,alice,"brecourt");
    unsigned char native[BYTES], restored[BYTES];
    for(unsigned i=0;i<BYTES;++i) native[i]=static_cast<unsigned char>(i*7);
    assert(Capture(r,2,a,alice,"brecourt",native,BYTES,31,45));
    int weapon=-1,view=-1; std::memset(restored,0,sizeof restored);
    assert(!Restore(r,1,a,alice,"brecourt",restored,BYTES,weapon,view));
    assert(!Restore(r,2,a,bob,"brecourt",restored,BYTES,weapon,view));
    assert(!Restore(r,2,stranger,alice,"brecourt",restored,BYTES,weapon,view));
    assert(!Restore(r,2,newer,alice,"brecourt",restored,BYTES,weapon,view));
    assert(!Restore(r,2,a,alice,"foy",restored,BYTES,weapon,view));
    assert(!Restore(r,2,a,alice,"brecourt",restored,BYTES-1,weapon,view));
    assert(weapon==-1 && view==-1 && !r.installed);
    // Arrival order cannot give Bob Alice's seat or numeric data.
    assert(Owner(r,2,a.session,alice) && !Owner(r,2,a.session,bob));
    assert(Restore(r,2,a,alice,"brecourt",restored,BYTES,weapon,view));
    assert(!std::memcmp(native,restored,BYTES) && weapon==31 && view==45 && r.installed);
    Store reloaded; std::memcpy(&reloaded,&store,sizeof store);
    assert(Owner(reloaded.slots[2],2,a.session,alice) && reloaded.slots[2].installed);
    // A legitimate unarmed/zero-ammo kit remains present, never a fallback signal.
    std::memset(native,0,sizeof native);
    assert(Capture(r,2,a,alice,"brecourt",native,0x210,0,0));
    assert(Restore(r,2,a,alice,"brecourt",restored,0x210,weapon,view));
    assert(r.installed && weapon==0 && view==0);
    assert(!Capture(r,2,a,alice,"brecourt",native,BYTES+1,0,0));
    Transition(r,newer,"brecourt");
    assert(Owner(r,2,a.session,alice) && !r.captured && !r.installed);
    assert(!Restore(r,2,newer,alice,"brecourt",restored,0x210,weapon,view));
    Transition(r,stranger,"brecourt"); assert(!r.reserved);
    Reserve(r,0,a,alice,"brecourt"); assert(!r.reserved);
}
