#include "../src/archive_rules.h"
#include <cassert>
#include <cstring>
int main() {
    struct Native { const char* string; const char* latched; float value; int integer, flags; };
    Native vars[] = {{"1.9", nullptr, 1.9f, 1, 1}, {".55", "1", .55f, 0, 1}, {"1", nullptr, 1, 1, 1}};
    archive_rules::Pair pairs[3];
    for (unsigned i=0;i<3;++i) pairs[i]={&vars[i].string,&vars[i].latched};
    const char* local[3] = {"0.800000", "0.25", "0"};
    archive_rules::Swap swap; swap.Begin(pairs,local);
    for (unsigned i=0;i<3;++i) assert(!strcmp(vars[i].string,local[i]) && vars[i].flags==1);
    assert(!strcmp(vars[1].latched,"0.25") && !vars[0].latched);
    assert(vars[0].value==1.9f && vars[2].integer==1); // prediction remains host-owned
    swap.Begin(pairs,local); // nested writer must not overwrite originals
    swap.End(); swap.End();
    assert(!strcmp(vars[0].string,"1.9") && !strcmp(vars[1].latched,"1") && !strcmp(vars[2].string,"1"));
    swap.Begin(pairs,local);
    // Persistent swap bookkeeping supports restoration after native longjmp,
    // which skips C++ stack destructors; the next Core entry calls End().
    swap.End(); assert(!strcmp(vars[2].string,"1") && vars[2].flags==1);
    archive_rules::Pair empty[3]{};swap.Begin(empty,local);swap.End();
}
