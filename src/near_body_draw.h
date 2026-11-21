#pragma once
#include <cmath>
namespace near_body_draw {
// Conservative same-spawn coincidence only. These are numerical-equality tolerances,
// not body radii, and deliberately do not handle merely nearby teammates.
struct View {
 bool ready=false,thirdPerson=false,movie=false,ownDowned=false,foreignDowned=false;
 int currentClient=-1,expectedClient=-1,pmType=-1,pmFlags=0,foreignFlags=0,health=0,viewLocked=1;
 float camera[3]{},predictedFeet[3]{},snapshotFeet[3]{},foreignFeet[3]{},foreignVelocity[3]{};
 float viewHeight=0,standingHeight=0;
};
inline bool Equal(float a,float b){return std::isfinite(a)&&std::isfinite(b)&&std::fabs(a-b)<=0.01f;}
// Actual native same-spawn deltas measured: 0.198/0.199/0.040 per axis.
// This half-unit coordinate-equivalence bound is deliberately not a body radius.
inline bool SameSpawn(float a,float b){return std::isfinite(a)&&std::isfinite(b)&&std::fabs(a-b)<=0.5f;}
inline bool Suppress(const View& v){
 if(!v.ready||v.expectedClient<0||v.expectedClient>=4||v.thirdPerson||v.movie||v.ownDowned||v.foreignDowned||v.currentClient!=v.expectedClient||v.pmType!=0||v.pmFlags&3||v.foreignFlags&0x60||v.health<=0||v.viewLocked||!Equal(v.viewHeight,v.standingHeight)||v.viewHeight<=0)return false;
 for(unsigned k=0;k<3;++k)
  if(!SameSpawn(v.snapshotFeet[k],v.foreignFeet[k])||!Equal(v.foreignVelocity[k],0)||!Equal(v.camera[k],v.predictedFeet[k]+(k==2?v.viewHeight:0)))return false;
 return true;
}
}
