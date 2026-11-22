#pragma once
#include "party_native_bridge.h"
#include "asset_bootstrap.h"

namespace party_native_bridge {
struct Kit {char family[16];uint16_t choice[4];};
struct Plan {
 Hex64 party,catalog,package,worldSha,planSha,localGuid;
 Roster roster;Kit kit[PLAYERS];
 uint32_t revision,workerPid;
 uint64_t updatedUnix,expiresUnix;
 char map[64];
};
inline bool Valid(const Plan& p){return Valid(p.party)&&Valid(p.catalog)&&Valid(p.package)&&Valid(p.worldSha)&&Valid(p.planSha)&&Valid(p.localGuid)&&Valid(p.roster)&&Slot(p.roster,p.localGuid)>=0&&p.revision&&p.revision<=0x7fffffff&&Text(p.map,"abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-");}
// Portable decoding only: caller Hash is native SHA256; verifyCatalogAndUnion
// must check the actually installed, pinned UF catalog and ALL owners' choices
// plus the authoritative host map/year graph. This helper never guesses a kit.
template<class Hash,class VerifyCatalogAndUnion>
bool ParsePlan(const std::string& bytes,const Hex64& installedCatalog,const Hex64& installedPackage,Hash hash,VerifyCatalogAndUnion verify,Plan& out){
 using namespace party_native_json;Value root;
 if(!Parse(bytes,root)||!Keys(root,{"schema","kind","party_session","catalog_sha256","package_sha256","world","world_sha256","revision","plan_sha256","members","local_guid","confirmed_slots","plan","runtime_ready","worker_pid","updated_unix_ms","expires_unix_ms"}))return false;
 Plan p{};uint64_t schema=0,revision=0,pid=0;std::string kind;
 if(!Unsigned(root.Find("schema"),1,schema)||schema!=1||!String(root.Find("kind"),kind)||kind!=IDL||
  !ReadHex(root.Find("party_session"),p.party)||!ReadHex(root.Find("catalog_sha256"),p.catalog)||!Same(p.catalog,installedCatalog)||
  !ReadHex(root.Find("package_sha256"),p.package)||!Same(p.package,installedPackage)||!ReadHex(root.Find("world_sha256"),p.worldSha)||!ReadHex(root.Find("plan_sha256"),p.planSha)||!ReadHex(root.Find("local_guid"),p.localGuid)||
  !Unsigned(root.Find("revision"),0x7fffffff,revision)||!revision||!Unsigned(root.Find("worker_pid"),0xffffffff,pid)||!pid||
  !Unsigned(root.Find("updated_unix_ms"),(uint64_t(1)<<53)-1,p.updatedUnix)||!p.updatedUnix||!Unsigned(root.Find("expires_unix_ms"),(uint64_t(1)<<53)-1,p.expiresUnix)||p.expiresUnix<=p.updatedUnix||p.expiresUnix-p.updatedUnix>5000)return false;
 auto runtime=root.Find("runtime_ready");if(!runtime||runtime->kind!=Value::Boolean||runtime->boolean)return false;
 p.revision=(uint32_t)revision;p.workerPid=(uint32_t)pid;
 auto members=root.Find("members"),confirmed=root.Find("confirmed_slots"),world=root.Find("world"),plan=root.Find("plan");
 if(!members||members->kind!=Value::Array||members->array.empty()||members->array.size()>PLAYERS||!confirmed||confirmed->kind!=Value::Array||!world||world->kind!=Value::Object||!plan||
    !Keys(*plan,{"schema","catalog_sha256","host_slot","world","members","revision","unresolved_automatic_slots","required_weapons","required_server_models","required_media_models","support","plan_sha256"}))return false;
 p.roster.count=(uint8_t)members->array.size();
 for(unsigned i=0;i<p.roster.count;++i){const auto& member=members->array[i];uint64_t slot=0;
  if(!Keys(member,{"guid","slot"})||!ReadHex(member.Find("guid"),p.roster.member[i].guid)||!Unsigned(member.Find("slot"),3,slot))return false;p.roster.member[i].slot=(uint8_t)slot;
 }
 for(const auto& value:confirmed->array){uint64_t slot=0;if(!Unsigned(&value,3,slot)||(p.roster.confirmed&(1u<<slot)))return false;p.roster.confirmed|=1u<<slot;}
 if(!Valid(p.roster)||Slot(p.roster,p.localGuid)<0)return false;
 std::string canonicalWorld;Hex64 digest{};
 if(!Canonical(*world,canonicalWorld)||!hash(canonicalWorld.data(),canonicalWorld.size(),digest)||!Same(digest,p.worldSha))return false;
 const char* worldKeys[]={"variant","package_id","map","campaign","sp_ally","sp_axis","sp_ally_nation","sp_year","sp_history","sp_order","difficulty"};
 for(const auto& field:world->object){bool allowed=false;for(auto key:worldKeys)if(field.first==key)allowed=true;if(!allowed||field.second.kind!=Value::String||field.second.string.empty()||field.second.string.size()>160)return false;for(unsigned char c:field.second.string)if(c<32||c>=127||c==';')return false;}
 std::string variant,package,map;
 if(!String(world->Find("variant"),variant)||variant!="united_fronts"||!String(world->Find("package_id"),package)||package!=p.package.text||!ReadText(world->Find("map"),p.map)||!Text(p.map,"abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"))return false;
 auto planWorld=plan->Find("world");std::string planWorldBytes;if(!planWorld||!Canonical(*planWorld,planWorldBytes)||planWorldBytes!=canonicalWorld)return false;
 uint64_t planSchema=0,planRevision=0,hostSlot=0;Hex64 planCatalog{},declaredSha{};
 if(!Unsigned(plan->Find("schema"),1,planSchema)||planSchema!=1||!Unsigned(plan->Find("revision"),0x7fffffff,planRevision)||planRevision!=revision||
  !Unsigned(plan->Find("host_slot"),0,hostSlot)||!ReadHex(plan->Find("catalog_sha256"),planCatalog)||!Same(planCatalog,p.catalog)||!ReadHex(plan->Find("plan_sha256"),declaredSha)||!Same(declaredSha,p.planSha))return false;
 Value unhashed=*plan;unhashed.object.erase("plan_sha256");std::string canonicalPlan;
 if(!Canonical(unhashed,canonicalPlan)||!hash(canonicalPlan.data(),canonicalPlan.size(),digest)||!Same(digest,p.planSha))return false;
 auto unresolved=plan->Find("unresolved_automatic_slots"),kits=plan->Find("members");
 if(!unresolved||unresolved->kind!=Value::Array||!unresolved->array.empty()||!kits||kits->kind!=Value::Array||kits->array.size()!=p.roster.count)return false;
 unsigned seen=0;
 for(const auto& member:kits->array){uint64_t slot=0;auto kit=member.Find("kit");
  if(!Keys(member,{"slot_id","kit"})||!Unsigned(member.Find("slot_id"),3,slot)||(seen&(1u<<slot))||!kit||!Keys(*kit,{"mode","family","slots"}))return false;
  seen|=1u<<slot;std::string mode;if(!String(kit->Find("mode"),mode)||mode!="manual"||!ReadText(kit->Find("family"),p.kit[slot].family)||!Text(p.kit[slot].family,"abcdefghijklmnopqrstuvwxyz_"))return false;
  auto choices=kit->Find("slots");if(!choices||!Keys(*choices,{"primary","secondary","pistol","grenade"}))return false;
  const char* names[]={"primary","secondary","pistol","grenade"};for(unsigned i=0;i<4;++i){uint64_t id=0;if(!Unsigned(choices->Find(names[i]),65535,id))return false;p.kit[slot].choice[i]=(uint16_t)id;}
 }
 if(seen!=p.roster.confirmed)return false;
 // The resolver compares exact native catalogue resources, including support
 // graph requirements, rather than trusting a claimed model/weapon union.
 if(!verify(p,*world,*plan))return false;out=p;return true;
}
struct Heartbeat {uint32_t pid,firstTick;uint64_t updatedUnix;Hex64 plan;bool seen;};
template<class OwnerProcessAlive>bool FreshWorker(Heartbeat& previous,const Plan& plan,uint32_t tick,uint64_t unixMs,OwnerProcessAlive alive){
 if(!Valid(plan.party)||!Valid(plan.planSha)||!plan.workerPid||!plan.updatedUnix||plan.expiresUnix<=plan.updatedUnix||plan.expiresUnix-plan.updatedUnix>5000||unixMs<plan.updatedUnix||unixMs>=plan.expiresUnix||!alive(plan.workerPid))return false;
 if(previous.seen&&previous.pid==plan.workerPid){
  if(plan.updatedUnix<previous.updatedUnix)return false;
  if(plan.updatedUnix==previous.updatedUnix)return Same(previous.plan,plan.planSha)&&uint32_t(tick-previous.firstTick)<5000;
 }
 previous={plan.workerPid,tick,plan.updatedUnix,plan.planSha,true};return true;
}
inline bool Matches(const Context& native,const Plan& confirmed){return Valid(native)&&Valid(confirmed)&&Same(native.party,confirmed.party)&&Same(native.plan,confirmed.planSha)&&Same(native.world,confirmed.worldSha)&&Same(native.catalog,confirmed.catalog)&&Same(native.package,confirmed.package)&&native.revision==confirmed.revision&&!std::strcmp(native.map,confirmed.map);}
template<class OwnerProcessAlive>bool IssueApproved(Store& store,const NativeReady& ready,const Plan& currentWorker,Heartbeat& heartbeat,unsigned index,
 const Hex64& guid,const Hex64& nonce,const Hex64& clientNonce,Endpoint target,Endpoint observed,uint32_t tick,uint64_t unixMs,OwnerProcessAlive alive,Challenge& out){
 if(Slot(currentWorker.roster,currentWorker.localGuid)!=0||!Matches(ready.context,currentWorker)||!FreshWorker(heartbeat,currentWorker,tick,unixMs,alive))return false;
 return Issue(store,ready,currentWorker.roster,index,guid,nonce,clientNonce,target,observed,tick,unixMs,out);
}
template<class OwnerProcessAlive>bool ConsumeApproved(Store& store,unsigned index,const Ack& ack,const NativeReady& ready,const Plan& currentWorker,Heartbeat& heartbeat,
 Endpoint actualPeer,uint32_t tick,uint64_t unixMs,OwnerProcessAlive alive,int& slot){
 slot=-1;if(Slot(currentWorker.roster,currentWorker.localGuid)!=0||!Matches(ready.context,currentWorker)||!FreshWorker(heartbeat,currentWorker,tick,unixMs,alive))return false;
 return Consume(store,index,ack,ready,currentWorker.roster,actualPeer,tick,true,slot);
}
inline bool ResourceJson(const asset_bootstrap::Resources& resources,party_native_json::Value& out){
 std::string encoded;uint16_t entries=0;if(!asset_bootstrap::EncodeResources(resources,encoded,entries))return false;
 using V=party_native_json::Value;auto value=V::Dict();value.object["models"].kind=V::Array;value.object["weapons"].kind=V::Array;
 for(const auto& model:resources.models)value.object["models"].array.push_back(V::Text(model));
 for(const auto& weapon:resources.weapons){auto row=V::Dict();row.object["index"]=V::Number(weapon.index);row.object["name"]=V::Text(weapon.name);row.object["registered"]=V::Bool(weapon.registered);value.object["weapons"].array.push_back(std::move(row));}
 out=std::move(value);return true;
}
template<class Hash>bool HostReadyJson(const NativeReady& ready,const Plan& confirmed,const asset_bootstrap::Resources& resources,Hash hash,party_native_json::Value& out){
 if(!Valid(ready)||Slot(confirmed.roster,confirmed.localGuid)!=0||!Matches(ready.context,confirmed))return false;
 std::string body;uint16_t count=0;Hex64 actual{};if(!asset_bootstrap::EncodeResources(resources,body,count)||!hash(body.data(),body.size(),actual)||!Same(actual,ready.context.resource))return false;
 using V=party_native_json::Value;V resource;if(!ResourceJson(resources,resource))return false;auto value=V::Dict();value.object["schema"]=V::Number(1);value.object["kind"]=V::Text(IDL);value.object["phase"]=V::Number(2);value.object["context"]=ContextJson(ready.context);value.object["resources"]=std::move(resource);out=std::move(value);return true;
}
}
