#include "../src/mt_epoch.h"
#include <cassert>
#include <climits>
int main() {
    mt_epoch::Counter epoch;
    unsigned saved=epoch.value;
    assert(mt_epoch::MayFree(saved,epoch.value,123,9494));
    epoch.Reset();
    assert(!mt_epoch::MayFree(saved,epoch.value,123,9494));
    assert(mt_epoch::MayFree(epoch.value,epoch.value,65535,65535));
    assert(!mt_epoch::MayFree(0,epoch.value,123,9494));
    assert(!mt_epoch::MayFree(epoch.value,epoch.value,0,9494));
    assert(!mt_epoch::MayFree(epoch.value,epoch.value,65536,9494));
    assert(!mt_epoch::MayFree(epoch.value,epoch.value,123,0));
    assert(!mt_epoch::MayFree(epoch.value,epoch.value,123,65536));
    epoch.value=UINT32_MAX; assert(epoch.Reset()==1);
    unsigned freed=0,forgotten=0;
    for(unsigned generation=1;generation<10;++generation) {
        if(mt_epoch::MayFree(generation,9,123,9494))++freed;else ++forgotten;
    }
    assert(freed==1&&forgotten==8);
}
