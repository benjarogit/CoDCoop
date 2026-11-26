#include "../src/mt_epoch_hook.h"
#include <cassert>
// The original UO instructions reference a fixed address. The linker maps
// this fixture section there before the test runs.
constexpr uintptr_t FixtureBase = 0x8f0000;
constexpr uintptr_t NativeSlot = 0x8f72f0;
constexpr size_t SlotIndex = (NativeSlot - FixtureBase) / sizeof(unsigned);
[[gnu::section(".mtdata"), gnu::used]] static volatile unsigned fixtureData[SlotIndex + 1];
static unsigned calls;
static void Notify(uint32_t epoch) { assert(epoch==2);assert(fixtureData[SlotIndex]==0);++calls; }
static void Jump(unsigned char* at,uintptr_t destination){at[0]=0xe9;*(int32_t*)(at+1)=(int32_t)(destination-(uintptr_t)at-5);}
int main(){
 assert(reinterpret_cast<uintptr_t>(&fixtureData[SlotIndex]) == NativeSlot);
 auto* code=(unsigned char*)VirtualAlloc(nullptr,4096,MEM_RESERVE|MEM_COMMIT,PAGE_EXECUTE_READWRITE);assert(code);
 memcpy(code,qa_mt_epoch::signature,sizeof qa_mt_epoch::signature);code[12]=0x5f;code[13]=0x5e;code[14]=0xc3;
 code[0]=0x90;assert(!qa_mt_epoch::Sync(true,Notify,(uintptr_t)code));assert(code[0]==0x90);code[0]=0x56;
 assert(qa_mt_epoch::Sync(true,Notify,(uintptr_t)code));
 ((void(*)())code)();assert(calls==1&&qa_mt_epoch::counter.value==2&&fixtureData[SlotIndex]==0x8f7400);
 // A later wrapper retains our callback: detachment must fail, and disabled
 // interception must forward the native initializer without notifying again.
 Jump(code+64,(uintptr_t)qa_mt_epoch::Intercept);Jump(code,(uintptr_t)(code+64));
 assert(!qa_mt_epoch::Sync(false,nullptr));fixtureData[SlotIndex]=0;
 ((void(*)())code)();assert(calls==1&&qa_mt_epoch::counter.value==2&&fixtureData[SlotIndex]==0x8f7400);
 Jump(code,(uintptr_t)qa_mt_epoch::Intercept);assert(qa_mt_epoch::Sync(false,nullptr));
 assert(!memcmp(code,qa_mt_epoch::signature,sizeof qa_mt_epoch::signature));
 fixtureData[SlotIndex]=0;((void(*)())code)();assert(fixtureData[SlotIndex]==0x8f7400);
 VirtualFree(code,0,MEM_RELEASE);
}
