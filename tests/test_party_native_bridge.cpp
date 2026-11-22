#include "../src/party_native_bridge_plan.h"
#include <cassert>
#include <iostream>
using namespace party_native_bridge;
static Hex64 digest(char c){Hex64 d{};std::memset(d.text,c,64);return d;}
static Context context(){Context c{};c.native={55,7};std::strcpy(c.engine,"uo");std::strcpy(c.variant,"united_fronts");std::strcpy(c.map,"brecourt");c.party=digest('a');c.catalog=digest('b');c.package=digest('c');c.world=digest('d');c.plan=digest('e');c.resource=digest('f');c.revision=3;return c;}
static Roster roster(){Roster r{};r.count=4;r.confirmed=15;for(unsigned i=0;i<4;++i){r.member[i].slot=i;r.member[i].guid=digest(char('1'+i));}return r;}
static NativeReady ready(Context c){return {c,3,3,true,true};}
static bool seal(const char*,size_t,Hex64& out){out=digest('9');return true;} // transaction oracle, not a cryptographic test
int main(int argc,char**argv){
 using namespace party_native_json;
 auto ctx=context();auto members=roster();Store state{};assert(Activate(state,55));assert(Valid(ctx)&&Valid(members));
 Endpoint target{0x7f000001,28960},peer{0xc0000202,30000};Challenge c{};
 auto notReady=ready(ctx);notReady.preInitPlanSerial=0;
 assert(!Issue(state,notReady,members,0,members.member[2].guid,digest('5'),digest('6'),target,peer,20,100000,c)&&state.nextSerial==0);
 notReady=ready(ctx);notReady.phase2=false;
 assert(!Issue(state,notReady,members,0,members.member[2].guid,digest('5'),digest('6'),target,peer,20,100000,c));
 assert(Issue(state,ready(ctx),members,0,members.member[2].guid,digest('5'),digest('6'),target,peer,0xfffffff0,100000,c));
 assert(c.serial==1&&c.index==0&&Seal(state,0,seal));
 if(argc==2&&std::string(argv[1])=="--canonical") {std::string out;assert(Canonical(c,out));std::cout<<out;return 0;}
 // Invalid identity cannot be confused with the first available native seat.
 assert(!Issue(state,ready(ctx),members,1,members.member[0].guid,digest('7'),digest('6'),target,peer,20,100000,c));
 assert(!Issue(state,ready(ctx),members,1,digest('0'),digest('7'),digest('6'),target,peer,20,100000,c));
 auto pending=state.pending[0].challenge;Ack ack{pending,state.pending[0].canonicalSha};int slot=-1;
 assert(!Consume(state,0,ack,ready(ctx),members,peer,20,false,slot));
 auto bad=ack;bad.challenge.clientNonce=digest('7');assert(!Consume(state,0,bad,ready(ctx),members,peer,20,true,slot));
 bad=ack;bad.challenge.guid=members.member[1].guid;assert(!Consume(state,0,bad,ready(ctx),members,peer,20,true,slot));
 bad=ack;bad.canonicalSha=digest('7');assert(!Consume(state,0,bad,ready(ctx),members,peer,20,true,slot));
 auto changed=ctx;changed.revision++;assert(!Consume(state,0,ack,ready(changed),members,peer,20,true,slot));
 auto swapped=members;std::swap(swapped.member[1].guid,swapped.member[2].guid);assert(!Consume(state,0,ack,ready(ctx),swapped,peer,20,true,slot));
 auto newInit=ready(ctx);newInit.nativeInitSerial=newInit.preInitPlanSerial=4;assert(!Consume(state,0,ack,newInit,members,peer,20,true,slot));
 changed=ctx;changed.native.generation++;assert(!Consume(state,0,ack,ready(changed),members,peer,20,true,slot));
 assert(!Consume(state,0,ack,ready(ctx),members,{peer.address,(uint16_t)(peer.port+1)},20,true,slot));
 assert(!Consume(state,0,ack,ready(ctx),members,peer,30000,true,slot));
 assert(Consume(state,0,ack,ready(ctx),members,peer,20,true,slot)&&slot==2);
 assert(!Consume(state,0,ack,ready(ctx),members,peer,21,true,slot)&&slot==-1);
 // Replacing an index obtains a strictly higher serial. Old receipt stays dead.
 assert(Issue(state,ready(ctx),members,0,members.member[2].guid,digest('7'),digest('8'),target,peer,30,100001,c)&&c.serial==2);
 assert(Seal(state,0,seal));assert(!Consume(state,0,ack,ready(ctx),members,peer,31,true,slot));
 // Global serials may finish out of order across independent indices.
 Challenge other{};assert(Issue(state,ready(ctx),members,1,members.member[1].guid,digest('8'),digest('6'),target,peer,30,100001,other));
 assert(Seal(state,1,seal));Ack a2{other,state.pending[1].canonicalSha};assert(Consume(state,1,a2,ready(ctx),members,peer,32,true,slot)&&slot==1);
 Ack a1{c,state.pending[0].canonicalSha};assert(Consume(state,0,a1,ready(ctx),members,peer,32,true,slot)&&slot==2);
 // Repeated worker activation cannot reset the native serial or consume fence.
 auto before=state.nextSerial;assert(Activate(state,55)&&state.nextSerial==before);assert(!Consume(state,0,a1,ready(ctx),members,peer,33,true,slot));
 assert(Activate(state,56)&&!state.pending[0].present&&state.nextSerial==0);
 assert(!Issue(state,ready(ctx),members,0,members.member[1].guid,digest('7'),digest('8'),target,peer,33,100001,c));
 // Socket receipt is authenticated by local intent; a GUID alone is insufficient.
 ClientIntent intent{};intent.context=ctx;intent.guid=pending.guid;intent.clientNonce=pending.clientNonce;intent.target=target;intent.issuedTick=0xfffffff0;intent.active=true;intent.nativePhase2=true;intent.catalogAndAllKitsVerified=true;intent.resourceSerial=9;intent.nativeInitSerial=intent.preInitPlanSerial=3;
 assert(ReceivedOnOwnSocket(intent,pending,target,20,ready(ctx),9));
 assert(!ReceivedOnOwnSocket(intent,pending,peer,20,ready(ctx),9));
 auto foreign=pending;foreign.clientNonce=digest('7');assert(!ReceivedOnOwnSocket(intent,foreign,target,20,ready(ctx),9));
 auto oldIntent=intent;oldIntent.context.native.generation--;assert(!ReceivedOnOwnSocket(oldIntent,pending,target,20,ready(ctx),9));
 oldIntent=intent;oldIntent.nativePhase2=false;assert(!ReceivedOnOwnSocket(oldIntent,pending,target,20,ready(ctx),9));
 assert(!ReceivedOnOwnSocket(intent,pending,target,20,ready(ctx),10));
 assert(!ReceivedOnOwnSocket(intent,pending,target,20,newInit,9));
 Value client;assert(ClientJson(intent,pending,target,20,100000,ready(ctx),9,client));
 assert(client.object["intent"].object.size()==15&&client.object["received_challenge"].object.size()==23);
 // Reconstruct exact wire/local JSON, including one-use ACK envelope.
 Value json;assert(ChallengeJson(pending,json));std::string canonical;assert(party_native_json::Canonical(json,canonical));
 Value parsed;assert(Parse(canonical,parsed));Challenge again{};assert(ParseChallenge(parsed,again)&&Same(again,pending));
 parsed.object["unexpected"]=Value::Number(1);assert(!ParseChallenge(parsed,again));
 auto wrapper=Value::Dict();wrapper.object["schema"]=Value::Number(1);wrapper.object["kind"]=Value::Text(IDL);wrapper.object["decision"]=Value::Text("approve");wrapper.object["challenge"]=json;wrapper.object["challenge_sha256"]=Value::Text(digest('9').text);wrapper.object["owner_public"]=Value::Text(std::string(64,'a'));wrapper.object["owner_signature"]=Value::Text(std::string(128,'b'));
 std::string encoded;assert(party_native_json::Canonical(wrapper,encoded));Ack decoded{};assert(ParseAck(encoded,decoded)&&Same(decoded.challenge,pending));
 wrapper.object["decision"]=Value::Text("approve;quit");assert(party_native_json::Canonical(wrapper,encoded)&&!ParseAck(encoded,decoded));
 Endpoint e{};assert(ParseEndpoint("192.0.2.7:28960",e)&&EndpointText(e)=="192.0.2.7:28960");
 for(auto badEndpoint:{"192.00.2.7:28960","192.0.2.7:0","192.0.2.7:65536","192.0.2.7:28960;quit","0.0.0.0:28960"})assert(!ParseEndpoint(badEndpoint,e));
 for(auto invalid:{"{\"a\":1,\"a\":2}","{\"a\":1,\"\\u0061\":2}","{\"a\":01}","{\"a\":1.0}","{\"a\":18446744073709551616}","{\"a\":true,}","[1,]","{\"a\":\"\\ud800\"}","nullX"})assert(!Parse(invalid,parsed));
 assert(Parse("{\"z\":-0,\"a\":\"\\u0061\\n\"}",parsed));assert(party_native_json::Canonical(parsed,encoded)&&encoded=="{\"a\":\"a\\n\",\"z\":0}");
 assert(!Parse(std::string(20,'[')+std::string(20,']'),parsed));assert(!Parse(std::string(MAX_BYTES+1,' '),parsed));
 auto unterminated=ctx;std::memset(unterminated.engine,'u',sizeof unterminated.engine);assert(!Valid(unterminated));
 unterminated=ctx;std::memset(unterminated.variant,'u',sizeof unterminated.variant);assert(!Valid(unterminated));
 assert(Parse("\"\\u007f\"",parsed)&&party_native_json::Canonical(parsed,encoded)&&encoded=="\"\\u007f\"");
 Store campaign{};assert(Activate(campaign,55));
 for(unsigned i=1;i<=1100;++i){unsigned index=i%3;auto evolving=ctx;evolving.native.generation=i;Challenge issued{};Hex64 nonce{};std::strcpy(nonce.text,FixedHex(i,64).c_str());
  assert(Issue(campaign,ready(evolving),members,index,members.member[index+1].guid,nonce,digest('6'),target,peer,i*100,100000+i,issued));
  assert(issued.serial==i&&Seal(campaign,index,seal));Ack reply{issued,campaign.pending[index].canonicalSha};
  assert(Consume(campaign,index,reply,ready(evolving),members,peer,i*100+1,true,slot)&&slot==int(index+1));
 }
 assert(campaign.nextSerial==1100);campaign.nextSerial=UINT64_MAX;
 assert(!Issue(campaign,ready(ctx),members,0,members.member[1].guid,digest('7'),digest('8'),target,peer,120000,200000,c));
 Plan heartbeatPlan{};heartbeatPlan.party=ctx.party;heartbeatPlan.planSha=ctx.plan;heartbeatPlan.workerPid=123;heartbeatPlan.updatedUnix=100000;heartbeatPlan.expiresUnix=105000;
 Heartbeat fence{};auto process=[](uint32_t pid){return pid==123;};
 assert(FreshWorker(fence,heartbeatPlan,0xfffffff0,100001,process));
 assert(FreshWorker(fence,heartbeatPlan,20,100002,process));
 assert(!FreshWorker(fence,heartbeatPlan,6000,100001,process)); // UTC rollback cannot reset monotone budget
 auto oldHeartbeat=heartbeatPlan;oldHeartbeat.updatedUnix--;assert(!FreshWorker(fence,oldHeartbeat,30,100002,process));
 assert(!FreshWorker(fence,heartbeatPlan,30,105000,process));
 assert(!FreshWorker(fence,heartbeatPlan,30,100003,[](uint32_t){return false;}));
 heartbeatPlan.updatedUnix=103000;heartbeatPlan.expiresUnix=108000;assert(FreshWorker(fence,heartbeatPlan,7000,103001,process));
}
