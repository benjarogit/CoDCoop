#include "../src/dobj_abi.h"
#include <cassert>
extern "C" { int observedEntity = -1, observedClear = -1; void TestNativeFree(); }
asm(R"(
.intel_syntax noprefix
.globl _TestNativeFree
_TestNativeFree:
    mov dword ptr [_observedEntity], ecx
    mov eax, dword ptr [esp+4]
    mov dword ptr [_observedClear], eax
    mov ecx, 123
    mov edx, 456
    ret
.att_syntax
)");
int main() {
    for (int i = 0; i < 1000; ++i) {
        native_dobj::Free((uintptr_t)&TestNativeFree, i, false);
        assert(observedEntity == i && observedClear == 0);
        native_dobj::Free((uintptr_t)&TestNativeFree, i + 17, true);
        assert(observedEntity == i + 17 && observedClear == 1);
    }
}
