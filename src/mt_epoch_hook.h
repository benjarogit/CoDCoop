#pragma once
#include "mt_epoch.h"
#include <cstdio>
#include "hook.h"
#include "patch_ownership.h"
namespace qa_mt_epoch {
using Notify = void(*)(uint32_t);
inline mt_epoch::Counter counter;
inline void(__cdecl* original)();
inline Notify notify;
inline bool enabled;
inline uintptr_t entryAddress = 0x45fab0;
constexpr uintptr_t ENTRY = 0x45fab0;
inline constexpr uint8_t signature[] = {0x56,0x57,0xc7,0x05,0xf0,0x72,0x8f,0x00,0x00,0x74,0x8f,0x00};
inline void __cdecl Intercept()
{
    if (enabled) { uint32_t epoch = counter.Reset(); if (notify) notify(epoch); }
    if (original) original();
}
// UO1.51 only; caller must enforce QA/engine gating. No guard or pool-size change.
// False on detach means a later hook may retain this forwarding callback;
// caller must keep the containing module pinned for the process lifetime.
inline bool Sync(bool on, Notify callback, uintptr_t entry = ENTRY)
{
    if (on) {
        if (original && entry != entryAddress) return false;
        entryAddress = entry;
        notify = callback;
        if (patch_owner::JumpTargets((uint8_t*)entryAddress,(uintptr_t)Intercept)) { enabled = true; return true; }
        if (memcmp((void*)entryAddress, signature, sizeof signature)) return false;
        original = (void(__cdecl*)())hook::Inline(entryAddress,(void*)Intercept,sizeof signature);
        enabled = original != nullptr;
        return enabled;
    }
    enabled = false; notify = nullptr;
    if (!original) return true;
    bool restored = !memcmp((void*)entryAddress,signature,sizeof signature);
    if (patch_owner::JumpTargets((uint8_t*)entryAddress,(uintptr_t)Intercept)) restored = hook::Write(entryAddress,signature,sizeof signature);
    if (!restored) return false;
    VirtualFree((void*)original,0,MEM_RELEASE); original = nullptr; return true;
}
}
