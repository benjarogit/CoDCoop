#include "../src/peer_vitals.h"
#include <cassert>
#include <climits>
using namespace peer_vitals;
int main(){
    Saved saved{};
    assert(Capture(saved,550,550,600,true)&&saved.health==550&&saved.maxHealth==600);
    assert(Capture(saved,1,1,600,true)&&saved.health==1); // standing1HP is not downed
    assert(!Capture(saved,1,1,600,false)&&!saved.valid); // actual downed/scripted role
    assert(!Capture(saved,550,600,600,true)&&!saved.valid); // incoherent native fields
    assert(!Capture(saved,0,0,600,true)&&!saved.valid);
    assert(!Capture(saved,-1,-1,600,true)&&!saved.valid);
    assert(Capture(saved,601,601,600,true)); // preserve coherent host-authored overheal
    assert(!Capture(saved,550,550,0,true)&&!saved.valid);
    assert(Capture(saved,12000,12000,12000,true)); // original Gimp preset
    assert(Capture(saved,INT_MAX,INT_MAX,INT_MAX,true)); // no invented health clamp
}
