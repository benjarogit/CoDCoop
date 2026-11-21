#include "../src/inventory_preservation.h"
#include <cassert>
using namespace inventory_preservation;
int main() {
    Identity alice{123,2,7,1};Record r{};
    Begin(r,alice);assert(!Commit(r,alice,FRESH,true));
    Issued(r,alice);assert(Commit(r,alice,FRESH,true));
    auto bob=alice;bob.ticket=8;assert(!Commit(r,bob,PRESERVED,true));
    auto world=alice;++world.world;assert(!Commit(r,world,PRESERVED,true));
    auto session=alice;++session.session;assert(!Commit(r,session,PRESERVED,true));
    auto slot=alice;slot.slot=2;assert(!Commit(r,slot,PRESERVED,true));
    Begin(r,alice);assert(!Commit(r,alice,PRESERVED,false));
    assert(Commit(r,alice,PRESERVED,true));assert(!IsFresh(r,alice));
    Begin(r,bob);assert(r.phase==WAIT&&!IsFresh(r,bob));
    assert(!Commit(r,alice,PRESERVED,true));
    Issued(r,bob);Begin(r,bob,true);assert(IsFresh(r,bob));
    Begin(r,world,true);assert(!IsFresh(r,world));
    // A verified save may rebind to a current monotonic ticket/world without
    // restoring old script receipts or re-running a fresh equipment grant.
    Begin(r,bob);assert(Commit(r,bob,PRESERVED,true));
    assert(r.phase==PRESERVED&&!r.freshIssued);
    Identity invalid{};Issued(r,invalid);assert(!Commit(r,invalid,FRESH,true));
    Store persisted{};persisted.slots[1]=r;
    Store reloaded=persisted;assert(reloaded.slots[1].phase==r.phase);
}
