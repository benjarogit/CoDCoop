#pragma once
#include "party_native_bridge_json.h"
#include "reload_delivery.h"
#include <cstring>
#include <type_traits>

namespace party_native_bridge {
constexpr unsigned PENDING=3,PLAYERS=4,TTL_MS=30000;
constexpr const char* IDL="coop-party-native-1";
struct Hex64 {char text[65];};
inline bool Same(const Hex64& a,const Hex64& b){return !std::memcmp(a.text,b.text,65);}
inline bool Hex(const char* s,unsigned n,bool nonzero=false){if(!s||s[n])return false;bool any=false;for(unsigned i=0;i<n;++i){char c=s[i];if(!((c>='0'&&c<='9')||(c>='a'&&c<='f')))return false;any|=c!='0';}return !nonzero||any;}
inline bool Valid(const Hex64& h){return Hex(h.text,64,true);}
template<size_t N>bool Text(const char(&s)[N],const char* allowed){size_t n=0;for(;n<N&&s[n];++n)if(!std::strchr(allowed,s[n]))return false;return n&&n<N;}
template<size_t N>bool Literal(const char(&s)[N],const char* expected){return std::memchr(s,0,N)&&!std::strcmp(s,expected);}
struct Endpoint {uint32_t address;uint16_t port;}; // canonical octets/port in host numerical order
inline bool Valid(Endpoint e){return e.address&&e.port;}
inline bool Same(Endpoint a,Endpoint b){return a.address==b.address&&a.port==b.port;}
struct Context {
 reload_delivery::Token native;
 char engine[8],variant[32],map[64];
 Hex64 party,catalog,package,world,plan,resource;
 uint32_t revision;
};
inline bool Valid(const Context& c){return reload_delivery::Valid(c.native)&&Literal(c.engine,"uo")&&Literal(c.variant,"united_fronts")&&
 Text(c.map,"abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")&&c.revision&&c.revision<=0x7fffffff&&
 Valid(c.party)&&Valid(c.catalog)&&Valid(c.package)&&Valid(c.world)&&Valid(c.plan)&&Valid(c.resource);}
inline bool Same(const Context& a,const Context& b){return Valid(a)&&Valid(b)&&reload_delivery::Same(a.native,b.native)&&
 !std::strcmp(a.engine,b.engine)&&!std::strcmp(a.variant,b.variant)&&!std::strcmp(a.map,b.map)&&a.revision==b.revision&&
 Same(a.party,b.party)&&Same(a.catalog,b.catalog)&&Same(a.package,b.package)&&Same(a.world,b.world)&&Same(a.plan,b.plan)&&Same(a.resource,b.resource);}
struct Member {Hex64 guid;uint8_t slot;};
struct Roster {Member member[PLAYERS];uint8_t count,confirmed;};
inline bool Valid(const Roster& r){
 if(!r.count||r.count>PLAYERS)return false;unsigned mask=0;
 for(unsigned i=0;i<r.count;++i){const auto& m=r.member[i];if(m.slot>=PLAYERS||!Valid(m.guid)||(mask&(1u<<m.slot)))return false;mask|=1u<<m.slot;for(unsigned j=0;j<i;++j)if(Same(m.guid,r.member[j].guid))return false;}
 return (mask&1)&&r.confirmed==mask;
}
inline int Slot(const Roster& r,const Hex64& guid){if(!Valid(r))return -1;for(unsigned i=0;i<r.count;++i)if(Same(r.member[i].guid,guid))return r.member[i].slot;return -1;}
struct Challenge {
 Context context;
 Hex64 nonce,clientNonce,guid;
 Endpoint target,observed;
 uint64_t serial,createdUnix,expiresUnix;
 uint8_t index;
};
inline bool Valid(const Challenge& c){return Valid(c.context)&&Valid(c.nonce)&&Valid(c.clientNonce)&&Valid(c.guid)&&Valid(c.target)&&Valid(c.observed)&&
 c.index<PENDING&&c.serial&&c.createdUnix&&c.expiresUnix>c.createdUnix&&c.expiresUnix<(uint64_t(1)<<53)&&c.expiresUnix-c.createdUnix<=TTL_MS;}
struct Pending {
 Challenge challenge;
 Hex64 canonicalSha;
 uint32_t issuedTick,nativeInitSerial;
 uint8_t reservedSlot;
 bool present,consumed;
};
// These receipts are supplied only by the native lifecycle/resource adapter.
// A valid worker JSON plan alone must never manufacture native readiness.
struct NativeReady {Context context;uint32_t nativeInitSerial,preInitPlanSerial;bool phase2,catalogAndAllKitsVerified;};
inline bool Valid(const NativeReady& r){return Valid(r.context)&&r.nativeInitSerial&&r.preInitPlanSerial==r.nativeInitSerial&&r.phase2&&r.catalogAndAllKitsVerified;}
struct Store {uint64_t nativeSession,nextSerial;Pending pending[PENDING];};
static_assert(std::is_trivial<Store>::value&&std::is_trivially_copyable<Store>::value&&std::is_standard_layout<Store>::value,"native approval state must survive DLLs as POD");
// Called only for a genuinely new locally generated native session. A remote
// challenge, worker restart or heartbeat may never activate a serial epoch.
inline bool Activate(Store& s,uint64_t localNativeSession){if(!localNativeSession)return false;if(s.nativeSession!=localNativeSession){s={};s.nativeSession=localNativeSession;}return true;}
inline bool Alive(const Pending& p,uint32_t tick){return p.present&&!p.consumed&&uint32_t(tick-p.issuedTick)<TTL_MS;}
inline void Retire(Store& s,unsigned index){if(index<PENDING)s.pending[index].consumed=true;}
inline bool Issue(Store& store,const NativeReady& nativeReady,const Roster& roster,unsigned index,const Hex64& guid,const Hex64& nonce,const Hex64& clientNonce,
                  Endpoint target,Endpoint observed,uint32_t tick,uint64_t unixMs,Challenge& out){
 const auto& ready=nativeReady.context;
 if(!Valid(nativeReady)||!Valid(roster)||store.nativeSession!=ready.native.session||index>=PENDING||Slot(roster,guid)<=0||!Valid(nonce)||!Valid(clientNonce)||
    !Valid(target)||!Valid(observed)||!unixMs||unixMs>=(uint64_t(1)<<53)-TTL_MS||store.nextSerial==UINT64_MAX)return false;
 // One GUID cannot occupy two pending indices, and a random nonce is never
 // reused in any retained record, including consumed/expired records.
 for(unsigned i=0;i<PENDING;++i)if(store.pending[i].present){auto& p=store.pending[i];if(Same(p.challenge.nonce,nonce))return false;if(i!=index&&Alive(p,tick)&&Same(p.challenge.guid,guid))return false;}
 Challenge c{};c.context=ready;c.nonce=nonce;c.clientNonce=clientNonce;c.guid=guid;c.target=target;c.observed=observed;c.serial=++store.nextSerial;c.index=(uint8_t)index;c.createdUnix=unixMs;c.expiresUnix=unixMs+TTL_MS;
 auto& p=store.pending[index];p={};p.present=true;p.issuedTick=tick;p.nativeInitSerial=nativeReady.nativeInitSerial;p.reservedSlot=(uint8_t)Slot(roster,guid);p.challenge=c;out=c;return true;
}
inline std::string FixedHex(uint64_t value,unsigned n){static const char h[]="0123456789abcdef";std::string out(n,'0');for(unsigned i=0;i<n;++i){out[n-i-1]=h[value&15];value>>=4;}return out;}
inline std::string EndpointText(Endpoint e){return std::to_string(e.address>>24)+'.'+std::to_string((e.address>>16)&255)+'.'+std::to_string((e.address>>8)&255)+'.'+std::to_string(e.address&255)+':'+std::to_string(e.port);}
inline bool ParseEndpoint(const std::string& s,Endpoint& result){
 if(s.empty()||s.size()>21)return false;size_t p=0;uint32_t address=0,port=0;
 for(unsigned i=0;i<5;++i){size_t start=p;uint32_t v=0;while(p<s.size()&&s[p]>='0'&&s[p]<='9'){if(p-start>4)return false;v=v*10+s[p++]-'0';}if(p==start||(p-start>1&&s[start]=='0'))return false;
  if(i<4){if(v>255||p==s.size()||s[p++]!=(i==3?':':'.'))return false;address=(address<<8)|v;}else {if(!v||v>65535||p!=s.size())return false;port=v;}
 }result={address,(uint16_t)port};return Valid(result);
}
inline party_native_json::Value ContextJson(const Context& c){
 using V=party_native_json::Value;auto v=V::Dict();auto put=[&](const char* n,const char* text){v.object[n]=V::Text(text);};
 v.object["native_session"]=V::Text(FixedHex(c.native.session,16));v.object["native_world"]=V::Text(FixedHex(c.native.generation,8));
 put("engine",c.engine);put("variant",c.variant);put("map",c.map);put("party_session",c.party.text);put("catalog_sha256",c.catalog.text);put("package_sha256",c.package.text);put("world_sha256",c.world.text);put("plan_sha256",c.plan.text);put("resource_sha256",c.resource.text);v.object["roster_revision"]=V::Number(c.revision);return v;
}
inline bool ChallengeJson(const Challenge& c,party_native_json::Value& out){
 if(!Valid(c))return false;using V=party_native_json::Value;auto v=ContextJson(c.context);
 v.object["schema"]=V::Number(1);v.object["kind"]=V::Text(IDL);v.object["pending_index"]=V::Number(c.index);
 v.object["nonce"]=V::Text(c.nonce.text);v.object["client_join_nonce"]=V::Text(c.clientNonce.text);v.object["member_guid"]=V::Text(c.guid.text);
 v.object["client_target"]=V::Text(EndpointText(c.target));v.object["client_endpoint"]=V::Text(EndpointText(c.observed));v.object["challenge_serial"]=V::Text(FixedHex(c.serial,16));v.object["created_unix_ms"]=V::Number(c.createdUnix);v.object["expires_unix_ms"]=V::Number(c.expiresUnix);out=std::move(v);return true;
}
inline bool Canonical(const Challenge& c,std::string& text){party_native_json::Value v;return ChallengeJson(c,v)&&party_native_json::Canonical(v,text);}
// Hash callback is the existing native SHA256 implementation, not a crypto or
// filesystem authority. Sealing commits the exact emitted descriptor bytes.
template<class Hash>bool Seal(Store& s,unsigned index,Hash hash){if(index>=PENDING||!s.pending[index].present||s.pending[index].consumed)return false;std::string bytes;Hex64 digest{};if(!Canonical(s.pending[index].challenge,bytes)||!hash(bytes.data(),bytes.size(),digest)||!Valid(digest))return false;s.pending[index].canonicalSha=digest;return true;}
struct Ack {Challenge challenge;Hex64 canonicalSha;};
inline bool Same(const Challenge& a,const Challenge& b){return Same(a.context,b.context)&&a.index==b.index&&a.serial==b.serial&&a.createdUnix==b.createdUnix&&a.expiresUnix==b.expiresUnix&&Same(a.nonce,b.nonce)&&Same(a.clientNonce,b.clientNonce)&&Same(a.guid,b.guid)&&Same(a.target,b.target)&&Same(a.observed,b.observed);}
inline bool Consume(Store& s,unsigned index,const Ack& ack,const NativeReady& nativeReady,const Roster& currentRoster,
 Endpoint actualPeer,uint32_t tick,bool freshLiveWorker,int& nativeSlot){
 const auto& actualReady=nativeReady.context;
 nativeSlot=-1;if(index>=PENDING||!freshLiveWorker||!Valid(nativeReady)||!Valid(currentRoster))return false;auto& p=s.pending[index];
 if(s.nativeSession!=actualReady.native.session||p.nativeInitSerial!=nativeReady.nativeInitSerial||!Alive(p,tick)||!Same(actualReady,p.challenge.context)||!Valid(p.canonicalSha)||!Same(p.canonicalSha,ack.canonicalSha)||
    !Same(actualPeer,p.challenge.observed)||!Same(p.challenge,ack.challenge))return false;
 int slot=Slot(currentRoster,p.challenge.guid);if(slot<=0||slot!=p.reservedSlot)return false;
 p.consumed=true;nativeSlot=slot;return true; // fence BEFORE any native slot allocation
}
// issuedTick starts only when local native resource phase2 is actually ready;
// cold map-loading time before that must not consume the proof's30s budget.
struct ClientIntent {Context context;Hex64 guid,clientNonce;Endpoint target;uint32_t issuedTick,resourceSerial,nativeInitSerial,preInitPlanSerial;bool active,nativePhase2,catalogAndAllKitsVerified;};
inline bool ReceivedOnOwnSocket(const ClientIntent& own,const Challenge& received,Endpoint actualSource,uint32_t tick,const NativeReady& currentLocal,uint32_t currentResourceSerial){return own.active&&own.nativePhase2&&own.catalogAndAllKitsVerified&&Valid(currentLocal)&&
 own.nativeInitSerial==currentLocal.nativeInitSerial&&own.preInitPlanSerial==currentLocal.preInitPlanSerial&&Same(own.context,currentLocal.context)&&own.resourceSerial&&own.resourceSerial==currentResourceSerial&&Valid(received)&&
 uint32_t(tick-own.issuedTick)<TTL_MS&&Same(own.context,received.context)&&Same(own.guid,received.guid)&&Same(own.clientNonce,received.clientNonce)&&Same(own.target,received.target)&&Same(own.target,actualSource);}

template<size_t N>bool ReadText(const party_native_json::Value* v,char(&out)[N]){if(!v||v->kind!=party_native_json::Value::String||v->string.empty()||v->string.size()>=N||v->string.find('\0')!=std::string::npos)return false;std::memset(out,0,N);std::memcpy(out,v->string.data(),v->string.size());return true;}
inline bool ReadHex(const party_native_json::Value* v,Hex64& out){return ReadText(v,out.text)&&Valid(out);}
inline bool ReadHexNumber(const party_native_json::Value* v,unsigned digits,uint64_t& out){
 if(!v||v->kind!=party_native_json::Value::String||v->string.size()!=digits||!Hex(v->string.c_str(),digits,true))return false;uint64_t n=0;for(char c:v->string)n=(n<<4)|(c<='9'?c-'0':c-'a'+10);out=n;return true;
}
inline bool ParseContext(const party_native_json::Value& v,Context& out){
 Context c{};uint64_t session=0,world=0,revision=0;
 if(!ReadHexNumber(v.Find("native_session"),16,session)||!ReadHexNumber(v.Find("native_world"),8,world)||
  !ReadText(v.Find("engine"),c.engine)||!ReadText(v.Find("variant"),c.variant)||!ReadText(v.Find("map"),c.map)||
  !ReadHex(v.Find("party_session"),c.party)||!ReadHex(v.Find("catalog_sha256"),c.catalog)||!ReadHex(v.Find("package_sha256"),c.package)||
  !ReadHex(v.Find("world_sha256"),c.world)||!ReadHex(v.Find("plan_sha256"),c.plan)||!ReadHex(v.Find("resource_sha256"),c.resource)||
  !party_native_json::Unsigned(v.Find("roster_revision"),0x7fffffff,revision))return false;
 c.native={session,(uint32_t)world};c.revision=(uint32_t)revision;if(!Valid(c))return false;out=c;return true;
}
inline bool ParseChallenge(const party_native_json::Value& v,Challenge& out){
 using namespace party_native_json;
 if(!Keys(v,{"schema","kind","pending_index","nonce","client_join_nonce","native_session","native_world","challenge_serial","engine","variant","map","client_target","client_endpoint","party_session","catalog_sha256","package_sha256","world_sha256","member_guid","roster_revision","plan_sha256","resource_sha256","created_unix_ms","expires_unix_ms"}))return false;
 Challenge c{};uint64_t schema=0,index=0;std::string kind,target,observed;
 if(!Unsigned(v.Find("schema"),1,schema)||schema!=1||!String(v.Find("kind"),kind)||kind!=IDL||!Unsigned(v.Find("pending_index"),2,index)||
  !ParseContext(v,c.context)||!ReadHex(v.Find("nonce"),c.nonce)||!ReadHex(v.Find("client_join_nonce"),c.clientNonce)||!ReadHex(v.Find("member_guid"),c.guid)||
  !String(v.Find("client_target"),target)||!ParseEndpoint(target,c.target)||!String(v.Find("client_endpoint"),observed)||!ParseEndpoint(observed,c.observed)||
  !ReadHexNumber(v.Find("challenge_serial"),16,c.serial)||!Unsigned(v.Find("created_unix_ms"),(uint64_t(1)<<53)-1,c.createdUnix)||
  !Unsigned(v.Find("expires_unix_ms"),(uint64_t(1)<<53)-1,c.expiresUnix))return false;
 c.index=(uint8_t)index;if(!Valid(c))return false;out=c;return true;
}
inline bool ParseAck(const std::string& bytes,Ack& out){
 using namespace party_native_json;Value v;std::string kind,decision,pub,signature;uint64_t schema=0;Ack ack{};
 if(!Parse(bytes,v)||!Keys(v,{"schema","kind","decision","challenge","challenge_sha256","owner_public","owner_signature"})||
  !Unsigned(v.Find("schema"),1,schema)||schema!=1||!String(v.Find("kind"),kind)||kind!=IDL||!String(v.Find("decision"),decision)||decision!="approve"||
  !v.Find("challenge")||!ParseChallenge(*v.Find("challenge"),ack.challenge)||!ReadHex(v.Find("challenge_sha256"),ack.canonicalSha)||
  !String(v.Find("owner_public"),pub)||pub.size()!=64||!Hex(pub.c_str(),64,true)||!String(v.Find("owner_signature"),signature)||signature.size()!=128||!Hex(signature.c_str(),128,true))return false;
 // Signature verification belongs to the admitted local party worker. This
 // parser neither proves its liveness nor authorizes consuming a pending slot.
 out=ack;return true;
}
inline bool ClientJson(const ClientIntent& own,const Challenge& received,Endpoint actualSource,uint32_t tick,uint64_t receivedUnix,const NativeReady& currentLocal,uint32_t currentResourceSerial,party_native_json::Value& out){
 if(!ReceivedOnOwnSocket(own,received,actualSource,tick,currentLocal,currentResourceSerial)||!receivedUnix||receivedUnix>=(uint64_t(1)<<53))return false;
 using V=party_native_json::Value;auto intent=ContextJson(own.context);intent.object["client_join_nonce"]=V::Text(own.clientNonce.text);intent.object["member_guid"]=V::Text(own.guid.text);intent.object["client_target"]=V::Text(EndpointText(own.target));
 V challenge;if(!ChallengeJson(received,challenge))return false;auto v=V::Dict();v.object["schema"]=V::Number(1);v.object["kind"]=V::Text(IDL);v.object["phase"]=V::Number(2);
 v.object["intent"]=std::move(intent);v.object["received_challenge"]=std::move(challenge);v.object["received_source"]=V::Text(EndpointText(actualSource));v.object["received_unix_ms"]=V::Number(receivedUnix);out=std::move(v);return true;
}
}
