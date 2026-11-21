#include "../src/qa_deferred_models.h"
#include <cassert>
int main() {
    for (uintptr_t pc : {0x3890a,0x1e7aa,0x1e7b5,0x1e7c0,0x1e7df,0x1e7f0}) assert(qa_deferred::DiscardOnly(pc));
    for (uintptr_t pc : {0x2ec98,0x17925,0x48aa2,0,0x38909}) assert(!qa_deferred::DiscardOnly(pc));
    qa_deferred::Ledger ledger;
    assert(!ledger.Approve("xmodel/../bad"));
    auto* a = ledger.Approve("xmodel/test"); assert(a && !a->cached && !a->id);
    assert(ledger.Approve("xmodel/TEST") == a);
    assert(!ledger.Bind(*a, 0)); assert(!ledger.Bind(*a, 256));
    assert(ledger.Bind(*a, 1)); assert(ledger.Bind(*a, 1)); assert(ledger.bindings == 1);
    assert(!ledger.Bind(*a, 2));
    ledger.Approve("xmodel/second");
    assert(!ledger.Bind(ledger.entries[1], 1));
    assert(ledger.Bind(ledger.entries[1], 255)); assert(ledger.bindings == 2);
    // Serializing names and reconstructing approval deliberately forgets IDs;
    // native save old->new remapping creates the new world's actual bindings.
    qa_deferred::Ledger reload;
    for (const auto& entry : ledger.entries) assert(reload.Approve(entry.name));
    assert(reload.entries.size() == 2 && !reload.entries[0].id);
    assert(reload.Bind(reload.entries[0], 9));
    for (unsigned i = 2; i < qa_preload::MAX_NAMES; ++i) assert(ledger.Approve("xmodel/model_" + std::to_string(i)));
    assert(!ledger.Approve("xmodel/overflow"));
}
