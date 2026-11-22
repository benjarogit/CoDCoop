#include "../src/resource_bootstrap_state.h"
#include <cassert>
#include <cstring>
using namespace resource_bootstrap_state;
int main(){
 Store s{};s.nonceCounter=9;s.serialCounter=11;Clear(s);assert(s.epoch==1&&s.nonceCounter==9&&s.serialCounter==11);
 assert(Next(s.nonceCounter)==10);s.nonceCounter=0xffffffff;assert(Next(s.nonceCounter)==1);
 HostPeer h{};h.active=true;h.requestNonce=7;h.last=0xfffffff0;
 assert(AcceptNonce(h,7)&&AcceptNonce(h,8)&&!AcceptNonce(h,6)&&!AcceptNonce(h,0));
 assert(!Expired(h,5,false)&&!Expired(h,400000,true)&&Expired(h,400000,false));
 Peer p{};p.endpoint={0x7f000001,123};p.token={55,7};p.capability=p.token;p.requestNonce=9;
 {Peer zero=p;zero.token={};zero.capability={};assert(!Scope(zero,zero.endpoint,{}));}
 assert(Scope(p,p.endpoint,p.token));assert(!Scope(p,{0x7f000001,124},p.token));assert(!Scope(p,p.endpoint,{55,8}));p.capability={55,6};assert(!Scope(p,p.endpoint,p.token));
 assert(resource_bootstrap_flow::Capability(resource_bootstrap_flow::CAPABILITY,2,6));assert(!resource_bootstrap_flow::Capability(resource_bootstrap_flow::CAPABILITY,1,6));
 resource_bootstrap_flow::Key key{55,7,4,9,0x7f000001,123};resource_bootstrap_flow::Progress progress{};progress.Reset(key);
 assert(!progress.Ack(key,2,true)&&!progress.Allocate(key));
 auto wrong=key;wrong.port=124;assert(!progress.Ack(wrong,1,true));
 wrong=key;wrong.nonce=8;assert(!progress.Ack(wrong,1,true));
 wrong=key;wrong.world=6;assert(!progress.Ack(wrong,1,true));
 assert(!progress.Ack(key,1,false)&&!progress.Ack(key,3,true));
 assert(progress.Ack(key,1,true)&&!progress.Allocate(key));assert(progress.Ack(key,2,true)&&progress.Allocate(key));
 progress.Reset(wrong);assert(!progress.Allocate(key)&&!progress.Ack(key,2,true));
 Receiver r{};asset_bootstrap::Resources resources{{"xmodel/gear_us_carbinebelt"},{{1,"m1garand",true}}};std::string body;uint16_t count=0;
 assert(asset_bootstrap::EncodeResources(resources,body,count));asset_bootstrap::Description d{};d.serial=1;d.bytes=body.size();d.parts=1;d.names=count;d.sha256[0]=1;std::strcpy(d.map,"training");
 assert(r.Start(d));assert(!r.Add(2,0,(const uint8_t*)body.data(),body.size()));assert(!r.Add(1,1,(const uint8_t*)body.data(),body.size()));
 assert(r.Add(1,0,(const uint8_t*)body.data(),body.size()));assert(r.Ready());
 auto bad=d;bad.map[0]='x';assert(!r.Start(bad));asset_bootstrap::Resources out;
 assert(!r.FinishResources(out,[](auto,auto,auto){return false;}));assert(!r.Ready());
 assert(r.Add(1,0,(const uint8_t*)body.data(),body.size()));assert(r.FinishResources(out,[](auto,auto,auto){return true;}));assert(out.weapons[0].name=="m1garand");
 r.Reset();assert(!r.Ready()&&!r.Add(1,0,(const uint8_t*)body.data(),body.size()));
}
