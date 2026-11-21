#include "../src/qa_renderer_preload.h"
#include <cassert>
int main() {
    assert(qa_preload::ValidName("xmodel/o_us_nat_haystack_large(d)"));
    assert(qa_preload::ValidName("xmodel/o_rs_prp_sandbagscurved(d)"));
    std::vector<std::string> names;
    assert(qa_preload::Parse("xmodel/v_rs_air_il2\r\nxmodel/V_RS_AIR_IL2\nxmodel/viewmodel_30cal_z\n", names));
    assert(names.size()==2);
    for (const char* text : {"../xmodel/foo", "xmodel/../foo", "xmodel/foo;quit", "xmodel//foo", "xmodel/", "foo/bar", "xmodel/f oo", "xmodel/ä"})
        assert(!qa_preload::Parse(text,names));
    assert(!qa_preload::Parse("",names));
    assert(!qa_preload::Parse(std::string(qa_preload::MAX_BYTES+1,'a'),names));
    std::string text;
    for (unsigned i=0;i<qa_preload::MAX_NAMES;++i) text += "xmodel/test"+std::to_string(i)+"\n";
    assert(qa_preload::Parse(text,names) && names.size()==qa_preload::MAX_NAMES);
    assert(!qa_preload::Parse(text+"xmodel/overflow\n",names) && names.empty());
}
