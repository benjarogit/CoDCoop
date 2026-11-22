#include "../src/resource_approval_save.h"
#ifdef _WIN32
#include <windows.h>
#include <wincrypt.h>
#else
#include <openssl/evp.h>
#endif
#include <cassert>
#include <cstdio>
#include <vector>
namespace rs=resource_approval_save;
namespace fu=first_use_resources;
bool sha(const uint8_t*p,size_t n,uint8_t(&out)[32]){
#ifdef _WIN32
 if(n>0xffffffffu)return false;
 HCRYPTPROV provider=0;HCRYPTHASH hash=0;DWORD count=32;
 if(!CryptAcquireContextA(&provider,nullptr,nullptr,PROV_RSA_AES,CRYPT_VERIFYCONTEXT))return false;
 bool ok=CryptCreateHash(provider,CALG_SHA_256,0,0,&hash)&&CryptHashData(hash,p,(DWORD)n,0)&&CryptGetHashParam(hash,HP_HASHVAL,out,&count,0)&&count==32;
 if(hash)CryptDestroyHash(hash);
 CryptReleaseContext(provider,0);return ok;
#else
 unsigned count=0;return EVP_Digest(p,n,out,&count,EVP_sha256(),nullptr)==1&&count==32;
#endif
}
fu::Context context(){fu::Context c{};c.session=42;c.world=2;c.nativeInit=3;c.gameEpoch=4;c.rendererEpoch=5;c.authority=fu::Authority::Host;std::strcpy(c.map,"foy");return c;}
rs::Binding binding(){rs::Binding b{};std::strcpy(b.engine,"uo");std::strcpy(b.variant,"united_fronts");std::strcpy(b.map,"foy");b.svg[0]=1;b.gameplay[0]=2;b.package[0]=3;b.worldRules[0]=4;return b;}
fu::Store store(bool reverse=false){fu::Store s{};auto c=context();assert(fu::Begin(s,c));
 const char*a=reverse?"xmodel/a":"xmodel/z";const char*b=reverse?"xmodel/z":"xmodel/a";
 assert(fu::Approve(s,c,a,fu::OriginalPure));assert(fu::Approve(s,c,b,fu::AuthoredWorld));
 // Fix source flags independently of insertion order.
 s.entries[fu::Find(s,"xmodel/a")-1].sources=fu::AuthoredWorld;s.entries[fu::Find(s,"xmodel/z")-1].sources=fu::OriginalPure;
 for(unsigned i=0;i<s.count;++i){s.entries[i].nativeCached=c.gameEpoch;s.entries[i].rendererCached=c.rendererEpoch;}
 s.definitionsObserved=true;s.weaponCount=s.nativeWeaponCount=2;
 for(unsigned i=1;i<=2;++i){auto&w=s.weapons[i];std::strcpy(w.name,i==1?"bar":"bar-alt");w.defined=w.registered=w.mediaComplete=true;w.models[0]=(uint16_t)fu::Find(s,"xmodel/z");w.models[1]=(uint16_t)fu::Find(s,"xmodel/a");w.alt=i==1?2:0;}
 assert(fu::Complete(s,c));return s;
}
std::vector<uint8_t> encode(const rs::Manifest&m){std::vector<uint8_t>b(rs::MAX_BYTES);size_t n=0;assert(rs::Encode(m,b.data(),b.size(),n,sha)==rs::Status::OK);b.resize(n);return b;}
void resign(std::vector<uint8_t>&b){uint8_t hash[32]={};assert(sha(b.data(),b.size()-32,hash));std::memcpy(b.data()+b.size()-32,hash,32);}
void rejected(const std::vector<uint8_t>&b,const rs::Binding&binding){rs::Manifest out{};std::memset(&out,0xa5,sizeof out);auto before=out;assert(rs::Decode(b.data(),b.size(),binding,out,sha)!=rs::Status::OK);assert(!std::memcmp(&before,&out,sizeof out));}
int main(){
 const uint8_t abc[]={97,98,99};uint8_t known[32]={};
 static constexpr uint8_t expected[]={0xba,0x78,0x16,0xbf,0x8f,0x01,0xcf,0xea,0x41,0x41,0x40,0xde,0x5d,0xae,0x22,0x23,0xb0,0x03,0x61,0xa3,0x96,0x17,0x7a,0x9c,0xb4,0x10,0xff,0x61,0xf2,0x00,0x15,0xad};
 assert(sha(abc,3,known)&&!std::memcmp(known,expected,32));
 auto c=context();auto b=binding();auto s=store();rs::Manifest m{};assert(rs::Capture(s,c,b,m)==rs::Status::OK);
 assert(!std::strcmp(m.names[0].name,"xmodel/a")&&m.weapons[1].models[0]==2&&m.weapons[1].models[1]==1);
 auto bytes=encode(m);uint8_t canonicalSHA[32]={};assert(sha(bytes.data(),bytes.size(),canonicalSHA));
 std::printf("canonical %zu bytes SHA256 ",bytes.size());for(auto v:canonicalSHA)std::printf("%02x",v);std::puts("");
 rs::Manifest decoded{};assert(rs::Decode(bytes.data(),bytes.size(),b,decoded,sha)==rs::Status::OK);assert(encode(decoded)==bytes);
 auto reversed=store(true);rs::Manifest equivalent{};assert(rs::Capture(reversed,c,b,equivalent)==rs::Status::OK);assert(encode(equivalent)==bytes);
 // Physical IDs, recipients and cache stamps are not serialized.
 s.entries[0].id=153;s.idOwner[153]=1;s.boundCount=1;s.peers[0].ready=true;s.contract.valid=true;s.transactionCounter=900;
 rs::Manifest ignored{};assert(rs::Capture(s,c,b,ignored)==rs::Status::OK);assert(encode(ignored)==bytes);
 auto unchanged=m;auto incomplete=s;incomplete.entries[0].rendererCached=0;assert(rs::Capture(incomplete,c,b,unchanged)==rs::Status::Incomplete);assert(!std::memcmp(&unchanged,&m,sizeof m));
 auto malformed=c;std::memset(malformed.map,'x',64);assert(rs::Capture(s,malformed,b,unchanged)==rs::Status::Context);
 // Every truncation and every single-byte mutation fails without touching output.
 for(size_t n=0;n<bytes.size();++n){auto cut=bytes;cut.resize(n);rejected(cut,b);}
 for(size_t n=0;n<bytes.size();++n){auto mutation=bytes;mutation[n]^=0x80;rejected(mutation,b);}
 auto extra=bytes;extra.push_back(0);rejected(extra,b);
 for(unsigned which=0;which<7;++which){auto other=b;switch(which){case 0:other.svg[0]++;break;case 1:other.gameplay[0]++;break;case 2:other.package[0]++;break;case 3:other.worldRules[0]++;break;case 4:std::strcpy(other.engine,"cod1");break;case 5:std::strcpy(other.variant,"uo");break;default:std::strcpy(other.map,"noville");}rejected(bytes,other);}
 // Valid digest cannot make unknown version/reserved header/duplicate/counts valid.
 auto bad=bytes;bad[8]=2;resign(bad);rejected(bad,b);bad=bytes;bad[10]=1;resign(bad);rejected(bad,b);
 // Locate fields by portable reader; malformed semantic fields are re-signed.
 rs::Reader r{bytes.data(),bytes.size()-32,16,true};char engine[8]={},variant[64]={},map[64]={};r.str(engine);r.str(variant);r.str(map);r.pos+=128;size_t counts=r.pos;r.u16();r.u16();size_t first=r.pos;r.str(map);size_t sources=r.pos;r.u16();size_t second=r.pos;r.str(map);r.u16();size_t weapon=r.pos;r.str(map);size_t flags=r.pos;
 bad=bytes;bad[counts]=1;bad[counts+1]=2;resign(bad);rejected(bad,b); // 513 names.
 bad=bytes;bad[counts+2]=128;resign(bad);rejected(bad,b);
 bad=bytes;bad[sources+1]=0x80;resign(bad);rejected(bad,b);
 bad=bytes;std::memcpy(bad.data()+second,bytes.data()+first,9);resign(bad);rejected(bad,b); // duplicate name.
 bad=bytes;bad[first+1]='X';resign(bad);rejected(bad,b); // uppercase noncanonical.
 bad=bytes;bad[first+2]=0;resign(bad);rejected(bad,b); // embeddedNUL.
 bad=bytes;bad[first+1]=0xc3;bad[first+2]=0xa4;resign(bad);rejected(bad,b); // UTF8 names forbidden.
 bad=bytes;bad[flags]=4;resign(bad);rejected(bad,b);
 bad=bytes;bad[flags]=0;resign(bad);rejected(bad,b); // unregistered/incomplete with nonzero media.
 // Unknown profile and engine/profile mismatch cannot be approved even with
 // a valid manifest digest and an independently matching expected binding.
 auto unknown=b;std::strcpy(unknown.variant,"other");assert(!rs::Valid(unknown));
 auto mismatch=b;std::strcpy(mismatch.variant,"cod1");assert(!rs::Valid(mismatch));
 auto wrongEngine=b;std::strcpy(wrongEngine.engine,"cod1");assert(!rs::Valid(wrongEngine));
 auto validClassic=b;std::strcpy(validClassic.engine,"cod1");std::strcpy(validClassic.variant,"cod1");assert(rs::Valid(validClassic));
 for(const char*variantName:{"uo","sp_improved","united_fronts"}){auto good=b;std::strcpy(good.variant,variantName);assert(rs::Valid(good));}
 bad=bytes;std::memcpy(bad.data()+17,"xx",2);resign(bad);rejected(bad,b); // unknown engine.
 bad=bytes;std::memcpy(bad.data()+20,"unknown_front",13);resign(bad);rejected(bad,b); // same-length unknown variant.
 // Build a canonical-looking yet unregistered engine/variant pair by splicing
 // a cod1 engine string into the encoded payload and correcting exact length.
 bad=bytes;bad[16]=4;bad.insert(bad.begin()+19,2,0);std::memcpy(bad.data()+17,"cod1",4);
 for(unsigned i=0;i<4;++i){bad[12+i]=(uint8_t)(bad.size()>>(8*i));}
 resign(bad);rejected(bad,wrongEngine);
 bad=bytes;bad[flags+1]=3;resign(bad);rejected(bad,b); // missing alt.
 bad=bytes;bad[flags+2]=3;resign(bad);rejected(bad,b); // missing model ref.
 bad=bytes;bad[weapon]=0;resign(bad);rejected(bad,b);
 // Equal-length trailing bytes with declared total and valid digest still fail.
 bad=bytes;bad.insert(bad.end()-32,0);for(unsigned i=0;i<4;++i)bad[12+i]=(uint8_t)(bad.size()>>(8*i));resign(bad);rejected(bad,b);
 auto invalid=m;invalid.names[0].sources=0;assert(!rs::Valid(invalid));invalid=m;std::memset(invalid.names[0].name,'a',64);assert(!rs::Valid(invalid));
 invalid=m;invalid.weapons[2]=invalid.weapons[1];assert(!rs::Valid(invalid));invalid=m;invalid.weapons[2].registered=false;assert(!rs::Valid(invalid));
 uint8_t output[rs::MAX_BYTES];std::memset(output,0x77,sizeof output);size_t length=123;
 auto nohash=[](const uint8_t*,size_t,uint8_t(&)[32]){return false;};
 assert(rs::Encode(m,output,sizeof output,length,nohash)==rs::Status::Digest&&length==123&&output[0]==0x77);
 assert(rs::Encode(m,output,1,length,sha)==rs::Status::Invalid&&length==123&&output[0]==0x77);
 auto zeroHash=[](const uint8_t*,size_t,uint8_t(&out)[32]){std::memset(out,0,32);return true;};
 rs::Manifest keep=m;assert(rs::Decode(bytes.data(),bytes.size(),b,keep,zeroHash)==rs::Status::Digest&&!std::memcmp(&keep,&m,sizeof m));assert(rs::Decode(bytes.data(),bytes.size(),b,keep,nohash)==rs::Status::Digest&&!std::memcmp(&keep,&m,sizeof m));
 // Approval restoration imports zero IDs/caches/registration and needs genuine
 // fresh lifecycle proof. Current kit roster is deliberately NOT compared.
 fu::Store fresh{};auto nc=c;nc.world++;nc.nativeInit++;nc.gameEpoch++;nc.rendererEpoch++;
 assert(rs::RestoreApprovals(m,b,nc,fresh,[](const fu::Context&){return false;})==rs::Status::NotFresh);
 assert(rs::RestoreApprovals(m,b,nc,fresh,[&](const fu::Context&x){return !fu::SameWorld(c,x)&&x.gameEpoch!=c.gameEpoch;})==rs::Status::OK);
 assert(fresh.count==2&&!fresh.boundCount&&!fresh.weaponCount&&!fresh.definitionsObserved&&!fresh.contract.valid&&!fresh.peerMapCommitted);
 for(const auto&e:fresh.entries)assert(!e.id&&!e.nativeCached&&!e.rendererCached);
 assert(!fu::Complete(fresh,nc));auto saved=fresh;assert(rs::RestoreApprovals(m,b,nc,fresh,[](const fu::Context&){return true;})==rs::Status::NotFresh);assert(!std::memcmp(&fresh,&saved,sizeof fresh));
 // Maximum exact counts, names and complete 127 native metadata records.
 rs::Manifest maximum{};maximum.binding=b;maximum.count=512;maximum.weaponCount=127;
 for(unsigned i=0;i<512;++i){std::snprintf(maximum.names[i].name,64,"xmodel/model%03u",i);maximum.names[i].sources=fu::ALL_SOURCES;}
 for(unsigned i=1;i<=127;++i){auto&w=maximum.weapons[i];std::snprintf(w.name,64,"weapon%03u",i);w.registered=w.mediaComplete=true;w.models[0]=512;}
 // Exercise the maximum63byte canonical names rather than short placeholders.
 for(unsigned i=0;i<512;++i){size_t n=std::strlen(maximum.names[i].name);std::memset(maximum.names[i].name+n,'a',63-n);maximum.names[i].name[63]=0;}
 for(unsigned i=1;i<=127;++i){size_t n=std::strlen(maximum.weapons[i].name);std::memset(maximum.weapons[i].name+n,'b',63-n);maximum.weapons[i].name[63]=0;}
 auto full=encode(maximum);assert(rs::Decode(full.data(),full.size(),b,decoded,sha)==rs::Status::OK&&decoded.count==512&&decoded.weaponCount==127);
 assert(rs::Decode(nullptr,0,b,decoded,sha)==rs::Status::Missing);
 uint8_t legacy[16]={};assert(rs::Decode(legacy,sizeof legacy,b,decoded,sha)==rs::Status::LegacyOrVersion);
 std::puts("resource approval SAVE manifest canonical codec/actual SHA256/context/fresh-only PASS");
}
