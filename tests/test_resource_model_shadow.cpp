#include "../src/resource_model_shadow.h"
#include <cassert>
#include <string>
int main(){
    using R=resource_model_shadow::Result;
    std::string actual,shadow;bool approved=true,media=true,bound=false,partial=false;unsigned writes=0;
    const char* wanted="xmodel/weapon_bar";
    auto run=[&](unsigned id=33){return resource_model_shadow::Sync(approved,id,wanted,
        [&](unsigned){return actual.c_str();},[&](unsigned){return shadow.c_str();},
        [&](unsigned,const char*,bool slot){return media&&(!slot||bound);},
        [&](unsigned,const char* name){++writes;shadow=name;bound=!partial;return true;});};
    // Reordered DObj before native reliable CS never publishes a guessed ID.
    assert(run()==R::Wait&&!writes);actual=wanted;
    approved=false;assert(run()==R::Wait&&!writes);approved=true;
    assert(run(0)==R::Wait&&run(256)==R::Wait&&!writes);
    shadow="xmodel/other";assert(run()==R::Conflict&&!writes);shadow.clear();
    media=false;assert(run()==R::Wait&&!writes);media=true;
    assert(run()==R::Ready&&writes==1&&bound&&shadow==wanted);
    assert(run()==R::Ready&&writes==1);
    // Same-name CS with a stale local cache is repaired, never reuses a name.
    bound=false;assert(run()==R::Ready&&writes==2);
    shadow.clear();bound=false;partial=true;
    assert(run()==R::Failed&&writes==3);
    actual="xmodel/other";assert(run()==R::Wait&&writes==3);
}
