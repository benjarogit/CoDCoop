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
    const uint8_t leave[]{1},temporary[]{0},extra[]{1,1};
    assert(ReservedDeparture(r,2,a,alice,leave,1));
    assert(!ReservedDeparture(r,2,newer,alice,leave,1));
    assert(!ReservedDeparture(r,2,stranger,alice,leave,1));
    assert(!ReservedDeparture(r,2,a,bob,leave,1));
    assert(!ReservedDeparture(r,1,a,alice,leave,1));
    assert(!ReservedDeparture(r,2,a,alice,nullptr,0));
    assert(!ReservedDeparture(r,2,a,alice,temporary,1));
    assert(!ReservedDeparture(r,2,a,alice,extra,2));
    auto unleased=r;unleased.lease=0;assert(!ReservedDeparture(unleased,2,a,alice,leave,1));
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
    float origin[3]={12,34,56},angles[3]={1,137,0};
    assert(peer_pose::Capture(r.pose,origin,angles,true));r.pose.pending=true;
    assert(peer_vitals::Capture(r.vitals,550,550,600,true));
    r.savedRole=saved_role::Alive;
    Store poseReload;std::memcpy(&poseReload,&store,sizeof store);
    assert(poseReload.slots[2].pose.valid&&poseReload.slots[2].pose.pending);
    assert(poseReload.slots[2].vitals.valid&&poseReload.slots[2].vitals.health==550);
    Transition(r,newer,"brecourt");
    assert(!r.pose.valid&&!r.pose.pending);
    assert(!r.vitals.valid);
    assert(r.savedRole==saved_role::Unknown);
    assert(Owner(r,2,a.session,alice) && !r.captured && !r.installed);
    assert(!Restore(r,2,newer,alice,"brecourt",restored,0x210,weapon,view));
    Transition(r,stranger,"brecourt"); assert(!r.reserved);
    Reserve(r,0,a,alice,"brecourt"); assert(!r.reserved);
}
