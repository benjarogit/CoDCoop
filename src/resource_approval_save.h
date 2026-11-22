#pragma once
#include "first_use_resources.h"

// Portable approvals only. No native IDs, cache epochs, inventories or file IO.
namespace resource_approval_save {
namespace fu=first_use_resources;
constexpr uint16_t VERSION=1;
constexpr size_t MAX_BYTES=65536;
enum class Status {OK,Missing,LegacyOrVersion,Invalid,Context,Digest,Incomplete,NotFresh};
struct Binding {
 char engine[8],variant[64],map[64];
 uint8_t svg[32],gameplay[32],package[32],worldRules[32];
};
struct Name {char name[64];uint16_t sources;};
struct Weapon {char name[64];uint16_t models[5];uint8_t alt;bool registered,mediaComplete;};
struct Manifest {Binding binding;uint16_t count,weaponCount;Name names[fu::MAX_NAMES];Weapon weapons[fu::MAX_WEAPONS+1];};
inline bool Token(const char* s,size_t cap){
 if(!s)return false;
 size_t i=0;for(;i<cap&&s[i];++i){char c=s[i];if(!((c>='a'&&c<='z')||(c>='0'&&c<='9')||c=='_'||c=='-'))return false;}
 return i&&i<cap;
}
inline bool Valid(const Binding&b){
 if(!Token(b.engine,8)||!Token(b.variant,64)||!Token(b.map,64))return false;
 bool profile=(!std::strcmp(b.engine,"cod1")&&!std::strcmp(b.variant,"cod1"))||(!std::strcmp(b.engine,"uo")&&(!std::strcmp(b.variant,"uo")||!std::strcmp(b.variant,"sp_improved")||!std::strcmp(b.variant,"united_fronts")));
 return profile&&fu::Nonzero(b.svg)&&fu::Nonzero(b.gameplay)&&fu::Nonzero(b.package)&&fu::Nonzero(b.worldRules);
}
inline bool Equal(const Binding&a,const Binding&b){return Valid(a)&&Valid(b)&&!std::strcmp(a.engine,b.engine)&&!std::strcmp(a.variant,b.variant)&&!std::strcmp(a.map,b.map)&&!std::memcmp(a.svg,b.svg,32)&&!std::memcmp(a.gameplay,b.gameplay,32)&&!std::memcmp(a.package,b.package,32)&&!std::memcmp(a.worldRules,b.worldRules,32);}
inline bool Canonical(const char*name,bool model){char s[64]={};return fu::Canonical(name,s,model)&&!std::strcmp(name,s);}
inline bool Valid(const Manifest&m){
 if(!Valid(m.binding)||!m.count||m.count>fu::MAX_NAMES||m.weaponCount>fu::MAX_WEAPONS)return false;
 for(unsigned i=0;i<m.count;++i){const auto&n=m.names[i];if(!Canonical(n.name,true)||!n.sources||(n.sources&~fu::ALL_SOURCES)||(i&&std::strcmp(m.names[i-1].name,n.name)>=0))return false;}
 for(unsigned i=1;i<=m.weaponCount;++i){const auto&w=m.weapons[i];if(!Canonical(w.name,false)||(w.registered&&!w.mediaComplete)||w.alt>m.weaponCount)return false;
  for(unsigned j=1;j<i;++j)if(!std::strcmp(w.name,m.weapons[j].name))return false;
  if(w.alt&&w.registered&&!m.weapons[w.alt].registered)return false;
  for(auto r:w.models)if(r>m.count||(!w.mediaComplete&&r))return false;
 }
 return true;
}
// Sorting makes equivalent approval insertion orders byte-identical. Weapon
// order remains the actual native index order; media refs follow sorted names.
inline Status Capture(const fu::Store&s,const fu::Context&c,const Binding&b,Manifest&out){
 if(!Valid(b)||!fu::Scope(s,c)||std::strcmp(b.map,c.map))return Status::Context;
 if(!fu::Complete(s,c))return Status::Incomplete;
 Manifest m{};m.binding=b;m.count=s.count;m.weaponCount=s.weaponCount;
 uint16_t order[fu::MAX_NAMES]={},remap[fu::MAX_NAMES+1]={};
 for(unsigned i=0;i<s.count;++i){order[i]=(uint16_t)i;unsigned j=i;while(j&&std::strcmp(s.entries[order[j-1]].name,s.entries[order[j]].name)>0){auto t=order[j];order[j]=order[j-1];order[--j]=t;}}
 for(unsigned i=0;i<s.count;++i){const auto&e=s.entries[order[i]];std::memcpy(m.names[i].name,e.name,64);m.names[i].sources=e.sources;remap[order[i]+1]=(uint16_t)(i+1);}
 for(unsigned i=1;i<=s.weaponCount;++i){const auto&w=s.weapons[i];auto&v=m.weapons[i];std::memcpy(v.name,w.name,64);v.alt=w.alt;v.registered=w.registered;v.mediaComplete=w.mediaComplete;for(unsigned j=0;j<5;++j){if(w.models[j]>s.count)return Status::Incomplete;v.models[j]=remap[w.models[j]];}}
 if(!Valid(m))return Status::Invalid;
 out=m;return Status::OK;
}
struct Writer {
 uint8_t*data;size_t cap,pos;bool ok;
 void bytes(const void*p,size_t n){if(!ok||n>cap-pos){ok=false;return;}std::memcpy(data+pos,p,n);pos+=n;}
 void u8(uint8_t n){bytes(&n,1);}void u16(uint16_t n){u8((uint8_t)n);u8((uint8_t)(n>>8));}
 void u32(uint32_t n){u16((uint16_t)n);u16((uint16_t)(n>>16));}
 void str(const char*s){size_t n=std::strlen(s);u8((uint8_t)n);bytes(s,n);}
};
struct Reader {
 const uint8_t*data;size_t size,pos;bool ok;
 void bytes(void*p,size_t n){if(!ok||n>size-pos){ok=false;return;}std::memcpy(p,data+pos,n);pos+=n;}
 uint8_t u8(){uint8_t n=0;bytes(&n,1);return n;}
 uint16_t u16(){auto a=u8();auto b=u8();return uint16_t(a|(uint16_t(b)<<8));}
 uint32_t u32(){auto a=u16();auto b=u16();return uint32_t(a)|(uint32_t(b)<<16);}
 template<size_t N>void str(char(&out)[N]){unsigned n=u8();if(!n||n>=N){ok=false;return;}bytes(out,n);out[n]=0;/* Embedded NUL is never canonical. */if(std::memchr(out,0,n))ok=false;}
};
// digest must compute actual SHA-256 over precisely the provided bytes. Binding
// hashes are supplied from completed SVG/package/rules verification, never paths.
template<class SHA> Status Encode(const Manifest&m,uint8_t*out,size_t cap,size_t&written,SHA digest){
 if(!out||!Valid(m))return Status::Invalid;
 // Build privately: output and length are unchanged on EVERY failure.
 uint8_t encoded[MAX_BYTES]={};Writer w{encoded,MAX_BYTES-32,0,true};
 static constexpr uint8_t magic[8]={'C','O','O','P','R','A','P',0};w.bytes(magic,8);w.u16(VERSION);w.u16(0);w.u32(0);
 w.str(m.binding.engine);w.str(m.binding.variant);w.str(m.binding.map);
 w.bytes(m.binding.svg,32);w.bytes(m.binding.gameplay,32);w.bytes(m.binding.package,32);w.bytes(m.binding.worldRules,32);
 w.u16(m.count);w.u16(m.weaponCount);
 for(unsigned i=0;i<m.count;++i){w.str(m.names[i].name);w.u16(m.names[i].sources);}
 for(unsigned i=1;i<=m.weaponCount;++i){const auto&v=m.weapons[i];w.str(v.name);w.u8(uint8_t(v.registered)|(uint8_t(v.mediaComplete)<<1));w.u8(v.alt);for(auto r:v.models)w.u16(r);}
 if(!w.ok||w.pos+32>cap)return Status::Invalid;
 uint32_t total=(uint32_t)(w.pos+32);for(unsigned i=0;i<4;++i)encoded[12+i]=(uint8_t)(total>>(8*i));
 uint8_t sha[32]={};if(!digest(encoded,w.pos,sha)||!fu::Nonzero(sha))return Status::Digest;
 std::memcpy(encoded+w.pos,sha,32);std::memcpy(out,encoded,total);written=total;return Status::OK;
}
template<class SHA>Status Decode(const uint8_t*data,size_t size,const Binding&expected,Manifest&out,SHA digest){
 if(!data||!size)return Status::Missing;
 if(size<16||size>MAX_BYTES)return Status::Invalid;
 static constexpr uint8_t magic[8]={'C','O','O','P','R','A','P',0};
 if(std::memcmp(data,magic,8))return Status::LegacyOrVersion;
 Reader r{data,size,8,true};if(r.u16()!=VERSION)return Status::LegacyOrVersion;
 if(r.u16()!=0||r.u32()!=size||size<48)return Status::Invalid;
 uint8_t sha[32]={};if(!digest(data,size-32,sha)||!fu::Nonzero(sha)||std::memcmp(sha,data+size-32,32))return Status::Digest;
 r.size=size-32;Manifest m{};r.str(m.binding.engine);r.str(m.binding.variant);r.str(m.binding.map);
 r.bytes(m.binding.svg,32);r.bytes(m.binding.gameplay,32);r.bytes(m.binding.package,32);r.bytes(m.binding.worldRules,32);
 m.count=r.u16();m.weaponCount=r.u16();if(!r.ok||!m.count||m.count>fu::MAX_NAMES||m.weaponCount>fu::MAX_WEAPONS)return Status::Invalid;
 for(unsigned i=0;i<m.count;++i){r.str(m.names[i].name);m.names[i].sources=r.u16();}
 for(unsigned i=1;i<=m.weaponCount;++i){auto&v=m.weapons[i];r.str(v.name);unsigned flags=r.u8();if(flags&~3u)return Status::Invalid;v.registered=(flags&1)!=0;v.mediaComplete=(flags&2)!=0;v.alt=r.u8();for(auto&ref:v.models)ref=r.u16();}
 if(!r.ok||r.pos!=r.size||!Valid(m))return Status::Invalid;
 if(!Equal(m.binding,expected))return Status::Context;
 out=m;return Status::OK;
}
// Fresh lifecycle proof belongs to the native adapter. Require virgin output;
// no IDs/weapon registration/cache stamps/receipts are imported from a save.
// Saved Weapon metadata remains in Manifest for subsequent native verification.
template<class Fresh>Status RestoreApprovals(const Manifest&m,const Binding&verified,const fu::Context&fresh,fu::Store&out,Fresh genuinelyNew){
 if(!Valid(m)||!Equal(m.binding,verified))return Status::Context;
 const uint8_t*raw=reinterpret_cast<const uint8_t*>(&out);for(size_t i=0;i<sizeof out;++i)if(raw[i])return Status::NotFresh;
 if(!fu::Valid(fresh)||std::strcmp(fresh.map,m.binding.map)||!genuinelyNew(fresh))return Status::NotFresh;
 fu::Store s{};if(!fu::Begin(s,fresh))return Status::NotFresh;
 for(unsigned i=0;i<m.count;++i)if(!fu::Approve(s,fresh,m.names[i].name,uint16_t(m.names[i].sources|fu::SaveManifest)))return Status::Invalid;
 out=s;return Status::OK;
}
static_assert(std::is_trivial<Manifest>::value&&std::is_standard_layout<Manifest>::value,"manifest must not persist pointers");
}
