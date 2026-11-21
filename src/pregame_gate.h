#pragma once
#include <cstdint>
namespace pregame {
struct Gate {
    int world{}, lastClock{}, attemptClock{};
    uintptr_t cgame{}, ui{};
    uint32_t since{}, firstAttempt{}, lastAttempt{};
    unsigned attempts{};
    bool initialized{}, tracking{}, completed{}, exhausted{};
    bool Poll(int id, uintptr_t cg, uintptr_t menu, bool ready, bool panel, bool paused, int clock, uint32_t now)
    {
        if (!initialized || id != world || cg != cgame || menu != ui || clock < lastClock) {
            *this = Gate{};
            initialized = true; world = id; cgame = cg; ui = menu;
        }
        lastClock = clock;
        if (attempts && clock != attemptClock) completed = true;
        if (completed) return false;
        if (attempts && paused && clock == attemptClock && now - firstAttempt > 5000) exhausted = true;
        bool retry = attempts && paused && clock == attemptClock && now - firstAttempt <= 5000;
        if (!ready || (!panel && !retry) || exhausted) { tracking = false; return false; }
        if (!tracking) { since = now; tracking = true; }
        if (now - since < 750 || (attempts && now - lastAttempt < 750)) return false;
        if (attempts >= 3) { exhausted = true; return false; }
        if (!attempts) { firstAttempt = now; attemptClock = clock; }
        ++attempts; lastAttempt = now; tracking = false;
        return true;
    }
};
}
