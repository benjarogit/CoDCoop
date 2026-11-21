#include "../src/anim_fragments.h"
#include "../src/packet_buffer.h"
#include <cassert>
#include <cstdio>
int main()
{
    animwire::Assembler a;
    std::vector<uint8_t> data(150 * animwire::STATE_BYTES, 7), out;
    animwire::Header h{12,150,50,50,100};
    assert(!a.Feed(h,data.data()+50*24,50*24,out));
    assert(out.empty());
    h.start=0;
    assert(!a.Feed(h,data.data(),50*24,out));
    assert(!a.Feed(h,data.data(),50*24,out)); // duplicate cannot finish early
    h.start=100;
    assert(a.Feed(h,data.data()+100*24,50*24,out));
    assert(out.size()==4+150*24);
    assert(!a.Feed(h,data.data()+100*24,50*24,out)); // old frame ignored
    h={12,150,0,50,101}; assert(!a.Feed(h,data.data(),50*24,out));
    h={12,150,50,50,102}; assert(!a.Feed(h,data.data()+50*24,50*24,out));
    h={12,150,100,50,101}; assert(!a.Feed(h,data.data()+100*24,50*24,out));
    h={12,150,0,50,102}; assert(!a.Feed(h,data.data(),50*24,out));
    h={12,150,100,50,102}; assert(a.Feed(h,data.data()+100*24,50*24,out));
    h={12,4097,0,1,103}; assert(!a.Feed(h,data.data(),24,out));
    h={12,150,149,2,103}; assert(!a.Feed(h,data.data(),48,out));
    h={12,0,0,0,103}; assert(a.Feed(h,nullptr,0,out)); assert(out.size()==4);
    a.Reset(); h={12,0,0,0,1}; assert(a.Feed(h,nullptr,0,out));
    a.Reset();
    for (int e=0; e<64; ++e) {
        h={(uint16_t)e,2,0,1,100}; assert(!a.Feed(h,data.data(),24,out));
    }
    h={100,2,0,1,101}; assert(!a.Feed(h,data.data(),24,out));
    h={100,2,1,1,101}; assert(a.Feed(h,data.data()+24,24,out));
    unsigned char buf[8] = {0,0,0,0,0,0,0,42}; int len=0;
    const char* value="abcdefg";
    assert(packet::Append(buf,7,len,value,7)); assert(len==7);
    assert(!packet::Append(buf,7,len,value,1)); assert(len==-1 && buf[7]==42);
    assert(!packet::Append(buf,7,len,value,1));
    puts("fragmentation, loss, reorder, duplicates, stale frames and bounds: PASS");
}
