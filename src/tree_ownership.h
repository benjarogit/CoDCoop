#pragma once
#include <cstdint>
namespace tree_owner {
enum class Owner { None, Native, Core };
enum class Release { Forget, Detach, FreeCore };
struct Reference { uintptr_t tree = 0; uint32_t generation = 0; Owner owner = Owner::None; };
inline Release OnRelease(const Reference& reference, uint32_t generation, bool nativeStillOwns, bool treeValid) {
    if (!reference.tree || reference.generation != generation || !treeValid) return Release::Forget;
    if (reference.owner == Owner::Native) return nativeStillOwns ? Release::Detach : Release::Forget;
    if (reference.owner == Owner::Core) return Release::FreeCore;
    return Release::Forget;
}
inline bool CanBorrow(uintptr_t pointer, uint32_t generation, bool nativeStillOwns, bool compatible, bool aliased) {
    return pointer && generation && nativeStillOwns && compatible && !aliased;
}
template<class Free> inline Release ReleaseReference(const Reference& reference, uint32_t generation,
        bool nativeStillOwns, bool treeValid, Free freeCore) {
    Release action = OnRelease(reference, generation, nativeStillOwns, treeValid);
    if (action == Release::FreeCore) freeCore(reference.tree);
    return action;
}

}
