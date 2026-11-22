#include "../src/first_use_resources.h"
#include <array>
#include <cassert>
#include <cstdio>
#include <fstream>
#include <set>
#include <string>
#include <vector>
using namespace first_use_resources;
constexpr uint32_t PURE[]={0x3890a,0x1e7aa,0x1e7b5,0x1e7c0,0x1e7df,0x1e7f0};
constexpr uint32_t BINDING[]={0x17925,0x1dc30,0x1e8b1,0x2141e,0x27ccf,0x27e7f,0x28068,0x2ec98,0x34324,0x3600d,0x44cc3,0x48a76,0x48aa2,0x62658};
Context context(){Context c{};c.session=1234;c.world=7;c.nativeInit=9;c.gameEpoch=3;c.rendererEpoch=4;c.authority=Authority::Host;std::strcpy(c.map,"noville");return c;}
struct Code {
 std::vector<uint8_t> image;CodeView view;
 Code(uint32_t base=0x20000000):image(DIRTY_RVA+4096){
  view={image.data(),image.size(),base,{},0};std::memcpy(view.diskSHA,GAME_SHA,32);
  const uint8_t prologue[]={0x80,0x3b,0,0x75,3,0x33,0xc0,0xc3};std::memcpy(image.data()+MODEL_INDEX_RVA,prologue,8);
  std::vector<const Pattern*> patterns{&PublicationPattern()};for(auto ret:PURE)patterns.push_back(PurePattern(ret));
  for(auto ret:BINDING)patterns.push_back(BindingPattern(ret));
  std::set<unsigned> relocations;
  for(auto p:patterns){std::memcpy(image.data()+p->start,p->bytes,p->length);for(unsigned i=0;i<p->relocCount;++i)relocations.insert(p->start+p->relocs[i]);}
  for(unsigned rva:relocations){uint32_t old=0;std::memcpy(&old,image.data()+rva,4);uint32_t value=base+(old-0x20000000);std::memcpy(image.data()+rva,&value,4);}
 }
 void hook(uint32_t target){view.ownedHook=target;image[MODEL_INDEX_RVA]=0xe9;int32_t rel=int32_t(target-(view.base+MODEL_INDEX_RVA+5));std::memcpy(image.data()+MODEL_INDEX_RVA+1,&rel,4);for(unsigned i=5;i<8;++i)image[MODEL_INDEX_RVA+i]=0x90;}
};
struct Native {
 using Table=std::array<std::array<char,64>,256>;
 Table server{},client{},shadow{},slotCache{};std::set<std::string> names,render;
 static void put(Table&t,unsigned id,const char*n){assert(id&&id<=255);t[id]={};assert(std::strlen(n)<64);std::strcpy(t[id].data(),n);}
 static auto reader(const Table&t){return [&t](unsigned id,char(&out)[64]){if(!id||id>255)return false;std::memcpy(out,t[id].data(),64);return true;};}
 auto cache(){return [this](const char*n,const Context&){return names.count(n)!=0;};}
 auto renderer(){return [this](const char*n,const Context&){return render.count(n)!=0;};}
 auto bound(){return [this](unsigned id,const char*n,const Context&){return id&&id<=255&&!std::strcmp(slotCache[id].data(),n)&&names.count(n);};}
 void publish(const Decision&d,const char*n){put(slotCache,d.id,n);put(server,d.id,n);}
};
unsigned approved(Store&s,const Context&c,Native&n,const char*name,uint16_t source=ConfirmedKit){
 unsigned i=Approve(s,c,name,source);assert(i);n.names.insert(s.entries[i-1].name);n.render.insert(s.entries[i-1].name);
 assert(CacheNative(s,c,i,n.cache()));assert(CacheRenderer(s,c,i,n.renderer()));return i;
}
Decision actual(Store&s,const Context&c,Code&code,Native&n,const char*name,Use use=Use::CoreHeldGun,uint32_t ret=0,bool loading=false){
 return Actual(s,c,code.view,use,ret,name,loading,Native::reader(n.server),n.cache(),n.bound());
}
Decision bind(Store&s,const Context&c,Code&code,Native&n,const char*name){
 auto d=actual(s,c,code,n,name);assert(d.action==Action::BIND_CACHED_EMPTY);n.publish(d,name);
 assert(Commit(s,c,d,Native::reader(n.server),n.bound()));int out=-1;assert(NativeValue(s,c,d,false,out)&&out==d.id);return d;
}
void fingerprints(){
 for(uint32_t base:{0x20000000u,0x51000000u}){
  Code code(base);assert(NativeLayout(code.view));for(auto ret:PURE)assert(FingerprintPure(code.view,ret));for(auto ret:BINDING)assert(FingerprintBinding(code.view,ret));
  assert(!FingerprintPure(code.view,0x38909));assert(!FingerprintPure(code.view,0x2ec98));
  for(auto ret:PURE){auto p=PurePattern(ret);code.image[p->start]^=1;assert(!FingerprintPure(code.view,ret));code.image[p->start]^=1;}
  for(auto ret:BINDING){auto p=BindingPattern(ret);code.image[p->start]^=1;assert(!FingerprintBinding(code.view,ret));code.image[p->start]^=1;}
  code.view.diskSHA[0]^=1;assert(!NativeLayout(code.view));code.view.diskSHA[0]^=1;
  code.image[PublicationPattern().start+12]^=1;assert(!NativeLayout(code.view));code.image[PublicationPattern().start+12]^=1;
  auto size=code.view.size;code.view.size=MODEL_INDEX_RVA+4;assert(!NativeLayout(code.view));code.view.size=size;
  code.hook(0x61002000);assert(NativeLayout(code.view));for(auto ret:PURE)assert(FingerprintPure(code.view,ret));
  code.view.ownedHook++;assert(!NativeLayout(code.view));code.view.ownedHook--;code.image[MODEL_INDEX_RVA+7]=0;assert(!NativeLayout(code.view));
 }
 unsigned count=0;for(uint32_t ret:{0x17925,0x1dc30,0x1e8b1,0x2141e,0x27ccf,0x27e7f,0x28068,0x2ec98,0x34324,0x3600d,0x44cc3,0x48a76,0x48aa2,0x62658}){assert(BindingSite(ret));++count;}
 assert(count==14);for(auto ret:PURE)assert(!BindingSite(ret));
}
void pure_and_bounds(){
 Store s{};auto c=context();assert(Begin(s,c));Code code;Native n;
 for(unsigned j=0;j<6;++j){char name[64];std::snprintf(name,sizeof name,"xmodel/pure_%u",j);n.names.insert(name);
  auto d=Pure(s,c,code.view,PURE[j],name,true,n.cache());assert(d.action==Action::DEFERRED_ZERO);int value=99;
  assert(NativeValue(s,c,d,true,value)&&value==0);assert(!NativeValue(s,c,d,false,value));assert(!s.entries[d.entry-1].id);
  auto notloading=Pure(s,c,code.view,PURE[j],name,false,n.cache());assert(notloading.action==Action::NORMAL_NATIVE);
 }
 auto missing=Pure(s,c,code.view,PURE[0],"xmodel/not_cached",true,n.cache());assert(missing.action==Action::NORMAL_NATIVE&&s.count==6);
 auto foreign=Pure(s,c,code.view,0x48aa2,"xmodel/pure_0",true,n.cache());assert(foreign.action==Action::NORMAL_NATIVE);
 unsigned old=Find(s,"XMODEL/PURE_0");assert(old);auto revision=s.revision;
 assert(Approve(s,c,"xmodel/PURE_0",AuthoredWorld)==old&&s.count==6&&s.revision==revision);
 assert(!Approve(s,c,"xmodel/new",0)&&!Approve(s,c,"xmodel/new",0x8000));
 char noNul[64];std::memset(noNul,'a',64);assert(!Approve(s,c,noNul,ConfirmedKit));
 for(auto name:{"xmodel/../bad","xmodel/a//b","xmodel/x;quit","xmodel/end/","../model","xmodel/a.b"})assert(!Approve(s,c,name,ConfirmedKit));
 assert(Approve(s,c,"xmodel/legitimate(part)",AuthoredWorld));
 while(s.count<MAX_NAMES){char name[64];std::snprintf(name,sizeof name,"xmodel/fill_%u",s.count);assert(Approve(s,c,name,AuthoredWorld));}
 assert(!Approve(s,c,"xmodel/overflow",AuthoredWorld)&&s.count==MAX_NAMES);
 n.names.insert("xmodel/overflow");assert(Pure(s,c,code.view,PURE[0],"xmodel/overflow",true,n.cache()).action==Action::NORMAL_NATIVE);
 auto damaged=s;damaged.count=513;assert(!Scope(damaged,c)&&!Complete(damaged,c));
 damaged=s;damaged.weaponCount=128;assert(!Scope(damaged,c));damaged=s;damaged.boundCount=256;assert(!Scope(damaged,c));
}
void first_use_transaction(){
 Store s{};auto c=context();assert(Begin(s,c));Code code;Native n;
 approved(s,c,n,"xmodel/held_gun");Native::put(n.server,1,"xmodel/native_npc");
 auto d=actual(s,c,code,n,"xmodel/held_gun");assert(d.action==Action::BIND_CACHED_EMPTY&&d.id==2&&s.boundCount==0);
 int value=99;assert(!NativeValue(s,c,d,false,value));assert(actual(s,c,code,n,"xmodel/held_gun").action==Action::WAIT);
 auto bad=d;bad.transaction++;assert(!Commit(s,c,bad,Native::reader(n.server),n.bound())&&s.pending.active);
 n.publish(d,"xmodel/held_gun");assert(Commit(s,c,d,Native::reader(n.server),n.bound()));assert(s.boundCount==1);
 assert(NativeValue(s,c,d,false,value)&&value==2);assert(!Commit(s,c,d,Native::reader(n.server),n.bound()));
 assert(actual(s,c,code,n,"xmodel/held_gun").action==Action::BOUND&&s.boundCount==1);
 auto unknown=actual(s,c,code,n,"xmodel/unapproved_late");assert(unknown.action==Action::NORMAL_NATIVE&&!NativeValue(s,c,unknown,false,value));
 assert(actual(s,c,code,n,"xmodel/held_gun",Use::SaveRemap,0x2ec98).action==Action::NORMAL_NATIVE);
 assert(actual(s,c,code,n,"xmodel/held_gun",Use::GameActual,0x48a76,true).action==Action::NORMAL_NATIVE);
 assert(actual(s,c,code,n,"xmodel/held_gun",Use::GameActual,0x3890a).action==Action::NORMAL_NATIVE);
 assert(!ObserveNativeBinding(s,c,"xmodel/wrong",2,Native::reader(n.server),n.bound()));
 auto copy=s;assert(!Begin(copy,Context{}));auto changed=c;changed.rendererEpoch++;assert(!Begin(copy,changed));assert(copy.boundCount==1);
 changed=c;changed.gameEpoch++;assert(!Begin(copy,changed));changed=c;changed.nativeInit++;assert(!Begin(copy,changed));
 auto wrong=c;wrong.world++;assert(!Commit(s,wrong,d,Native::reader(n.server),n.bound()));assert(!NativeValue(s,wrong,d,false,value));
 // Native slot disappears: it is never reclaimed from our own bookkeeping.
 Native::put(n.server,2,"");auto stale=actual(s,c,code,n,"xmodel/held_gun");assert(stale.action==Action::STOP&&s.failed);
 assert(!Begin(s,c));wrong=c;wrong.world++;assert(Begin(s,wrong)&&s.boundCount==0);
 approved(s,wrong,n,"xmodel/held_gun");auto fresh=actual(s,wrong,code,n,"xmodel/held_gun");assert(fresh.action==Action::BIND_CACHED_EMPTY&&fresh.transaction==d.transaction);
 // Same transaction number after a new world cannot replay the old decision.
 assert(!Commit(s,wrong,d,Native::reader(n.server),n.bound()));PublicationFailed(s,wrong,d);assert(!s.failed);
 PublicationFailed(s,wrong,fresh);assert(s.failed);
}
void capacity_and_native_binding(){
 Store s{};auto c=context();assert(Begin(s,c));Code code;Native n;approved(s,c,n,"xmodel/new");
 for(unsigned i=1;i<=255;++i){char name[64];std::snprintf(name,sizeof name,"xmodel/native_%u",i);Native::put(n.server,i,name);}
 auto full=actual(s,c,code,n,"xmodel/new");assert(full.action==Action::NORMAL_NATIVE&&full.reason==Reason::Capacity&&!s.pending.active);
 int value=77;assert(!NativeValue(s,c,full,false,value)&&value==77);
 Native::put(n.server,255,"xmodel/new");Native::put(n.slotCache,255,"xmodel/new");
 assert(ObserveNativeBinding(s,c,"xmodel/new",255,Native::reader(n.server),n.bound()));assert(s.entries[0].id==255);
 Native::put(n.server,254,"xmodel/new");assert(actual(s,c,code,n,"xmodel/new").action==Action::STOP&&s.failed);
 Store bad{};assert(Begin(bad,c));approved(bad,c,n,"xmodel/new");auto before=bad;before.version=42;assert(!Begin(before,c));
 n.names.erase("xmodel/new");assert(actual(bad,c,code,n,"xmodel/new").action==Action::STOP);
}
void contract_and_peer_order(){
 Store s{};auto c=context();assert(Begin(s,c));Code code;Native n;
 unsigned gun=approved(s,c,n,"xmodel/gun");uint16_t media[5]={(uint16_t)gun,0,(uint16_t)gun,0,0},none[5]={};
 assert(DefineWeapon(s,c,1,"mg30cal",true,2,media,true));assert(!Complete(s,c));
 assert(DefineWeapon(s,c,2,"mg30cal_de",false,1,none,false));assert(!Complete(s,c));
 assert(!DefineWeapon(s,c,2,"mg30cal_de",true,1,none,false));
 assert(DefineWeapon(s,c,2,"mg30cal_de",true,1,media,true));assert(!Complete(s,c));
 assert(!ObserveDefinitionCount(s,c,2,[](auto&){return 94;}));assert(!ObserveDefinitionCount(s,c,128,[](auto&){return 128;}));
 assert(ObserveDefinitionCount(s,c,2,[](auto&){return 2;}));assert(!ObserveDefinitionCount(s,c,1,[](auto&){return 1;}));assert(Complete(s,c));
 auto missing=s;assert(ObserveDefinitionCount(missing,c,94,[](auto&){return 94;})&&!Complete(missing,c));
 assert(!DefineWeapon(s,c,2,"different",true,1,media,true));assert(!DefineWeapon(s,c,2,"mg30cal_de",false,1,media,true));
 assert(!DefineWeapon(s,c,3,"mg30cal",true,0,media,true));
 unsigned exportedModels=0,exportedWeapons=0;
 assert(CaptureContract(s,c,[&](const char*){++exportedModels;return true;},[&](unsigned i,const Weapon&w){assert(i==++exportedWeapons&&w.mediaComplete&&w.alt);return true;}));
 assert(exportedModels==1&&exportedWeapons==2);
 assert(!CaptureContract(s,c,[](auto){return false;},[](auto,auto){return true;}));
 uint8_t sha[32]={1},sha2[32]={2},empty[32]={};
 assert(!Seal(s,c,1,sha,[](auto&,auto&,auto&){return false;}));assert(!Seal(s,c,1,empty,[](auto&,auto&,auto&){return true;}));
 assert(Seal(s,c,1,sha,[](auto&,auto&,auto&){return true;}));
 assert(!PeerReady(s,c,1,1,sha,[](auto&,auto&){return false;}));assert(!PeerReady(s,c,1,1,sha2,[](auto&,auto&){return true;}));
 assert(PeerReady(s,c,1,1,sha,[](auto&,auto&){return true;}));assert(PeerReady(s,c,2,1,sha,[](auto&,auto&){return true;}));
 auto d=bind(s,c,code,n,"xmodel/gun");
 Store receiver{};auto rc=c;rc.authority=Authority::Peer;assert(Begin(receiver,rc));
 assert(approved(receiver,rc,n,"xmodel/gun",PeerContract)==gun);
 assert(DefineWeapon(receiver,rc,1,"mg30cal",true,2,media,true)&&DefineWeapon(receiver,rc,2,"mg30cal_de",true,1,media,true));
 assert(ObserveDefinitionCount(receiver,rc,2,[](auto&){return 2;}));
 assert(Seal(receiver,rc,1,sha,[](auto&,auto&,auto&){return true;}));
 assert(PeerReady(receiver,rc,1,1,sha,[](auto&,auto&){return true;})&&PeerReady(receiver,rc,2,1,sha,[](auto&,auto&){return true;}));
 // Local bootstrap order deliberately disagrees: its gun was Native ID9.
 Native::put(n.shadow,9,"xmodel/gun");Native::put(n.slotCache,9,"xmodel/gun");
 assert(actual(receiver,rc,code,n,"xmodel/gun",Use::GameActual,0x48a76,true).action==Action::NORMAL_NATIVE);
 assert(!ObserveNativeBinding(receiver,rc,"xmodel/gun",9,Native::reader(n.shadow),n.bound()));assert(!receiver.entries[gun-1].id);
 assert(!ArmPeerMap(receiver,rc,[](auto&,auto&){return false;}));
 assert(!AdoptPeerBinding(receiver,rc,1,1,d.id,"xmodel/gun",Native::reader(n.client),Native::reader(n.shadow),n.bound()));
 assert(ArmPeerMap(receiver,rc,[](auto&,auto&){return true;}));
 auto adopt=[&](unsigned serial,unsigned id,const char*name){return AdoptPeerBinding(receiver,rc,1,serial,id,name,Native::reader(n.client),Native::reader(n.shadow),n.bound());};
 auto gate=[&](unsigned peer,uint32_t serial,unsigned id,const char*name){return PeerDObj(receiver,rc,peer,serial,id,name,Native::reader(n.client),Native::reader(n.shadow),n.renderer());};
 assert(!gate(1,1,d.id,"xmodel/gun"));Native::put(n.client,d.id,"xmodel/gun");assert(!gate(1,1,d.id,"xmodel/gun"));
 Native::put(n.shadow,d.id,"xmodel/old_npc");assert(!adopt(1,d.id,"xmodel/gun")&&!gate(1,1,d.id,"xmodel/gun"));Native::put(n.shadow,d.id,"xmodel/gun");
 assert(adopt(1,d.id,"xmodel/gun")&&receiver.entries[gun-1].id==d.id&&d.id!=9);assert(gate(1,1,d.id,"xmodel/gun"));
 assert(!gate(1,2,d.id,"xmodel/gun")&&!gate(1,1,256,"xmodel/gun"));assert(!gate(1,1,d.id,"xmodel/wrong"));
 assert(PeerWeapon(s,c,1,1,1)&&!PeerWeapon(s,c,1,2,1));
 n.render.erase("xmodel/gun");assert(!gate(1,1,d.id,"xmodel/gun"));assert(!CacheRenderer(receiver,rc,gun,n.renderer())&&!Complete(receiver,rc));
 n.render.insert("xmodel/gun");assert(CacheRenderer(receiver,rc,gun,n.renderer()));
 // New approved assets do not kick/reset previous approved peers or bindings.
 unsigned addition=approved(s,c,n,"xmodel/new_hat",AuthoredWorld);auto hat=bind(s,c,code,n,"xmodel/new_hat");
 assert(approved(receiver,rc,n,"xmodel/new_hat",PeerContract)==addition);
 Native::put(n.client,hat.id,"xmodel/new_hat");Native::put(n.shadow,hat.id,"xmodel/new_hat");
 assert(gate(1,1,d.id,"xmodel/gun")&&!gate(1,1,hat.id,"xmodel/new_hat"));
 assert(!PeerReady(s,c,1,1,sha,[](auto&,auto&){return true;}));
 assert(!Seal(s,c,1,sha,[](auto&,auto&,auto&){return true;}));assert(Seal(s,c,2,sha2,[](auto&,auto&,auto&){return true;}));
 assert(!adopt(1,hat.id,"xmodel/new_hat"));
 assert(Seal(receiver,rc,2,sha2,[](auto&,auto&,auto&){return true;}));
 assert(PeerReady(receiver,rc,1,2,sha2,[](auto&,auto&){return true;}));assert(adopt(2,hat.id,"xmodel/new_hat"));assert(gate(1,2,hat.id,"xmodel/new_hat")&&!gate(1,1,hat.id,"xmodel/new_hat"));
 assert(gate(2,1,d.id,"xmodel/gun")&&!gate(2,1,hat.id,"xmodel/new_hat"));
 assert(s.entries[gun-1].id==d.id&&s.entries[addition-1].id==hat.id&&s.boundCount==2);
 auto stale=rc;stale.world++;assert(!PeerDObj(receiver,stale,1,2,d.id,"xmodel/gun",Native::reader(n.client),Native::reader(n.shadow),n.renderer()));
 auto unauthorized=receiver;assert(actual(unauthorized,rc,code,n,"xmodel/gun").action==Action::STOP&&!unauthorized.pending.active);
 auto corrupted=s;corrupted.weapons[1].alt=255;assert(!Complete(corrupted,c));
 auto old=s;old.transactionCounter=std::numeric_limits<uint64_t>::max();approved(old,c,n,"xmodel/third");assert(actual(old,c,code,n,"xmodel/third").action==Action::STOP);
 auto revision=s;revision.revision=std::numeric_limits<uint64_t>::max();assert(!Approve(revision,c,"xmodel/counter_wrap",AuthoredWorld)&&revision.failed);
 assert(SaveApproval(true,true,true)==Reason::None);assert(SaveApproval(false,true,true)==Reason::SaveUnresolved);assert(SaveApproval(true,false,true)==Reason::SaveUnresolved);assert(SaveApproval(true,true,false)==Reason::SaveUnresolved);
}
int main(int argc,char**argv){
 if(argc==2){std::ifstream f(argv[1],std::ios::binary);assert(f);std::vector<uint8_t>b((std::istreambuf_iterator<char>(f)),{});CodeView v{b.data(),b.size(),0x20000000,{},0};std::memcpy(v.diskSHA,GAME_SHA,32);assert(NativeLayout(v));for(auto ret:PURE)assert(FingerprintPure(v,ret));for(auto ret:BINDING)assert(FingerprintBinding(v,ret));std::puts("actual pinned native20caller code map PASS");return 0;}
 fingerprints();pure_and_bounds();first_use_transaction();capacity_and_native_binding();contract_and_peer_order();
 std::printf("first-use POD/caller/cache/binding/contract/peer lifecycle PASS; Store=%zu bytes\n",sizeof(Store));
}
