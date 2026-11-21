#pragma once
#include <cstddef>
#include <cstdint>
#include <cstring>

// Observe the game VM's console trap, not CL_PlayCinematic_f: local menus and
// received peer commands must never become new campaign broadcasts.
namespace campaign_cinematics {
constexpr std::size_t NAME_BYTES = 96;
using Syscall = intptr_t (*)(const intptr_t*);
using Notify = void (*)(const char* name);
inline bool Newer(uint32_t sequence, uint32_t cutoff)
{
    return sequence && (!cutoff || static_cast<int32_t>(sequence - cutoff) > 0);
}

// Both supported game DLLs emit exactly this command from their level-exit
// runner (CoD command callsite RVA 0x1e7fc; UO RVA 0x20d98), via trap
// 0x29 / EXEC_APPEND=2.
// Keep filenames independent of commands and paths received from a peer.
inline bool Parse(const char* command, char (&name)[NAME_BYTES])
{
    name[0] = 0;
    constexpr char prefix[] = "cinematic ";
    if (!command || std::strncmp(command, prefix, sizeof prefix - 1)) return false;
    const char* begin = command + sizeof prefix - 1;
    std::size_t length = 0;
    while (begin[length] && begin[length] != ' ') {
        const unsigned char c = static_cast<unsigned char>(begin[length]);
        if (length >= NAME_BYTES - 1 ||
            !((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
              (c >= '0' && c <= '9') || c == '_' || c == '-' || c == '.')) return false;
        ++length;
    }
    if (length < 5 || std::strstr(begin, "..") ||
        (std::strncmp(begin + length - 4, ".roq", 4) &&
         std::strncmp(begin + length - 4, ".bik", 4))) return false;
    const char* tail = begin + length;
    if (std::strcmp(tail, " 0 force") && std::strcmp(tail, " 0 force\n")) return false;
    std::memcpy(name, begin, length);
    name[length] = 0;
    return true;
}

inline Syscall previous = nullptr;
inline Notify notify = nullptr;
inline void* attached = nullptr;
inline bool notifying = false;

// Native vm_t.systemCall is cdecl(intptr_t*), as used by CgSyscallHook. Engine
// builds are x86; intptr_t also permits native harnesses to check forwarding.
inline intptr_t Intercept(const intptr_t* args)
{
    Syscall original = previous;
    char name[NAME_BYTES];
    if (!notifying && notify && args && args[0] == 0x29 && args[1] == 2 &&
        Parse(reinterpret_cast<const char*>(args[2]), name)) {
        notifying = true;
        notify(name); // copy/send before the engine appends the local command
        notifying = false;
    }
    return original ? original(args) : 0;
}

// Call each frame with the current gvm, on=true only for the authoritative
// host. VM recreation discards its former allocation: never touch that old
// address. Preserve an existing plugin's syscall chain without patching code.
inline bool Sync(void* currentVM, bool on, Notify callback)
{
    if (currentVM != attached) {
        attached = currentVM;
        previous = nullptr;
    }
    auto* slot = static_cast<Syscall*>(currentVM);
    if (!on || !callback) {
        notify = nullptr;
        // A later plugin may have retained Intercept in its own chain. Do not
        // erase its forwarding target or claim it is safe to unload our DLL.
        if (slot && previous && *slot != Intercept) return false;
        if (slot && *slot == Intercept) *slot = previous;
        previous = nullptr;
        return true;
    }
    if (!slot || !*slot) return false;
    if (*slot != Intercept) {
        // Re-chaining a later wrapper that already calls us creates recursion.
        if (previous && *slot != previous) return false;
        previous = *slot;
        *slot = Intercept;
    }
    notify = callback;
    return previous != nullptr;
}
} // namespace campaign_cinematics
