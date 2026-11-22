#include "../src/peer_pose.h"
#include <cassert>
#include <limits>
#include <initializer_list>
using namespace peer_pose;
int main(){
    Saved saved{};float origin[3]={-1359.238f,5227.186f,.002634f},angles[3]={51.586304f,137.312622f,0};
    assert(Capture(saved,origin,angles,true)&&saved.valid&&!saved.pending);
    assert(!std::memcmp(saved.origin,origin,12)&&!std::memcmp(saved.angles,angles,12));
    saved.pending=true;saved.commandFloor=1000;
    assert(!CommandReady(saved,0)&&!CommandReady(saved,999)&&CommandReady(saved,1000)&&CommandReady(saved,1001));
    saved.commandFloor=0xfffffff0u;assert(CommandReady(saved,12)&&!CommandReady(saved,0xffffffefu));
    for(float angle:{0.f,90.f,137.312622f,-45.f,359.9f,720.f,-720.f}) {
        auto desired=Delta(angle,0);
        for(uint32_t raw:{0u,1u,0x7fffffffu,0x80000000u,0xffffffffu})
            assert(((raw+Delta(angle,raw))&0xffffu)==desired);
    }
    assert(!Capture(saved,origin,angles,false)&&!saved.valid&&!saved.pending);
    assert(!Capture(saved,nullptr,angles,true));
    float prone[3]={31.39343f,359.98242f,-.09338f};
    assert(Capture(saved,origin,angles,true,prone)&&saved.hasProneBasis);
    assert(!std::memcmp(saved.proneBasis,prone,12)&&saved.proneBasis[0]!=saved.angles[1]);
    assert(Capture(saved,origin,angles,true)&&!saved.hasProneBasis);
    for(float bad:{std::numeric_limits<float>::quiet_NaN(),std::numeric_limits<float>::infinity()}) {
        float invalid[3]={0,bad,0};
        assert(!Capture(saved,invalid,angles,true)&&!saved.valid);
        assert(!Capture(saved,origin,invalid,true)&&!saved.valid);
        assert(!Capture(saved,origin,angles,true,invalid)&&!saved.valid&&!saved.hasProneBasis);
    }
}
