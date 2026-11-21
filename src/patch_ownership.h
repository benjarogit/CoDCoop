#pragma once
#include <cstdint>
#include <cstring>
namespace patch_owner {
inline bool JumpTargets(const uint8_t* code, uintptr_t target)
{
    if (!code || code[0] != 0xe9) return false;
    int32_t displacement;
    std::memcpy(&displacement, code + 1, sizeof displacement);
    return reinterpret_cast<uintptr_t>(code) + 5 + displacement == target;
}
inline int ExpectedAfterDeparture(int expected, bool explicitLeave)
{
    if (expected < 1) expected = 1;
    return explicitLeave && expected > 1 ? expected - 1 : expected;
}
}
