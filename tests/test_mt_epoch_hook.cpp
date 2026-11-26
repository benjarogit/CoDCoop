#include "../src/mt_epoch_hook.h"
#include <cassert>
// UO's native instruction references a fixed address. Place a zero-filled
// buffer in the fixed-base test image so that it already owns that address.
constexpr uintptr_t NativeSlot = 0x8f72f0;
[[gnu::used]] static volatile unsigned fixtureData[5 * 1024 * 1024 / sizeof(unsigned)];
static volatile unsigned& NativeValue() {
    return *reinterpret_cast<volatile unsigned*>(NativeSlot);
}
static unsigned calls;
static void Notify(uint32_t epoch) { assert(epoch==2);assert(NativeValue()==0);++calls; }
static void Jump(unsigned char* at,uintptr_t destination){at[0]=0xe9;*(int32_t*)(at+1)=(int32_t)(destination-(uintptr_t)at-5);}
int main(){
 const auto start = reinterpret_cast<uintptr_t>(fixtureData);
 assert(start <= NativeSlot && NativeSlot + sizeof(unsigned) <= start + sizeof(fixtureData));
 auto* code=(unsigned char*)VirtualAlloc(nullptr,4096,MEM_RESERVE|MEM_COMMIT,PAGE_EXECUTE_READWRITE);assert(code);
 memcpy(code,qa_mt_epoch::signature,sizeof qa_mt_epoch::signature);code[12]=0x5f;code[13]=0x5e;code[14]=0xc3;
 code[0]=0x90;assert(!qa_mt_epoch::Sync(true,Notify,(uintptr_t)code));assert(code[0]==0x90);code[0]=0x56;
 assert(qa_mt_epoch::Sync(true,Notify,(uintptr_t)code));
 ((void(*)())code)();assert(calls==1&&qa_mt_epoch::counter.value==2&&NativeValue()==0x8f7400);
 // A later wrapper retains our callback: detachment must fail, and disabled
 // interception must forward the native initializer without notifying again.
 Jump(code+64,(uintptr_t)qa_mt_epoch::Intercept);Jump(code,(uintptr_t)(code+64));
 assert(!qa_mt_epoch::Sync(false,nullptr));NativeValue()=0;
 ((void(*)())code)();assert(calls==1&&qa_mt_epoch::counter.value==2&&NativeValue()==0x8f7400);
 Jump(code,(uintptr_t)qa_mt_epoch::Intercept);assert(qa_mt_epoch::Sync(false,nullptr));
 assert(!memcmp(code,qa_mt_epoch::signature,sizeof qa_mt_epoch::signature));
 NativeValue()=0;((void(*)())code)();assert(NativeValue()==0x8f7400);
 VirtualFree(code,0,MEM_RELEASE);
}
