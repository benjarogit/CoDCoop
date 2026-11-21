#pragma once
#include <cstdint>
namespace native_dobj {
// Both 1.5 and UO1.51: ECX=entity, one caller-cleaned stack argument.
// The native server wrapper forwards clearInfos to DObjFree only after the
// final server/client DObj reference is released. Tree blocks stay Game-owned.
inline void Free(uintptr_t target, int entity, bool clearInfos)
{
    int clear = clearInfos ? 1 : 0;
    asm volatile("push %2\n\tcall *%1\n\tadd $4, %%esp"
                 : "+c"(entity) : "r"(target), "r"(clear) : "eax", "edx", "memory", "cc");
}
}
