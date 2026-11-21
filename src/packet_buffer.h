#pragma once
#include <cstddef>
#include <cstring>
namespace packet {
// Negative length is a failed packet, never a truncated valid message.
inline bool Append(void* buffer, int capacity, int& length, const void* source, int size)
{
    if (length < 0) return false;
    if (size < 0 || length > capacity || size > capacity - length) { length = -1; return false; }
    if (size) memcpy((char*)buffer + length, source, (size_t)size);
    length += size;
    return true;
}
}
