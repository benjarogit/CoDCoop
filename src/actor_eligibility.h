#pragma once
namespace actor_eligibility {
enum class State { Wait, Eligible, Ineligible };
struct View {
    bool worldReady, authoritative, ownerReady, connected, remoteReady, downed;
    int health;
};
inline State Evaluate(const View& view) {
    if(!view.authoritative) return State::Ineligible;
    if(!view.worldReady||!view.ownerReady) return State::Wait;
    if(!view.connected||!view.remoteReady||view.health<=0||view.downed) return State::Ineligible;
    return State::Eligible; // a standing player with exactly1HP remains eligible
}
inline const char* Name(State state) {
    return state==State::Eligible?"ELIGIBLE":state==State::Ineligible?"INELIGIBLE":"WAIT";
}
}
