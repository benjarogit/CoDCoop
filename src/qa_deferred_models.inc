// Deliberately isolated QA prototype. Native byte IDs remain stable until GAME_INIT.
#include "qa_deferred_models.h"
#include "tree_ownership.h"
extern "C" { void* g_qaVMTrampoline; void* g_qaIndexTrampoline; }
void QAPreGameInitHostBodies();
bool g_gameLifecycleReady;
qa_deferred::Ledger g_qaLedger;
uintptr_t g_qaGameBase;
bool g_qaDeferredEnabled, g_qaBorrowEnabled;
tree_owner::Reference g_qaBorrowed[2048];
struct QANativeOwner { uintptr_t slot = 0, tree = 0; unsigned generation = 0; };
QANativeOwner g_qaNativeOwners[2048];
unsigned g_qaBorrowCount;
std::string g_qaLedgerPath;
unsigned g_qaInitCount, g_qaCallsBeforeEnd;
bool g_qaImportedCached;
void QAPersistLedger()
{
    if (g_qaLedgerPath.empty()) return;
    FILE* f = fopen((g_qaLedgerPath + ".tmp").c_str(), "wb");
    if (!f) return;
    for (const auto& e : g_qaLedger.entries) fprintf(f, "%s\n", e.name.c_str());
    fclose(f);
    MoveFileExA((g_qaLedgerPath + ".tmp").c_str(), g_qaLedgerPath.c_str(), MOVEFILE_REPLACE_EXISTING);
}
void QAImportLedger(const std::string& path)
{
    FILE* f = fopen(path.c_str(), "rb"); if (!f) return;
    char buffer[2048]; size_t n; std::string text;
    while ((n = fread(buffer, 1, sizeof buffer, f)) && text.size() <= qa_preload::MAX_BYTES) text.append(buffer, n);
    fclose(f); std::vector<std::string> names;
    if (!qa_preload::Parse(text, names)) { Log("QA deferred: invalid ledger %s", path.c_str()); return; }
    for (const auto& name : names) g_qaLedger.Approve(name);
}
int QAOriginalIndex(const char* name)
{
    int result;
    asm volatile("call *%2" : "=a"(result), "+b"(name) : "r"(g_qaIndexTrampoline) : "ecx", "edx", "memory");
    return result;
}
extern "C" int __cdecl QADeferredIndex(const char* raw, uintptr_t caller)
{
    if (!g_qaDeferredEnabled || !raw || !*raw) return QAOriginalIndex(raw);
    std::string name = QASafeModel(raw);
    if (name.empty()) return QAOriginalIndex(raw);
    ++g_qaCallsBeforeEnd;
    bool loading = *(int*)(g_qaGameBase + 0x307f28) != 0;
    if (loading && g_qaInitCount > 1 && !g_qaImportedCached) {
        g_qaImportedCached = true;
        unsigned primed = 0;
        for (auto& imported : g_qaLedger.entries) {
            if (!imported.cached) imported.cached = g::XModelPrecache(imported.name.c_str() + 7);
            if (imported.cached) ++primed;
        }
        Log("QA deferred: native-init cache reconstruction %u/%u", primed, (unsigned)g_qaLedger.entries.size());
    }
    auto* entry = g_qaLedger.Find(name);
    if (qa_deferred::DiscardOnly(caller - g_qaGameBase) && (loading || (entry && entry->cached))) {
        if (!entry) entry = g_qaLedger.Approve(name);
        if (!entry) return QAOriginalIndex(raw);
        if (!entry->cached) entry->cached = g::XModelPrecache(name.c_str() + 7);
        if (!entry->cached) return QAOriginalIndex(raw);
        ++g_qaLedger.deferrals;
        return 0; // only the six verified void/discard callers enter here
    }
    int present = 0, empty = 0;
    for (int i = 1; i < 256; ++i) {
        const char* old = g::ConfigString(32 + i);
        if (!*old && !empty) empty = i;
        if (!_stricmp(old, name.c_str())) present = i;
    }
    if (!loading && !present && entry && entry->cached && empty) {
        // Only an empty slot: no replacement, guard toggle or ID recycling.
        if (!g_qaLedger.Bind(*entry, empty)) return QAOriginalIndex(raw);
        *(void**)(g_qaGameBase + 0xd2e70 + 4 * empty) = entry->cached;
        g::SV_SetConfigstring(32 + empty, name.c_str());
        *(int*)(g_qaGameBase + 0x307f2c) = 1;
        ++g_qaLedger.lateBindings;
        QAPersistLedger();
        Log("QA deferred late binding id=%d caller=%lx name=%s cumulative=%u", empty,
            (unsigned long)(caller - g_qaGameBase), name.c_str(), g_qaLedger.bindings);
        return empty;
    }
    // Includes unknown late assets (native rejection), all save remaps and body/PS/attachment consumers.
    if (!loading && !present) Log("QA deferred: native late rejection caller=%lx approved=%d cached=%d empty=%d name=%s",
        (unsigned long)(caller - g_qaGameBase), entry != nullptr, entry && entry->cached, empty, name.c_str());
    int id = QAOriginalIndex(raw);
    if (id > 0 && id < 256) {
        entry = g_qaLedger.Approve(name);
        if (entry) {
            entry->cached = *(void**)(g_qaGameBase + 0xd2e70 + 4 * id);
            if (!g_qaLedger.Bind(*entry, id)) Log("QA deferred: ERROR non-monotonic binding %s %d", name.c_str(), id);
        }
    }
    return id;
}
asm(R"(
.intel_syntax noprefix
.globl _Hook_QADeferredIndex
_Hook_QADeferredIndex:
    push dword ptr [esp]
    push ebx
    call _QADeferredIndex
    add esp, 8
    ret
.globl _Hook_QAPreVM
_Hook_QAPreVM:
    pushfd
    pushad
    lea ecx, [esp+40]
    push ecx
    push dword ptr [esp+32]
    call _QABeforeVM
    add esp, 8
    popad
    popfd
    jmp dword ptr [_g_qaVMTrampoline]
.att_syntax
)");
extern "C" void Hook_QADeferredIndex();
extern "C" void Hook_QAPreVM();
extern "C" void __cdecl QABeforeVM(void* vm, const int* args)
{
    if (vm != g::gvm || args[0] != 0) return;
    if(suite::IsQA())Log("QA native GAME_INIT engine=%s arg1=%d arg2=%d save_intent=%d level_time=%d",g::uo?"uo":"cod1",args[1],args[2],args[3],args[4]);
    PreservationBeforeInit(args[3]);
    QUFWorldBeforeInit(args[3]);
    // Cold map loads replace gamex86 before entering GAME_INIT. Install the
    // existing saved-remote compatibility patch before native deserialization,
    // rather than waiting until SpawnServer returns after the load has failed.
    if(S&&S->role==HOST)HookLoad((uint8_t*)GetModuleHandleA(g::GameDll()),true);
    PrepareInventoryGameInit();
    QAPreGameInitHostBodies();
    if (!g_qaDeferredEnabled) {BootPreInit();return;}
    uintptr_t base = (uintptr_t)GetModuleHandleA(g::GameDll());
    if (!base) return;
    constexpr unsigned char signature[] = {0x80,0x3b,0,0x75,3,0x33,0xc0,0xc3};
    uintptr_t entry = base + 0x485d0;
    if (!patch_owner::JumpTargets((uint8_t*)entry, (uintptr_t)Hook_QADeferredIndex)) {
        if (memcmp((void*)entry, signature, 8)) { Log("QA deferred: G_ModelIndex signature mismatch before GAME_INIT"); return; }
        if (g_qaIndexTrampoline && g_qaGameBase != base) { Log("QA deferred: refusing relocated module hot reload"); return; }
        if (g_qaIndexTrampoline) {
            unsigned char patch[8] = {0xe9,0,0,0,0,0x90,0x90,0x90};
            *(int32_t*)(patch+1) = (int32_t)((uintptr_t)Hook_QADeferredIndex-entry-5);
            if (!hook::Write(entry, patch, 8)) return;
        } else g_qaIndexTrampoline = hook::Inline(entry, (void*)Hook_QADeferredIndex, 8);
        if (!g_qaIndexTrampoline) return;
    }
    g_qaGameBase = base;
    for (auto& borrowed : g_qaBorrowed) borrowed = {};
    for (auto& owner : g_qaNativeOwners) owner = {};
    g_qaBorrowCount = 0;
    g_qaLedger = {}; g_qaImportedCached = false; g_qaCallsBeforeEnd = 0; ++g_qaInitCount;
    std::string map = g::CvarString("mapname");
    if (map.empty() || map.find_first_not_of("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-") != std::string::npos) {
        g_qaLedgerPath.clear();
    } else g_qaLedgerPath = suite::GameDir() + "qa-model-ledger-" + map + ".txt";
    if (!g_qaLedgerPath.empty()) QAImportLedger(g_qaLedgerPath);
    QAImportLedger(suite::GameDir() + "qa-deferred-models.txt");
    Log("QA deferred: hooked BEFORE GAME_INIT %u map=%s imported=%u initflag=%d", g_qaInitCount,
        map.c_str(), (unsigned)g_qaLedger.entries.size(), *(int*)(base + 0x307f28));
    BootPreInit();
}
bool HookQADeferred(bool on)
{
    if (on) {
        char value[8] = {};
        bool requested=g::uo&&suite::IsQA()&&GetEnvironmentVariableA("CODCOOP_QA_DEFER_MODELS",value,sizeof value)&&!strcmp(value,"1");
        uintptr_t vmAddress=g::A(0x44f270,0x451570);
        const unsigned char signature[8]={0x8b,0x4c,0x24,0x34,0x8b,0x54,0x24,0x30};
        if(!g_qaVMTrampoline) {
            if(memcmp((void*)vmAddress,signature,8)) {Log("memory: VM_Call signature mismatch");return false;}
            g_qaVMTrampoline=hook::Inline(vmAddress,(void*)Hook_QAPreVM,8);
        }
        g_gameLifecycleReady=g_qaVMTrampoline&&patch_owner::JumpTargets((uint8_t*)vmAddress,(uintptr_t)Hook_QAPreVM);
        g_qaDeferredEnabled=requested&&g_gameLifecycleReady;
        value[0]=0;
        g_qaBorrowEnabled=g_qaDeferredEnabled&&GetEnvironmentVariableA("CODCOOP_QA_BORROW_TREES",value,sizeof value)&&!strcmp(value,"1");
        Log("memory: pre-init lifecycle=%d QA deferred=%d",g_gameLifecycleReady,g_qaDeferredEnabled);
        return g_gameLifecycleReady;
    } else {
        g_gameLifecycleReady = g_qaDeferredEnabled = g_qaBorrowEnabled = false;
        bool retained = false;
        const unsigned char vm[8] = {0x8b,0x4c,0x24,0x34,0x8b,0x54,0x24,0x30};
        const unsigned char index[8] = {0x80,0x3b,0,0x75,3,0x33,0xc0,0xc3};
        if (g_qaVMTrampoline) {
            uintptr_t vmAddress=g::A(0x44f270,0x451570);
            if (patch_owner::JumpTargets((uint8_t*)vmAddress, (uintptr_t)Hook_QAPreVM) && hook::Write(vmAddress, vm, 8)) {
                VirtualFree(g_qaVMTrampoline, 0, MEM_RELEASE); g_qaVMTrampoline = nullptr;
            } else retained = true;
        }
        if (g_qaIndexTrampoline) {
            uintptr_t entry = g_qaGameBase + 0x485d0;
            bool unloaded = (uintptr_t)GetModuleHandleA(g::GameDll()) != g_qaGameBase;
            if (unloaded || (!memcmp((void*)entry, index, 8)) ||
                (patch_owner::JumpTargets((uint8_t*)entry, (uintptr_t)Hook_QADeferredIndex) && hook::Write(entry, index, 8))) {
                VirtualFree(g_qaIndexTrampoline, 0, MEM_RELEASE); g_qaIndexTrampoline = nullptr;
            } else retained = true;
        }
        if (retained) { HMODULE module = nullptr; bool pinned = GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_PIN,
            reinterpret_cast<LPCSTR>(&Hook_QAPreVM), &module); Log("QA deferred: retained chain PIN=%d", pinned); }
    }
    return true;
}
