#pragma once
#include "asset_bootstrap.h"
#include "resource_bootstrap_flow.h"
#include "reload_delivery.h"
#include <type_traits>
namespace resource_bootstrap_state {
struct Endpoint {uint32_t address;uint16_t port;};
inline bool Same(Endpoint a,Endpoint b){return a.address==b.address&&a.port&&a.port==b.port;}
// Fixed buffers and receipt metadata only. Native resources are parsed into
// ephemeral containers; no STL ownership or native heap pointer crosses DLLs.
struct Receiver {
 asset_bootstrap::Description description;
 uint8_t data[asset_bootstrap::MAX_BYTES];
 bool received[asset_bootstrap::MAX_PARTS],present;
 uint16_t receivedParts;
 void ClearParts(){std::memset(received,0,sizeof received);receivedParts=0;}
 void Reset(){description={};present=false;ClearParts();}
 const asset_bootstrap::Description& Header()const{return description;}
 bool Start(const asset_bootstrap::Description& d){
  if(!asset_bootstrap::Valid(d))return false;
  if(present&&d.serial==description.serial)return !std::memcmp(&d,&description,sizeof d);
  if(present&&int32_t(d.serial-description.serial)<=0)return false;
  description=d;present=true;ClearParts();return true;
 }
 bool Add(uint32_t serial,unsigned part,const uint8_t* bytes,unsigned size){
  if(!present||serial!=description.serial||part>=description.parts||part>=asset_bootstrap::MAX_PARTS||!bytes)return false;
  unsigned offset=part*asset_bootstrap::PART_BYTES;
  if(size!=std::min(asset_bootstrap::PART_BYTES,description.bytes-offset))return false;
  if(received[part])return !std::memcmp(data+offset,bytes,size);
  std::memcpy(data+offset,bytes,size);received[part]=true;++receivedParts;return true;
 }
 bool Ready()const{return present&&receivedParts==description.parts;}
 template<class Verify>bool FinishResources(asset_bootstrap::Resources& out,Verify verify){
  if(!Ready())return false;
  asset_bootstrap::Resources decoded;
  if(!verify(data,description.bytes,description.sha256)||!asset_bootstrap::DecodeResources(data,description.bytes,description.names,decoded)){ClearParts();return false;}
  out=std::move(decoded);return true;
 }
};
struct HostPeer {
 bool active,allocated;
 resource_bootstrap_flow::Progress progress;
 Endpoint endpoint;
 reload_delivery::Token token;
 asset_bootstrap::Description description;
 char body[asset_bootstrap::MAX_BYTES];
 uint32_t sent,last,requestNonce;
};
struct Peer {
 Receiver receiver;
 Endpoint endpoint;
 reload_delivery::Token token,capability;
 bool transferred,loading,itemDone,endDone,nativeReady,failed,requireMapChange;
 uint32_t requestSent,readySent,nativeMap,requestNonce,readyMap,initSerial,gameBase,cgBase;
};
struct Store {HostPeer host[3];Peer peer;uint32_t serialCounter,nonceCounter,epoch;};
inline void Clear(Store& s){for(auto& p:s.host)p={};s.peer={};if(!++s.epoch)++s.epoch;}
inline uint32_t Next(uint32_t& n){if(!++n)++n;return n;}
inline bool Expired(const HostPeer& p,uint32_t now,bool reserved){return p.active&&!reserved&&uint32_t(now-p.last)>300000;}
inline bool AcceptNonce(const HostPeer& p,uint32_t nonce){return nonce&&(!p.active||nonce==p.requestNonce||int32_t(nonce-p.requestNonce)>0);}
inline bool Scope(const Peer& p,Endpoint endpoint,reload_delivery::Token token){
 return p.requestNonce&&reload_delivery::Valid(token)&&Same(p.endpoint,endpoint)&&reload_delivery::Same(p.token,token)&&reload_delivery::Same(p.capability,token);
}
static_assert(std::is_trivial<Store>::value && std::is_trivially_copyable<Store>::value,"bootstrap lifetime belongs to POD State");
static_assert(std::is_standard_layout<Store>::value,"bootstrap POD layout must be inspectable");
}
