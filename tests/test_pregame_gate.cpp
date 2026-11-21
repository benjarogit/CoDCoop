#include "../src/pregame_gate.h"
#include <cassert>
#include <cstdio>
int main()
{
    pregame::Gate g;
    auto poll = [&](uint32_t now, bool ready=true, bool panel=true, bool paused=true, int clock=300, int world=1) {
        return g.Poll(world, 100, 200, ready, panel, paused, clock, now);
    };
    assert(!poll(0, false)); // cgame/UI still loading: no early native action
    assert(!poll(100)); assert(!poll(849)); assert(poll(850));
    assert(!poll(900, true, false, false)); // action cleared both flags before the next engine frame
    assert(!poll(1000, true, false, true)); // native UI reasserted pause only; timer restarts
    assert(!poll(1749, true, false, true));
    assert(poll(1750, true, false, true)); // bounded same-world retry repairs the observed race
    assert(!poll(1800, true, false, false, 350));
    assert(!poll(3000, true, true, true, 350)); // game advanced: never dismiss a subsequent user pause
    assert(!poll(4000, true, true, true, 300, 2)); // new world has its own stable-readiness delay
    assert(poll(4750, true, true, true, 300, 2));
    pregame::Gate limited;
    assert(!limited.Poll(1,100,200,true,true,true,300,0));
    assert(limited.Poll(1,100,200,true,true,true,300,750));
    assert(!limited.Poll(1,100,200,true,false,true,300,751));
    assert(limited.Poll(1,100,200,true,false,true,300,1501));
    assert(!limited.Poll(1,100,200,true,false,true,300,1502));
    assert(limited.Poll(1,100,200,true,false,true,300,2252));
    assert(!limited.Poll(1,100,200,true,false,true,300,3003));
    assert(!limited.Poll(1,100,200,true,false,true,300,3753)); assert(limited.exhausted);
    pregame::Gate wrap;
    assert(!wrap.Poll(1,100,200,true,true,true,300,0xfffffff0));
    assert(wrap.Poll(1,100,200,true,true,true,300,uint32_t(0xfffffff0u+750u)));
    puts("stable native readiness, late-pause retry, world reset, user pause and retry bounds: PASS");
}
