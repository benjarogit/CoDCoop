#include "../src/patch_ownership.h"
#include <cassert>
#include <cstdio>
int main()
{
    uint8_t code[64]{};
    int32_t relative = 24;
    code[0] = 0xe9;
    std::memcpy(code + 1, &relative, sizeof relative);
    uintptr_t ours = reinterpret_cast<uintptr_t>(code) + 5 + relative;
    assert(patch_owner::JumpTargets(code, ours));
    assert(!patch_owner::JumpTargets(code, ours + 1));
    relative = -4; std::memcpy(code + 1, &relative, sizeof relative);
    assert(patch_owner::JumpTargets(code, reinterpret_cast<uintptr_t>(code) + 1));
    code[0] = 0xe8;
    assert(!patch_owner::JumpTargets(code, reinterpret_cast<uintptr_t>(code) + 1));
    assert(!patch_owner::JumpTargets(nullptr, ours));
    assert(patch_owner::ExpectedAfterDeparture(4, false) == 4); // timeout / reload / clock resync
    assert(patch_owner::ExpectedAfterDeparture(4, true) == 3);  // one reserved peer explicitly leaves
    assert(patch_owner::ExpectedAfterDeparture(2, true) == 1);
    assert(patch_owner::ExpectedAfterDeparture(1, true) == 1);
    assert(patch_owner::ExpectedAfterDeparture(0, true) == 1);
    puts("owned relative jumps and explicit-versus-temporary party departure: PASS");
}
