#include "../src/save_provenance.h"
#include <cassert>
#include <cstring>
int main() {
    std::string path;
    for(const char* good:{"save/test.svg","save\\autosave\\bastogne1.svg"}) assert(save_provenance::Path(good,path));
    for(const char* bad:{"../save/a.svg","save/../a.svg","/save/a.svg","save//a.svg","save/a.svg.exe","save/a:bad.svg","save/a.svg;quit","Save/a.svg"}) assert(!save_provenance::Path(bad,path));
    std::string overlong="save/"+std::string(190,'a')+".svg";assert(!save_provenance::Path(overlong.c_str(),path));
    save_provenance::Metadata m{};m.magic=save_provenance::MAGIC;m.version=1;m.session=55;m.engine=2;m.variant=4;
    strcpy(m.map,"brecourt");strcpy(m.sha256,"native-bytes-hash");m.owners[1]={7,123,456};
    assert(save_provenance::Valid(m,2,4,"brecourt","native-bytes-hash",55));
    assert(!save_provenance::Valid(m,2,4,"brecourt","partial-native-bytes",55));
    assert(!save_provenance::Valid(m,2,3,"brecourt","native-bytes-hash",55));
    assert(!save_provenance::Valid(m,1,4,"brecourt","native-bytes-hash",55));
    assert(!save_provenance::Valid(m,2,4,"foy","native-bytes-hash",55));
    assert(!save_provenance::Valid(m,2,4,"brecourt","native-bytes-hash",56));
    peer_inventory::Record alice{},bob{};
    peer_inventory::Reserve(alice,1,{55,10},{123,456},"brecourt",7);
    peer_inventory::Reserve(bob,1,{55,10},{123,456},"brecourt",8);
    assert(save_provenance::Owns(m,1,alice));
    assert(!save_provenance::Owns(m,1,bob)); // even the same endpoint after explicit leave gets a new lease
    assert(!save_provenance::Owns(m,2,alice));
    bob=alice;bob.endpoint.port=999;assert(!save_provenance::Owns(m,1,bob));
    bob=alice;bob.world.session=56;assert(!save_provenance::Owns(m,1,bob));
    std::memset(m.map,'x',sizeof m.map);assert(!save_provenance::Valid(m,2,4,"brecourt","native-bytes-hash",55));
}
