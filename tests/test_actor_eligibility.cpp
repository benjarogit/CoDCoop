#include "../src/actor_eligibility.h"
#include <cassert>
int main() {
    using namespace actor_eligibility;
    View player{true,true,true,true,true,false,1};
    assert(Evaluate(player)==State::Eligible);
    player.downed=true;assert(Evaluate(player)==State::Ineligible);
    player.downed=false;player.health=0;assert(Evaluate(player)==State::Ineligible);
    player.health=1;player.connected=false;assert(Evaluate(player)==State::Ineligible);
    player.connected=true;player.remoteReady=false;assert(Evaluate(player)==State::Ineligible);
    player.remoteReady=true;player.ownerReady=false;assert(Evaluate(player)==State::Wait);
    player.ownerReady=true;player.worldReady=false;assert(Evaluate(player)==State::Wait);
    player.worldReady=true;player.authoritative=false;assert(Evaluate(player)==State::Ineligible);
}
