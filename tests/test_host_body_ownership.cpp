#include "../src/host_body_ownership.h"
#include <cassert>
#include <cstring>
int main() {
    using namespace host_body_owner;
    Record r{MT_BASE+8*2048,0x123456,2,2048,9494,1185,1};
    assert(Valid(r));
    assert(Evaluate(r,2,false,true)==Decision::Free);
    assert(Evaluate(r,3,false,true)==Decision::Forget);
    assert(Evaluate(r,2,true,true)==Decision::Hold);
    assert(Evaluate(r,2,false,false)==Decision::Hold);
    unsigned freed=0;auto free=[&](const Record&){++freed;};
    Release(r,3,false,true,free);Release(r,2,true,true,free);Release(r,2,false,false,free);assert(!freed);
    Record hunk=r;hunk.tree=0x301a0000;assert(!Valid(hunk));Release(hunk,2,false,true,free);assert(!freed);
    Record wrong=r;wrong.bytes=9000;assert(!Valid(wrong));Release(wrong,2,false,true,free);assert(!freed);
    Release(r,2,false,true,free);assert(freed==1);
    Store original{};assert(original.Append(r));original.freed=7;
    Store restored{};std::memcpy(&restored,&original,sizeof original);
    assert(restored.count==1&&restored.freed==7&&restored.records[0].epoch==2&&restored.records[0].tree==r.tree);
    restored.Erase(0);assert(!restored.count);
    for (unsigned i = 0; i < MAX_RECORDS; ++i) assert(restored.Append(r));
    assert(!restored.Append(r));
    r={};Release(r,2,false,true,free);assert(freed==1); // forgotten record cannot double-free
}
