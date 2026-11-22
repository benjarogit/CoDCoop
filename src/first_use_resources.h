#pragma once
#include <cstdint>
#include <cstddef>
#include <cstring>
#include <limits>
#include <type_traits>

// ISOLATED policy/POD only. No hooks, native pointers, file IO or feature enable.
// Native adapters must execute NORMAL_NATIVE/BIND_CACHED_EMPTY/STOP explicitly;
// only a verified pure-precache decision may return a deferred numeric zero.
namespace first_use_resources {
constexpr unsigned VERSION=1,MAX_NAMES=512,NAME_BYTES=64,MAX_WEAPONS=127,MAX_IDS=255;
constexpr uint32_t MODEL_INDEX_RVA=0x485d0,MODEL_CACHE_RVA=0xd2e70,DIRTY_RVA=0x307f2c,CS_BASE=32;
constexpr uint8_t GAME_SHA[32]={0x9f,0xd3,0x66,0x5b,0xa2,0xb6,0x74,0x26,0xbf,0xd7,0x6d,0xf6,0x73,0xd7,0xe6,0x57,0x5e,0x23,0x72,0x24,0xbd,0x5e,0x86,0xc4,0xb9,0x79,0xa4,0x28,0x7b,0xbe,0xb3,0x2e};
enum Source:uint16_t {OriginalPure=1,NativeActual=2,ConfirmedKit=4,AuthoredWorld=8,PeerContract=16,SaveManifest=32};
constexpr uint16_t ALL_SOURCES=63;
enum class Action:uint8_t {NORMAL_NATIVE,DEFERRED_ZERO,BOUND,BIND_CACHED_EMPTY,WAIT,STOP};
enum class Reason:uint8_t {None,Context,Name,Fingerprint,Cache,Capacity,Unknown,NativeMap,Pending,Transaction,Resource,SaveUnresolved};
enum class Use:uint8_t {GameActual,CoreHeldGun,SaveRemap};
enum class Authority:uint8_t {Host=1,Peer=2};
struct Context {uint64_t session;uint32_t world,nativeInit,gameEpoch,rendererEpoch;char map[64];Authority authority;};
struct Entry {char name[NAME_BYTES];uint64_t introduced;uint32_t nativeCached,rendererCached;uint16_t sources;uint8_t id;};
// Native index table, including alternates and unregistered definitions. The
// five model refs mean gun/hand/world/pickup/projectile;0 means no such media.
struct Weapon {char name[64];uint16_t models[5];uint64_t introduced;uint8_t alt;bool defined,registered,mediaComplete;};
struct Contract {uint64_t revision;uint32_t serial;uint8_t sha[32];bool valid;};
struct Peer {uint64_t revision;uint32_t serial;uint8_t sha[32];bool ready;};
struct Pending {uint64_t transaction;uint16_t entry;uint8_t id;bool active;};
struct Store {
 uint32_t version;Context context;Entry entries[MAX_NAMES];Weapon weapons[MAX_WEAPONS+1];
 uint16_t count,weaponCount,boundCount,nativeWeaponCount;uint16_t idOwner[MAX_IDS+1];
 uint64_t revision,transactionCounter;Contract contract;Peer peers[4];Pending pending;
 bool active,failed,peerMapCommitted,definitionsObserved;
};
struct Decision {Action action;Reason reason;uint16_t entry;uint8_t id;uint64_t transaction;Context scope;};
inline Decision Result(Action a,Reason r=Reason::None,unsigned entry=0,unsigned id=0,uint64_t txn=0,const Context*scope=nullptr){Decision d{};d.action=a;d.reason=r;d.entry=(uint16_t)entry;d.id=(uint8_t)id;d.transaction=txn;if(scope)d.scope=*scope;return d;}
inline bool Nonzero(const uint8_t (&sha)[32]){for(auto b:sha)if(b)return true;return false;}
inline bool Map(const char (&s)[64]){
 unsigned n=0;for(;n<64&&s[n];++n){unsigned char c=s[n];if(!((c>='a'&&c<='z')||(c>='A'&&c<='Z')||(c>='0'&&c<='9')||c=='_'||c=='-'))return false;}
 return n&&n<64;
}
inline bool Valid(const Context& c){return c.session&&c.world&&c.nativeInit&&c.gameEpoch&&c.rendererEpoch&&Map(c.map)&&(c.authority==Authority::Host||c.authority==Authority::Peer);}
inline bool SameWorld(const Context&a,const Context&b){return a.session==b.session&&a.world==b.world;}
inline bool Same(const Context&a,const Context&b){return SameWorld(a,b)&&a.authority==b.authority&&a.nativeInit==b.nativeInit&&a.gameEpoch==b.gameEpoch&&a.rendererEpoch==b.rendererEpoch&&Map(a.map)&&Map(b.map)&&!std::strcmp(a.map,b.map);}
inline bool Scope(const Store&s,const Context&c){return s.version==VERSION&&s.active&&!s.failed&&s.count<=MAX_NAMES&&s.weaponCount<=MAX_WEAPONS&&s.nativeWeaponCount<=MAX_WEAPONS&&s.boundCount<=MAX_IDS&&Valid(c)&&Same(s.context,c);}
inline bool Canonical(const char* raw,char (&out)[64],bool model=true){
 if(!raw)return false;
 unsigned n=0;
 for(;n<64;++n){unsigned char c=raw[n];if(!c)break;
  if(c>='A'&&c<='Z')c+=32;
  bool common=(c>='a'&&c<='z')||(c>='0'&&c<='9')||c=='_'||c=='-';
  if(!common&&!(model&&(c=='/'||c=='('||c==')')))return false;
  out[n]=(char)c;
 }
 if(!n||n>=64)return false;
 out[n]=0;
 if(!model)return std::strcmp(out,"none")!=0;
 return n>7&&!std::memcmp(out,"xmodel/",7)&&out[n-1]!='/'&&!std::strstr(out,"//");
}
inline bool Begin(Store&s,const Context&c){
 if(!Valid(c))return false;
 if(s.active&&s.version!=VERSION)return false;
 if(s.version==VERSION&&s.active&&SameWorld(s.context,c))return Scope(s,c);
 std::memset(&s,0,sizeof s);s.version=VERSION;s.context=c;s.active=true;s.revision=1;return true;
}
// Preserve bindings for diagnostics: a same-world cache/module change cannot
// silently clear and reuse IDs. A fresh authoritative world/session is required.
inline void End(Store&s){s.failed=true;for(auto& p:s.peers)p.ready=false;}
inline bool Touch(Store&s){if(s.revision==std::numeric_limits<uint64_t>::max()){End(s);return false;}++s.revision;return true;}
inline unsigned Find(const Store&s,const char* name){
 char canonical[64]={};if(!Canonical(name,canonical))return 0;
 for(unsigned i=0;i<s.count&&i<MAX_NAMES;++i)if(std::memchr(s.entries[i].name,0,64)&&!std::strcmp(s.entries[i].name,canonical))return i+1;
 return 0;
}
inline unsigned Approve(Store&s,const Context&c,const char*name,uint16_t sources){
 char canonical[64]={};if(!Scope(s,c)||!sources||(sources&~ALL_SOURCES)||!Canonical(name,canonical))return 0;
 if(unsigned i=Find(s,canonical)){s.entries[i-1].sources|=sources;return i;}
 if(s.count>=MAX_NAMES||!Touch(s))return 0;
 auto& e=s.entries[s.count++];std::memcpy(e.name,canonical,64);e.sources=sources;e.introduced=s.revision;return s.count;
}
template<class NativeCache>bool CacheNative(Store&s,const Context&c,unsigned entry,NativeCache check){
 if(!Scope(s,c)||!entry||entry>s.count)return false;
 bool valid=check(s.entries[entry-1].name,c);s.entries[entry-1].nativeCached=valid?c.gameEpoch:0;return valid;
}
template<class RendererCache>bool CacheRenderer(Store&s,const Context&c,unsigned entry,RendererCache check){
 if(!Scope(s,c)||!entry||entry>s.count)return false;
 bool valid=check(s.entries[entry-1].name,c);s.entries[entry-1].rendererCached=valid?c.rendererEpoch:0;return valid;
}
struct CodeView {const uint8_t* bytes;size_t size;uint32_t base;uint8_t diskSHA[32];uint32_t ownedHook;};
struct Pattern {uint32_t start,ret;uint8_t length,relocCount,relocs[4],bytes[48];};
inline const Pattern* PurePattern(uint32_t ret){
 static constexpr Pattern sites[]={
 {0x388f7,0x3890a,21,1,{5},{0x53,0x6a,0x00,0xff,0x15,0x44,0x62,0x11,0x20,0x83,0xc4,0x04,0x8b,0xd8,0xe8,0xc6,0xfc,0x00,0x00,0x5b,0xc3}},
 {0x1e79c,0x1e7aa,26,0,{}, {0x8b,0x34,0xb0,0x8b,0x9e,0xc8,0x01,0x00,0x00,0xe8,0x26,0x9e,0x02,0x00,0x8b,0x9e,0xcc,0x01,0x00,0x00,0xe8,0x1b,0x9e,0x02,0x00,0x8b}},
 {0x1e7aa,0x1e7b5,23,0,{}, {0x8b,0x9e,0xcc,0x01,0x00,0x00,0xe8,0x1b,0x9e,0x02,0x00,0x8b,0x9e,0x84,0x03,0x00,0x00,0xe8,0x10,0x9e,0x02,0x00,0x8b}},
 {0x1e7b5,0x1e7c0,20,0,{}, {0x8b,0x9e,0x84,0x03,0x00,0x00,0xe8,0x10,0x9e,0x02,0x00,0x8b,0xb6,0x64,0x03,0x00,0x00,0x85,0xf6,0x74}},
 {0x1e7d0,0x1e7df,24,2,{2,17},{0x8b,0x9e,0x80,0x73,0x0a,0x20,0x85,0xdb,0x74,0x05,0xe8,0xf1,0x9d,0x02,0x00,0x8b,0xb6,0x84,0x73,0x0a,0x20,0x85,0xf6,0x74}},
 {0x1e7df,0x1e7f0,26,1,{2},{0x8b,0xb6,0x84,0x73,0x0a,0x20,0x85,0xf6,0x74,0x07,0x8b,0xde,0xe8,0xe0,0x9d,0x02,0x00,0x8b,0x44,0x24,0x10,0x85,0xc0,0x5e,0x5b,0x74}}
 };
 for(const auto& p:sites)if(p.ret==ret)return &p;
 return nullptr;
}
inline bool Bytes(const CodeView&v,const Pattern&p){
 if(!v.bytes||p.start>v.size||p.length>v.size-p.start||p.length>48||p.relocCount>4)return false;
 uint8_t expected[48];std::memcpy(expected,p.bytes,p.length);
 for(unsigned i=0;i<p.relocCount;++i){unsigned at=p.relocs[i];if(at+4>p.length)return false;
  uint32_t old=0;std::memcpy(&old,expected+at,4);
  if(old<0x20000000||uint64_t(v.base)+(old-0x20000000)>0xffffffffull)return false;
  uint32_t relocated=v.base+(old-0x20000000);std::memcpy(expected+at,&relocated,4);
 }
 return !std::memcmp(v.bytes+p.start,expected,p.length);
}
inline const Pattern& PublicationPattern(){
 static constexpr Pattern publication={0x48682,0,42,4,{5,19,25,34},{0x53,0x6a,0x5b,0xff,0x15,0xbc,0xb8,0x0a,0x20,0x53,0x8d,0x57,0x20,0x52,0x6a,0x2d,0x89,0x04,0xbd,0x70,0x2e,0x0d,0x20,0xff,0x15,0xbc,0xb8,0x0a,0x20,0x83,0xc4,0x14,0xc7,0x05,0x2c,0x7f,0x30,0x20,0x01,0x00,0x00,0x00}};
 return publication;
}
inline bool NativeLayout(const CodeView&v){
 if(std::memcmp(v.diskSHA,GAME_SHA,32)||v.size<DIRTY_RVA+4||!v.bytes||!v.base)return false;
 static constexpr uint8_t original[]={0x80,0x3b,0,0x75,3,0x33,0xc0,0xc3};
 if(v.ownedHook){
  if(v.bytes[MODEL_INDEX_RVA]!=0xe9||v.bytes[MODEL_INDEX_RVA+5]!=0x90||v.bytes[MODEL_INDEX_RVA+6]!=0x90||v.bytes[MODEL_INDEX_RVA+7]!=0x90)return false;
  int32_t relative=0;std::memcpy(&relative,v.bytes+MODEL_INDEX_RVA+1,4);
  if(uint32_t(v.base+MODEL_INDEX_RVA+5+relative)!=v.ownedHook)return false;
 }else if(std::memcmp(v.bytes+MODEL_INDEX_RVA,original,8))return false;
 return Bytes(v,PublicationPattern());
}
inline bool FingerprintPure(const CodeView&v,uint32_t ret){auto p=PurePattern(ret);return p&&NativeLayout(v)&&Bytes(v,*p);}
inline bool BindingSite(uint32_t ret){
 switch(ret){case 0x17925:case 0x1dc30:case 0x1e8b1:case 0x2141e:case 0x27ccf:case 0x27e7f:case 0x28068:case 0x2ec98:case 0x34324:case 0x3600d:case 0x44cc3:case 0x48a76:case 0x48aa2:case 0x62658:return true;default:return false;}
}
inline const Pattern* BindingPattern(uint32_t ret){
 static constexpr Pattern sites[]={
 {0x17917,0x17925,30,1,{0},{0x44,0x62,0x11,0x20,0x83,0xc4,0x04,0x8b,0xd8,0xe8,0xab,0x0c,0x03,0x00,0x8b,0x8e,0x08,0x01,0x00,0x00,0x5e,0x89,0x81,0xd4,0x00,0x00,0x00,0x5b,0xc3,0xcc}},
 {0x1dc23,0x1dc30,29,0,{},{0x86,0x31,0x01,0x00,0x00,0x00,0xeb,0x0d,0xe8,0xa0,0xa9,0x02,0x00,0x88,0x86,0x31,0x01,0x00,0x00,0x33,0xff,0x8b,0xc6,0xe8,0xc1,0xac,0x02,0x00,0x8b}},
 {0x1e8a4,0x1e8b1,32,1,{28},{0x31,0x01,0x00,0x00,0xeb,0x0f,0x8b,0xd8,0xe8,0x1f,0x9d,0x02,0x00,0x88,0x86,0x31,0x01,0x00,0x00,0x33,0xdb,0x8d,0x4c,0x24,0x10,0x51,0x53,0x68,0xd4,0x63,0x09,0x20}},
 {0x21411,0x2141e,29,2,{4,15},{0x83,0xc4,0x08,0xbb,0xa8,0x67,0x09,0x20,0xe8,0xb2,0x71,0x02,0x00,0x8b,0x0d,0x04,0x7f,0x30,0x20,0x8b,0x91,0x08,0x01,0x00,0x00,0x89,0x82,0xd4,0x00}},
 {0x27cc2,0x27ccf,29,0,{},{0x5f,0x5e,0x8b,0xc5,0x5d,0x5b,0x59,0xc3,0xe8,0x01,0x09,0x02,0x00,0x88,0x85,0x31,0x01,0x00,0x00,0x8b,0xc5,0xe8,0x24,0x0c,0x02,0x00,0x5f,0x5e,0x8b}},
 {0x27e72,0x27e7f,29,0,{},{0x84,0x03,0x00,0x00,0x38,0x03,0x74,0x05,0xe8,0x51,0x07,0x02,0x00,0x88,0x85,0x31,0x01,0x00,0x00,0x8b,0xc5,0xe8,0x74,0x0a,0x02,0x00,0x5f,0x5e,0x8b}},
 {0x2805b,0x28068,29,0,{},{0x8b,0xc5,0x5d,0x5b,0x83,0xc4,0x18,0xc3,0xe8,0x68,0x05,0x02,0x00,0x88,0x85,0x31,0x01,0x00,0x00,0x8b,0xc5,0xe8,0x8b,0x08,0x02,0x00,0x5f,0x5e,0x8b}},
 {0x2ec89,0x2ec98,31,2,{0,17},{0xc4,0x0c,0x0c,0x20,0x74,0x11,0x8d,0x5c,0x24,0x18,0xe8,0x38,0x99,0x01,0x00,0x8b,0x0d,0xc4,0x0c,0x0c,0x20,0xeb,0x02,0x33,0xc0,0x8b,0x54,0x24,0x14,0x88,0x82}},
 {0x34317,0x34324,29,0,{},{0x86,0x31,0x01,0x00,0x00,0x00,0xeb,0x0b,0xe8,0xac,0x42,0x01,0x00,0x88,0x86,0x31,0x01,0x00,0x00,0x8d,0x8e,0x8a,0x01,0x00,0x00,0x57,0x51,0xff,0x15}},
 {0x36000,0x3600d,29,0,{},{0x00,0x00,0x00,0xeb,0x0f,0x53,0x8b,0xd8,0xe8,0xc3,0x25,0x01,0x00,0x88,0x86,0x31,0x01,0x00,0x00,0x5b,0x8b,0xc6,0xe8,0xe5,0x28,0x01,0x00,0x56,0x6a}},
 {0x44cb6,0x44cc3,29,0,{},{0x5d,0x5b,0x83,0xc4,0x0c,0xc3,0x8b,0xdf,0xe8,0x0d,0x39,0x00,0x00,0x5f,0x5e,0x88,0x85,0x31,0x01,0x00,0x00,0x5d,0x5b,0x83,0xc4,0x0c,0xc3,0x8d,0x49}},
 {0x48a69,0x48a76,29,0,{},{0x86,0x31,0x01,0x00,0x00,0x00,0x5b,0xc3,0xe8,0x5a,0xfb,0xff,0xff,0x88,0x86,0x31,0x01,0x00,0x00,0x5b,0xc3,0xcc,0xcc,0x56,0x33,0xf6,0x8a,0x84,0x37}},
 {0x48a95,0x48aa2,29,0,{},{0xc0,0x5e,0xc3,0x53,0x8b,0x5c,0x24,0x0c,0xe8,0x2e,0xfb,0xff,0xff,0x88,0x84,0x3e,0xa8,0x02,0x00,0x00,0x8b,0x44,0x24,0x10,0x6a,0x00,0x50,0xff,0x15}},
 {0x6264b,0x62658,29,1,{16},{0x46,0x83,0xfe,0x07,0x7c,0xef,0xeb,0x2b,0xe8,0x78,0x5f,0xfe,0xff,0x6a,0x00,0x68,0x64,0x73,0x09,0x20,0x88,0x84,0x3e,0xa8,0x02,0x00,0x00,0xff,0x15}},
 };
 for(const auto&p:sites)if(p.ret==ret)return &p;
 return nullptr;
}
inline bool FingerprintBinding(const CodeView&v,uint32_t ret){auto p=BindingPattern(ret);return p&&NativeLayout(v)&&Bytes(v,*p);}
template<class Cache>Decision Pure(Store&s,const Context&c,const CodeView&code,uint32_t ret,const char*name,bool nativeLoading,Cache cache){
 if(!Scope(s,c))return Result(Action::NORMAL_NATIVE,Reason::Context);
 if(!nativeLoading||!FingerprintPure(code,ret))return Result(Action::NORMAL_NATIVE,Reason::Fingerprint);
 char canon[64]={};if(!Canonical(name,canon))return Result(Action::NORMAL_NATIVE,Reason::Name);
 // Actual cache proof is renewed on EVERY call; no persisted pointer or bool
 // alone can turn a model into an approved preload.
 if(!cache(canon,c)){if(unsigned i=Find(s,canon))s.entries[i-1].nativeCached=0;return Result(Action::NORMAL_NATIVE,Reason::Cache);}
 unsigned i=Approve(s,c,canon,OriginalPure);if(!i)return Result(Action::NORMAL_NATIVE,Reason::Capacity);
 s.entries[i-1].nativeCached=c.gameEpoch;return Result(Action::DEFERRED_ZERO,Reason::None,i,0,0,&c);
}
template<class ReadCS>bool ReadName(ReadCS read,unsigned id,char (&name)[64]){
 char raw[64]={};if(!id||id>MAX_IDS||!read(id,raw)||!std::memchr(raw,0,64))return false;
 if(!raw[0]){name[0]=0;return true;}return Canonical(raw,name);
}
inline bool Record(Store&s,unsigned entry,unsigned id){
 if(!entry||entry>s.count||!id||id>MAX_IDS)return false;
 auto&e=s.entries[entry-1];
 if((e.id&&e.id!=id)||(s.idOwner[id]&&s.idOwner[id]!=entry))return false;
 if(!e.id){e.id=(uint8_t)id;s.idOwner[id]=(uint16_t)entry;++s.boundCount;}return true;
}
template<class ReadCS,class BoundCache>bool ObserveNativeBinding(Store&s,const Context&c,const char*name,unsigned id,ReadCS read,BoundCache cache){
 char canon[64]={},native[64]={};
 if(!Scope(s,c)||c.authority!=Authority::Host||!Canonical(name,canon)||!ReadName(read,id,native)||std::strcmp(canon,native)||!cache(id,canon,c))return false;
 unsigned i=Approve(s,c,canon,NativeActual);if(!i||!Record(s,i,id)){End(s);return false;}
 s.entries[i-1].nativeCached=c.gameEpoch;return true;
}
template<class ReadCS,class Cache,class BoundCache>
Decision Actual(Store&s,const Context&c,const CodeView&code,Use use,uint32_t ret,const char*name,bool loading,ReadCS read,Cache cached,BoundCache boundCache){
 if(!Scope(s,c))return Result(Action::NORMAL_NATIVE,Reason::Context);
 bool known=use==Use::CoreHeldGun||(use==Use::SaveRemap&&ret==0x2ec98)||(use==Use::GameActual&&BindingSite(ret)&&ret!=0x2ec98);
 if(!known)return Result(Action::NORMAL_NATIVE,Reason::Fingerprint);
 if(!NativeLayout(code)||(use!=Use::CoreHeldGun&&!FingerprintBinding(code,ret))){End(s);return Result(Action::STOP,Reason::Fingerprint);}
 char canonical[64]={};if(!Canonical(name,canonical))return Result(Action::NORMAL_NATIVE,Reason::Name);
 // Loading/save-name remapping ALWAYS retains the original numeric binding.
 if(loading||use==Use::SaveRemap)return Result(Action::NORMAL_NATIVE);
 if(c.authority!=Authority::Host){End(s);return Result(Action::STOP,Reason::Context);}
 unsigned entry=Find(s,canonical);if(!entry)return Result(Action::NORMAL_NATIVE,Reason::Unknown);
 if(s.pending.active)return Result(Action::WAIT,Reason::Pending);
 auto&e=s.entries[entry-1];
 if(e.nativeCached!=c.gameEpoch||!cached(canonical,c)){End(s);return Result(Action::STOP,Reason::Cache);}
 unsigned empty=0,present=0;
 for(unsigned id=1;id<=MAX_IDS;++id){char current[64]={};if(!ReadName(read,id,current)){End(s);return Result(Action::STOP,Reason::NativeMap);}
  if(!current[0]&&!empty)empty=id;
  if(!std::strcmp(current,canonical)){if(present){End(s);return Result(Action::STOP,Reason::NativeMap);}present=id;}
 }
 if(present){if(!boundCache(present,canonical,c)||!Record(s,entry,present)){End(s);return Result(Action::STOP,Reason::NativeMap);}return Result(Action::BOUND,Reason::None,entry,present,0,&c);}
 if(e.id){End(s);return Result(Action::STOP,Reason::NativeMap);}
 if(!empty)return Result(Action::NORMAL_NATIVE,Reason::Capacity);
 if(s.idOwner[empty]||s.transactionCounter==std::numeric_limits<uint64_t>::max()){End(s);return Result(Action::STOP,Reason::Transaction);}
 s.pending={++s.transactionCounter,(uint16_t)entry,(uint8_t)empty,true};
 return Result(Action::BIND_CACHED_EMPTY,Reason::None,entry,empty,s.pending.transaction,&c);
}
// The native adapter publishes cachedXModel[empty], SV_SetConfigstring and dirty
// flag under the fingerprinted layout. No initializing/strict guard is changed.
// A failed/partial publication ends this registry; it cannot recycle the slot.
template<class ReadCS,class BoundCache>bool Commit(Store&s,const Context&c,const Decision&d,ReadCS read,BoundCache cached){
 if(!Scope(s,c)||c.authority!=Authority::Host||!Same(d.scope,c)||!s.pending.active||!d.entry||d.entry>s.count||!d.id||d.action!=Action::BIND_CACHED_EMPTY||d.transaction!=s.pending.transaction||d.entry!=s.pending.entry||d.id!=s.pending.id)return false;
 char current[64]={};auto&e=s.entries[d.entry-1];
 if(!ReadName(read,d.id,current)||std::strcmp(current,e.name)||!cached(d.id,e.name,c)||!Record(s,d.entry,d.id)){End(s);return false;}
 s.pending={};return true;
}
inline void PublicationFailed(Store&s,const Context&c,const Decision&d){if(Scope(s,c)&&Same(d.scope,c)&&s.pending.active&&s.pending.transaction==d.transaction)End(s);}
inline bool DefineWeapon(Store&s,const Context&c,unsigned index,const char*name,bool registered,unsigned alt,const uint16_t(&models)[5],bool mediaComplete){
 char canon[64]={};if(!Scope(s,c)||!index||index>MAX_WEAPONS||alt>MAX_WEAPONS||!Canonical(name,canon,false))return false;
 if(registered&&!mediaComplete)return false;
 for(auto ref:models)if(ref>s.count||(!mediaComplete&&ref))return false;
 for(unsigned i=1;i<=MAX_WEAPONS;++i)if(i!=index&&s.weapons[i].defined&&!std::strcmp(s.weapons[i].name,canon))return false;
 auto&w=s.weapons[index];
 if(w.defined){
  if(std::strcmp(w.name,canon)||w.alt!=alt||(w.mediaComplete&&(!mediaComplete||std::memcmp(w.models,models,sizeof models)))||(w.registered&&!registered))return false;
  if(w.registered==registered&&w.mediaComplete==mediaComplete)return true;
 }else {std::memcpy(w.name,canon,64);w.alt=(uint8_t)alt;w.defined=true;}
 if(!Touch(s))return false;
 std::memcpy(w.models,models,sizeof models);w.mediaComplete=mediaComplete;w.registered=registered;w.introduced=s.revision;if(index>s.weaponCount)s.weaponCount=(uint16_t)index;return true;
}
template<class NativeCount>bool ObserveDefinitionCount(Store&s,const Context&c,unsigned count,NativeCount observed){
 if(!Scope(s,c)||count>MAX_WEAPONS||observed(c)!=int(count)||(s.definitionsObserved&&count<s.nativeWeaponCount))return false;
 if(s.definitionsObserved&&count==s.nativeWeaponCount)return true;
 if(!Touch(s))return false;
 s.nativeWeaponCount=(uint16_t)count;s.definitionsObserved=true;return true;
}
inline bool Complete(const Store&s,const Context&c){
 if(!Scope(s,c)||!s.count||s.pending.active||!s.definitionsObserved||s.weaponCount!=s.nativeWeaponCount)return false;
 for(unsigned i=0;i<s.count;++i){const auto&e=s.entries[i];char name[64]={};if(!e.sources||(e.sources&~ALL_SOURCES)||!Canonical(e.name,name)||std::strcmp(name,e.name)||e.nativeCached!=c.gameEpoch||e.rendererCached!=c.rendererEpoch)return false;}
 for(unsigned i=1;i<=s.weaponCount;++i){const auto&w=s.weapons[i];char name[64]={};if(!w.defined||!Canonical(w.name,name,false)||std::strcmp(name,w.name)||(w.registered&&!w.mediaComplete)||w.alt>MAX_WEAPONS)return false;
  if(w.alt&&(!s.weapons[w.alt].defined||(w.registered&&!s.weapons[w.alt].registered)))return false;
  for(auto ref:w.models)if(ref>s.count)return false;
 }
 return true;
}
template<class Model,class WeaponDef>bool CaptureContract(const Store&s,const Context&c,Model model,WeaponDef weapon){
 if(!Complete(s,c))return false;
 for(unsigned i=0;i<s.count;++i)if(!model(s.entries[i].name))return false;
 for(unsigned i=1;i<=s.weaponCount;++i)if(!weapon(i,s.weapons[i]))return false;
 return true;
}
// verify must hash the complete canonical model+ordered weapon/alt/media
// contract AND trusted external world/rule/plan scope, never just trust an ACK.
template<class Verify>bool Seal(Store&s,const Context&c,uint32_t serial,const uint8_t(&sha)[32],Verify verify){
 if(!Complete(s,c)||!serial||!Nonzero(sha)||!verify(s,c,sha))return false;
 if(s.contract.valid&&serial<=s.contract.serial)return serial==s.contract.serial&&s.contract.revision==s.revision&&!std::memcmp(s.contract.sha,sha,32);
 s.contract={};s.contract.serial=serial;s.contract.revision=s.revision;std::memcpy(s.contract.sha,sha,32);s.contract.valid=true;return true;
}
template<class NativeMapping>bool PeerReady(Store&s,const Context&c,unsigned peer,uint32_t serial,const uint8_t(&sha)[32],NativeMapping verified){
 if(!Scope(s,c)||peer>=4||!s.contract.valid||s.contract.revision!=s.revision||serial!=s.contract.serial||std::memcmp(sha,s.contract.sha,32)||!verified(s,c))return false;
 auto&p=s.peers[peer];p.revision=s.contract.revision;p.serial=serial;std::memcpy(p.sha,sha,32);p.ready=true;return true;
}
// Bootstrap-local Game IDs are NOT authoritative Host IDs. Local GAME_INIT
// must not call ObserveNativeBinding on a Peer Store. Arm only after the
// verified detach/sync barrier; adopt only actual received Host name/ID facts.
template<class Barrier>bool ArmPeerMap(Store&s,const Context&c,Barrier verified){
 if(!Scope(s,c)||c.authority!=Authority::Peer||s.pending.active)return false;
 if(s.peerMapCommitted)return true;
 if(!verified(s,c))return false;
 s.peerMapCommitted=true;return true;
}
template<class ClientCS,class FrozenSV,class BoundCache>
bool AdoptPeerBinding(Store&s,const Context&c,unsigned peer,uint32_t serial,unsigned id,const char*authenticatedHostName,ClientCS clientCS,FrozenSV shadowCS,BoundCache cached){
 if(!Scope(s,c)||c.authority!=Authority::Peer||!s.peerMapCommitted||peer>=4||!id||id>MAX_IDS)return false;
 const auto&p=s.peers[peer];unsigned entry=Find(s,authenticatedHostName);
 if(!p.ready||serial!=p.serial||!entry||s.entries[entry-1].introduced>p.revision)return false;
 auto&e=s.entries[entry-1];char client[64]={},shadow[64]={};
 if(!ReadName(clientCS,id,client)||!ReadName(shadowCS,id,shadow)||std::strcmp(client,e.name)||std::strcmp(shadow,e.name)||!cached(id,e.name,c))return false;
 if(!Record(s,entry,id)){End(s);return false;}return true;
}
// readClient and readFrozenSV must read ACTUAL native tables, not this POD map.
// Different arrival orders yield WAIT until both names and cached media match.
template<class ClientCS,class FrozenSV,class Renderer>
bool PeerDObj(const Store&s,const Context&c,unsigned peer,uint32_t packetSerial,unsigned id,const char*name,ClientCS readClient,FrozenSV readFrozenSV,Renderer rendered){
 if(!Scope(s,c)||c.authority!=Authority::Peer||!s.peerMapCommitted||peer>=4||!id||id>MAX_IDS)return false;
 const auto&p=s.peers[peer];
 if(!p.ready||!packetSerial||packetSerial!=p.serial)return false;
 unsigned i=Find(s,name);if(!i||s.entries[i-1].introduced>p.revision)return false;
 const auto&e=s.entries[i-1];char client[64]={},shadow[64]={};
 return e.id==id&&ReadName(readClient,id,client)&&ReadName(readFrozenSV,id,shadow)&&!std::strcmp(client,e.name)&&!std::strcmp(shadow,e.name)&&rendered(e.name,c);
}
inline bool PeerWeapon(const Store&s,const Context&c,unsigned peer,uint32_t serial,unsigned index){
 if(!Scope(s,c)||peer>=4||!index||index>s.weaponCount)return false;
 const auto&p=s.peers[peer];const auto&w=s.weapons[index];
 return p.ready&&p.serial==serial&&w.defined&&w.registered&&w.introduced<=p.revision;
}
// Approval manifests are separate from numeric SVG remapping. Missing/legacy
// approval provenance is explicit unresolved; it never authorizes dropped IDs.
inline Reason SaveApproval(bool manifestPresent,bool saveShaVerified,bool scopedWorldPackageVerified){return manifestPresent&&saveShaVerified&&scopedWorldPackageVerified?Reason::None:Reason::SaveUnresolved;}
inline bool NativeValue(const Store&s,const Context&c,const Decision&d,bool verifiedPure,int&out){
 if(!Scope(s,c)||!Same(d.scope,c))return false;
 if((d.action==Action::BOUND||(d.action==Action::BIND_CACHED_EMPTY&&!s.pending.active))&&d.id&&d.entry&&d.entry<=s.count&&s.entries[d.entry-1].id==d.id&&s.idOwner[d.id]==d.entry){out=d.id;return true;}
 if(d.action==Action::DEFERRED_ZERO&&verifiedPure&&!d.id&&d.entry&&d.entry<=s.count&&(s.entries[d.entry-1].sources&OriginalPure)&&s.entries[d.entry-1].nativeCached==c.gameEpoch){out=0;return true;}
 return false;
}
static_assert(std::is_trivial<Store>::value&&std::is_trivially_copyable<Store>::value&&std::is_standard_layout<Store>::value,"first-use state must be durable POD without native/STL pointers");
}
