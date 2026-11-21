#pragma once
#include <cstdint>
#include <cmath>
#include <cfloat>
#include <cstring>
namespace host_rules {
// r169 Cevar range: sprintSpeedScale [0, FLT_MAX]. Native sprintmult
// has no upstream range; preserve every finite value rather than clamp it.
struct Values { float sprintScale{1.6f}, sprintMult{0.66666669f}; uint32_t jumpShot{}; };
static_assert(sizeof(Values) == 12, "fixed rules wire size");
inline bool Valid(const Values& v) {
    return std::isfinite(v.sprintScale) && v.sprintScale >= 0 && v.sprintScale <= FLT_MAX &&
           std::isfinite(v.sprintMult) && v.jumpShot <= 1;
}
inline bool Same(const Values& a, const Values& b) { return memcmp(&a, &b, sizeof a) == 0; }
inline bool Newer(uint32_t a, uint32_t b) { return a && (!b || int32_t(a-b) > 0); }
inline const char* const Names[] = {"player_sprintSpeedScale", "player_sprintmult", "bg_allowJumpShot"};
struct Control {
    Values host{}, accepted{};
    uint32_t serial{}, received{}, required{}, ack[4]{};
    uint32_t sent[4]{};
    bool known{}, saved{}, invalidWarned{};
    char local[3][128]{};
};
template<class Read> inline bool SaveLocal(Control& control, Read read) {
    if (control.saved) return true;
    for (unsigned i = 0; i < 3; ++i)
        if (strlen(read(Names[i])) >= sizeof control.local[i]) return false;
    for (unsigned i = 0; i < 3; ++i) {
        const char* value = read(Names[i]);
        memcpy(control.local[i], value, strlen(value) + 1);
    }
    control.saved = true;
    return true;
}
template<class Set> inline bool RestoreLocal(Control& control, Set set) {
    if (!control.saved) return false;
    for (unsigned i = 0; i < 3; ++i) set(Names[i], control.local[i]);
    control.saved = false;
    return true;
}
}
