#include "../src/spawn_ticket.h"
#include <cassert>
#include <initializer_list>
int main() {
    assert(spawn_ticket::FreshMission(0)); // fresh map, even if no bodies existed
    assert(!spawn_ticket::FreshMission(1)); // cold/cross-map save still frees bodies, not kit ownership
    assert(!spawn_ticket::FreshMission(-1)&&!spawn_ticket::FreshMission(2)); // unknown flags never guess a new kit
    for(uint64_t nonce:{uint64_t(1),uint64_t(0x80000000),uint64_t(0x8000000000000000),~uint64_t(0)}) {
        auto s=spawn_ticket::Split(nonce);
        assert(s.a<=0x7fffffff&&s.b<=0x7fffffff&&s.c<=3);
        assert((uint64_t(s.a)|(uint64_t(s.b)<<31)|(uint64_t(s.c)<<62))==nonce);
    }
    uint32_t counter=0,ticket=0;
    assert(spawn_ticket::Next(counter,ticket)&&ticket==1);
    assert(spawn_ticket::Next(counter,ticket)&&ticket==2);
    counter=0x7ffffffe;
    assert(spawn_ticket::Next(counter,ticket)&&ticket==0x7fffffff);
    assert(!spawn_ticket::Next(counter,ticket)&&ticket==0x7fffffff);
}
