#include "../src/near_body_draw.h"
#include <cassert>
#include <initializer_list>
#include <limits>
int main(){
 near_body_draw::View v{};v.ready=true;v.currentClient=v.expectedClient=1;v.pmType=0;v.health=100;v.viewLocked=0;v.camera[2]=v.viewHeight=v.standingHeight=60;
 assert(near_body_draw::Suppress(v));auto base=v;
 v.currentClient=v.expectedClient=-1;assert(!near_body_draw::Suppress(v));v=base;
 v.currentClient=v.expectedClient=4;assert(!near_body_draw::Suppress(v));v=base;
 v.foreignFeet[0]=.5f;assert(near_body_draw::Suppress(v));v.foreignFeet[0]=.501f;assert(!near_body_draw::Suppress(v));v.foreignFeet[0]=15;assert(!near_body_draw::Suppress(v));v=base;
 v.camera[0]=.1f;assert(!near_body_draw::Suppress(v));v=base;
 v.foreignVelocity[1]=1;assert(!near_body_draw::Suppress(v));v=base;
 v.foreignDowned=true;assert(!near_body_draw::Suppress(v));v=base;
 v.ownDowned=true;assert(!near_body_draw::Suppress(v));v=base;
 for(int flags:{1,2,3,8193}){v.pmFlags=flags;assert(!near_body_draw::Suppress(v));}v=base;
 for(int flags:{0x20,0x40,0x60}){v.foreignFlags=flags;assert(!near_body_draw::Suppress(v));}v=base;
 v.pmType=1;assert(!near_body_draw::Suppress(v));v=base;
 v.pmType=2;assert(!near_body_draw::Suppress(v));v=base;
 v.viewLocked=1;assert(!near_body_draw::Suppress(v));v=base;
 v.thirdPerson=true;assert(!near_body_draw::Suppress(v));v=base;
 v.movie=true;assert(!near_body_draw::Suppress(v));v=base;
 v.currentClient=0;assert(!near_body_draw::Suppress(v));v=base;
 v.health=0;assert(!near_body_draw::Suppress(v));v=base;
 v.viewHeight=40;assert(!near_body_draw::Suppress(v));v=base;
 v.camera[0]=std::numeric_limits<float>::quiet_NaN();assert(!near_body_draw::Suppress(v));
}
