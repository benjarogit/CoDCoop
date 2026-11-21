#include "../src/host_rules.h"
#include <cassert>
#include <limits>
#include <string>
int main() {
    using namespace host_rules;
    Values v; assert(Valid(v));
    v.sprintScale = 0; v.sprintMult = -2; v.jumpShot = 1;
    assert(Valid(v)); // native multiplier is deliberately not silently clamped
    v.sprintScale = FLT_MAX; assert(Valid(v));
    v.sprintScale = -0.001f; assert(!Valid(v));
    v.sprintScale = std::numeric_limits<float>::infinity(); assert(!Valid(v));
    v.sprintScale = 1.6f; v.sprintMult = std::numeric_limits<float>::quiet_NaN(); assert(!Valid(v));
    v.sprintMult = 0.5f; v.jumpShot = 2; assert(!Valid(v));
    v.jumpShot = 0; Values copy = v; assert(Same(copy, v));
    copy.sprintScale += 0.01f; assert(!Same(copy, v));
    assert(Newer(1, 0)); assert(!Newer(0, 0)); assert(!Newer(4, 4));
    assert(Newer(5, 4)); assert(!Newer(4, 5));
    assert(Newer(1, 0xffffffffu)); assert(!Newer(0xffffffffu, 1));
    Control control;
    std::string local[] = {"0.800000", "0.25", "0"};
    auto read = [&](const char* name) -> const char* {
        for (unsigned i = 0; i < 3; ++i) if (!strcmp(name, Names[i])) return local[i].c_str();
        assert(false); return "";
    };
    assert(SaveLocal(control, read));
    local[0] = "2.25"; local[1] = "0.75"; local[2] = "1";
    assert(SaveLocal(control, read)); // live updates must not overwrite originals
    unsigned restores = 0;
    auto set = [&](const char* name, const char* value) {
        for (unsigned i = 0; i < 3; ++i) if (!strcmp(name, Names[i])) { local[i] = value; ++restores; }
    };
    control.received = 8;
    assert(RestoreLocal(control, set));
    assert(local[0] == "0.800000" && local[1] == "0.25" && local[2] == "0" && restores == 3);
    assert(!RestoreLocal(control, set) && restores == 3); // leave then shutdown is idempotent
    assert(control.received == 8); // same-endpoint hot reload can reapply accepted rules
    local[2] = std::string(128, '1');
    assert(!SaveLocal(control, read) && !control.saved);
    assert(!RestoreLocal(control, set)); // failed capture never restores truncated data
}
