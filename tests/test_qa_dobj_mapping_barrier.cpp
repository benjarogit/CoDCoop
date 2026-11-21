#include "../src/qa_dobj_mapping_barrier.h"
#include <cassert>
int main() {
    unsigned owners[4]={11,22,33,44};
    unsigned maps[4]={1,0,3,0},detaches=0,syncs=0;
    auto has=[&](unsigned e){return maps[e]!=0;};
    auto detach=[&](unsigned e,bool clear){assert(clear);assert(maps[e]);maps[e]=0;++detaches;};
    auto sync=[&]{++syncs;};
    assert(!qa_dobj_barrier::Run(false,true,4,has,detach,sync).ran);
    assert(!qa_dobj_barrier::Run(true,false,4,has,detach,sync).ran);
    assert(!qa_dobj_barrier::Run(true,true,2049,has,detach,sync).ran);
    assert(!detaches&&!syncs&&maps[0]==1&&maps[2]==3);
    auto result=qa_dobj_barrier::Run(true,true,4,has,detach,sync);
    assert(result.ran&&result.detached==2&&detaches==2&&syncs==1);
    assert(!maps[0]&&!maps[2]);
    assert(owners[0]==11&&owners[1]==22&&owners[2]==33&&owners[3]==44);
    // Empty local scene still synchronizes exactly once; no phantom detaches.
    result=qa_dobj_barrier::Run(true,true,4,has,detach,sync);
    assert(result.ran&&!result.detached&&detaches==2&&syncs==2);
}
