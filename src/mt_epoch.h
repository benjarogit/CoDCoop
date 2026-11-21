#pragma once
#include <cstdint>
namespace mt_epoch {
struct Counter {
    uint32_t value = 1;
    uint32_t Reset() { if (!++value) value = 1; return value; }
};
inline bool MayFree(uint32_t allocatedEpoch, uint32_t currentEpoch, unsigned index, unsigned bytes) {
    return allocatedEpoch && allocatedEpoch == currentEpoch && index > 0 && index < 65536 && bytes > 0 && bytes < 65536;
}
}
