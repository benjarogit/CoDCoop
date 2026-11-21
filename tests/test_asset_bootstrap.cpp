#include "../src/asset_bootstrap.h"
#include <cassert>
#include <limits>

// Deterministic stand-in verifies the callback/atomicity contract. Native
// integration must supply the existing CryptoAPI SHA256 implementation.
static std::array<uint8_t,32> Digest(const uint8_t* data, unsigned size) {
    uint32_t hash = 2166136261u;
    for (unsigned i = 0; i < size; ++i) hash = (hash ^ data[i]) * 16777619u;
    std::array<uint8_t,32> result{};
    for (unsigned i = 0; i < result.size(); ++i) result[i] = (uint8_t)(hash >> ((i % 4) * 8));
    return result;
}
static asset_bootstrap::Description Describe(const std::string& blob, unsigned names, unsigned serial = 5) {
    asset_bootstrap::Description result{};
    result.serial = serial; result.bytes = (uint32_t)blob.size(); result.names = (uint16_t)names;
    result.parts = (uint16_t)((blob.size() + asset_bootstrap::PART_BYTES - 1) / asset_bootstrap::PART_BYTES);
    auto digest = Digest((const uint8_t*)blob.data(), (unsigned)blob.size());
    std::memcpy(result.sha256, digest.data(), digest.size()); std::strcpy(result.map, "brecourt"); return result;
}
static bool Verify(const uint8_t* data, unsigned size, const uint8_t* expected) {
    auto digest = Digest(data,size); return !std::memcmp(digest.data(),expected,digest.size());
}
int main() {
    using namespace asset_bootstrap;
    std::string blob = "unchanged"; uint16_t count = 0;
    assert(Encode({"xmodel/gear_US_helmet", "xmodel/gear_us_helmet", "xmodel/test(d)"},blob,count));
    assert(count == 2 && blob == "xmodel/gear_us_helmet\nxmodel/test(d)\n");
    std::vector<std::string> names{"old-approved"};
    Receiver receiver; auto meta = Describe(blob,count);
    assert(receiver.Start(meta)); assert(!receiver.Finish(names,Verify)); assert(names[0] == "old-approved");
    assert(!receiver.Add(meta.serial,0,(const uint8_t*)blob.data(),(unsigned)blob.size()-1));
    assert(!receiver.Add(meta.serial+1,0,(const uint8_t*)blob.data(),(unsigned)blob.size()));
    assert(!receiver.Add(meta.serial,MAX_PARTS,(const uint8_t*)blob.data(),1));
    assert(receiver.Add(meta.serial,0,(const uint8_t*)blob.data(),(unsigned)blob.size()));
    assert(receiver.Start(meta)); assert(receiver.Ready()); // retry does not discard partial work
    assert(receiver.Finish(names,Verify) && names.size()==2);
    auto conflicting = meta; conflicting.map[0] = 'f'; assert(!receiver.Start(conflicting));
    auto old = meta; --old.serial; assert(!receiver.Start(old));
    auto invalid = meta; invalid.bytes = MAX_BYTES+1; assert(!receiver.Start(invalid));
    invalid = meta; invalid.parts = 65535; assert(!receiver.Start(invalid));
    invalid = meta; std::strcpy(invalid.map,"../other"); assert(!receiver.Start(invalid));
    invalid = meta; invalid.map[20]='x'; assert(!receiver.Start(invalid));
    assert(!Encode({"xmodel/../../evil"},blob,count));
    assert(!Encode({"xmodel/name;quit"},blob,count));
    std::vector<std::string> full;
    for (unsigned i=0;i<MAX_NAMES;++i) {
        std::string name="xmodel/"+std::string(51,'a')+std::to_string(10000+i);
        assert(name.size()==63); full.push_back(name);
    }
    assert(Encode(full,blob,count) && blob.size()==MAX_MODEL_BYTES && count==MAX_NAMES);
    meta=Describe(blob,count,10); assert(receiver.Start(meta));
    for (unsigned part=meta.parts;part-->0;) {
        auto* bytes=(const uint8_t*)blob.data()+part*PART_BYTES;
        assert(receiver.Add(meta.serial,part,bytes,PART_BYTES));
        assert(receiver.Add(meta.serial,part,bytes,PART_BYTES));
    }
    assert(receiver.Ready() && receiver.Finish(names,Verify) && names.size()==MAX_NAMES);
    full.push_back("xmodel/another"); assert(!Encode(full,blob,count));
    receiver.Reset(); assert(!receiver.Ready());
    blob="xmodel/one\n"; meta=Describe(blob,1,11); assert(receiver.Start(meta));
    std::string corrupt=blob; corrupt[7]='z';
    assert(receiver.Add(meta.serial,0,(const uint8_t*)corrupt.data(),(unsigned)corrupt.size()));
    names={"previous"}; assert(!receiver.Finish(names,Verify) && names[0]=="previous" && !receiver.Ready());
    assert(receiver.Start(meta));
    assert(receiver.Add(meta.serial,0,(const uint8_t*)blob.data(),(unsigned)blob.size()));
    assert(receiver.Finish(names,Verify) && names[0]=="xmodel/one");
    receiver.Reset(); meta=Describe("xmodel/ONE\n",1,12); assert(receiver.Start(meta));
    std::string noncanonical="xmodel/ONE\n";
    assert(receiver.Add(meta.serial,0,(const uint8_t*)noncanonical.data(),(unsigned)noncanonical.size()));
    assert(!receiver.Finish(names,Verify)); // digest alone must not authorize ambiguous/unsafe names

    Resources resources{{"xmodel/one","xmodel/two"},{{1,"m1garand",true},{2,"colt",false}}};
    assert(EncodeResources(resources,blob,count) && count==4);
    assert(blob=="codcoop-assets-1\nm\txmodel/one\nm\txmodel/two\nw\t001\t1\tm1garand\nw\t002\t0\tcolt\n");
    Resources decoded;
    assert(DecodeResources((const uint8_t*)blob.data(),unsigned(blob.size()),count,decoded));
    auto readName=[&](unsigned i){return resources.weapons.at(i-1).name;};
    auto registered=[&](unsigned i){return resources.weapons.at(i-1).registered;};
    assert(MatchWeapons(decoded,2,128,readName,registered));
    assert(!MatchWeapons(decoded,1,128,readName,registered));
    assert(!MatchWeapons(decoded,2,2,readName,registered));
    assert(!MatchWeapons(decoded,2,129,readName,registered));
    auto differentName=[&](unsigned i){return resources.weapons.at(2-i).name;};
    assert(!MatchWeapons(decoded,2,128,differentName,registered)); // same union, different native indices
    assert(!MatchWeapons(decoded,2,128,readName,[](unsigned){return true;}));
    auto wrong=resources; wrong.weapons[1].index=3; assert(!EncodeResources(wrong,blob,count));
    wrong=resources; wrong.weapons[1].name="m1garand"; assert(!EncodeResources(wrong,blob,count));
    for(const char* invalidName:{"M1garand","../colt","colt;quit","colt\n","","none"}) {
        wrong=resources; wrong.weapons[1].name=invalidName; assert(!EncodeResources(wrong,blob,count));
    }
    assert(EncodeResources(resources,blob,count));
    auto noncanonicalResources=blob; noncanonicalResources.replace(noncanonicalResources.find("001"),3,"01");
    assert(!DecodeResources((const uint8_t*)noncanonicalResources.data(),unsigned(noncanonicalResources.size()),count,decoded));
    assert(!DecodeResources((const uint8_t*)blob.data(),unsigned(blob.size()),count-1,decoded));

    resources.models=std::vector<std::string>(full.begin(),full.begin()+MAX_NAMES);
    resources.weapons.clear();
    for(unsigned i=1;i<=MAX_WEAPONS;++i) resources.weapons.push_back({uint8_t(i),"weapon_"+std::to_string(i),i%2==0});
    assert(EncodeResources(resources,blob,count) && blob.size()>MAX_MODEL_BYTES && count==MAX_ENTRIES);
    receiver.Reset(); meta=Describe(blob,count,20); assert(receiver.Start(meta));
    for(unsigned part=meta.parts;part-->0;) {
        unsigned offset=part*PART_BYTES, bytes=std::min(PART_BYTES,meta.bytes-offset);
        assert(receiver.Add(meta.serial,part,(const uint8_t*)blob.data()+offset,bytes));
    }
    assert(receiver.FinishResources(decoded,Verify));
    assert(decoded.models.size()==MAX_NAMES && decoded.weapons.size()==MAX_WEAPONS);
    assert(decoded.weapons[126].index==127 && decoded.weapons[126].name=="weapon_127");
    resources.weapons.push_back({128,"extra",true}); assert(!EncodeResources(resources,blob,count));
}
