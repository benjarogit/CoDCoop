#pragma once
#include "mt_epoch.h"
#include <cstdint>
#include <type_traits>
namespace host_body_owner {
constexpr uintptr_t MT_BASE = 0x8f7400;
struct Record {
    uintptr_t tree, xanim;
    uint32_t epoch, index, bytes, nodes;
    int player;
    uint8_t heap;  // 1: bloque propio en el heap (CreateOwnTree); 0: bloque de la memoria de los scripts
};
constexpr unsigned MAX_RECORDS = 64;
struct Store {
    Record records[MAX_RECORDS];
    uint32_t count,freed,forgotten;
    bool Append(const Record& record) { if(count>=MAX_RECORDS)return false;records[count++]=record;return true; }
    void Erase(unsigned index) { for(unsigned i=index+1;i<count;++i)records[i-1]=records[i];if(count)--count; }
};
static_assert(std::is_trivial<Store>::value&&std::is_standard_layout<Store>::value,"shared ownership store must remain POD");
enum class Decision { Forget, Hold, Free };
inline bool Valid(const Record& r) {
    if (r.player < 0 || r.player >= 4 || r.nodes == 0 || r.nodes > 4096) return false;
    if (r.bytes != r.nodes * 8 + 14) return false;
    if (r.heap) return r.tree != 0;
    return r.tree == MT_BASE + r.index * 8 && mt_epoch::MayFree(r.epoch,r.epoch,r.index,r.bytes);
}
inline Decision Evaluate(const Record& r,uint32_t currentEpoch,bool referenced,bool animationValid) {
    if (!r.tree || !r.epoch || r.epoch != currentEpoch) return Decision::Forget;
    if (!Valid(r) || referenced || !animationValid) return Decision::Hold;
    return Decision::Free;
}
template<class Free> inline Decision Release(const Record& r,uint32_t epoch,bool referenced,bool animationValid,Free freeOwned) {
    auto result = Evaluate(r,epoch,referenced,animationValid);
    if (result == Decision::Free) freeOwned(r);
    return result;
}
}
