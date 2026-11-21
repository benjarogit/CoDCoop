#pragma once
#include <cstddef>
namespace archive_rules {
struct Pair { const char** current{}; const char** latched{}; };
// The native writer reads string/latchedString only. Never call Cvar_Set here:
// it would dirty ARCHIVE again and could cause a write on every engine frame.
struct Swap {
    Pair fields[3]{};
    const char* current[3]{};
    const char* latched[3]{};
    bool active{};
    void Begin(const Pair (&pairs)[3], const char* const (&local)[3]) {
        if (active) return;
        for (unsigned i = 0; i < 3; ++i) {
            fields[i] = pairs[i];
            current[i] = pairs[i].current ? *pairs[i].current : nullptr;
            latched[i] = pairs[i].latched ? *pairs[i].latched : nullptr;
            if (pairs[i].current) *pairs[i].current = local[i];
            if (pairs[i].latched && latched[i]) *pairs[i].latched = local[i];
        }
        active = true;
    }
    void End() {
        if (!active) return;
        for (unsigned i = 0; i < 3; ++i) {
            if (fields[i].current) *fields[i].current = current[i];
            if (fields[i].latched) *fields[i].latched = latched[i];
        }
        active = false;
    }
};
}
