#pragma once
namespace qa_dobj_barrier {
struct Result { bool ran = false; unsigned detached = 0; };
// Call only between native-owner capture and the host's configstring mapping.
// Deliberately exposes no tree/block allocator: only DObj detach and one sync.
template<class Has, class Detach, class Sync>
Result Run(bool qaEnabled, bool nativeWorldReady, unsigned limit, Has has, Detach detach, Sync sync)
{
    if (!qaEnabled || !nativeWorldReady || !limit || limit > 2048) return {};
    Result result{true,0};
    for (unsigned e = 0; e < limit; ++e) if (has(e)) { detach(e,true); ++result.detached; }
    sync();
    return result;
}
}
