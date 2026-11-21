// Nucleo del coop (codcoop_core.dll, recargable en caliente por ddraw.dll):
// el host corre la campaña y los demas se conectan como clientes 1..3 de su servidor.
// Transporte UDP propio (el exe solo tiene loopback) + canal de control para lo que el SP
// comparte por memoria entre servidor y cliente (gamestate, estados de entidad, DObj, animaciones).
#include <winsock2.h>
#include <ws2tcpip.h>
#include <cmath>
#include <cstdarg>
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <deque>
#include <vector>
#include "api.h"
#include "actor_eligibility.h"
#include "game.h"
#include "hook.h"
#include "steam.h"
#include "suite_identity.h"
#include "anim_fragments.h"
#include "packet_buffer.h"
#include "cinematics.h"
#include "cinematic_assets.h"
#include "patch_ownership.h"
#include "pregame_gate.h"
#include "host_rules.h"
#include "archive_rules.h"
#include "reload_delivery.h"
#include "world_wire.h"
#include "qa_renderer_preload.h"
#include "qa_dobj_mapping_barrier.h"
#include "mt_epoch_hook.h"
#include "host_body_ownership.h"
#include "host_body_policy.h"
#include "peer_inventory.h"
#include "save_provenance.h"
#include "spawn_ticket.h"
#include "weapon_selection.h"
#include "inventory_preservation.h"
#include "saved_remote_patch.h"

static const CoreApi* g_api;

void Log(const char* fmt, ...)
{
    char b[2048];
    va_list a;
    va_start(a, fmt);
    vsnprintf(b, sizeof b, fmt, a);
    va_end(a);
    if (g_api) g_api->logLine(b);
}

// linea de estado de la ventana "Cooperativo" del menu (ui/coop_popmenu.menu la muestra)
void CoopStatus(const char* fmt, ...)
{
    char b[256];
    va_list a;
    va_start(a, fmt);
    vsnprintf(b, sizeof b, fmt, a);
    va_end(a);
    g::Cvar_Set("ui_coop_status", b);
}

// VM_Call: EAX = vm, 13 argumentos en la pila (ver game.h GameCall). Las direcciones que usan los asm de este
// archivo estan en variables (CoD1 o UO).
extern "C" {
uintptr_t g_addrVMCall = g::A(0x44f270, 0x451570), g_addrAnimKnob = g::A(0x47d8b0, 0x4823e0),
          g_addrAnimUpdate = g::A(0x47ccd0, 0x4817c0), g_addrCgSyscalls = g::A(0x401a50, 0x401b80);
int g_cgEntityTrap = (int)g::A(0xf8, 0xfa);  // trap del cgame que devuelve el entityState del servidor
int g_cgRunServerTrap = (int)g::A(0xfc, 0xfe);
}
asm(R"(
.intel_syntax noprefix
.globl _CallVM
_CallVM:
    push esi
    push edi
    mov eax, [esp+12]
    mov esi, [esp+16]
    sub esp, 52
    mov edi, esp
    mov ecx, 13
    rep movsd
    call dword ptr [_g_addrVMCall]
    add esp, 52
    pop edi
    pop esi
    ret
.att_syntax
)");

namespace {

constexpr uint32_t CTRL = world_wire::CONTROL;
constexpr int CONTROL_HEADER = (int)world_wire::HEADER_BYTES;
enum : uint8_t { M_JOIN = 'J', M_ACCEPT = 'A', M_FULL = 'F', M_CS = 'C', M_CSDONE = 'G', M_ENTS = 'E', M_DOBJ = 'D', M_ANIM = 'N',
                 M_WORLD_READY = 'r', M_DOWNED = 'W', M_RELOAD = 'R', M_MAP = 'M', M_PING = 'P', M_BYE = 'B',
                 M_CINEMATIC = 'v', M_CINEMATIC_ACK = 'a', M_RULES = 'h', M_RULES_ACK = 'i', M_RELOAD_ACK = 't' };
constexpr int ANIM_STATE = 22;  // estado cliente de un XAnimInfo: +0x1c(4) +0x24(2) +0x28..+0x37(16)
constexpr int MAX_PACKET = 1400;

enum Role { NONE, HOST, JOINER };

// host: por slot remoto
struct Remote {
    bool active;
    bool worldReady;
    sockaddr_in addr;
    uint8_t lastEnt[g::MAX_GENTITIES][g::ENTSTATE_MAX];
    DWORD lastSent[g::MAX_GENTITIES];
    uint32_t dobjSig[g::MAX_GENTITIES];  // ultima forma de DObj mandada (0 = sin DObj)
    DWORD dobjSent[g::MAX_GENTITIES];
};

struct MovieControl {
    uint32_t serial;
    char name[campaign_cinematics::NAME_BYTES];
    char map[64];
    DWORD sent[g::MAX_CLIENTS], begun;
    uint8_t ack[g::MAX_CLIENTS]; // 0 queued, 1 playing/played, 2 missing asset
    bool warned;
};

// Todo lo que tiene que sobrevivir a una recarga del nucleo. La memoria la guarda ddraw.dll; si cambia
// el tamaño o STATE_VERSION, el cargador la pone en cero (se pierde la conexion).
struct PendingReload {
    reload_delivery::Pending delivery;
    sockaddr_in address;
    char map[64];
    uint32_t movieCutoff;
};
constexpr uint32_t STATE_VERSION = 18; // completed native-world identity for preservation receipts
struct State {
    int role;
    host_body_owner::Store hostBodies;
    peer_inventory::Store inventories;
    uint64_t inventoryLeaseCounter,loadedInventoryLease[g::MAX_CLIENTS];
    bool inventoryLoading;
    uint32_t spawnTicketCounter,spawnTicket[g::MAX_CLIENTS];
    weapon_selection::Control selection;
    inventory_preservation::Store preservation;
    uint32_t memoryEpoch;
    bool memoryRequired,memoryReady;
    reload_delivery::Token reloadToken;
    PendingReload reloadPending[g::MAX_CLIENTS];
    MovieControl movie;
    host_rules::Control rules;
    uint32_t receivedMovie;
    uint8_t receivedMovieStatus;
    bool movieWorldSuspended;
    SOCKET sock;
    Remote remote[g::MAX_CLIENTS];  // host
    bool god[g::MAX_CLIENTS];       // prueba: vida al maximo
    sockaddr_in host;               // joiner
    DWORD lastJoinTry;
    bool joined, frozen;
    bool compatible;
    DWORD joinStarted;
    bool gamestateReady;
    bool recoveringConnection;
    uint32_t suppressedClientFrames;
    bool waitingForMap;
    int previousLocalWorld;
    DWORD mapLoadStarted;
    char pendingMap[64];
    uint16_t qport;
    int slot;
    int frozenTime;
    char hostMap[64];
    uint8_t* ownTree[g::MAX_GENTITIES];  // arboles de animacion creados por nosotros
    uint8_t* bodyTree[g::MAX_CLIENTS];   // host: arbol del cuerpo del jugador n (0 = sin cuerpo)
    bool downed[g::MAX_CLIENTS];         // host: caido esperando que lo levanten
    float reviveTime[g::MAX_CLIENTS];    // host: segundos que un compañero lleva levantandolo
    char cs[g::MAX_CONFIGSTRINGS][1024];
    uint64_t steamPeer[steam::MAX_PEERS];  // amigos de Steam detras de las direcciones falsas (steam::Addr)
};
State* S;
peer_inventory::Endpoint InventoryEndpoint(const sockaddr_in& peer);
void QueueWeaponSelection(int n,int weapon,bool seed);
void PublishActorEligibility(int only=-1);
inventory_preservation::Identity PreservationIdentity(int n);
void WeaponSelectionTick();
void SelectionUsercmd(int n,uint8_t* cmd,bool local);
struct Reader;
void SelectionPeerMessage(Reader r);
void SelectionResetStatus(int n);
void PreservationIssued(int n);
void PreservationWait(int n,bool keepFresh=false);
void PreservationCommit(int n,bool preserved);
bool PreservationFresh(int n);
void PreservationBeforeInit(int intent);
void PreservationObserveReady();
void PreservationTick();
void PreservationWorld(const char* map);
void HookLoad(uint8_t* game,bool on);
bool SavedRemoteLoadReady();
suite::Identity g_identity{};
bool g_profileReady;
animwire::Assembler g_animAssembler;
bool ConfigureBodyMemory(bool prepared);
void BodyMemoryFailure(const char* reason);
bool PrepareIdentity()
{
    std::string error;
    g_profileReady = suite::LoadIdentity(g::uo, g::CvarString("fs_game"), g_identity, error);
    if (g_profileReady && !ConfigureBodyMemory(!suite::IsQA()||suite::PreparedQA())) return false;
    if (!g_profileReady) {
        Log("suite: %s", error.c_str());
        CoopStatus("%s", error.c_str());
        g::Com_Printf("^1COOP: %s\n", error.c_str());
    }
    return g_profileReady;
}

struct ModelEntry {  // lo que recibe Com_ServerDObjCreate (0x476e00 resuelve tag -> hueso padre); CoD1 sin `extra`
    void* model;
    const char* tag;
    uint16_t flags;
    uint16_t pad;
    int extra;  // UO: distinto de 0 marca el modelo en la mascara DObj+0x18
};
void DObjCreate(const ModelEntry* models, int num, void* tree, int ent, int u12)
{
    if (g::uo) return g::Com_ServerDObjCreate((void*)models, num, tree, ent, u12);
    uint8_t packed[8][12];
    for (int k = 0; k < num && k < 8; ++k) memcpy(packed[k], &models[k], 12);
    g::Com_ServerDObjCreate(packed, num, tree, ent, u12);
}
void ReleaseInfo(uint8_t* tree, uint16_t* slot)
{
    g::XAnimFreeInfo(tree, *slot);
    *slot = 0;
}

int BrokenPathLists(int* lists = nullptr);
void JoinerLeave(const char* why);

// diagnostico: contadores que se vuelcan al log cada 5 s
int g_statSnaps, g_statEnts, g_statRecv, g_statCtrl;
uint32_t g_staleWorldPackets, g_untaggedEnginePackets, g_taggedEngineSent, g_taggedEngineReceived;
uint32_t g_staleWorldTypes[256];
void StaleWorldPacket(uint8_t type) { ++g_staleWorldPackets; ++g_staleWorldTypes[type]; }
void StatsTick()
{
    static DWORD last;
    if (GetTickCount() - last < 5000) return;
    last = GetTickCount();
    if (S->role == HOST) {
        static int lastBad;
        int bad = BrokenPathLists();
        if (bad != lastBad) Log("listas de caminos rotas: %d -> %d", lastBad, bad);
        lastBad = bad;
    }
    if (g_statSnaps || g_statEnts || g_statRecv || g_statCtrl) {
        Log("stats 5s: snaps=%d ents=%d recv=%d ctrl=%d cls.state=%d serverMsgSeq=%d cl.snap(time=%d num=%d)", g_statSnaps,
            g_statEnts, g_statRecv, g_statCtrl, g::cls_state, g::clc_serverMessageSequence, g::cl_snapServerTime, g::cl_snapNum);
        if (uint8_t* cg = (uint8_t*)GetModuleHandleA(g::CgameDll())) {
            uint8_t* snap = *(uint8_t**)(cg + g::A(0x10b8a8, 0x259548));  // cg.snap CURRENT; transition promotes next into this slot
            Log("  cgame %p: cg.snap=%p serverTime=%d nextSnap=%p", cg, snap, snap ? *(int*)(snap + 4) : -1,
                *(void**)(cg + g::A(0x10b8ac, 0x25954c)));
        }
    }
    g_statSnaps = g_statEnts = g_statRecv = g_statCtrl = 0;
}

bool OpenSocket(int port)
{
    if (S->sock != INVALID_SOCKET) return true;
    WSADATA w;
    WSAStartup(MAKEWORD(2, 2), &w);
    S->sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    u_long nb = 1;
    ioctlsocket(S->sock, FIONBIO, &nb);
    int buf = 1 << 20;
    setsockopt(S->sock, SOL_SOCKET, SO_RCVBUF, (char*)&buf, sizeof buf);
    setsockopt(S->sock, SOL_SOCKET, SO_SNDBUF, (char*)&buf, sizeof buf);
    sockaddr_in a{};
    a.sin_family = AF_INET;
    a.sin_port = htons((u_short)port);
    if (bind(S->sock, (sockaddr*)&a, sizeof a) != 0) {
        Log("bind %d fallo: %d", port, WSAGetLastError());
        closesocket(S->sock);
        S->sock = INVALID_SOCKET;
        return false;
    }
    Log("socket UDP en puerto %d", port);
    return true;
}

// IP local (la que ven los demas en la red): se pregunta al sistema cual seria la salida
// (connect UDP no manda nada) y si falla se resuelve el nombre del equipo.
const char* LocalIp()
{
    static char ip[64] = "";
    if (ip[0]) return ip;
    SOCKET s = socket(AF_INET, SOCK_DGRAM, 0);
    if (s != INVALID_SOCKET) {
        sockaddr_in dst{};
        dst.sin_family = AF_INET;
        dst.sin_port = htons(53);
        inet_pton(AF_INET, "8.8.8.8", &dst.sin_addr);
        if (connect(s, (sockaddr*)&dst, sizeof dst) == 0) {
            sockaddr_in self{};
            int len = sizeof self;
            if (getsockname(s, (sockaddr*)&self, &len) == 0)
                inet_ntop(AF_INET, &self.sin_addr, ip, sizeof ip);
        }
        closesocket(s);
    }
    if (!ip[0]) {
        char host[256];
        if (gethostname(host, sizeof host) == 0) {
            addrinfo hints{}, *res = nullptr;
            hints.ai_family = AF_INET;
            if (getaddrinfo(host, nullptr, &hints, &res) == 0 && res) {
                inet_ntop(AF_INET, &((sockaddr_in*)res->ai_addr)->sin_addr, ip, sizeof ip);
                freeaddrinfo(res);
            }
        }
    }
    if (!ip[0]) snprintf(ip, sizeof ip, "your IP");
    return ip;
}

netadr_t ToNet(const sockaddr_in& a)
{
    netadr_t n{};
    n.type = NA_IP;
    memcpy(n.ip, &a.sin_addr, 4);
    n.port = a.sin_port;
    return n;
}

sockaddr_in ToSock(const netadr_t& n)
{
    sockaddr_in a{};
    a.sin_family = AF_INET;
    memcpy(&a.sin_addr, n.ip, 4);
    a.sin_port = n.port;
    return a;
}

// Simulacion de internet (2.8): `coopnet <ms> <perdida%>` -> cvars coop_simlag / coop_simloss. Todo lo que este
// juego manda sale con ese retraso y se pierde con esa probabilidad (para ida y vuelta, en los dos juegos).
struct Delayed {
    DWORD due;
    sockaddr_in to;
    std::vector<uint8_t> data;
};
std::deque<Delayed> g_delayed;

int CvarInt(const char* name)
{
    uint8_t* v = g::Cvar_FindVar(name);
    return v ? *(int*)(v + 0x20) : 0;
}

// por UDP, o por Steam si es la direccion falsa de un amigo de Steam
void RawSend(const sockaddr_in& to, const void* data, int len)
{
    if (steam::IsAddr(to)) steam::Send(steam::IdOf(S->steamPeer, to), data, len);
    else sendto(S->sock, (const char*)data, len, 0, (const sockaddr*)&to, sizeof to);
}

void FlushDelayed(bool all = false)
{
    DWORD now = GetTickCount();
    while (!g_delayed.empty() && (all || (int)(now - g_delayed.front().due) >= 0)) {
        const Delayed& d = g_delayed.front();
        RawSend(d.to, d.data.data(), (int)d.data.size());
        g_delayed.pop_front();
    }
}

void SendTo(const sockaddr_in& to, const void* data, int len)
{
    if (len <= 0 || len > 65536) return;
    int lag = CvarInt("coop_simlag"), loss = CvarInt("coop_simloss");
    if (loss > 0 && rand() % 100 < loss) return;
    if (lag <= 0) {
        FlushDelayed(true);  // si se acaba de apagar, primero lo que quedo en la cola
        RawSend(to, data, len);
        return;
    }
    g_delayed.push_back({GetTickCount() + lag, to, std::vector<uint8_t>((const uint8_t*)data, (const uint8_t*)data + len)});
    FlushDelayed();
}

// Paquete de control: [CTRL][tipo][datos]
struct Writer {
    uint8_t buf[MAX_PACKET + 64];
    int len = 0;
    explicit Writer(uint8_t type, bool tagged = true) {
        Put(&CTRL, 4); buf[len++] = type; Put(&g_identity, sizeof g_identity);
        if (tagged) Put(S->reloadToken);
    }
    void Put(const void* p, int n) { if (!packet::Append(buf, MAX_PACKET, len, p, n)) Log("network: oversized control packet rejected"); }
    template <class T> void Put(T v) { Put(&v, sizeof v); }
};

struct Reader {
    const uint8_t* p;
    const uint8_t* end;
    template <class T> T Get()
    {
        T v{};
        if (!valid || p > end || (size_t)(end - p) < sizeof v) { valid = false; p = end; return v; }
        memcpy(&v, p, sizeof v);
        p += sizeof v;
        return v;
    }
    bool valid = true;
    bool Ok() const { return valid && p <= end; }
};

using ArchiveWriter = void(__cdecl*)(int);
ArchiveWriter g_archiveOriginal;
archive_rules::Swap g_archiveSwap;
bool g_archiveEnabled;
constexpr uint8_t kArchivePrologue[] = {0x81, 0xec, 0x04, 0x04, 0x00, 0x00};
void __cdecl Hook_ArchiveVariables(int file)
{
    bool outer = !g_archiveSwap.active;
    if (outer && g_archiveEnabled && g_api && S && S->rules.saved) {
        archive_rules::Pair fields[3]{};
        const char* local[3];
        for (unsigned i = 0; i < 3; ++i) {
            uint8_t* var = g::Cvar_FindVar(host_rules::Names[i]);
            if (var) fields[i] = {reinterpret_cast<const char**>(var + 4), reinterpret_cast<const char**>(var + 0x0c)};
            local[i] = S->rules.local[i];
        }
        g_archiveSwap.Begin(fields, local);
    }
    if (g_archiveOriginal) g_archiveOriginal(file);
    if (outer) g_archiveSwap.End();
}
bool HookArchiveVariables(bool on)
{
    if (!g::uo) return true;
    uint8_t* entry = (uint8_t*)g::A(0x432750, 0x4344e0);
    if (on) {
        if (patch_owner::JumpTargets(entry, (uintptr_t)Hook_ArchiveVariables)) return g_archiveEnabled = true;
        if (memcmp(entry, kArchivePrologue, sizeof kArchivePrologue)) {
            Log("rules: native archive writer signature/ownership mismatch; cannot safely override local settings");
            return false;
        }
        g_archiveOriginal = (ArchiveWriter)hook::Inline((uintptr_t)entry, (void*)Hook_ArchiveVariables, sizeof kArchivePrologue);
        g_archiveEnabled = g_archiveOriginal != nullptr;
        return g_archiveEnabled;
    }
    g_archiveEnabled = false;
    g_archiveSwap.End();
    if (!g_archiveOriginal) return true;
    bool restored = !memcmp(entry, kArchivePrologue, sizeof kArchivePrologue);
    if (patch_owner::JumpTargets(entry, (uintptr_t)Hook_ArchiveVariables))
        restored = hook::Write((uintptr_t)entry, kArchivePrologue, sizeof kArchivePrologue);
    if (!restored) {
        HMODULE retained = nullptr;
        if (GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_PIN,
                             reinterpret_cast<LPCSTR>(&Hook_ArchiveVariables), &retained))
            Log("rules: retained archive-writer chain preserved; core pinned until process exit");
        else Log("rules: ERROR could not pin retained archive-writer hook (%lu)", GetLastError());
        return false;
    }
    VirtualFree((void*)g_archiveOriginal, 0, MEM_RELEASE); g_archiveOriginal = nullptr;
    return true;
}

host_rules::Values ReadHostRules()
{
    host_rules::Values values;
    if (!g::uo) return values; // CoD1 never loads YAP
    values.sprintScale = strtof(g::CvarString(host_rules::Names[0]), nullptr);
    values.sprintMult = strtof(g::CvarString(host_rules::Names[1]), nullptr);
    values.jumpShot = CvarInt(host_rules::Names[2]) != 0 ? 1u : 0u;
    return values;
}
void SetHostRules(const host_rules::Values& values)
{
    if (!g::uo || g_archiveSwap.active) return;
    char text[64];
    snprintf(text, sizeof text, "%.9g", values.sprintScale); g::Cvar_Set(host_rules::Names[0], text);
    snprintf(text, sizeof text, "%.9g", values.sprintMult); g::Cvar_Set(host_rules::Names[1], text);
    g::Cvar_Set(host_rules::Names[2], values.jumpShot ? "1" : "0");
}
void RestoreHostRules()
{
    if (!host_rules::RestoreLocal(S->rules, [](const char* name, const char* value) { g::Cvar_Set(name, value); })) return;
    Log("rules: restored local YAP gameplay settings");
}
bool ApplyHostRules(uint32_t serial, const host_rules::Values& values)
{
    if (!serial || !host_rules::Valid(values) || (g::uo && !g_archiveEnabled)) return false;
    if (serial == S->rules.received && !host_rules::Same(values, S->rules.accepted)) return false;
    if (serial != S->rules.received && !host_rules::Newer(serial, S->rules.received)) return false;
    // Save exact strings once; failure never leaves a partially saved record.
    if (g::uo && !host_rules::SaveLocal(S->rules, [](const char* name) { return g::CvarString(name); })) return false;
    bool changed = serial != S->rules.received;
    S->rules.accepted = values; S->rules.received = serial;
    SetHostRules(values);
    Writer ack(M_RULES_ACK); ack.Put(serial); SendTo(S->host, ack.buf, ack.len);
    if (changed) Log("rules: applied host sequence %u sprint=%.9g multiplier=%.9g jumpshot=%u", serial,
                     values.sprintScale, values.sprintMult, values.jumpShot);
    return true;
}
void RefreshHostRules()
{
    host_rules::Values values = ReadHostRules();
    if (!S->rules.known || !host_rules::Same(values, S->rules.host)) {
        S->rules.known = true; S->rules.host = values;
        if (!++S->rules.serial) ++S->rules.serial;
        memset(S->rules.ack, 0, sizeof S->rules.ack);
        memset(S->rules.sent, 0, sizeof S->rules.sent);
        Log("rules: host sequence %u sprint=%.9g multiplier=%.9g jumpshot=%u", S->rules.serial,
            values.sprintScale, values.sprintMult, values.jumpShot);
    }
    bool valid = host_rules::Valid(values);
    if (!valid && !S->rules.invalidWarned) {
        CoopStatus("Invalid host YAP gameplay setting. Sprint scale must be nonnegative and both sprint values finite.");
        Log("rules: unsupported host values; new joins rejected and existing peers notified");
    }
    S->rules.invalidWarned = !valid;
}
void HostRulesTick()
{
    if (S->role == HOST) {
        RefreshHostRules();
        DWORD now = GetTickCount();
        for (int n = 1; n < g::MAX_CLIENTS; ++n) {
            if (!S->remote[n].active || S->rules.ack[n] == S->rules.serial || now - S->rules.sent[n] < 250) continue;
            Writer packet(M_RULES); packet.Put(S->rules.serial); packet.Put(S->rules.host);
            SendTo(S->remote[n].addr, packet.buf, packet.len); S->rules.sent[n] = now;
        }
    } else if (S->role == JOINER && S->rules.received && g::uo) {
        if (!S->rules.saved) {
            if (!ApplyHostRules(S->rules.received, S->rules.accepted)) {
                Writer bye(M_BYE); SendTo(S->host, bye.buf, bye.len);
                JoinerLeave("Cannot protect local YAP settings after reloading the core. Restart the game before retrying.");
            }
            return;
        }
        // Local config/console changes cannot override host prediction rules during a session.
        if (!host_rules::Same(ReadHostRules(), S->rules.accepted)) SetHostRules(S->rules.accepted);
    } else if (S->role == NONE && !S->waitingForMap) {
        RestoreHostRules(); S->rules.received = S->rules.required = 0;
    }
}

bool MoviePlaying()
{
    // Stock cl_movieplaying remains zero during the native scripted movie.
    // cls_state=3 and CIN's active handle are the actual playback state; the
    // native stop path resets the handle to -1 (UO 0x40776b).
    return g::cls_state == 3 && *(int*)g::A(0x56ee48, 0x571154) >= 0;
}
void ForgetMovieWorld();

bool MovieAvailable(const char* name)
{
    char member[128]; snprintf(member, sizeof member, "video/%s", name);
    const std::string base = suite::GameDir();
    const char* roots[] = {"Main", g::uo ? "uo" : "Main", g::CvarString("fs_game")};
    unsigned packages = 0;
    for (unsigned root = 0; root < 3; ++root) {
        if (!*roots[root] || (root == 1 && !g::uo)) continue;
        std::string directory = base + roots[root] + "\\";
        DWORD attrs = GetFileAttributesA((directory + member).c_str());
        if (attrs != INVALID_FILE_ATTRIBUTES && !(attrs & FILE_ATTRIBUTE_DIRECTORY)) return true;
        WIN32_FIND_DATAA info{};
        HANDLE search = FindFirstFileA((directory + "*.pk3").c_str(), &info);
        if (search == INVALID_HANDLE_VALUE) continue;
        bool found = false;
        do {
            if (info.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) continue;
            if (++packages > 256) break;
            if (campaign_cinematics::PackageHasMovie((directory + info.cFileName).c_str(), member)) {
                found = true; break;
            }
        } while (FindNextFileA(search, &info));
        FindClose(search);
        if (found) return true;
        if (packages > 256) return false;
    }
    return false;
}

void SendMovie(int n)
{
    Writer w(M_CINEMATIC); w.Put(S->movie.serial);
    w.Put(S->movie.map, sizeof S->movie.map);
    w.Put(S->movie.name, (int)strlen(S->movie.name) + 1);
    SendTo(S->remote[n].addr, w.buf, w.len);
    S->movie.sent[n] = GetTickCount();
}

void HostScriptMovie(const char* name)
{
    if (S->role != HOST) return;
    uint32_t serial = S->movie.serial + 1;
    if (!serial) serial = 1;
    S->movie = MovieControl{};
    S->movie.serial = serial;
    snprintf(S->movie.name, sizeof S->movie.name, "%s", name);
    snprintf(S->movie.map, sizeof S->movie.map, "%s", g::CvarString("mapname"));
    S->movie.begun = GetTickCount();
    Log("cinematic: host script requested %s (sequence %u, asset %s)", name, serial,
        MovieAvailable(name) ? "present" : "MISSING");
    for (int n = 1; n < g::MAX_CLIENTS; ++n)
        if (S->remote[n].active) SendMovie(n);
}

void AckMovie()
{
    Writer ack(M_CINEMATIC_ACK); ack.Put(S->receivedMovie); ack.Put(S->receivedMovieStatus);
    SendTo(S->host, ack.buf, ack.len);
}

void JoinerMovie(Reader r)
{
    uint32_t serial = r.Get<uint32_t>();
    if (!r.Ok() || r.end - r.p < 64 || !memchr(r.p, 0, 64)) return;
    if (_stricmp((const char*)r.p, S->hostMap)) return;
    r.p += 64;
    size_t bytes = (size_t)(r.end - r.p);
    if (!r.Ok() || !serial || !bytes || bytes > campaign_cinematics::NAME_BYTES || r.end[-1] ||
        memchr(r.p, 0, bytes - 1)) return;
    char command[160], name[campaign_cinematics::NAME_BYTES];
    snprintf(command, sizeof command, "cinematic %s 0 force", (const char*)r.p);
    if (!campaign_cinematics::Parse(command, name)) return;
    if (serial == S->receivedMovie) { AckMovie(); return; }
    // Delayed duplicates from an older movie must not interrupt a newer one.
    if (!campaign_cinematics::Newer(serial, S->receivedMovie)) return;
    S->receivedMovie = serial;
    S->receivedMovieStatus = MovieAvailable(name) ? 0 : 2;
    if (S->receivedMovieStatus == 2) {
        Log("cinematic: missing local asset %s; session retained", name);
        CoopStatus("Missing campaign movie %s. Repair the complete suite.", name);
        g::Com_Printf("^1COOP: missing campaign movie %s; repair the complete suite.\n", name);
    } else {
        // Actual two-instance UO playback clears the local world. Retaining
        // its animation block indices caused a post-movie MT_FreeIndex crash.
        // Forget before native cleanup; preserve the party and its control link.
        ForgetMovieWorld();
        // Native CIN_Stop executes local nextmap. Only the host advances the
        // campaign; its normal map load will arrive through M_RELOAD.
        g::Cvar_Set("nextmap", "");
        strcat(command, "\n");
        g::Cbuf_AddText(command);
        Log("cinematic: joiner queued %s (sequence %u)", name, serial);
    }
    AckMovie();
}

#include "save_provenance.inc"

void MovieTick()
{
    campaign_cinematics::observer=S->role==HOST?InventoryFSObserver:nullptr;
    campaign_cinematics::Sync(g::gvm, S->role == HOST, HostScriptMovie);
    if (S->role == JOINER && S->joined && S->receivedMovie && !S->receivedMovieStatus && MoviePlaying()) {
        S->receivedMovieStatus = 1; AckMovie();
        Log("cinematic: joiner playback started (sequence %u)", S->receivedMovie);
    }
    if (S->role != HOST || !S->movie.serial || !*S->movie.name) return;
    DWORD now = GetTickCount();
    for (int n = 1; n < g::MAX_CLIENTS; ++n) {
        if (!S->remote[n].active || S->movie.ack[n]) continue;
        if (now - S->movie.sent[n] >= 250) SendMovie(n);
        if (!S->movie.warned && now - S->movie.begun > 15000) {
            S->movie.warned = true;
            Log("cinematic: waiting for playback acknowledgement; retaining session and retrying");
            CoopStatus("Waiting for campaign movie playback acknowledgement...");
        }
    }
}

const char* SafeStr(const void* p)
{
    return p && !IsBadReadPtr(p, 4) ? (const char*)p : "?";
}

// QA-only evidence harness. No model catalog is read in regular sessions.
using QAEndRegistration = void(__cdecl*)();
QAEndRegistration g_qaEndOriginal;
bool g_qaEndEnabled;
int QAModelCount()
{
    if (suite::IsQA() && g::uo && S && S->role == JOINER && S->joined) {
        int count = 0;
        for (int i = 1; i < 256; ++i) {
            uint16_t h = ((uint16_t*)0x48362d0)[32 + i];
            if (h && *(const char*)(g::sl_pool + h * 8 + 4)) ++count;
        }
        return count;
    }
    if (g::sv_state == 0) return 0;
    int count = 0;
    for (int i = 1; i < 256; ++i) if (*g::ConfigString(32 + i)) ++count;
    return count;
}
std::string QASafeModel(const char* pointer)
{
    if (!pointer) return {};
    MEMORY_BASIC_INFORMATION region{};
    if (!VirtualQuery(pointer, &region, sizeof region) || region.State != MEM_COMMIT ||
        (region.Protect & (PAGE_NOACCESS | PAGE_GUARD))) return {};
    size_t available = (uintptr_t)region.BaseAddress + region.RegionSize - (uintptr_t)pointer;
    size_t length = 0;
    while (length < available && length < 64 && pointer[length]) ++length;
    if (length >= available || length >= 64) return {};
    std::string name(pointer, length);
    if (name.compare(0, 7, "xmodel/")) name = "xmodel/" + name;
    return qa_preload::ValidName(name) ? name : std::string{};
}
#include "qa_deferred_models.inc"

void QAExportModels()
{
    if (!suite::IsQA() || !g::uo || S->role != HOST || g::sv_state != 2 || g::cls_state != 2 || !g::cgvm) return;
    uint8_t* game = (uint8_t*)GetModuleHandleA(g::GameDll());
    if (!game) return;
    static int world = -1, previousCount = -1;
    int id = CvarInt("sv_serverid"), count = QAModelCount();
    if (!count || (world == id && previousCount == count)) return;
    std::vector<std::string> names;
    for (int i = 1; i < 256; ++i) {
        std::string name = QASafeModel(g::ConfigString(32 + i));
        if (!name.empty() && !qa_preload::Add(names, name)) return;
    }
    size_t csNames = names.size();
    uint8_t** definitions = *(uint8_t***)(game + g::G_WEAPONDEFS);
    int weapons = *(int*)(game + g::G_NUMWEAPONS);
    int* registered = (int*)(game + g::G_ITEMREGISTERED);
    if (definitions && weapons >= 0 && weapons < 128 && !IsBadReadPtr(definitions, (weapons + 1) * sizeof(void*))) {
        for (int w = 1; w <= weapons; ++w) {
            if (!registered[w] || !definitions[w] || IsBadReadPtr(definitions[w], 0x18)) continue;
            for (int offset : {0x10, 0x14}) {
                std::string name = QASafeModel(*(char**)(definitions[w] + offset));
                if (!name.empty() && !qa_preload::Add(names, name)) return;
            }
        }
    }
    const auto base = suite::GameDir();
    FILE* file = fopen((base + "qa-model-export.tmp").c_str(), "wb");
    if (!file) return;
    for (const auto& name : names) fprintf(file, "%s\n", name.c_str());
    fclose(file);
    MoveFileExA((base + "qa-model-export.tmp").c_str(), (base + "qa-model-export.txt").c_str(), MOVEFILE_REPLACE_EXISTING);
    file = fopen((base + "qa-model-export.json").c_str(), "wb");
    if (file) {
        fprintf(file, "{\"map\":\"%s\",\"world\":%d,\"game_cs_models\":%d,\"cs_names\":%u,\"total_names\":%u,\"registered_weapons\":%d}\n",
                g::CvarString("mapname"), id, count, (unsigned)csNames, (unsigned)names.size(), weapons);
        fclose(file);
    }
    world = id; previousCount = count;
}
void __cdecl Hook_QAEndRegistration()
{
    if (g_qaEndEnabled && g_api && suite::IsQA()) {
        const auto base = suite::GameDir();
        if (g_qaDeferredEnabled) {
            // Observe native baseline/restore reservations too; never rewrite them.
            for (int i = 1; i < 256; ++i) {
                std::string name = QASafeModel(g::ConfigString(32 + i));
                if (name.empty()) continue;
                if (auto* entry = g_qaLedger.Approve(name)) {
                    entry->cached = *(void**)(g_qaGameBase + 0xd2e70 + 4 * i);
                    if (!g_qaLedger.Bind(*entry, i)) Log("QA deferred: ERROR native CS binding conflict %s %d", name.c_str(), i);
                }
            }
            int before = QAModelCount(), loaded = 0;
            int strict = CvarInt("r_errorOnConflicts"), closed = *(int*)0x47a91a4, allowance = *(int*)0x47a91a0;
            if (strict == 1 && (!closed || allowance > 0)) {
                for (auto& entry : g_qaLedger.entries) {
                    int handle = ((int(__cdecl*)(const char*, int))0x4fda70)(entry.name.c_str(), 7);
                    if (handle <= 0 || handle >= 2048) break;
                    if (!entry.cached) entry.cached = g::XModelPrecache(entry.name.c_str() + 7);
                    if (entry.cached) ++loaded;
                }
            }
            QAPersistLedger();
            FILE* audit = fopen((base + "qa-deferred-models.json").c_str(), "wb");
            if (audit) {
                fprintf(audit, "{\"map\":\"%s\",\"init_count\":%u,\"calls_before_end\":%u,\"approved\":%u,\"loaded\":%d,\"deferred\":%u,\"bound_cumulative\":%u,\"late_bindings\":%u,\"cs_before\":%d,\"cs_after\":%d,\"strict\":%d,\"guards_unchanged\":%s}\n",
                    g::CvarString("mapname"), g_qaInitCount, g_qaCallsBeforeEnd, (unsigned)g_qaLedger.entries.size(), loaded,
                    g_qaLedger.deferrals, g_qaLedger.bindings, g_qaLedger.lateBindings, before, QAModelCount(), strict,
                    strict == CvarInt("r_errorOnConflicts") && closed == *(int*)0x47a91a4 && allowance == *(int*)0x47a91a0 ? "true" : "false");
                fclose(audit);
            }
            Log("QA deferred before EndRegistration: calls=%u approved=%u loaded=%d deferred=%u bound=%u CS=%d->%d",
                g_qaCallsBeforeEnd, (unsigned)g_qaLedger.entries.size(), loaded, g_qaLedger.deferrals, g_qaLedger.bindings, before, QAModelCount());
        }
        FILE* local = fopen((base + "qa-model-local-at-end.txt").c_str(), "wb");
        if (local) {
            for (int i = 1; i < 256; ++i) if (*g::ConfigString(32 + i)) fprintf(local, "%s\n", g::ConfigString(32 + i));
            fclose(local);
        }
        FILE* file = fopen((base + "qa-render-models.txt").c_str(), "rb");
        if (file) {
            std::string text; char chunk[2048]; size_t got;
            while ((got = fread(chunk, 1, sizeof chunk, file)) && text.size() <= qa_preload::MAX_BYTES) text.append(chunk, got);
            fclose(file);
            std::vector<std::string> names;
            bool valid = qa_preload::Parse(text, names);
            int before = QAModelCount(), rendererBefore = *(int*)0x47abb58;
            int closedBefore = *(int*)0x47a91a4, allowanceBefore = *(int*)0x47a91a0, strictBefore = CvarInt("r_errorOnConflicts");
            bool allowed = strictBefore == 1 && (!closedBefore || allowanceBefore > 0);
            unsigned loaded = 0;
            if (valid && allowed) {
                for (const auto& name : names) {
                    int handle = ((int(__cdecl*)(const char*, int))0x4fda70)(name.c_str(), 7);
                    if (handle <= 0 || handle >= 2048) break;
                    ++loaded;
                }
            }
            int after = QAModelCount(), rendererAfter = *(int*)0x47abb58;
            bool missingFixture = true;
            for (int i = 1; i < 256; ++i) if (!_stricmp(g::ConfigString(32 + i), "xmodel/v_rs_air_il2")) missingFixture = false;
            bool guards = closedBefore == *(int*)0x47a91a4 && allowanceBefore == *(int*)0x47a91a0 && strictBefore == CvarInt("r_errorOnConflicts");
            file = fopen((base + "qa-render-preload.json").c_str(), "wb");
            if (file) {
                fprintf(file, "{\"map\":\"%s\",\"valid_catalog\":%s,\"native_loading_allowed\":%s,\"names\":%u,\"loaded\":%u,\"game_cs_before\":%d,\"game_cs_after\":%d,\"renderer_before\":%d,\"renderer_after\":%d,\"closed_before\":%d,\"allowance_before\":%d,\"strict_guard\":%d,\"guards_unchanged\":%s,\"fixture_missing_local_cs\":%s}\n",
                        g::CvarString("mapname"), valid ? "true" : "false", allowed ? "true" : "false", (unsigned)names.size(), loaded,
                        before, after, rendererBefore, rendererAfter, closedBefore, allowanceBefore, strictBefore, guards ? "true" : "false", missingFixture ? "true" : "false");
                fclose(file);
            }
            Log("QA cache-only preload: %u/%u models, game CS %d -> %d, renderer %d -> %d, closed=%d allowance=%d strict=%d unchanged=%d",
                loaded, (unsigned)names.size(), before, after, rendererBefore, rendererAfter, closedBefore, allowanceBefore, strictBefore, guards);
        }
    }
    if (g_qaEndOriginal) g_qaEndOriginal();
}
void HookQAEndRegistration(bool on)
{
    if (!g::uo || (!suite::IsQA() && on)) return;
    constexpr uintptr_t entry = 0x4fdc10;
    const uint8_t expected[] = {0xe8, 0x6b, 0x7d, 0xfd, 0xff}; // call 0x4d5980; relocated in trampoline
    if (on) {
        if (patch_owner::JumpTargets((uint8_t*)entry, (uintptr_t)Hook_QAEndRegistration)) { g_qaEndEnabled = true; return; }
        if (memcmp((void*)entry, expected, sizeof expected)) { Log("QA preload: EndRegistration signature mismatch"); return; }
        uint8_t* trampoline = (uint8_t*)VirtualAlloc(nullptr, 10, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
        if (!trampoline) return;
        trampoline[0] = 0xe8; *(int32_t*)(trampoline + 1) = (int32_t)(0x4d5980 - ((uintptr_t)trampoline + 5));
        trampoline[5] = 0xe9; *(int32_t*)(trampoline + 6) = (int32_t)(entry + 5 - ((uintptr_t)trampoline + 10));
        uint8_t patch[5] = {0xe9}; *(int32_t*)(patch + 1) = (int32_t)((uintptr_t)Hook_QAEndRegistration - entry - 5);
        g_qaEndOriginal = (QAEndRegistration)trampoline;
        if (!hook::Write(entry, patch, sizeof patch)) { VirtualFree(trampoline, 0, MEM_RELEASE); g_qaEndOriginal = nullptr; return; }
        g_qaEndEnabled = true;
    } else {
        g_qaEndEnabled = false;
        if (!g_qaEndOriginal) return;
        bool restored = !memcmp((void*)entry, expected, sizeof expected);
        if (patch_owner::JumpTargets((uint8_t*)entry, (uintptr_t)Hook_QAEndRegistration)) restored = hook::Write(entry, expected, sizeof expected);
        if (restored) { VirtualFree((void*)g_qaEndOriginal, 0, MEM_RELEASE); g_qaEndOriginal = nullptr; }
        else {
            HMODULE retained = nullptr;
            GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_PIN,
                               reinterpret_cast<LPCSTR>(&Hook_QAEndRegistration), &retained);
            Log("QA preload: later EndRegistration wrapper retained; forwarding core pinned");
        }
    }
}

// ---------- host ----------

int FindSlot(const sockaddr_in& from)
{
    for (int n = 1; n < g::MAX_CLIENTS; ++n)
        if (S->remote[n].active && S->remote[n].addr.sin_addr.s_addr == from.sin_addr.s_addr &&
            S->remote[n].addr.sin_port == from.sin_port)
            return n;
    return -1;
}

// M_CS en varios paquetes y M_CSDONE con cuantos configstrings con texto son: si al remoto le falta alguno (UDP)
// no entra y su reintento de M_JOIN (cada 1 s) hace que se mande todo de nuevo; junta lo que llega de cada vez.
void SendGamestate(int n)
{
    const sockaddr_in& to = S->remote[n].addr;
    Writer w(M_CS);
    uint16_t packets = 0, strings = 0;
    for (int i = 0; i < g::MAX_CONFIGSTRINGS; ++i) {
        const char* s = g::ConfigString(i);
        int l = (int)strlen(s);
        if (!l) continue;
        ++strings;
        if (l > 1000) l = 1000;  // shortcut: los configstrings del SP no pasan de 1 KB, si aparece uno mas largo se trunca
        if (w.len + 4 + l > MAX_PACKET) {
            SendTo(to, w.buf, w.len);
            ++packets;
            w = Writer(M_CS);
        }
        w.Put<uint16_t>((uint16_t)i);
        w.Put<uint16_t>((uint16_t)l);
        w.Put(s, l);
    }
    SendTo(to, w.buf, w.len);
    ++packets;
    Writer done(M_CSDONE);
    done.Put<uint16_t>(strings);
    SendTo(to, done.buf, done.len);
    Log("host: gamestate para el jugador %d: %d configstrings en %d partes", n, strings, packets);
}

// ClientSpawn (gamex86 0x14900) borra el gclient y no vuelve a poner ps.clientNum (+0x9c): en el SP
// siempre era 0. Con 0, Pmove se choca con su propia entidad (allsolid) y el jugador no se mueve.
void FixClientNum(int n)
{
    if (uint8_t* ps = g::PlayerState(n)) *(int*)(ps + g::PS_CLIENTNUM) = n;
}

// El script de la mision solo arma a level.player: si un remoto no tiene armas (al entrar o al
// reaparecer) recibe el mismo equipo que el host. ps: arma actual, ammo[64], cargador[64], bits de armas, ranuras
// (en UO 128 armas; ver giveweapon gamex86 RVA 0x15020 / UO 0x16c10 y game.h PS_*).
// arma de vehiculo (clase 6 ametralladora / 7 cañon del tanque): no se copia ni cuenta como arma en la mano
bool VehicleWeapon(int w)
{
    uint8_t* game = (uint8_t*)GetModuleHandleA(g::GameDll());
    uint8_t** defs = game ? *(uint8_t***)(game + g::G_WEAPONDEFS) : nullptr;
    if (!defs || w <= 0 || w >= g::MAX_WEAPONS || !defs[w]) return false;
    return g::VehicleClass(*(int*)(defs[w] + g::WD_CLASS));
}

peer_inventory::Endpoint InventoryEndpoint(const sockaddr_in& peer)
{
    return {peer.sin_addr.s_addr, peer.sin_port};
}

void SetCoopCvarChanged(const char* key,const char* value)
{if(strcmp(g::CvarString(key),value))g::Cvar_Set(key,value);}

void PublishSpawnTickets()
{
    char value[32],key[48];
    const auto session=spawn_ticket::Split(S->reloadToken.session);
    const uint32_t parts[]={session.a,session.b,session.c};
    for(int i=0;i<3;++i) {snprintf(key,sizeof key,"coop_spawn_session_%c",'a'+i);snprintf(value,sizeof value,"%u",parts[i]);SetCoopCvarChanged(key,value);}
    for(int n=0;n<g::MAX_CLIENTS;++n) {snprintf(key,sizeof key,"coop_spawn_ticket_%d",n);snprintf(value,sizeof value,"%u",S->spawnTicket[n]);SetCoopCvarChanged(key,value);}
    snprintf(value,sizeof value,"%u",S->reloadToken.generation);SetCoopCvarChanged("coop_spawn_world",value);
}

bool FreshSpawnTicket(int n)
{
    if(!spawn_ticket::Next(S->spawnTicketCounter,S->spawnTicket[n])) {S->spawnTicket[n]=0;PublishSpawnTickets();CoopStatus("Player spawn ticket limit reached. Restart hosting.");return false;}
    PublishSpawnTickets();
    PreservationIssued(n);
    if(n>0)SelectionResetStatus(n);
    Log("inventory: fresh role ticket slot=%d ticket=%u",n,S->spawnTicket[n]);return true;
}

bool UFPlannedSlot(int n)
{
    if(!(g::uo&&g_identity.variant==4&&suite::IsQA()&&n>=0&&n<g::MAX_CLIENTS&&
        !strcmp(g::CvarString("coop_qa_kit_enable"),"1")&&!strcmp(g::CvarString("coop_qa_kit_authority"),"host")&&
        !strcmp(g::CvarString("coop_qa_kit_commit"),"1")&&!strcmp(g::CvarString("coop_qa_kit_status"),"PLAN_VALIDATED"))) return false;
    std::string catalog=g::CvarString("coop_qa_kit_catalog"),epoch=g::CvarString("coop_qa_kit_epoch"),map=g::CvarString("coop_qa_kit_map");
    char mode[48];snprintf(mode,sizeof mode,"coop_qa_kit_%d_mode",n);
    return !catalog.empty()&&!epoch.empty()&&map==g::CvarString("mapname")&&
        catalog==g::CvarString("coop_qa_kit_verified_catalog")&&epoch==g::CvarString("coop_qa_kit_verified_epoch")&&
        !strcmp(g::CvarString(mode),"manual");
}

bool OwnInventoryInstalled(int n)
{
    const auto& record = S->inventories.slots[n];
    return record.installed && peer_inventory::Current(record,n,S->reloadToken,
        InventoryEndpoint(S->remote[n].addr),g::CvarString("mapname"));
}

void CapturePeerInventory(int n, const char* reason, bool restoredCheckpoint=false)
{
    auto& record=S->inventories.slots[n];
    bool observedWorld=g_gameLifecycleReady&&patch_owner::JumpTargets((uint8_t*)g::A(0x44f270,0x451570),(uintptr_t)Hook_QAPreVM);
    if(restoredCheckpoint&&record.reserved&&(!observedWorld||!record.lease||S->loadedInventoryLease[n]!=record.lease)) {
        record.captured=record.installed=false;
        FreshSpawnTicket(n);
        Log("inventory: restored guest ownership unverified slot=%d; fresh-role fallback required",n);
        g::Com_Printf("^3COOP: saved player %d ownership is unverified; returning guest receives a fresh role.\n",n+1);
        CoopStatus("Saved guest ownership is unverified. Returning player %d needs a fresh role.",n+1);
        return;
    }
    uint8_t* ps=g::PlayerState(n);
    if (!ps || !peer_inventory::Current(record,n,S->reloadToken,record.endpoint,g::CvarString("mapname"))) return;
    int weapon=*(int*)(ps+g::PS_WEAPON), viewmodel=*(int*)(ps+g::PS_VIEWMODEL);
    if(weapon<0 || weapon>=g::MAX_WEAPONS || viewmodel<0 || viewmodel>255) {
        record.captured=record.installed=false;
        Log("inventory: invalid native numeric IDs slot=%d weapon=%d viewmodel=%d",n,weapon,viewmodel); return;
    }
    if(peer_inventory::Capture(record,n,S->reloadToken,record.endpoint,g::CvarString("mapname"),
        ps+g::PS_AMMO,g::PS_LOADOUT_END-g::PS_AMMO,weapon,viewmodel))
        Log("inventory: captured own slot=%d weapon=%d viewmodel=%d world=%u reason=%s",n,weapon,viewmodel,S->reloadToken.generation,reason);
}

void RestorePeerInventory(int n)
{
    uint8_t* ps=g::PlayerState(n);
    auto& record=S->inventories.slots[n];
    if(ps && peer_inventory::Restore(record,n,S->reloadToken,InventoryEndpoint(S->remote[n].addr),g::CvarString("mapname"),
        ps+g::PS_AMMO,g::PS_LOADOUT_END-g::PS_AMMO,*(int*)(ps+g::PS_WEAPON),*(int*)(ps+g::PS_VIEWMODEL))) {
        Log("inventory: restored own slot=%d weapon=%d viewmodel=%d world=%u",n,record.weapon,record.viewmodel,S->reloadToken.generation);
        QueueWeaponSelection(n,record.weapon,true);
        PreservationCommit(n,true);
    }
}

void GiveHostLoadout(int n)
{
    if(UFPlannedSlot(n)) return; // host-owned kit adapter supplies this actual actor's fresh role
    if (OwnInventoryInstalled(n)) return; // an intentionally empty owned kit is authoritative too
    uint8_t* host = g::PlayerState(0);
    if (!host) return;
    uint8_t* ps = g::PlayerState(n);
    if (*(int*)(ps + g::PS_WEAPON) || !*(int*)(host + g::PS_WEAPON)) return;  // ya tiene un arma en la mano, o el host tampoco
    if (VehicleWeapon(*(int*)(host + g::PS_WEAPON))) return;                 // el host va en el tanque: ver HostVehicles
    bool none = true;
    for (int i = 0; i < g::MAX_WEAPONS / 32; ++i) none &= !((uint32_t*)(ps + g::PS_WEAPONS))[i];
    if (none) memcpy(ps + g::PS_AMMO, host + g::PS_AMMO, g::PS_LOADOUT_END - g::PS_AMMO);
    *(int*)(ps + g::PS_WEAPON) = *(int*)(host + g::PS_WEAPON);
    Log("jugador %d: recibe el equipo del host (arma %d)", n, *(int*)(ps + g::PS_WEAPON));
}

// Armas que el nivel registro (sus modelos estan cargados): gamex86 +0x12eea0 itemRegistered[arma] (arma =
// item), WeaponDef en *(+0x125650) (cantidad +0x12564c): +4 nombre, +0x74 clase (6/7 no se dan, como en
// giveweapon), +0x198 municion maxima, +0x1a0 indice de municion. ps: +0xf4 municion, +0x2f4 armas (64 bits).
// Devuelve la primera aliada que encuentre, si no cualquiera; 0 si no hay.
int PickLoadedWeapon(uint8_t* game)
{
    uint8_t** defs = *(uint8_t***)(game + g::G_WEAPONDEFS);
    int count = *(int*)(game + g::G_NUMWEAPONS), *registered = (int*)(game + g::G_ITEMREGISTERED);
    static const char* const kPreferred[] = {"ppsh", "mosin", "thompson", "bar", "m1garand", "m1carbine", "sten",
                                             "enfield", "mp40", "mp44", "kar98k", ""};
    for (const char* want : kPreferred)
        for (int w = 1; w <= count && w < g::MAX_WEAPONS; ++w) {
            if (!registered[w] || !defs[w]) continue;
            int cls = *(int*)(defs[w] + g::WD_CLASS);
            const char* name = SafeStr(*(char**)(defs[w] + 4));
            if (!g::VehicleClass(cls) && strstr(name, want)) return w;
        }
    return 0;
}

// como giveweapon (gamex86 0x15020): 0x2000b3e0 lugar libre (ECX arma, EDX ps), 0x2000b000 dar (EAX arma, ESI ps),
// 0x2001a940 municion (EAX ent; arma, cantidad, llenar cargador). Ademas la pone en la mano.
void GiveWeapon(uint8_t* game, int n, int w)
{
    uint8_t* ent = g::Entity(n);
    uint8_t* ps = *(uint8_t**)(ent + g::GE_CLIENT);
    uint8_t* def = (*(uint8_t***)(game + g::G_WEAPONDEFS))[w];
    int slot, ecx = w;
    uint8_t* edx = ps;
    asm volatile("call *%3" : "=a"(slot), "+c"(ecx), "+d"(edx) : "r"(game + g::G_WEAPON_SLOT) : "memory");
    if (!slot) {
        Log("jugador %d: sin lugar para el arma %d", n, w);
        return;
    }
    int eax = w;
    uint8_t* esi = ps;
    if (g::uo)  // UO: el arma va en la pila
        asm volatile("push %0\n\tcall *%2\n\tadd $4, %%esp" : "+a"(eax), "+S"(esi) : "r"(game + g::G_WEAPON_GIVE) : "ecx", "edx", "memory");
    else
        asm volatile("call *%2" : "+a"(eax), "+S"(esi) : "r"(game + g::G_WEAPON_GIVE) : "ecx", "edx", "memory");
    int amount = *(int*)(def + g::WD_MAXAMMO) - *(int*)(ps + g::PS_AMMO + *(int*)(def + g::WD_AMMOINDEX) * 4);
    if (amount > 0) {
        uint8_t* a = ent;
        asm volatile("push %3\n\tpush %2\n\tpush %1\n\tcall *%4\n\tadd $12, %%esp"
                     : "+a"(a)
                     : "g"(w), "g"(amount), "g"(1), "r"(game + g::G_ADD_AMMO)
                     : "ecx", "edx", "memory");
    }
    *(int*)(ps + g::PS_WEAPON) = w;
    Log("jugador %d: recibe el arma %s (%d)", n, SafeStr(*(char**)(def + 4)), w);
}

// coopnet <ms> [perdida%] -> simula internet en lo que manda este juego (0 = normal)
void Cmd_CoopNet()
{
    if (g::cmd_argc < 2) {
        g::Com_Printf("coopnet <ms> [loss%%]  (now: %d ms, %d %%)\n", CvarInt("coop_simlag"), CvarInt("coop_simloss"));
        return;
    }
    g::Cvar_Set("coop_simlag", g::Argv(1));
    g::Cvar_Set("coop_simloss", g::cmd_argc > 2 ? g::Argv(2) : "0");
    Log("coopnet: %d ms de retraso, %d %% de perdida", CvarInt("coop_simlag"), CvarInt("coop_simloss"));
}

// prueba: coopweapons -> armas que el nivel registro
void Cmd_CoopWeapons()
{
    uint8_t* game = (uint8_t*)GetModuleHandleA(g::GameDll());
    if (!game) return;
    uint8_t** defs = *(uint8_t***)(game + g::G_WEAPONDEFS);
    int count = *(int*)(game + g::G_NUMWEAPONS), *registered = (int*)(game + g::G_ITEMREGISTERED);
    for (int w = 1; w <= count && w < g::MAX_WEAPONS; ++w)
        if (defs[w] && registered[w])
            Log("arma %d: %s clase %d mundo %s", w, SafeStr(*(char**)(defs[w] + 4)), *(int*)(defs[w] + g::WD_CLASS),
                SafeStr(*(char**)(defs[w] + g::WD_WORLDMODEL)));
    Log("arma elegida para pasajeros: %d", PickLoadedWeapon(game));
}

// prueba: coopgive <n> <arma> -> el jugador n recibe esa arma (numero de coopweapons) y la pone en la mano
void Cmd_CoopGive()
{
    uint8_t* game = (uint8_t*)GetModuleHandleA(g::GameDll());
    int n = atoi(g::Argv(1)), w = atoi(g::Argv(2));
    if (game && n >= 0 && n < g::MAX_CLIENTS && g::svs_clients && *(int*)(g::Client(n) + g::CL_STATE) == 1 && w > 0)
        GiveWeapon(game, n, w);
}

// Brazos en primera persona (ps+0xac viewmodelIndex): el script del nivel hace setviewmodel solo al jugador 0 y el
// remoto queda con el de por defecto (viewmodel_hands_us), que el nivel no cargo y se ve blanco.
void CopyHostViewmodel(int n)
{
    if (OwnInventoryInstalled(n)) return;
    if (uint8_t* ps = g::PlayerState(n)) *(int*)(ps + g::PS_VIEWMODEL) = *(int*)(g::PlayerState(0) + g::PS_VIEWMODEL);
}

// Brujula: el cgame dibuja a los aliados de la IA desde una tabla de 32 lugares (cgame+0x12601c, 16 bytes c/u: hora,
// x, y, rumbo; se ve si la hora tiene menos de 800 ms) indexada por numero de actor. Los compañeros van en los
// ultimos lugares (31 - jugador); solo chocarian con un aliado de la IA con indice de actor 28 o mas.
void DrawTeamOnCompass(uint8_t mask, const float (*pos)[3], int self)
{
    uint8_t* cg = (uint8_t*)GetModuleHandleA(g::CgameDll());
    if (!cg || g::uo) return;  // UO: tabla de la brujula sin verificar
    int now = *(int*)(cg + 0x11e0a4);  // cg.time
    for (int p = 0; p < g::MAX_CLIENTS; ++p) {
        if (p == self || !(mask >> p & 1)) continue;
        int32_t* slot = (int32_t*)(cg + 0x12601c) + (31 - p) * 4;
        slot[0] = now;
        memcpy(slot + 1, pos[p], 12);
    }
}
uint8_t g_team;                            // remoto: jugadores en el mapa segun el host (mascara)
float g_teamPos[g::MAX_CLIENTS][3];        // x, y, rumbo de cada uno

// diagnostico: cuantas listas de enlaces de caminos (gentity+0x2b6) estan rotas (ver Cmd_CoopLists)
int BrokenPathLists(int* lists)
{
    uint8_t* game = (uint8_t*)GetModuleHandleA(g::GameDll());
    if (!game || !g::sv_gentities || g::uo) return 0;  // UO: nodos de caminos sin ubicar
    uint8_t* nodes = *(uint8_t**)(game + 0x2dc1c0);
    int bad = 0, count = 0;
    for (int e = 0; e < g::sv_numEntities; ++e) {
        uint8_t* ent = g::Entity(e);
        uint16_t head = *(uint16_t*)(ent + 0x2b6), cur = head;
        if (!head) continue;
        ++count;
        int steps = 0;
        do {
            uint16_t next = *(uint16_t*)(nodes + cur * 8 + 6);
            if (!next || *(uint16_t*)(nodes + next * 8 + 4) != cur || ++steps > 4096) { ++bad; break; }
            cur = next;
        } while (cur != head);
    }
    if (lists) *lists = count;
    return bad;
}

void CheckPathLists(const char* when)
{
    int lists, bad = BrokenPathLists(&lists);
    Log("listas de caminos %s: %d, rotas %d", when, lists, bad);
}

// Un checkpoint guardado con remotos los carga como jugadores del juego sin cliente del motor (HookLoad). Con la
// partida ya cargada se desconectan (ClientDisconnect, vmMain 4): el remoto vuelve a entrar como al empezar el nivel.
void HostDropGhosts()
{
    uint8_t* reloading = g::Cvar_FindVar("g_reloading");
    if (g::sv_state != 2 || !g::svs_clients || !g::sv_gameClients || (reloading && *(int*)(reloading + 0x20))) return;
    S->inventoryLoading=false;
    for (int n = 1; n < g::MAX_CLIENTS; ++n) {
        if (S->remote[n].active || *(int*)(g::Client(n) + g::CL_STATE) || !*(int*)(g::PlayerState(n) + g::GC_CONNECTED))
            continue;
        Log("host: el jugador %d vino en el checkpoint sin nadie en ese lugar, se desconecta", n);
        CapturePeerInventory(n,"native restored checkpoint before ghost disconnect",true);
        g::GameCall(4, n);
    }
}

void HostJoin(const sockaddr_in& from, Reader r)
{
    RefreshHostRules();
    if (!host_rules::Valid(S->rules.host)) {
        Writer reject(suite::REJECT);
        const char* why = "Host has an invalid YAP gameplay setting. Ask the host to correct it before joining.";
        reject.Put(why, (int)strlen(why) + 1); SendTo(from, reject.buf, reject.len); return;
    }
    int qport = r.Get<int>(), lastIncoming = r.Get<int>(), serverCmdSeq = r.Get<int>(), relSeq = r.Get<int>();
    if (!r.Ok()) return;
    if (g::sv_state != 2) return;  // sin partida no hay a donde unirse
    if(!SavedRemoteLoadReady()) {
        CoopStatus("Native saved-player compatibility is unavailable. Joining is blocked; check the installed game DLL.");return;
    }
    if(S->preservation.init.valid&&S->preservation.init.intent!=0&&S->preservation.init.intent!=1) {
        CoopStatus("Player join is waiting for recognized native save ownership.");return;
    }
    uint8_t* reloading = g::Cvar_FindVar("g_reloading");
    if (reloading && *(int*)(reloading + 0x20)) return;  // mision fallida: esperar a que cargue el checkpoint
    HostDropGhosts();
    const char* hostMap = g::CvarString("mapname");
    const char* theirMap = r.p < r.end && memchr(r.p, 0, r.end - r.p) ? (const char*)r.p : nullptr;
    if (theirMap && _stricmp(theirMap, hostMap) != 0) {  // que cargue el mapa del host y vuelva (sin ocupar slot)
        Writer w(M_MAP);
        w.Put(hostMap, (int)strlen(hostMap) + 1);
        SendTo(from, w.buf, w.len);
        return;
    }
    int n = FindSlot(from);
    if (n < 0) {
        // Return to the actual reserved seat, irrespective of arrival order.
        for (int i=1;i<g::MAX_CLIENTS;++i)
            if(peer_inventory::Owner(S->inventories.slots[i],i,S->reloadToken.session,InventoryEndpoint(from))) { n=i; break; }
        if(n<0) for (int i = 1; i < g::MAX_CLIENTS; ++i)
            if (!S->inventories.slots[i].reserved && *(int*)(g::Client(i) + g::CL_STATE) == 0) { n = i; break; }
        if (n < 0) {
            Writer w(M_FULL);
            SendTo(from, w.buf, w.len);
            return;
        }
        Remote* rm = &S->remote[n];
        memset(rm, 0, sizeof *rm);
        memset(rm->dobjSig, 0xff, sizeof rm->dobjSig);  // la primera vez se manda todo, incluso "sin DObj"
        rm->active = true;
        rm->addr = from;
        auto& inventory=S->inventories.slots[n];
        if(!peer_inventory::Owner(inventory,n,S->reloadToken.session,InventoryEndpoint(from))) {
            if(!++S->inventoryLeaseCounter) ++S->inventoryLeaseCounter;
            peer_inventory::Reserve(inventory,n,S->reloadToken,InventoryEndpoint(from),hostMap,S->inventoryLeaseCounter);
            if(!FreshSpawnTicket(n)) {rm->active=false;inventory={};return;}
        }

        if(!inventory.captured&&!PreservationFresh(n)) FreshSpawnTicket(n);
        PreservationWait(n,true);
        // como SVC_DirectConnect (0x448d70) pero en el slot n y continuando los contadores del que entra
        uint8_t* cl = g::Client(n);
        memset(cl, 0, g::CLIENT_SIZE);
        uint8_t* nc = cl + g::CL_NETCHAN;
        *(int*)(nc + g::NC_SOCK) = NS_SERVER;
        *(netadr_t*)(nc + g::NC_ADR) = ToNet(from);
        uint16_t assigned = (uint16_t)qport;
        if (!assigned) assigned = 1;
        for (int tries = 0; tries < g::MAX_CLIENTS; ++tries) {
            bool collision = false;
            for (int other = 1; other < g::MAX_CLIENTS; ++other)
                if (other != n && S->remote[other].active && S->remote[other].addr.sin_addr.s_addr == from.sin_addr.s_addr &&
                    *(int*)(g::Client(other) + g::CL_NETCHAN + g::NC_QPORT) == assigned) collision = true;
            if (!collision) break;
            if (!++assigned) assigned = 1;
        }
        *(int*)(nc + g::NC_QPORT) = assigned;
        *(int*)(nc + g::NC_IN) = 0;
        *(int*)(nc + g::NC_OUT) = lastIncoming + 10;  // el cgame del que entra ya vio snapshots hasta ahi
        if (g::uo) {
            g::SV_AllocClientBuffers(cl);
        } else {
            *(int*)(cl + 4) = 0x18000;
            *(void**)(cl + 8) = g::Z_Malloc(0x18000);
            *(void**)(cl + 0x10) = g::Z_Malloc(0x400);
            *(void**)(cl + 0xc) = g::Z_Malloc(0x400);
            *(void**)(cl + 0x14) = *(void**)(cl + 8);
        }
        *(int*)(cl + g::CL_RELSEQ) = *(int*)(cl + g::CL_RELACK) = *(int*)(cl + g::CL_RELSENT) = serverCmdSeq;
        *(int*)(cl + g::CL_LASTCLIENTCMD) = relSeq;
        *(int*)(cl + g::CL_GAMESTATEMSG) = *(int*)(nc + g::NC_OUT);
        *(int*)(cl + g::CL_STATE) = 1;

        // como SV_ClientEnterWorld (0x448e40), que tiene el ClientConnect fijo en 0
        // ClientConnect (gamex86 RVA 0x14800) empieza reiniciando el sistema de caminos de la IA (call 0x6fde0 en
        // RVA 0x14808): en el SP pasa una vez al cargar el mapa. Mas tarde deja a las puertas que bloquean caminos
        // apuntando a nodos liberados, y la carga de partida se cuelga en G_FreeEntity. Para los remotos se saltea.
        uint8_t* game = (uint8_t*)GetModuleHandleA(g::GameDll());
        uint8_t* call = game ? game + g::G_CONNECT_PATHINIT : nullptr;
        uint8_t saved[5] = {};
        bool skip = call && call[0] == 0xE8 && call + 5 + *(int32_t*)(call + 1) == game + g::G_PATHINIT;
        if (skip) {
            memcpy(saved, call, 5);
            hook::Write((uintptr_t)call, "\x0F\x1F\x44\x00\x00", 5);  // nop de 5 bytes
        } else {
            Log("ClientConnect: no se encontro la llamada a la init de caminos; se llama completo");
        }
        g::GameCall(2, n);
        if (skip) hook::Write((uintptr_t)call, saved, 5);
        CheckPathLists("despues de ClientConnect");
        *(uint8_t**)(cl + g::CL_GENTITY) = g::Entity(n);
        *(int*)(cl + g::CL_DELTA) = -1;
        g::GameCall(3, n);
        RestorePeerInventory(n); // ClientConnect/Begin retain their normal native lifecycle
        if(!OwnInventoryInstalled(n)) PreservationCommit(n,false);
        FixClientNum(n);
        // Initial launcher starts do not know how many friends will join. Carry
        // the actual party into the next mission, while preserving a larger
        // participant count already agreed for a supervised restart.
        int party = 1;
        for (int peer = 1; peer < g::MAX_CLIENTS; ++peer) party += S->remote[peer].active ? 1 : 0;
        if (party > CvarInt("coop_expected_players")) {
            char value[8]; snprintf(value, sizeof value, "%d", party);
            g::Cvar_Set("coop_expected_players", value);
        }
        Log("host: jugador remoto %s:%d -> slot %d (qport %d)", inet_ntoa(from.sin_addr), ntohs(from.sin_port), n, qport);
        g::Com_Printf("^2COOP: a player joined (slot %d)\n", n);
    }
    Writer w(M_ACCEPT);
    w.Put<int>(n);
    w.Put<int>(*(int*)(g::Client(n) + g::CL_NETCHAN + g::NC_QPORT));
    w.Put<int>(g::sv_time);
    w.Put(S->reloadToken);
    w.Put(S->rules.serial); w.Put(S->rules.host);
    S->rules.ack[n] = 0; // acceptance must be acknowledged even by a rejoining slot
    const char* map = g::CvarString("mapname");
    w.Put(map, (int)strlen(map) + 1);
    w.Put<uint32_t>(weapon_selection::CAPABILITY);w.Put<uint32_t>(S->spawnTicket[n]);
    SendTo(from, w.buf, w.len);
    SendGamestate(n);
}

// estados de entidad que el SP no manda en el snapshot (el cgame los lee de la memoria del servidor)
void SendEntities(int n)
{
    Remote* rm = &S->remote[n];
    DWORD now = GetTickCount();
    Writer w(M_ENTS);
    int countPos = w.len;
    uint16_t count = 0;
    w.Put<uint16_t>(0);
    auto flush = [&] {
        if (!count) return;
        memcpy(w.buf + countPos, &count, 2);
        SendTo(rm->addr, w.buf, w.len);
        w = Writer(M_ENTS);
        countPos = w.len;
        count = 0;
        w.Put<uint16_t>(0);
    };
    for (int i = 0; i < g::snap_numEntities; ++i) {
        int e = g::snap_entities[i];
        if (e < 0 || e >= g::MAX_GENTITIES) continue;
        const uint8_t* st = g::Entity(e);
        // shortcut: sin acks; lo cambiado va siempre y todo se reenvia cada 1 s por si se perdio un paquete
        if (!memcmp(rm->lastEnt[e], st, g::ENTSTATE_SIZE) && now - rm->lastSent[e] < 1000) continue;
        memcpy(rm->lastEnt[e], st, g::ENTSTATE_SIZE);
        rm->lastSent[e] = now;
        if (w.len + 2 + g::ENTSTATE_SIZE > MAX_PACKET) flush();
        w.Put<uint16_t>((uint16_t)e);
        w.Put(st, g::ENTSTATE_SIZE);
        ++count;
        ++g_statEnts;
    }
    flush();
}

// ---------- DObj y animaciones (el SP los comparte por memoria entre servidor y cliente) ----------

uint32_t DObjSig(const uint8_t* d)
{
    uint32_t h = 2166136261u;
    auto mix = [&](const void* p, int len) {
        for (int i = 0; i < len; ++i) h = (h ^ ((const uint8_t*)p)[i]) * 16777619u;
    };
    uint8_t* tree = *(uint8_t**)d;
    void* xanim = tree ? *(void**)tree : nullptr;
    mix(d + 0x12, 2);
    mix(d + 0x16, 1);
    mix(d + g::DO_MODELS, 0x20);
    mix(d + g::DO_FLAGS, 0x10);
    mix(d + g::DO_PARENTS, 8);
    mix(&xanim, 4);
    return h ? h : 1;
}

void PutStr(Writer& w, const char* s)
{
    int l = (int)strlen(s);
    if (l > 200) l = 200;
    w.Put<uint8_t>((uint8_t)l);
    w.Put(s, l);
}

bool GetStr(Reader& r, char* out, int size)
{
    int l = r.Get<uint8_t>();
    if (!r.Ok() || (size_t)l > (size_t)(r.end - r.p) || l >= size) return false;
    memcpy(out, r.p, l);
    out[l] = 0;
    r.p += l;
    return true;
}

// host: forma del DObj (cuando cambia o cada 2 s) y estado de animacion (cada snapshot) de lo visible.
// Se llama justo despues de SV_SendClientSnapshot, que ya copio el estado servidor -> cliente (0x44d8e0).
void SendDObjs(int n)
{
    Remote* rm = &S->remote[n];
    DWORD now = GetTickCount();
    Writer aw(M_ANIM);
    for (int i = 0; i < g::snap_numEntities; ++i) {
        int e = g::snap_entities[i];
        if (e < 0 || e >= g::MAX_GENTITIES) continue;
        uint8_t* d = g::ServerDObj(e);
        uint32_t sig = d ? DObjSig(d) : 0;
        if (sig != rm->dobjSig[e] || (sig && now - rm->dobjSent[e] > 2000)) {
            Writer w(M_DOBJ);
            int nm = d ? d[0x16] : 0;
            if (nm > 8) nm = 8;
            w.Put<uint16_t>((uint16_t)e);
            w.Put<uint8_t>((uint8_t)nm);
            w.Put<uint16_t>(d ? *(uint16_t*)(d + 0x12) : 0);
            uint8_t* tree = d ? *(uint8_t**)d : nullptr;
            PutStr(w, tree ? SafeStr(**(char***)tree) : "");
            for (int k = 0; k < nm; ++k) {
                uint8_t* model = *(uint8_t**)(d + g::DO_MODELS + k * 4);
                PutStr(w, model ? SafeStr(*(char**)model) : "");
                w.Put<uint8_t>(d[g::DO_PARENTS + k]);
                w.Put<uint16_t>(*(uint16_t*)(d + g::DO_FLAGS + k * 2));
            }
            SendTo(rm->addr, w.buf, w.len);
            rm->dobjSig[e] = sig;
            rm->dobjSent[e] = now;
        }
        uint8_t* tree = d ? *(uint8_t**)d : nullptr;
        if (!tree) continue;
        int size = *(int*)(*(uint8_t**)tree + 4);
        std::vector<uint8_t> states;
        for (int a = 0; a < size && a < animwire::MAX_NODES; ++a) {
            uint16_t idx = *(uint16_t*)(tree + g::TREE_INFO + a * 2);
            if (!idx) continue;
            const uint8_t* info = g::xanimInfo + idx * 0x44;
            size_t offset = states.size(); states.resize(offset + animwire::STATE_BYTES);
            uint16_t node = (uint16_t)a;
            memcpy(states.data() + offset, &node, 2);
            memcpy(states.data() + offset + 2, info + 0x1c, 4);
            memcpy(states.data() + offset + 6, info + 0x24, 2);
            memcpy(states.data() + offset + 8, info + 0x28, 16);
        }
        int total = (int)states.size() / animwire::STATE_BYTES;
        int offset = 0;
        do {
            int room = (MAX_PACKET - aw.len - (int)sizeof(animwire::Header)) / animwire::STATE_BYTES;
            if (room < 1) {
                SendTo(rm->addr, aw.buf, aw.len); aw = Writer(M_ANIM);
                room = (MAX_PACKET - aw.len - (int)sizeof(animwire::Header)) / animwire::STATE_BYTES;
            }
            int count = total - offset < room ? total - offset : room;
            animwire::Header header{(uint16_t)e, (uint16_t)total, (uint16_t)offset, (uint16_t)count, (uint32_t)g::sv_time};
            aw.Put(&header, sizeof header);
            if (count) aw.Put(states.data() + offset * animwire::STATE_BYTES, count * animwire::STATE_BYTES);
            offset += count;
        } while (offset < total);
    }
    if (aw.len > CONTROL_HEADER) SendTo(rm->addr, aw.buf, aw.len);
}

void FreeTreeInfos(uint8_t* tree)
{
    int size = *(int*)(*(uint8_t**)tree + 4);
    for (int a = 0; a < size; ++a) {
        uint16_t* slot = (uint16_t*)(tree + g::TREE_INFO + a * 2);
        if (*slot) ReleaseInfo(tree, slot);
    }
}

// El arbol se libera al final: DObjFree (0x477020) todavia lo usa, y el cliente suelta su referencia
// al DObj recien en Com_SyncClientDObjs.
uint8_t* FindXAnim(const char* name);
bool XAnimLoaded(const uint8_t* xanim)
{
    for (int i = 0; i < 256; ++i)
        if (g::xanimTable[i] == xanim) return true;
    return false;
}

// UO: al recargar el mapa los arboles propios no se liberan con el DObj (el servidor local corre un frame mas y
// los usa), pero tampoco los suelta el motor. Se sueltan sus infos ya, y el bloque con el mapa nuevo cargado
// (JoinerHijack); el tamano se toma ahora, porque despues el XAnim del arbol ya no existe.
struct OldTree { int index, bytes; uint32_t mtEpoch; };
OldTree g_oldTrees[g::MAX_GENTITIES];
int g_oldTreeCount;
void KeepOldTrees()
{
    for (auto& borrowed : g_qaBorrowed) borrowed = {};
    for (auto& owner : g_qaNativeOwners) owner = {};
    for (int e = 0; e < g::MAX_GENTITIES; ++e) {
        uint8_t* tree = S->ownTree[e];
        if (!tree || !XAnimLoaded(*(uint8_t**)tree) || g_oldTreeCount >= g::MAX_GENTITIES) continue;
        FreeTreeInfos(tree);
        g_oldTrees[g_oldTreeCount++] = {(int)(((uintptr_t)tree - g::UO_TREE_BASE) >> 3), g::TreeBytes(*(uint8_t**)tree), qa_mt_epoch::counter.value};
    }
}
void QAMTReset(uint32_t epoch)
{
    if(S) S->memoryEpoch=epoch;
    Log("memory: native MT reset epoch=%u queued_old_trees=%d",epoch,g_oldTreeCount);
}
void BodyMemoryFailure(const char* reason)
{
    Log("memory: ownership protection unavailable: %s",reason);
    CoopStatus("%s",reason);g::Com_Printf("^1COOP: %s\n",reason);
    if(!S) return;
    Writer bye(M_BYE);bye.Put<uint8_t>(1);
    if(S->role==HOST) {
        bye.Put(S->reloadToken);
        for(int n=1;n<g::MAX_CLIENTS;++n) {
            if(S->remote[n].active) SendTo(S->remote[n].addr,bye.buf,bye.len);
            if(S->reloadPending[n].delivery.active) SendTo(S->reloadPending[n].address,bye.buf,bye.len);
        }
    } else if(S->role==JOINER) SendTo(S->host,bye.buf,bye.len);
    bool active=S->role!=NONE;
    S->memoryReady=false;S->hostBodies.count=0;
    memset(S->bodyTree,0,sizeof S->bodyTree);memset(S->ownTree,0,sizeof S->ownTree);g_oldTreeCount=0;
    for(auto& remote:S->remote) remote.active=false;
    S->role=NONE;S->joined=S->frozen=S->waitingForMap=false;
    memset(S->reloadPending,0,sizeof S->reloadPending);
    if(active) g::Cbuf_AddText("disconnect\n");
}
bool ConfigureBodyMemory(bool prepared)
{
    int overrideValue=-1;char flag[8]={};
    if(suite::IsQA()&&GetEnvironmentVariableA("CODCOOP_QA_HOST_BODY_GC",flag,sizeof flag)) {
        if(!strcmp(flag,"0"))overrideValue=0;else if(!strcmp(flag,"1"))overrideValue=1;
        else {BodyMemoryFailure("Invalid QA memory-policy value.");return false;}
    }
    bool required=host_body_policy::Required(g::uo,suite::IsQA(),prepared,overrideValue);
    if(g::uo&&!suite::IsQA()&&!prepared&&(S->memoryRequired||S->hostBodies.count)) {
        BodyMemoryFailure("Cannot verify player-body memory protection after reload. Restart using CoDCoop Launcher.");return false;
    }
    if(!required&&S->hostBodies.count) {
        BodyMemoryFailure("Restart the game before changing player-body memory policy.");return false;
    }
    S->memoryRequired=required;
    qa_mt_epoch::counter.value=S->memoryEpoch?S->memoryEpoch:1;
    S->memoryEpoch=qa_mt_epoch::counter.value;
    bool observe=false;flag[0]=0;
    if(g::uo&&suite::IsQA()&&GetEnvironmentVariableA("CODCOOP_QA_MT_EPOCH",flag,sizeof flag))observe=!strcmp(flag,"1");
    bool allocator=true;
    if(g::uo&&(required||observe))allocator=qa_mt_epoch::Sync(true,QAMTReset);
    bool lifecycle=HookQADeferred(true);
    if(!lifecycle) {BodyMemoryFailure("Required native save-ownership lifecycle hook is unavailable. Restart from CoDCoop Launcher.");return false;}
    S->memoryReady=!required||(allocator&&lifecycle);
    if(!S->memoryReady) {
        BodyMemoryFailure("Required UO memory hooks are unavailable or owned by another plugin. Restart from CoDCoop Launcher.");return false;
    }
    return true;
}
void FreeOldTrees()
{
    if (g_oldTreeCount) Log("joiner: libero %d arboles del mapa anterior", g_oldTreeCount);
    for (int i = 0; i < g_oldTreeCount; ++i) {
        const auto& old = g_oldTrees[i];
        if (qa_mt_epoch::enabled && !mt_epoch::MayFree(old.mtEpoch,qa_mt_epoch::counter.value,(unsigned)old.index,(unsigned)old.bytes)) {
            Log("QA MT discard old tree index=%d bytes=%d epoch=%u current=%u",old.index,old.bytes,old.mtEpoch,qa_mt_epoch::counter.value);
            continue;
        }
        g::UO_FreeTreeBlock(old.index,old.bytes);
    }
    g_oldTreeCount = 0;
}

void ForgetMovieWorld()
{
    S->movieWorldSuspended = true;
    for (auto& borrowed : g_qaBorrowed) borrowed = {};
    for (auto& owner : g_qaNativeOwners) owner = {};
    g_animAssembler.Reset();
    memset(S->ownTree, 0, sizeof S->ownTree);
    g_oldTreeCount = 0; // native movie/map cleanup invalidates these allocator indices
}

void JoinerFreeDObj(int e)
{
    uint8_t* tree = S->ownTree[e];
    auto borrowed = g_qaBorrowed[e];
    g_qaBorrowed[e] = {}; // native Game ownership never enters the Core free path
    S->ownTree[e] = nullptr;
    if (g::serverObjMap[e]) g::Com_ServerDObjFree(e, true);
    g::Com_SyncClientDObjs();
    // un arbol hecho con un XAnim que ya no esta en la tabla (el juego recargo los assets al volver a entrar tras un
    // checkpoint) vive en memoria ya liberada: liberarlo de nuevo rompia el juego (0x45b8f0). Se olvida.
    if (tree && (IsBadReadPtr(tree, 4) || !XAnimLoaded(*(uint8_t**)tree))) {
        Log("dobj %d: arbol de antes de la recarga, se olvida", e);
        return;
    }
    if (g_qaBorrowEnabled) {
        tree_owner::Reference reference = tree_owner::Reference{(uintptr_t)tree, g_qaInitCount, tree_owner::Owner::Core};
        if (!tree || borrowed.tree == (uintptr_t)tree) reference = borrowed;
        tree_owner::ReleaseReference(reference, g_qaInitCount, true, reference.tree != 0, [&](uintptr_t address) {
            auto* owned = (uint8_t*)address;
            FreeTreeInfos(owned); g::XAnimFreeTree(owned);
        });
        return;
    }
    if (tree) {
        FreeTreeInfos(tree);
        g::XAnimFreeTree(tree);
    }
}

uint8_t* FindXAnim(const char* name)
{
    for (int i = 0; i < 256; ++i) {
        uint8_t* x = g::xanimTable[i];
        if (x && !_stricmp(SafeStr(*(char**)x), name)) return x;
    }
    return nullptr;
}

const char* QAModelConfigString(int index)
{
    if (g_qaDeferredEnabled && g::uo && S->role == JOINER && S->joined) {
        uint16_t handle = ((uint16_t*)0x48362d0)[index];
        return handle ? (const char*)(g::sl_pool + handle * 8 + 4) : "";
    }
    return g::ConfigString(index);
}
void QACaptureNativeTrees()
{
    for (auto& owner : g_qaNativeOwners) owner = {};
    if (!g_qaBorrowEnabled || (uintptr_t)GetModuleHandleA(g::GameDll()) != g_qaGameBase ||
        !g::sv_gentities || g::sv_gentitySize != 0x2d0) return;
    unsigned captured = 0;
    for (int e = 0; e < g::MAX_GENTITIES; ++e) {
        uint8_t* ent = g::Entity(e);
        if (!ent[0x11c]) continue;
        uintptr_t slot = (uintptr_t)ent + 0x2c8;
        if (ent[0] == 11) {
            uintptr_t actor = *(uintptr_t*)(ent + 0x10c), actors = *(uintptr_t*)(g_qaGameBase + 0x307f1c);
            if (!actors || actor < actors || (actor - actors) % 4656 || (actor - actors) / 4656 >= 32) continue;
            slot = g_qaGameBase + 0x153850 + 4 * ((actor - actors) / 4656);
        } else if (ent[0] == 13) {
            slot = 0;
            unsigned number = *(uint16_t*)(ent + 6);
            for (unsigned i = 0; i < 64; ++i)
                if (*(unsigned*)(g_qaGameBase + 0x1538d4 + 32 * i) == number) { slot = g_qaGameBase + 0x1538d0 + 32 * i; break; }
            if (!slot) continue;
        }
        auto* tree = *(uint8_t**)slot;
        if (!tree || IsBadReadPtr(tree, 12) || !XAnimLoaded(*(uint8_t**)tree)) continue;
        // Verify reconstruction against the pure native getter while local
        // entityState is still intact, before host packets replace its type.
        uint8_t* native = ent;
        asm volatile("call *%1" : "+a"(native) : "r"((void*)(g_qaGameBase + 0x48870)) : "ecx", "edx", "memory");
        if (native != tree) continue;
        g_qaNativeOwners[e] = {slot, (uintptr_t)tree, g_qaInitCount}; ++captured;
    }
    Log("QA native ownership captured before attach: %u exact entity owners", captured);
}
uint8_t* QANativeTree(int entity)
{
    if (!g_qaBorrowEnabled || entity < 0 || entity >= g::MAX_GENTITIES ||
        (uintptr_t)GetModuleHandleA(g::GameDll()) != g_qaGameBase) return nullptr;
    const auto& owner = g_qaNativeOwners[entity];
    if (!owner.slot || owner.generation != g_qaInitCount || IsBadReadPtr((void*)owner.slot, 4) ||
        *(uintptr_t*)owner.slot != owner.tree) return nullptr;
    return (uint8_t*)owner.tree;
}
uint8_t* QABorrowTree(int entity, uint8_t* xanim)
{
    uint8_t* tree = QANativeTree(entity);
    bool valid = tree && !IsBadReadPtr(tree, 12) && XAnimLoaded(*(uint8_t**)tree);
    if (!valid || !xanim || *(uint8_t**)tree != xanim) return nullptr;
    bool alias = false;
    for (int e = 0; e < g::MAX_GENTITIES && !alias; ++e) {
        if (e == entity) continue;
        alias = QANativeTree(e) == tree || g_qaBorrowed[e].tree == (uintptr_t)tree || S->ownTree[e] == tree;
    }
    if (!tree_owner::CanBorrow((uintptr_t)tree, g_qaInitCount, true, true, alias)) return nullptr;
    return tree;
}
uint8_t* QACurrentBorrow(int entity)
{
    const auto& borrowed = g_qaBorrowed[entity];
    if (!g_qaBorrowEnabled || !borrowed.tree || borrowed.owner != tree_owner::Owner::Native || borrowed.generation != g_qaInitCount) return nullptr;
    auto* tree = (uint8_t*)borrowed.tree;
    if (QANativeTree(entity) != tree || IsBadReadPtr(tree, 12) || !XAnimLoaded(*(uint8_t**)tree)) return nullptr;
    return tree;
}
void JoinerApplyDObj(Reader r)
{
    ModelEntry models[8] = {};
    uint8_t parents[8];
    char name[256], animName[256];
    int e = r.Get<uint16_t>(), nm = r.Get<uint8_t>(), u12 = r.Get<uint16_t>();
    if (e >= g::MAX_GENTITIES || nm > 8 || !GetStr(r, animName, sizeof animName)) return;
    for (int k = 0; k < nm; ++k) {
        if (!GetStr(r, name, sizeof name)) return;
        parents[k] = r.Get<uint8_t>();
        models[k].flags = r.Get<uint16_t>();
        if (g_qaDeferredEnabled) {
            int id = -(int16_t)models[k].flags;
            char full[264]; snprintf(full, sizeof full, "xmodel/%s", name);
            if (id <= 0 || id >= 256 || _stricmp(QAModelConfigString(32 + id), full)) return;
            // Native reliable CS can lag this UDP packet; host retries DObjs.
        }
        models[k].model = g::XModelPrecache(name);  // si no estaba cargado lo carga
        if (!models[k].model || _stricmp(SafeStr(*(char**)models[k].model), name) != 0) {
            Log("dobj %d: modelo '%s' no resuelto", e, name);
            return;
        }
    }
    if (!r.Ok()) return;
    if (!nm) {
        JoinerFreeDObj(e);
        return;
    }
    uint8_t* xanim = animName[0] ? FindXAnim(animName) : nullptr;
    if (animName[0] && !xanim) {  // assets recargandose (al volver a entrar): el host lo reenvia en 1 s
        Log("dobj %d: no hay arbol de animacion '%s' aca", e, animName);
        return;
    }
    uint8_t* d = g::ServerDObj(e);
    bool same = d && d[0x16] == nm && (*(uint8_t**)d ? **(uint8_t***)d : nullptr) == xanim;
    for (int k = 0; same && k < nm; ++k) same = *(void**)(d + g::DO_MODELS + k * 4) == models[k].model;
    if (!same) {
        uint8_t* borrowed = QABorrowTree(e, xanim);
        JoinerFreeDObj(e);
        uint8_t* tree = borrowed ? borrowed : (xanim ? g::XAnimCreateTree(xanim) : nullptr);
        if (borrowed) {
            g_qaBorrowed[e] = {(uintptr_t)tree, g_qaInitCount, tree_owner::Owner::Native};
            ++g_qaBorrowCount;
            Log("QA native tree borrowed entity=%d ptr=%p generation=%u", e, tree, g_qaInitCount);
        } else S->ownTree[e] = tree;
        DObjCreate(models, nm, tree, e, u12);
        d = g::ServerDObj(e);
        if (!d) return;
    }
    if (g_qaBorrowEnabled && !S->ownTree[e] && !g_qaBorrowed[e].tree) {
        if (uint8_t* native = QABorrowTree(e, xanim))
            if (d && *(uint8_t**)d == native) g_qaBorrowed[e] = {(uintptr_t)native, g_qaInitCount, tree_owner::Owner::Native};
    }
    for (int k = 0; k < nm; ++k) {
        d[g::DO_PARENTS + k] = parents[k];
        *(uint16_t*)(d + g::DO_FLAGS + k * 2) = models[k].flags;
    }
}

void JoinerApplyAnims(Reader r)
{
    static uint8_t seen[4096];
    while (r.p + 4 <= r.end) {
        int e = r.Get<uint16_t>(), count = r.Get<uint16_t>();
        if (r.p + count * (2 + ANIM_STATE) > r.end || e >= g::MAX_GENTITIES) return;
        uint8_t* d = g::ServerDObj(e);
        uint8_t* tree = d ? *(uint8_t**)d : nullptr;
        int size = tree ? *(int*)(*(uint8_t**)tree + 4) : 0;
        if (size > (int)sizeof seen) size = 0;
        memset(seen, 0, size);
        for (int k = 0; k < count; ++k) {
            int a = r.Get<uint16_t>();
            const uint8_t* st = r.p;
            r.p += ANIM_STATE;
            if (a >= size) continue;
            seen[a] = 1;
            uint16_t* slot = (uint16_t*)(tree + g::TREE_INFO + a * 2);
            if (!*slot) {  // como XAnimSetGoalWeight (0x47dd90) cuando el nodo no tenia info
                uint8_t* p = g::XAnimAllocInfo(tree, a);
                memset(p + 0xc, 0, 0x38);
                *(uint16_t*)(p + 4) = 0;
                *(uint16_t*)(p + 2) = 0xffff;
                *(uint16_t*)p = 0;
                *(uint16_t*)(p + 6) = 0;
            }
            // El host manda el bloque cliente (el que se dibuja). Aca se guarda como estado
            // confirmado del lado servidor, para que JoinerAdvanceAnims lo pueda avanzar entre
            // snapshots con BodyAnimUpdate; XAnimCloneServerToClient lo copia al cliente.
            uint8_t* info = g::xanimInfo + *slot * 0x44;
            memcpy(info + 0x3c, st, 4);       // tiempo confirmado
            memcpy(info + 0x42, st + 4, 2);   // ciclo confirmado
            memcpy(info + 0x44, st + 6, 16);  // goalTime, goalWeight, weight, rate
            memcpy(info + 0x38, st, 4);       // tiempo nuevo = confirmado
            memcpy(info + 0x40, st + 4, 2);   // ciclo nuevo = confirmado
        }
        for (int a = 0; a < size; ++a) {
            uint16_t* slot = (uint16_t*)(tree + g::TREE_INFO + a * 2);
            if (*slot && !seen[a]) ReleaseInfo(tree, slot);
        }
        if (tree) g::XAnimCloneServerToClient(tree);  // que este frame ya muestre lo nuevo
    }
}

// ---------- cuerpos de los jugadores (el SP no tiene: el jugador nunca se ve a si mismo) ----------

// host: DObj de soldado aliado para la entidad del jugador n (cuerpo + cabeza + casco, unidos al esqueleto del
// cuerpo, como en character/*.gsc).
// Indice de modelo (configstrings CS_MODELS 31..286, "xmodel/<nombre>") que el cliente usa para encontrar el
// modelo de dibujo de cada parte de un DObj (DObj+0x38 = -indice); 0 si el nivel no lo cargo. Solo sirven los
// que el nivel cargo: a mitad de partida XModelPrecache corta el juego con "model '%s' not precached".
const int CS_MODELS = (int)g::A(31, 32), MAX_MODELS = 256;  // UO: un configstring mas antes de los modelos
int ModelIndex(const char* name)
{
    char full[128];
    snprintf(full, sizeof full, "xmodel/%s", name);
    for (int i = 1; i < MAX_MODELS; ++i)
        if (!_stricmp(QAModelConfigString(CS_MODELS + i), full)) return i;
    return 0;
}

// Indice del preferido si el nivel lo cargo; si no, del primer modelo cargado que empiece con alguno de los
// prefijos (lista terminada en nullptr) y no contenga `exclude`. 0 si no hay.
int LoadedModel(const char* preferred, const char* const* prefixes, const char* exclude = nullptr)
{
    if (int i = ModelIndex(preferred)) return i;
    for (; *prefixes; ++prefixes)
        for (int i = 1; i < MAX_MODELS; ++i) {
            const char* s = g::ConfigString(CS_MODELS + i);
            if (_strnicmp(s, "xmodel/", 7) || _strnicmp(s + 7, *prefixes, strlen(*prefixes))) continue;
            if (exclude && strstr(s, exclude)) continue;
            return i;
        }
    return 0;
}
const char* ModelName(int index) { return g::ConfigString(CS_MODELS + index) + 7; }

// Modelo del arma en la mano del jugador n: ps.weapon (+0xa0) -> WeaponDef (tabla en gamex86 RVA 0x125650,
// ver giveweapon RVA 0x15020) -> worldModel (+0x188, "xmodel/..."). "" si no tiene arma.
const char* WeaponModelName(int n)
{
    uint8_t* game = (uint8_t*)GetModuleHandleA(g::GameDll());
    uint8_t** defs = game ? *(uint8_t***)(game + g::G_WEAPONDEFS) : nullptr;
    int weapon = *(int*)(g::PlayerState(n) + g::PS_WEAPON);
    if (!defs || weapon <= 0 || weapon >= g::MAX_WEAPONS || !defs[weapon]) return "";
    const char* name = *(const char**)(defs[weapon] + g::WD_WORLDMODEL);
    if (!name || IsBadReadPtr(name, 8)) return "";
    name = _strnicmp(name, "xmodel/", 7) == 0 ? name + 7 : name;
    return ModelIndex(name) ? name : "";  // sin cargar no se puede poner en el cuerpo
}

int g_bodyAnim[g::MAX_CLIENTS] = {-1, -1, -1, -1};  // animacion puesta (-1 = ninguna; tras recargar se vuelve a poner)
int g_bodyParts[g::MAX_CLIENTS];                     // modelos del cuerpo sin contar el arma

// Partes: las preferidas de cada jugador si el nivel las cargo; si no, las de algun aliado del nivel (asi en las
// misiones britanicas y sovieticas salen soldados de esa campaña). Sin cuerpo ni cabeza cargados no hay cuerpo.
#include "qa_host_body_gc.inc"

void HostCreateBody(int n)
{
    g_bodyAnim[n] = -1;  // arbol nuevo (puede caer en la misma direccion que el viejo)
    static const char* const kParts[g::MAX_CLIENTS][3] = {
        {"character_airborne", "basehead4_04", "gear_US_helmet"},
        {"character_airborne", "basehead_01", "gear_US_helmet_net"},
        {"character_airborne_101", "basehead2_02", "gear_US_helmet"},
        {"character_airborneslvup", "basehead3_03", "gear_US_helmet_scrim"},
    };
    static const char* const kBodies[] = {"character_airborne", "character_british", "character_soviet", nullptr};
    static const char* const kHeads[] = {"basehead", nullptr};
    static const char* const kHelmets[] = {"gear_US_helmet", nullptr};
    int parts[3] = {LoadedModel(kParts[n][0], kBodies), LoadedModel(kParts[n][1], kHeads, "axis"), 0};
    if (!parts[0] || !parts[1]) {
        static DWORD lastWarn;
        if (GetTickCount() - lastWarn > 10000) Log("cuerpo %d: el nivel no cargo modelos de soldado aliado", n);
        lastWarn = GetTickCount();
        return;
    }
    if (!_strnicmp(ModelName(parts[0]), "character_airborne", 18)) parts[2] = LoadedModel(kParts[n][2], kHelmets);
    ModelEntry models[4] = {};
    int count = 0;
    for (int index : parts) {
        if (!index) continue;
        models[count].model = g::XModelPrecache(ModelName(index));
        models[count++].flags = (uint16_t)-index;
    }
    g_bodyParts[n] = count;
    const char* weapon = WeaponModelName(n);
    if (*weapon) {
        models[count].model = g::XModelPrecache(weapon);
        models[count].tag = "tag_weapon_right";
        models[count++].flags = (uint16_t)-ModelIndex(weapon);
    }
    uint8_t* xanim = FindXAnim("generic_human.atr");
    uint8_t* tree = xanim ? g::XAnimCreateTree(xanim) : nullptr;
    DObjCreate(models, count, tree, n, 0);
    S->bodyTree[n] = tree;
    QATrackHostBody(n,tree);
    Log("cuerpo %d: creado (%s + %s%s%s, arma '%s')", n, ModelName(parts[0]), ModelName(parts[1]), parts[2] ? " + " : "",
        parts[2] ? ModelName(parts[2]) : "", weapon);
}

// el DObj del cuerpo tiene el arma que el jugador lleva en la mano?
bool BodyWeaponMatches(int n)
{
    uint8_t* d = g::ServerDObj(n);
    const char* want = WeaponModelName(n);
    if (!d) return true;
    if (!want[0]) return d[0x16] == g_bodyParts[n];
    uint8_t* model = d[0x16] == g_bodyParts[n] + 1 ? *(uint8_t**)(d + g::DO_MODELS + g_bodyParts[n] * 4) : nullptr;
    return model && !_stricmp(SafeStr(*(char**)model), want);
}

void HostFreeBody(int n)
{
    if (QAFreeHostBody(n)) return;
    uint8_t* tree = S->bodyTree[n];
    S->bodyTree[n] = nullptr;
    if (g::serverObjMap[n]) g::Com_ServerDObjFree(n, true);
    g::Com_SyncClientDObjs();
    if (tree) {
        FreeTreeInfos(tree);
        g::XAnimFreeTree(tree);
    }
    Log("cuerpo %d: borrado", n);
}

bool g_bodyDraw = true;  // prueba: coopbodydraw 0 -> sin cuerpos, los jugadores como en el SP
void Cmd_CoopBodyDraw()
{
    g_bodyDraw = atoi(g::Argv(1)) != 0;
}

// Con algun remoto conectado cada jugador tiene cuerpo; solo, como en el SP.
void HostUpdateBodies()
{
    QAHostBodySweep(false,"unreferenced host body");
    if (!g::svs_clients) return;
    bool anyRemote = false;
    for (int n = 1; n < g::MAX_CLIENTS; ++n) anyRemote |= S->remote[n].active;
    for (int n = 0; n < g::MAX_CLIENTS; ++n) {
        bool want = g_bodyDraw && anyRemote && *(int*)(g::Client(n) + g::CL_STATE) == 1;
        bool has = S->bodyTree[n] != nullptr;
        // tambien si el juego borro el DObj, o si cambio el arma (se rearma con la nueva)
        if (has && (!want || !g::serverObjMap[n] || !BodyWeaponMatches(n))) HostFreeBody(n);
        if (want && !S->bodyTree[n] && !g::serverObjMap[n]) HostCreateBody(n);
    }
}

}  // namespace

// cgame (host y remoto): el trap 0xf8 devuelve el entityState de la memoria del servidor. Los jugadores
// (eType 1) no se dibujan; a los demas jugadores con cuerpo se los da como entidad general (eType 0), que
// dibuja su DObj, y sin inclinacion (los angulos son los de la vista).
extern "C" uint8_t* CgEntityState(const int* args)
{
    static uint8_t copy[g::MAX_CLIENTS][g::ENTSTATE_MAX];
    int e = args[1];
    uint8_t* st = g::Entity(e);
    int self = S->role == JOINER ? S->slot : 0;
    if (!g_bodyDraw || S->role == NONE || e < 0 || e >= g::MAX_CLIENTS || e == self || st[0] != 1 || !g::serverObjMap[e]) return st;
    uint8_t* c = copy[e];
    memcpy(c, st, g::ENTSTATE_SIZE);
    c[0] = 0;
    *(float*)(c + 0x44) = 0;  // apos.trBase: pitch y roll
    *(float*)(c + 0x4c) = 0;
    return c;
}

// XAnim del lado servidor (el lado lo elige inGameCall): las mismas funciones que usa el juego para la IA.
//   BodyAnimKnob: 0x47d8b0 (ECX arbol, EAX anim; goalWeight, blendTime, rate, notify x3) pone la animacion
//                 con su cadena de padres y apaga las hermanas.
//   BodyAnimUpdate: 0x47ccd0 (ECX DObj; dtime, notify) avanza el tiempo.
asm(R"(
.intel_syntax noprefix
.globl _BodyAnimKnob
_BodyAnimKnob:
    mov ecx, [esp+4]
    mov eax, [esp+8]
    push 0
    push 0
    push 0
    push dword ptr [esp+0x20]
    push dword ptr [esp+0x20]
    push dword ptr [esp+0x20]
    call dword ptr [_g_addrAnimKnob]
    add esp, 24
    ret
.globl _BodyAnimUpdate
_BodyAnimUpdate:
    mov ecx, [esp+4]
    push 0
    push dword ptr [esp+0xc]
    call dword ptr [_g_addrAnimUpdate]
    add esp, 8
    ret
.att_syntax
)");
extern "C" void BodyAnimKnob(uint8_t* tree, int anim, float goalWeight, float blendTime, float rate);
extern "C" void BodyAnimUpdate(uint8_t* dobj, float dtime);

asm(R"(
.intel_syntax noprefix
.globl _CgSyscallHook
_CgSyscallHook:
    mov eax, [esp+4]
    mov ecx, [eax]
    cmp ecx, dword ptr [_g_cgEntityTrap]
    je 1f
    cmp ecx, dword ptr [_g_cgRunServerTrap]
    jne 3f
    call _CoopSuppressClientSimulation
    test eax, eax
    jz 3f
    xor eax, eax
    ret
1:
    push eax
    call _CgEntityState
    add esp, 4
    ret
3:  jmp dword ptr [_g_addrCgSyscalls]
.att_syntax
)");
extern "C" void CgSyscallHook();
extern "C" int __cdecl CoopSuppressClientSimulation()
{
    if (!S || S->role != JOINER || !S->frozen) return 0;
    if (!S->suppressedClientFrames++)
        Log("joiner: client server-simulation trap %x suppressed; host owns world", g_cgRunServerTrap);
    g::inGameCall = 0; // native secondary-frame epilogue selects the client animation block
    // The SP cgame also advances the local server through this separate trap
    // (UO 0x404719 -> 0x44f510 -> GAME call11). Running it against replicated
    // host DObjs updates obsolete local vehicle physics after checkpoints.
    // Client rendering and our per-frame animation advance are independent.
    return 1;
}

namespace {

// cgvm->systemCall (primer campo del vm_t) se rearma cada vez que el motor recrea el cgame
void HookCgame(bool on)
{
    const uintptr_t CL_CGAME_SYSCALLS = g_addrCgSyscalls;
    void** vm = (void**)g::cgvm;
    if (!vm) return;
    if (on && *vm == (void*)CL_CGAME_SYSCALLS) *vm = (void*)CgSyscallHook;
    if (!on && *vm == (void*)CgSyscallHook) *vm = (void*)CL_CGAME_SYSCALLS;
}

// ---------- animacion de los cuerpos (1.3) ----------

enum BodyAnim { BA_IDLE, BA_WALK, BA_RUN, BA_BACK, BA_LEFT, BA_RIGHT, BA_CROUCH, BA_CROUCHWALK, BA_CROUCHRUN, BA_PRONE,
                BA_CRAWL, BA_DEATH, BA_FIRE, BA_CROUCHFIRE, BA_PRONEFIRE, BA_DOWNED, BA_COUNT };
const char* const kBodyAnimName[BA_COUNT] = {
    "stand_aim_straight", "stand_walk_combat_loop_01", "combatrun_forward_1", "combatrun_back",
    "combatrun_left",     "combatrun_right",           "crouch_aim_straight", "crouchwalk_loop",
    "crouchrun_loop_forward_1", "prone_aim_idle",      "prone_crawl",         "death_stand_dropinplace",
    "stand_shoot_straight", "crouch_shoot_straight",   "prone_shoot_straight",  "wounded_crawlidle",
};
constexpr int EF_FIRING = 0x400;  // eFlags mientras dispara (visto: 0x18 -> 0x418)

int AnimIndex(uint8_t* xanim, const char* name)
{
    int size = *(int*)(xanim + 4);
    for (int i = 0; i < size; ++i) {
        uint8_t* node = xanim + 8 + i * 8;
        uint8_t* parts = *(uint16_t*)node ? nullptr : *(uint8_t**)(node + 4);
        if (parts && !_stricmp(SafeStr(*(char**)parts), name)) return i;
    }
    return -1;
}

// Postura (ps.pm_flags: 1 cuerpo a tierra, 2 agachado), vida y velocidad del jugador -> animacion
int ChooseBodyAnim(int n)
{
    uint8_t* ps = g::PlayerState(n);
    const float* v = (const float*)(ps + 0x20);
    float speed = sqrtf(v[0] * v[0] + v[1] * v[1]);
    int flags = *(int*)(ps + 0xc);
    bool firing = *(int*)(g::Entity(n) + 0x10) & EF_FIRING;
    if (S->downed[n]) return BA_DOWNED;
    if (*(int*)(ps + g::PS_HEALTH) <= 0) return BA_DEATH;
    if (flags & 1) return speed > 5 ? BA_CRAWL : firing ? BA_PRONEFIRE : BA_PRONE;
    if (flags & 2) return speed >= 5 ? (speed < 100 ? BA_CROUCHWALK : BA_CROUCHRUN) : firing ? BA_CROUCHFIRE : BA_CROUCH;
    if (speed < 5) return firing ? BA_FIRE : BA_IDLE;
    float yaw = *(const float*)(g::Entity(n) + 0x48);  // apos.trBase[YAW]
    float rel = atan2f(v[1], v[0]) * 180.0f / 3.14159265f - yaw;
    rel -= 360.0f * floorf((rel + 180.0f) / 360.0f);  // a [-180, 180)
    if (fabsf(rel) <= 50) return speed < 120 ? BA_WALK : BA_RUN;
    if (fabsf(rel) >= 130) return BA_BACK;
    return rel > 0 ? BA_LEFT : BA_RIGHT;
}

// hubo un tiro desde la ultima vez? Cada tiro baja un cargador (ps.ammoclip[64] en +0x1f4, indexado por
// cargador, no por arma): se mira la suma.
bool NewShot(int n)
{
    static int lastClip[g::MAX_CLIENTS];
    const int* clips = (const int*)(g::PlayerState(n) + g::PS_CLIP);
    int clip = 0;
    for (int i = 0; i < g::MAX_WEAPONS; ++i) clip += clips[i];
    bool shot = clip < lastClip[n];
    lastClip[n] = clip;
    return shot;
}

void HostAnimateBodies(float dt)
{
    uint8_t* xanim = FindXAnim("generic_human.atr");
    if (!xanim) return;
    int prevSide = g::inGameCall;
    g::inGameCall = 1;  // lado servidor; el cliente lo copia en cada snapshot (0x47b010)
    for (int n = 0; n < g::MAX_CLIENTS; ++n) {
        uint8_t* d = g::ServerDObj(n);
        uint8_t* tree = S->bodyTree[n];
        if (!tree || !d || *(uint8_t**)d != tree) { g_bodyAnim[n] = -1; continue; }
        int want = ChooseBodyAnim(n);
        int size = *(int*)(xanim + 4);
        if (want != g_bodyAnim[n]) {
            // el knob solo apaga las hermanas de la hoja: se apaga todo y se enciende la cadena nueva
            for (int a = 1; a < size; ++a)
                if (uint16_t idx = *(uint16_t*)(tree + g::TREE_INFO + a * 2)) {
                    uint8_t* info = g::xanimInfo + idx * 0x44;
                    *(float*)(info + 0x44) = *(float*)(info + 0x48) = *(float*)(info + 0x4c) = 0;
                }
            int index = AnimIndex(xanim, kBodyAnimName[want]);
            // shortcut: sin mezcla (blendTime 0); 0x47ccd0 sin notify no lleva el peso hacia la meta
            if (index > 0) BodyAnimKnob(tree, index, 1.0f, 0.0f, 1.0f);
            else Log("cuerpo %d: no esta la animacion %s", n, kBodyAnimName[want]);
            g_bodyAnim[n] = want;
        } else if ((want == BA_FIRE || want == BA_CROUCHFIRE || want == BA_PRONEFIRE) && NewShot(n)) {
            // otro tiro con el boton apretado: la animacion de disparo (sin bucle) vuelve a empezar
            int index = AnimIndex(xanim, kBodyAnimName[want]);
            if (uint16_t idx = index > 0 ? *(uint16_t*)(tree + g::TREE_INFO + index * 2) : 0) {
                uint8_t* info = g::xanimInfo + idx * 0x44;
                *(float*)(info + 0x38) = *(float*)(info + 0x3c) = 0;
                *(uint16_t*)(info + 0x40) = *(uint16_t*)(info + 0x42) = 0;
            }
        }
        BodyAnimUpdate(d, dt);
        // 0x47ba90 deja el tiempo nuevo en +0x38 (ciclo +0x40) calculado desde el confirmado +0x3c (+0x42); el
        // servidor lo confirma despues, pero tambien solo desde la entidad 4
        for (int a = 0; a < size; ++a)
            if (uint16_t idx = *(uint16_t*)(tree + g::TREE_INFO + a * 2)) {
                uint8_t* info = g::xanimInfo + idx * 0x44;
                *(float*)(info + 0x3c) = *(float*)(info + 0x38);
                *(uint16_t*)(info + 0x42) = *(uint16_t*)(info + 0x40);
            }
        g::XAnimCloneServerToClient(tree);  // 0x44d8e0 lo hace por snapshot pero desde la entidad 4
    }
    g::inGameCall = prevSide;
}

// En el que se une el servidor local no corre, asi que nadie avanza la animacion entre snapshots:
// el estado que manda el host se veria congelado hasta el siguiente paquete (20 Hz) y los cuerpos
// parecerian animados a muy pocos FPS. Aca se hace lo mismo que el host con los cuerpos de los
// jugadores: avanzar el lado servidor de cada arbol propio con BodyAnimUpdate, confirmar el tiempo
// y copiarlo al cliente. El proximo snapshot solo corrige la fase.
void JoinerAdvanceAnims(float dt)
{
    if (dt <= 0.0f) return;
    static int lastLog, lastTrees, frames;
    static float acc;
    int trees = 0;
    int prevSide = g::inGameCall;
    g::inGameCall = 1;  // BodyAnimUpdate trabaja sobre el bloque servidor (+0x38..)
    for (int e = 0; e < g::MAX_GENTITIES; ++e) {
        uint8_t* tree = S->ownTree[e] ? S->ownTree[e] : QACurrentBorrow(e);
        uint8_t* d = g::ServerDObj(e);
        if (!tree || !d || *(uint8_t**)d != tree) continue;
        ++trees;
        BodyAnimUpdate(d, dt);
        int size = *(int*)(*(uint8_t**)tree + 4);
        for (int a = 0; a < size; ++a)
            if (uint16_t idx = *(uint16_t*)(tree + g::TREE_INFO + a * 2)) {
                uint8_t* info = g::xanimInfo + idx * 0x44;
                *(float*)(info + 0x3c) = *(float*)(info + 0x38);
                *(uint16_t*)(info + 0x42) = *(uint16_t*)(info + 0x40);
            }
        g::XAnimCloneServerToClient(tree);
    }
    g::inGameCall = prevSide;
    if (!trees) return;
    if (!lastTrees) {
        lastLog = GetTickCount();
        Log("joiner: %d arboles de animacion propios, se avanzan por frame", trees);
    }
    lastTrees = trees;
    acc += dt;
    ++frames;
    if (GetTickCount() - lastLog > 10000) {  // prueba: tiene que dar ~10 s
        lastLog = GetTickCount();
        Log("joiner: animaciones propias +%.1f s en 10 s, %d frames/s (%d arboles)", acc, frames / 10, trees);
        acc = 0;
        frames = 0;
    }
}

// ---------- daño entre jugadores (opcion: set coop_friendlyfire 1 en el host) ----------

// G_Damage (gamex86 RVA 0x18800): (targ, inflictor, attacker, dir, point, damage, dflags, mod, hitLoc).
// gentity +0x104 = gclient (solo jugadores). gamex86 se recarga con el mapa: se vuelve a enganchar.
using GDamage_t = void(__cdecl*)(uint8_t*, uint8_t*, uint8_t*, float*, float*, int, int, int, int);
const uintptr_t G_DAMAGE_RVA = g::G_DAMAGE;
const uint8_t kGDamagePrologue[8] = {0x83, 0xEC, 0x18, 0x55, 0x8B, 0x6C, 0x24, 0x20};
GDamage_t g_origDamage;
uint8_t* g_damageHooked;  // base de gamex86 enganchada

// ---------- caido y revivir (fase 2, decision D1) ----------
// gentity: +0x1d8 health, +0x134 flags (1 godmode, 2 notarget: la IA no lo ve, 0x20 muerto).
// ps: +0xe4 health, +0xec maxhealth.
constexpr int FL_NOTARGET = 0x2;

bool CoopActive()
{
    if (S->role != HOST) return false;
    for (int n = 1; n < g::MAX_CLIENTS; ++n)
        if (S->remote[n].active) return true;
    return false;
}

bool PlayerInGame(int n) { return g::svs_clients && *(int*)(g::Client(n) + g::CL_STATE) == 1; }
uint8_t* PlayerState(int n) { return g::PlayerState(n); }

#include "actor_eligibility.inc"

bool AnyOtherStanding(int n)
{
    for (int m = 0; m < g::MAX_CLIENTS; ++m)
        if (m != n && PlayerInGame(m) && !S->downed[m] && *(int*)(g::Entity(m) + g::GE_HEALTH) > 0) return true;
    return false;
}

void SetHealth(int n, int health)
{
    *(int*)(g::Entity(n) + g::GE_HEALTH) = health;
    *(int*)(PlayerState(n) + g::PS_HEALTH) = health;
    PublishActorEligibility(n);
}

// aviso en la consola (las ultimas lineas se ven arriba de la pantalla). Texto en Latin-1 como la fuente.
void DownedMessage(int n, bool downed, int self)
{
    if (n == self)
        g::Com_Printf(downed ? "^1COOP: you are down. Wait for a teammate to revive you (Use 3 s)\n"
                             : "^2COOP: you were revived\n");
    else
        g::Com_Printf(downed ? "^1COOP: player %d is down: get close and hold Use for 3 s\n"
                             : "^2COOP: player %d is back up\n", n + 1);
}

// Carteles al centro de la pantalla: el host le manda "cp" a cada jugador (dura cg_centertime). Un cartel fijo
// (caido, barra de levantar) se renueva antes de que se borre; uno suelto (aviso) se manda una vez.
struct Banner {
    char text[128];
    DWORD sent;
    bool keep;
} g_banner[g::MAX_CLIENTS];

void SendBanner(int n, const char* text, bool keep)
{
    if (!PlayerInGame(n)) return;
    char cmd[160];
    snprintf(cmd, sizeof cmd, "cp \"%s\"", text);
    g::SV_SendServerCommand(g::Client(n), cmd);
    Banner& b = g_banner[n];
    snprintf(b.text, sizeof b.text, "%s", text);
    b.sent = GetTickCount();
    b.keep = keep;
}

void KeepBanner(int n, const char* text)  // "" borra el fijo anterior (no un aviso suelto)
{
    Banner& b = g_banner[n];
    if (!*text) {
        if (b.keep) SendBanner(n, "", false);
        return;
    }
    if (b.keep && !strcmp(b.text, text) && GetTickCount() - b.sent < 2000) return;
    SendBanner(n, text, true);
}

void AnnounceDowned(int n, bool downed)
{
    char text[128];
    for (int m = 0; m < g::MAX_CLIENTS; ++m) {
        if (m == n) {
            if (!downed) SendBanner(m, "^2You were revived", false);  // caido: el cartel fijo lo pone HostDownedFrame
        } else if (!S->downed[m]) {
            snprintf(text, sizeof text,
                     downed ? "^1Player %d is down^7\\nGet close and hold Use for 3 seconds"
                            : "^2Player %d is back up",
                     n + 1);
            SendBanner(m, text, false);
        }
    }
}

void SetDowned(int n, bool downed)
{
    S->downed[n] = downed;
    S->reviveTime[n] = 0;
    int& flags = *(int*)(g::Entity(n) + g::GE_FLAGS);
    flags = downed ? flags | FL_NOTARGET : flags & ~FL_NOTARGET;
    PublishActorEligibility(n);
    Log("jugador %d: %s", n, downed ? "caido" : "levantado");
    DownedMessage(n, downed, 0);
}

void __cdecl Hook_GDamage(uint8_t* targ, uint8_t* inflictor, uint8_t* attacker, float* dir, float* point, int damage,
                          int dflags, int mod, int hitLoc)
{
    if (!g_api) { // a pinned later-plugin chain must not touch retired Coop state
        if (g_origDamage) g_origDamage(targ, inflictor, attacker, dir, point, damage, dflags, mod, hitLoc);
        return;
    }
    uint8_t* ff = g::Cvar_FindVar("coop_friendlyfire");
    bool friendlyFire = ff && *(int*)(ff + 0x20);
    bool targPlayer = targ && *(void**)(targ + g::GE_CLIENT);
    if (!friendlyFire && targPlayer && attacker && targ != attacker && *(void**)(attacker + g::GE_CLIENT)) {
        Log("dano entre jugadores bloqueado: %d -> %d (%d)", *(uint16_t*)(attacker + 6), *(uint16_t*)(targ + 6), damage);
        return;  // un jugador no lastima a otro (si a si mismo, como en el SP)
    }
    int n = targPlayer ? *(uint16_t*)(targ + 6) : -1;
    if (n < 0 || n >= g::MAX_CLIENTS || !CoopActive()) {
        g_origDamage(targ, inflictor, attacker, dir, point, damage, dflags, mod, hitLoc);
        return;
    }
    if (S->downed[n]) return;  // caido: ya no recibe daño
    // El daño final depende de la zona del golpe (G_Damage lo escala): se aplica con la vida inflada para que
    // no muera adentro, se mide cuanto bajo y recien ahi se decide entre herido, caido o muerto.
    constexpr int BOOST = 100000;
    int health = *(int*)(targ + g::GE_HEALTH);
    SetHealth(n, health + BOOST);
    g_origDamage(targ, inflictor, attacker, dir, point, damage, dflags, mod, hitLoc);
    int left = *(int*)(targ + g::GE_HEALTH) - BOOST;
    if (left > 0) {
        SetHealth(n, left);
    } else if (AnyOtherStanding(n)) {
        SetHealth(n, 1);
        SetDowned(n, true);
        AnnounceDowned(n, true);
    } else {
        // Nadie mas en pie: muere el host de verdad, que es lo que dispara la mision fallida del SP y la vuelta
        // al ultimo checkpoint para todos. Un remoto no muere nunca (su muerte recarga la mision de otra forma).
        Log("jugador %d: cayo el ultimo en pie -> muere el host", n);
        if (n != 0) {
            SetHealth(n, 1);
            SetDowned(n, true);
        }
        if (S->downed[0]) SetDowned(0, false);
        SetHealth(0, 1);
        g_origDamage(g::Entity(0), inflictor, attacker, dir, point, BOOST, dflags, mod, hitLoc);
    }
}

// prueba: coopkill <n> <daño> -> G_Damage del mundo sobre el jugador n (con el modulo de juego como VM actual)
void Cmd_CoopKill()
{
    int n = atoi(g::Argv(1)), damage = g::cmd_argc > 2 ? atoi(g::Argv(2)) : 100000;
    if (n < 0 || n >= g::MAX_CLIENTS || !PlayerInGame(n) || !g_origDamage) return;
    uint8_t** currentVM = &g::currentVM;
    uint8_t* prevVM = *currentVM;
    int prevIn = g::inGameCall;
    *currentVM = g::gvm;
    g::inGameCall = 1;
    Hook_GDamage(g::Entity(n), nullptr, nullptr, nullptr, nullptr, damage, 0, 0, 0);
    *currentVM = prevVM;
    g::inGameCall = prevIn;
    Log("coopkill %d %d -> vida %d", n, damage, *(int*)(g::Entity(n) + g::GE_HEALTH));
}

// Caido: solo puede mirar. Se filtra el usercmd que el juego lee con SV_GetUsercmd (0x449a10, EAX = cliente).
// usercmd: +4 two-byte buttons (1 fire,0x40 use,0x4000 prone,0x8000 crouch),
// +6 weapon byte (UO40bd96 / Game19543); +0x14 forward,+0x15 side,+0x16 up.
}  // namespace
extern "C" void __cdecl FilterUsercmd(int n, uint8_t* cmd)
{
    if (!S || n < 0 || n >= g::MAX_CLIENTS) return;
    if(S->role==HOST&&n>0) SelectionUsercmd(n,cmd,false);
    if(!S->downed[n]) return;
    uint32_t& buttons = *(uint32_t*)(cmd + 4);
    buttons = (buttons & 0xffff0000) | 0x4000;
    cmd[0x14] = cmd[0x15] = 0;
    cmd[0x16] = 0x81;
}
// CL_GetUserCmd (0x401050): lo que el cgame usa para predecir al jugador local; sin esto el caido se
// veria parado y disparando hasta que llega la correccion del servidor
extern "C" void __cdecl FilterLocalUsercmd(uint8_t* cmd)
{
    if(S&&S->role==JOINER) SelectionUsercmd(S->slot,cmd,true);
    if (S && S->role != NONE) FilterUsercmd(S->role == JOINER ? S->slot : 0, cmd);
}
namespace {

// Levantar: un compañero en pie a menos de REVIVE_DIST manteniendo Usar REVIVE_SECONDS.
constexpr float REVIVE_DIST = 80, REVIVE_SECONDS = 3;

// prueba: coopendlevel <mapa> -> como missionSuccess("<mapa>") del script: pantalla de victoria y despues spmap
// (gamex86: +0x2dbd18 mapa siguiente, +0x2dbd08 con pantalla de victoria, +0x2dbd00 pedido de salida)
// prueba: coopuiclick <x> <y> -> lleva el cursor de los menus a (x, y) de 640x480 y hace clic, sin tocar el mouse
// real (UI vmMain 4 = mover el cursor dx dy, 3 = tecla; K_MOUSE1 = 200 segun la tabla de nombres de teclas)
void Cmd_CoopUiClick()
{
    if (!g::uivm) return;
    int moves[][13] = {{4, -2000, -2000}, {4, atoi(g::Argv(1)), atoi(g::Argv(2))}, {3, 200, 1}, {3, 200, 0}};
    for (auto& m : moves) g::CallVM(g::uivm, m);
}

void Cmd_CoopEndLevel()
{
    uint8_t* game = (uint8_t*)GetModuleHandleA(g::GameDll());
    if (!game || S->role != HOST || g::cmd_argc < 2) return;
    snprintf((char*)game + g::G_EXIT_MAP, 0x400, "%s", g::Argv(1));
    *(int*)(game + g::G_EXIT_VICTORY) = 1;
    *(int*)(game + g::G_EXIT_REQUEST) = 1;
    Log("coopendlevel %s", g::Argv(1));
}

// prueba: coophealth <n> <vida>
void Cmd_CoopHealth()
{
    int n = atoi(g::Argv(1));
    if (n < 0 || n >= g::MAX_CLIENTS || !PlayerInGame(n)) return;
    SetHealth(n, atoi(g::Argv(2)));
    Log("coophealth %d = %d", n, atoi(g::Argv(2)));
}

// "texto\n||||||||||" con la parte hecha en verde
void ProgressBanner(char* out, size_t size, const char* label, float t)
{
    constexpr int W = 20;
    int done = (int)(t / REVIVE_SECONDS * W);
    done = done < 0 ? 0 : done > W ? W : done;
    snprintf(out, size, "%s\\n^2%.*s^7%.*s", label, done, "||||||||||||||||||||", W - done, "||||||||||||||||||||");
}

void HostDownedFrame(float dt)
{
    int reviving[g::MAX_CLIENTS] = {-1, -1, -1, -1};  // a quien esta levantando cada jugador
    for (int n = 0; n < g::MAX_CLIENTS; ++n) {
        if (!S->downed[n]) continue;
        if (!PlayerInGame(n) || !CoopActive()) { SetDowned(n, false); continue; }
        SetHealth(n, 1);
        const float* o = (const float*)(PlayerState(n) + 0x14);
        int reviver = -1;
        for (int m = 0; m < g::MAX_CLIENTS && reviver < 0; ++m) {
            if (m == n || !PlayerInGame(m) || S->downed[m]) continue;
            const float* p = (const float*)(PlayerState(m) + 0x14);
            float dx = p[0] - o[0], dy = p[1] - o[1], dz = p[2] - o[2];
            bool use = *(uint32_t*)(g::Client(m) + 0x30 + 4) & 0x40;
            if (use && dx * dx + dy * dy + dz * dz < REVIVE_DIST * REVIVE_DIST) reviver = m;
        }
        float before = S->reviveTime[n];
        S->reviveTime[n] = reviver >= 0 ? before + dt : 0;
        if (reviver >= 0 && (int)S->reviveTime[n] != (int)before)
            Log("jugador %d: %d levantandolo (%.0f s)", n, reviver, S->reviveTime[n]);
        if (S->reviveTime[n] >= REVIVE_SECONDS) {
            SetDowned(n, false);
            SetHealth(n, *(int*)(PlayerState(n) + g::PS_MAXHEALTH) / 2);
            AnnounceDowned(n, false);
        } else if (reviver >= 0) {
            reviving[reviver] = n;
        }
    }
    for (int n = 0; n < g::MAX_CLIENTS; ++n) {
        char text[128] = "", label[64];
        if (S->downed[n] && S->reviveTime[n] > 0) {
            ProgressBanner(text, sizeof text, "^2Being revived", S->reviveTime[n]);
        } else if (S->downed[n]) {
            snprintf(text, sizeof text, "^1YOU ARE DOWN^7\\nWait for a teammate to revive you");
        } else if (reviving[n] >= 0) {
            snprintf(label, sizeof label, "Reviving player %d", reviving[n] + 1);
            ProgressBanner(text, sizeof text, label, S->reviveTime[reviving[n]]);
        }
        KeepBanner(n, text);
    }
}

// Vehiculos (D3). El script sube al jugador con playerlinkto(vehiculo, "tag_player", fraccion) (carride,
// truckride) y lo baja con unlink(). gentity +0x294 = enganche {padre, hermano, tag (string SL u16), hueso,
// offset...}, +0x298 = primer hijo; gclient +0x74c8 = fraccion de giro. gamex86: G_EntLinkTo 0x44b90 (ECX ent,
// EAX tag, push padre; 1 si engancho), 0x45280(ent, 0) fija el offset desde la posicion actual, G_EntUnlink
// 0x44d70 (ESI ent). Si el host va enganchado, los remotos van al mismo padre al costado del host (pasajeros:
// miran y disparan); cuando se baja, se sueltan donde estan.
int EntLinkTo(uint8_t* fn, uint8_t* ent, uint8_t* parent, const char* tag)
{
    int r = (int)tag;
    asm volatile("push %2\n\tcall *%3\n\tadd $4, %%esp" : "+a"(r), "+c"(ent) : "r"(parent), "r"(fn) : "edx", "memory");
    return r;
}
void EntUnlink(uint8_t* fn, uint8_t* ent)
{
    asm volatile("call *%1" : "+S"(ent) : "r"(fn) : "eax", "ecx", "edx", "memory");
}

// Alcanzar al host (D2). Un remoto en pie a mas de CATCHUP_DIST del host durante CATCHUP_SECONDS aparece en el
// rastro del host: los ultimos lugares donde piso (en el suelo, ps+0x54 groundEntityNum != 0x7ff), asi que
// se puede estar ahi sin calcular colisiones. Los caidos no se mueven (hay que ir a buscarlos) y los que van en un
// vehiculo siguen al host por HostVehicles.
constexpr float CATCHUP_DIST = 2000, CATCHUP_SECONDS = 10;
constexpr int TRAIL = 40;  // ultimos lugares del host, uno cada 32 unidades que se movio
float g_trail[TRAIL][3];
int g_trailCount, g_trailNext;
float g_farTime[g::MAX_CLIENTS];

float Dist2(const float* a, const float* b)
{
    float dx = a[0] - b[0], dy = a[1] - b[1], dz = a[2] - b[2];
    return dx * dx + dy * dy + dz * dz;
}

void HostCatchUp(float dt)
{
    const float* host = (const float*)(PlayerState(0) + 0x14);
    bool hostLinked = *(uint8_t**)(g::Entity(0) + g::GE_LINK);
    const float* last = g_trailCount ? g_trail[(g_trailNext - 1 + TRAIL) % TRAIL] : nullptr;
    if (!hostLinked && *(int*)(PlayerState(0) + g::PS_GROUNDENT) != 0x7ff && (!last || Dist2(last, host) > 32 * 32)) {
        memcpy(g_trail[g_trailNext], host, 12);
        g_trailNext = (g_trailNext + 1) % TRAIL;
        g_trailCount += g_trailCount < TRAIL;
    }
    for (int n = 1; n < g::MAX_CLIENTS; ++n) {
        float* o = (float*)(PlayerState(n) + 0x14);
        bool distant = S->remote[n].active && PlayerInGame(n) && !S->downed[n] && !hostLinked &&
                       !*(uint8_t**)(g::Entity(n) + g::GE_LINK) && Dist2(o, host) > CATCHUP_DIST * CATCHUP_DIST;
        g_farTime[n] = distant ? g_farTime[n] + dt : 0;
        if (g_farTime[n] < CATCHUP_SECONDS) continue;
        // el punto mas nuevo del rastro que no quede encima del host ni de otro jugador
        const float* spot = nullptr;
        for (int k = 1; k <= g_trailCount && !spot; ++k) {
            const float* p = g_trail[(g_trailNext - k + TRAIL) % TRAIL];
            bool clear = Dist2(p, host) > 48 * 48;
            for (int m = 1; m < g::MAX_CLIENTS && clear; ++m)
                if (m != n && PlayerInGame(m)) clear = Dist2(p, (const float*)(PlayerState(m) + 0x14)) > 40 * 40;
            if (clear) spot = p;
        }
        if (!spot) continue;  // el host no se movio todavia: se reintenta en el proximo frame
        Log("jugador %d: lejos del host %.0f s, aparece en su rastro (%.0f %.0f %.0f)", n, g_farTime[n], spot[0],
            spot[1], spot[2]);
        memcpy(o, spot, 12);
        memset(PlayerState(n) + 0x20, 0, 12);  // velocidad
        memcpy(g::Entity(n) + g::GE_ORIGIN, spot, 12);  // r.currentOrigin
        g_farTime[n] = 0;
        SendBanner(n, "^3You fell behind: moved next to the host", false);
    }
}

uint8_t* g_linkFailed[g::MAX_CLIENTS];
uint8_t* g_weaponTried[g::MAX_CLIENTS];

void HostVehicles()
{
    uint8_t* game = (uint8_t*)GetModuleHandleA(g::GameDll());
    if (!game || !CoopActive()) return;
    uint8_t* hostLink = *(uint8_t**)(g::Entity(0) + g::GE_LINK);
    uint8_t* parent = hostLink ? *(uint8_t**)hostLink : nullptr;
    uint8_t** currentVM = &g::currentVM;  // como un frame del juego (los traps usan la VM actual)
    uint8_t* prevVM = *currentVM;
    int prevIn = g::inGameCall;
    *currentVM = g::gvm;
    g::inGameCall = 1;
    for (int n = 1; n < g::MAX_CLIENTS; ++n) {
        if (!S->remote[n].active || !PlayerInGame(n)) continue;
        uint8_t* ent = g::Entity(n);
        uint8_t* link = *(uint8_t**)(ent + g::GE_LINK);
        // pasajero con las manos vacias (tanques: el host no tiene arma de infanteria): un arma del nivel
        int& held = *(int*)(PlayerState(n) + g::PS_WEAPON);
        if (parent && (!held || VehicleWeapon(held)) && g_weaponTried[n] != parent) {
            if (held) {  // el cañón copiado del host antes de este arreglo: fuera de la mano y de la lista
                *(uint32_t*)(PlayerState(n) + g::PS_WEAPONS + held / 32 * 4) &= ~(1u << (held % 32));
                held = 0;
            }
            g_weaponTried[n] = parent;
            if (int w = PickLoadedWeapon(game)) GiveWeapon(game, n, w);
            else Log("jugador %d: el nivel no tiene armas de infanteria cargadas", n);
        }
        if ((link ? *(uint8_t**)link : nullptr) == parent) continue;
        if (link) {
            EntUnlink(game + g::G_ENTUNLINK, ent);
            Log("jugador %d: se baja del vehiculo", n);
        }
        if (!parent || g_linkFailed[n] == parent) continue;
        // al costado del host (derecha, izquierda, atras) y enganchado desde ahi
        static const float kSide[g::MAX_CLIENTS] = {0, 32, -32, 0}, kForward[g::MAX_CLIENTS] = {0, 0, 0, -40};
        const float* h = (const float*)(PlayerState(0) + 0x14);
        float yaw = *(float*)(g::Entity(0) + 0x48) * 3.14159265f / 180;
        float* o = (float*)(PlayerState(n) + 0x14);
        o[0] = h[0] + cosf(yaw) * kForward[n] + sinf(yaw) * kSide[n];
        o[1] = h[1] + sinf(yaw) * kForward[n] - cosf(yaw) * kSide[n];
        o[2] = h[2];
        memset(PlayerState(n) + 0x20, 0, 12);  // velocidad
        memcpy(ent + g::GE_ORIGIN, o, 12);      // r.currentOrigin: de ahi sale el offset
        memcpy(*(uint8_t**)(ent + g::GE_CLIENT) + g::GC_LINKANGLES, *(uint8_t**)(g::Entity(0) + g::GE_CLIENT) + g::GC_LINKANGLES, 12);
        uint16_t tagName = *(uint16_t*)(hostLink + 8);
        const char* tag = tagName ? (const char*)(g::sl_pool + tagName * 8 + 4) : "";
        if (EntLinkTo(game + g::G_ENTLINKTO, ent, parent, tag)) {
            ((void(__cdecl*)(uint8_t*, int))(game + g::G_SETLINKOFFSET))(ent, 0);
            Log("jugador %d: sube al vehiculo del host (entidad %d, tag '%s')", n, *(uint16_t*)(parent + 6), tag);
        } else {
            g_linkFailed[n] = parent;  // no reintentar con el mismo padre en cada frame
            Log("jugador %d: no se pudo enganchar al vehiculo del host", n);
        }
    }
    *currentVM = prevVM;
    g::inGameCall = prevIn;
}

// SV_GetUsercmd: llama a la original (EAX = cliente, [esp+4] = destino) y despues a FilterUsercmd(n, cmd)
}  // namespace
extern "C" void* g_getUsercmdTramp;
void* g_getUsercmdTramp;
extern "C" void* g_reliableWriteTramp;
void* g_reliableWriteTramp;
extern "C" int __cdecl CoopAllowReliable(uint8_t* client, const char* text)
{
    if (!S || S->role != HOST || !g::svs_clients) return 1;
    uintptr_t offset = (uintptr_t)client - (uintptr_t)g::svs_clients;
    if (offset % g::CLIENT_SIZE || offset / g::CLIENT_SIZE >= g::MAX_CLIENTS) return 1;
    int n = (int)(offset / g::CLIENT_SIZE);
    if (!n) return 1; // never hide a failure of the host's own reliable channel
    bool initialized = *(int*)(client + 4) > 0 && *(void**)(client + 8) &&
                       *(void**)(client + 0xc) && *(void**)(client + 0x10);
    if (S->remote[n].active && *(int*)(client + g::CL_STATE) == 1 && initialized) return 1;
    // A save retains game clients for entity references, but their transport
    // buffers do not survive native loading. Scripts can still address those
    // disconnected players before HostDropGhosts removes them. Do not queue
    // commands for an absent transport; rejoin sends the authoritative gamestate.
    static DWORD logged[g::MAX_CLIENTS];
    DWORD now = GetTickCount();
    if (!logged[n] || now - logged[n] > 1000) {
        logged[n] = now;
        Log("reliable: skipped absent slot %d active=%d state=%d bytes=%d data=%p ring=%p seq=%d ack=%d command=%.80s",
            n, S->remote[n].active, *(int*)client, *(int*)(client + 4), *(void**)(client + 8),
            *(void**)(client + 0xc), *(int*)(client + g::CL_RELSEQ), *(int*)(client + g::CL_RELACK), text ? text : "");
    }
    return 0;
}
asm(R"(
.intel_syntax noprefix
.globl _Hook_ReliableWrite
_Hook_ReliableWrite:
    pushad
    push dword ptr [esp+40]
    push dword ptr [esp+32]
    call _CoopAllowReliable
    add esp, 8
    test eax, eax
    jz 1f
    popad
    jmp dword ptr [_g_reliableWriteTramp]
1:  popad
    ret
.att_syntax
)");
extern "C" void Hook_ReliableWrite();
asm(R"(
.intel_syntax noprefix
.globl _Hook_GetUsercmd
_Hook_GetUsercmd:
    push eax
    push dword ptr [esp+8]
    call dword ptr [_g_getUsercmdTramp]
    add esp, 4
    push dword ptr [esp+8]
    push dword ptr [esp+4]
    call _FilterUsercmd
    add esp, 8
    pop eax
    ret
.globl _Hook_CLGetUserCmd
_Hook_CLGetUserCmd:
    push dword ptr [esp+4]
    call dword ptr [_g_clGetUserCmdTramp]
    add esp, 4
    test eax, eax
    jz 1f
    push eax
    push dword ptr [esp+8]
    call _FilterLocalUsercmd
    add esp, 4
    pop eax
1:  ret
.att_syntax
)");
extern "C" void Hook_GetUsercmd();
extern "C" void Hook_CLGetUserCmd();
extern "C" void* g_clGetUserCmdTramp;
void* g_clGetUserCmdTramp;
namespace {
const uintptr_t SV_GET_USERCMD = g::A(0x449a10, 0x44bbe0);
const uint8_t kGetUsercmdPrologue[6] = {0x56, 0x8B, 0xF0, 0x85, 0xF6, 0x57};

const uintptr_t CL_GET_USERCMD = g::A(0x401050, 0x4011a0);
const uint8_t kCLGetUserCmdPrologueCoD1[8] = {0x56, 0x8B, 0xF0, 0xA1, 0x18, 0xFE, 0x42, 0x01},
              kCLGetUserCmdPrologueUO[8] = {0x56, 0x8B, 0xF0, 0xA1, 0x80, 0x7E, 0x83, 0x04};
const uint8_t* const kCLGetUserCmdPrologue = g::uo ? kCLGetUserCmdPrologueUO : kCLGetUserCmdPrologueCoD1;

// engancha (o restaura) una funcion del exe; el detour vive en esta DLL
void HookExe(bool on, uintptr_t addr, const uint8_t* prologue, int len, void* detour, void*& tramp, const char* name)
{
    bool hooked = *(uint8_t*)addr == 0xE9;
    if (on && !hooked) {
        if (memcmp((void*)addr, prologue, len) != 0) return;
        tramp = hook::Inline(addr, detour, len);
        Log("%s enganchado", name);
    }
    if (!on && hooked && tramp) hook::Write(addr, prologue, len);
}

void HookReliable(bool on)
{
    const uint8_t prologue[5] = {0x51, 0x53, 0x55, 0x56, 0x57};
    HookExe(on, g::A(0x44bc80, 0x44ded0), prologue, 5, (void*)Hook_ReliableWrite,
            g_reliableWriteTramp, "reliable command transport");
}

void HookUsercmd(bool on)
{
    if (S->role == HOST || !on)
        HookExe(on, SV_GET_USERCMD, kGetUsercmdPrologue, sizeof kGetUsercmdPrologue, (void*)Hook_GetUsercmd,
                g_getUsercmdTramp, "SV_GetUsercmd");
    HookExe(on, CL_GET_USERCMD, kCLGetUserCmdPrologue, 8, (void*)Hook_CLGetUserCmd,
            g_clGetUserCmdTramp, "CL_GetUserCmd");
}

// Checkpoint con remotos: el juego guarda a todos los jugadores conectados y al cargar (solo con el host) cortaba
// con "G_LoadGame: client mis-match in savegame". Se carga igual (el `jne` que saltea el error pasa a `jmp`): los
// remotos guardados quedan en el juego sin cliente del motor, y HostDropGhosts los desconecta. No guardarlos rompia
// otras entidades que los nombran (el camion con el remoto enganchado: cierre al cargar en UO).
saved_remote_patch::Ownership g_loadPatch;
bool SavedRemoteLoadReady()
{
    uint8_t* game=(uint8_t*)GetModuleHandleA(g::GameDll());
    uint8_t* branch=game?game+saved_remote_patch::Offset(g::uo):nullptr;
    return game&&saved_remote_patch::Valid(branch,(uintptr_t)game,g::uo)&&branch[0]==0xeb;
}
void HookLoad(uint8_t* game, bool on)
{
    if(!game)return;
    uint8_t* jne=game+saved_remote_patch::Offset(g::uo);
    if(!saved_remote_patch::Valid(jne,(uintptr_t)game,g::uo)) {
        static uint8_t* reported;
        if(on&&reported!=game) {
            reported=game;Log("checkpoint: native saved-player signature mismatch; joining and preservation are blocked");
            CoopStatus("Unsupported native saved-player code. Joining and equipment preservation are blocked.");
        }
        return;
    }
    if(on&&jne[0]==0x75) {
        const uint8_t op=0xeb;
        if(hook::Write((uintptr_t)jne,&op,1)) {
            g_loadPatch={(uintptr_t)jne,true};Log("checkpoint: carga tambien a los remotos guardados");
        }
    } else if(!on&&saved_remote_patch::CanRestore(g_loadPatch,jne,(uintptr_t)game,g::uo)) {
        const uint8_t op=0x75;
        if(hook::Write((uintptr_t)jne,&op,1))g_loadPatch={};
    }
}

void HookDamage(bool on)
{
    uint8_t* game = (uint8_t*)GetModuleHandleA(g::GameDll());
    if (on && game) {
        // UO: scripts como animscripts GetPlayer() hacen getent("player", "classname"); con varios jugadores el
        // juego corta el script con "getent used with more than one entity". Se salta el error y queda el primero
        // (el host): "push msg; call Scr_Error" -> "jmp" al siguiente.
        if (g::uo) {
            uint8_t* err = game + 0x45aef;
            if (err[-2] == 0x74 && err[-1] == 0x0e && err[0] == 0x68 && err[5] == 0xFF && err[6] == 0x15) {
                const uint8_t jmp[2] = {0xEB, 0x0E};
                hook::Write((uintptr_t)err, jmp, 2);
                Log("getent: con varios jugadores devuelve el primero");
            }
        }
        HookLoad(game, true);
        uint8_t* fn = game + G_DAMAGE_RVA;
        if (!memcmp(fn, kGDamagePrologue, sizeof kGDamagePrologue)) {
            // The engine reloads its game DLL at the same preferred base on
            // mission changes. A matching HMODULE is not proof of a live hook.
            if (g_origDamage && g_damageHooked == game) {
                uint8_t patch[sizeof kGDamagePrologue]; memset(patch, 0x90, sizeof patch);
                patch[0] = 0xE9;
                *(int32_t*)(patch + 1) = (int32_t)((uintptr_t)Hook_GDamage - ((uintptr_t)fn + 5));
                if (hook::Write((uintptr_t)fn, patch, sizeof patch))
                    Log("G_Damage reattached after game DLL reload at the same base %p", game);
            } else {
                GDamage_t previous = g_origDamage;
                g_origDamage = (GDamage_t)hook::Inline((uintptr_t)fn, (void*)Hook_GDamage, sizeof kGDamagePrologue);
                if (previous && g_origDamage) VirtualFree((void*)previous, 0, MEM_RELEASE);
                Log("G_Damage enganchado en %p", fn);
            }
            g_damageHooked = game;
        } else if (game != g_damageHooked) {
            Log("G_Damage: unexpected prologue; required damage hook unavailable");
            g_damageHooked = game;
        }
    }
    if (!on && game && g_damageHooked == game && g_origDamage) {
        uint8_t* fn = game + G_DAMAGE_RVA;
        bool restored = !memcmp(fn, kGDamagePrologue, sizeof kGDamagePrologue);
        if (patch_owner::JumpTargets(fn, (uintptr_t)Hook_GDamage))
            restored = hook::Write((uintptr_t)fn, kGDamagePrologue, sizeof kGDamagePrologue);
        if (restored) g_damageHooked = nullptr;
        else {
            // A later wrapper may still forward to Hook_GDamage. Preserve its
            // patch and keep that callback mapped after the loader releases us.
            HMODULE retained = nullptr;
            if (GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_PIN,
                                 reinterpret_cast<LPCSTR>(&Hook_GDamage), &retained))
                Log("G_Damage: foreign/retained hook preserved; core pinned until process exit");
            else Log("G_Damage: ERROR could not pin retained hook (%lu)", GetLastError());
        }
    }
    if (!on && game) HookLoad(game, false);
}

// Jugadores que se traspasan: en training (y otros mapas) todos aparecen en el mismo lugar y encimados nadie se
// podia mover. ClientThink (gamex86 RVA 0x12600: mov ecx, trace) le da a Pmove el trace del juego (RVA 0x42b00);
// lo cambiamos por este, que deja a los demas jugadores sin contents (gentity+0xc4, ver SV_LinkEntity 0x44db30)
// mientras dura el trace. Las balas y la IA usan otros traces: siguen pegando y chocando con los jugadores.
const uint32_t PMOVE_TRACE_IMM = g::G_PMOVE_TRACE_IMM, GAME_TRACE_RVA = g::G_TRACE;
uint8_t* g_gameBase;
void __cdecl PlayerMoveTrace(void* result, const float* start, const float* mins, const float* maxs, const float* end,
                             int passEnt, int mask)
{
    int saved[g::MAX_CLIENTS];
    for (int n = 0; n < g::MAX_CLIENTS; ++n) {
        int& contents = *(int*)(g::Entity(n) + g::GE_CONTENTS);
        saved[n] = contents;
        if (n != passEnt) contents = 0;
    }
    ((void(__cdecl*)(void*, const float*, const float*, const float*, const float*, int, int))(g_gameBase + GAME_TRACE_RVA))(
        result, start, mins, maxs, end, passEnt, mask);
    for (int n = 0; n < g::MAX_CLIENTS; ++n) *(int*)(g::Entity(n) + g::GE_CONTENTS) = saved[n];
}

void HookPlayerTrace(bool on)
{
    uint8_t* game = (uint8_t*)GetModuleHandleA(g::GameDll());
    if (!game || game[PMOVE_TRACE_IMM - 1] != 0xB9) return;  // mov ecx, imm32
    uintptr_t orig = (uintptr_t)(game + GAME_TRACE_RVA), want = on ? (uintptr_t)PlayerMoveTrace : orig;
    uintptr_t now = *(uintptr_t*)(game + PMOVE_TRACE_IMM);
    if (now == want || (now != orig && now != (uintptr_t)PlayerMoveTrace)) return;  // ya esta, o no es el codigo esperado
    g_gameBase = game;
    hook::Write((uintptr_t)(game + PMOVE_TRACE_IMM), &want, 4);
}

// Prediccion de cada cliente (cgame): choca con las entidades que tengan s.solid (gentity+0x80, lo arma SV_LinkEntity
// en cada link). En 0 para los jugadores despues del frame del servidor: el cgame del host lo lee de la memoria del
// servidor y a los remotos les llega asi en M_ENTS y en sus snapshots.
void PlayersNotSolidForPrediction()
{
    for (int n = 0; n < g::MAX_CLIENTS; ++n)
        if (PlayerInGame(n)) *(int*)(g::Entity(n) + 0x80) = 0;
}

// Pausas (tarea 2.5). El SP se pausa con cl_paused 1: SV_Frame no avanza y el cliente no manda usercmds
// (0x40b3e0). Lo pone la UI al abrir un menu y SV_Frame mismo si la UI esta en pantalla completa (0x44d0a3; el
// JNZ de 0x44d0a6 saltea ese paso).
// "Haz clic para iniciar" (ui/pregame.menu): pausa con el mundo sin dibujar; cg_norender queda en 1 desde la carga
// hasta el clic (uiScript playerstart). El ultimo menu de la UI (uix86+0x1bd394) no sirve: tras un devmap en
// juego queda en 7 aunque la pantalla sea la misma.
bool PregameOpen()
{
    uint8_t* norender = g::Cvar_FindVar("cg_norender");
    return norender && *(int*)(norender + 0x20) && g::cl_paused && *(int*)(g::cl_paused + 0x20);
}

void SkipUiPauseCheck(bool skip)
{
    uint8_t* jnz = (uint8_t*)g::A(0x44d0a6, 0x44f3b6);
    uint8_t want = skip ? 0xEB : 0x75;  // JMP / JNZ original
    if (*jnz != want && (*jnz == 0xEB || *jnz == 0x75)) hook::Write((uintptr_t)jnz, &want, 1);
}

// Fin de nivel en curso (changelevel / missionSuccess / missionFailed): ahi la pausa del SP vale (pantalla de
// victoria). gamex86: +0x2dbd00 pedido de salida, +0x298cac tipo de salida, +0x2dbd18 mapa siguiente.
bool LevelExiting()
{
    uint8_t* game = (uint8_t*)GetModuleHandleA(g::GameDll());
    return game && (*(int*)(game + g::G_EXIT_TYPE) || *(int*)(game + g::G_EXIT_REQUEST));
}

// Host: con remotos conectados el menu no pausa (como en multijugador). La pantalla de inicio tras cargar y la de
// fin de nivel si.
bool g_noPause;  // HostNoPause activo: el menu del host no pausa
void HostNoPause()
{
    bool on = g_noPause = CoopActive() && !PregameOpen() && !LevelExiting();
    SkipUiPauseCheck(on);
    if (on && *(int*)(g::cl_paused + 0x20)) {
        g::Cvar_Set("cl_paused", "0");
        Log("host: menu abierto con remotos conectados, el juego sigue");
    }
}

// El menu principal muestra los botones de partida en curso (Volver a la partida, Guardar...) o los de afuera
// (Continuar partida = cargar lo ultimo guardado) segun cl_paused. Como HostNoPause deja cl_paused en 0, el host
// veia los de afuera. El menu de pakz_coop.pk3 (tools/make_ui.py) mira ui_coop_paused: cl_paused, o 1 si el host
// tiene el menu abierto sin pausa (UI_IS_FULLSCREEN, vmMain 6 de la UI, como 0x4103e0).
void UiPausedFrame()
{
    if (!g::cl_paused) return;
    int args[13] = {6};
    bool paused = *(int*)(g::cl_paused + 0x20) || (g_noPause && g::uivm && g::CallVM(g::uivm, args));
    static int last = -1;
    if (paused == last) return;  // Cvar_Set lo anuncia en la consola
    g::Cvar_Set("ui_coop_paused", paused ? "1" : "0");
    last = paused;
}

// Remoto: "Haz clic para iniciar" se saltea solo, haciendo lo mismo que el clic
void JoinerSkipPregame()
{
    if (!S->joined || !g::uivm || !PregameOpen()) return;
    int args[13] = {7, 0};  // UI_SET_ACTIVE_MENU, ninguno: cierra los menus y suelta el teclado
    g::CallVM(g::uivm, args);
    g::Cvar_Set("cl_paused", "0");
    g::Cvar_Set("cg_norender", "0");
    g::Cbuf_AddText("fade 0 0 0 0 3\n");
    Log("joiner: pantalla de inicio salteada");
}

// Continue the earned CoD1 finale into UO, after preserving the original
// credits. This is exactly victoryscreen's normal Continue action (close +
// cl_paused 0), never a synthetic mission success or direct map command.
void MainlineContinue()
{
    static DWORD readySince;
    uint8_t* game = (uint8_t*)GetModuleHandleA(g::GameDll());
    bool earned = S->role == HOST && g::uo && CvarInt("coop_mainline") == 1 &&
                  !_stricmp(g::CvarString("mapname"), "coop_cod1_credits") &&
                  CvarInt("g_reloading") == 4 && !MoviePlaying() && game &&
                  !strcmp((const char*)game + g::G_EXIT_MAP, "bastogne1");
    if (!earned) { readySince = 0; return; }
    if (!readySince) {
        readySince = GetTickCount();
        Log("mainline: original credits complete; continuing into United Offensive in 5 seconds");
        CoopStatus("CoD completed. Continuing together into United Offensive...");
    }
    if (GetTickCount() - readySince < 5000 || !g::uivm) return;
    int args[13] = {7, 0};
    g::CallVM(g::uivm, args);
    g::Cvar_Set("cl_paused", "0");
    Log("mainline: normal victory Continue action, next mission bastogne1");
    readySince = 0;
}

void MainlineStartMission()
{
    static pregame::Gate startup;
    static bool warned;
    bool partyTransition = CvarInt("coop_expected_players") > 1;
    if (S->role != HOST || (!(g::uo && CvarInt("coop_mainline") == 1) && !partyTransition)) {
        startup = pregame::Gate{}; warned = false; return;
    }
    bool nativeReady = !MoviePlaying() && g::uivm && g::cgvm && g::cls_state == 2 && g::sv_state == 2 &&
        g::cl_snapNum > 0 && g::cl_snapServerTime > 0 && PlayerInGame(0);
    int expected = CvarInt("coop_expected_players");
    if (expected < 1) expected = 1;
    if (expected > g::MAX_CLIENTS) nativeReady = false;
    int ready = 1;
    for (int n = 1; n < g::MAX_CLIENTS; ++n) {
        if (!S->remote[n].active) continue;
        if (!S->remote[n].worldReady) nativeReady = false;
        ++ready;
    }
    nativeReady = nativeReady && ready >= expected;
    // Never close the previous UI while the new cgame is still initializing.
    // A late native pause reassertion may be retried only in this same world,
    // before its clock has advanced, at most three times within five seconds.
    bool start = startup.Poll(CvarInt("sv_serverid"), (uintptr_t)g::cgvm, (uintptr_t)g::uivm,
                              nativeReady, PregameOpen(), CvarInt("cl_paused") != 0, g::sv_time, GetTickCount());
    if (!startup.exhausted) warned = false;
    if (startup.exhausted && !warned) {
        warned = true;
        Log("mainline: native mission-start UI did not advance; waiting for manual start/retry");
        CoopStatus("Mission start is still paused. Use the game's Start action or retry the session.");
    }
    if (!start) return;
    int args[13] = {7, 0};
    g::CallVM(g::uivm, args);
    g::Cvar_Set("cl_paused", "0"); g::Cvar_Set("cg_norender", "0");
    g::Cbuf_AddText("fade 0 0 0 0 3\n");
    Log("mainline: %d players ready, normal mission-start UI action", ready);
}

// Desconexiones (3.3). El host anota cuando llego el ultimo paquete de cada remoto; si pasan REMOTE_TIMEOUT sin
// nada (se cerro el juego, se corto la red) lo suelta: cuerpo, entidad (ClientDisconnect = vmMain 4 del juego;
// el 5 es ClientCommand y el 6 ClientThink) y lugar. Con el menu abierto el remoto no manda usercmds: manda
// M_PING cada segundo. El remoto que no recibe nada del host en HOST_TIMEOUT vuelve al menu principal.
constexpr DWORD REMOTE_TIMEOUT = 8000, HOST_TIMEOUT = 15000;
DWORD g_lastSeen[g::MAX_CLIENTS];  // host: ultimo paquete de cada remoto (0 = sin medir todavia)
DWORD g_hostSeen;                  // remoto: ultimo paquete del host

void HostDropRemote(int n, bool explicitLeave = false)
{
    S->selection.host[n]={};S->selection.producer[n]={};
    Log("host: se libera el lugar del jugador %d (ultimo paquete hace %lu ms)", n, GetTickCount() - g_lastSeen[n]);
    if (S->bodyTree[n]) HostFreeBody(n);
    S->downed[n] = false;
    S->remote[n].active = false;
    if (explicitLeave) {
        char expected[8];
        snprintf(expected, sizeof expected, "%d", patch_owner::ExpectedAfterDeparture(CvarInt("coop_expected_players"), true));
        g::Cvar_Set("coop_expected_players", expected);
        Log("party: player %d explicitly left; expected players now %s", n + 1, expected);
    }
    if(explicitLeave) {S->inventories.slots[n]={};S->preservation.slots[n]={};}
    else CapturePeerInventory(n,"temporary disconnect before native cleanup");
    PreservationWait(n);
    g::GameCall(4, n);
    *(int*)(g::Client(n) + g::CL_STATE) = 0;
    g_lastSeen[n] = 0;
    char text[96];
    snprintf(text, sizeof text, "^3Player %d disconnected", n + 1);
    for (int m = 0; m < g::MAX_CLIENTS; ++m)
        if (m != n) SendBanner(m, text, false);
    g::Com_Printf("^3COOP: player %d disconnected\n", n + 1);
    CheckPathLists("despues de ClientDisconnect");
}

// se llama cuando ya no quedan paquetes por leer (asi una traba larga del host no suelta a nadie). Tambien manda
// M_PING cada segundo: en pausa (pantalla de victoria, "Haz clic para iniciar") no salen snapshots.
void HostCheckRemotes()
{
    HostDropGhosts();
    DWORD now = GetTickCount();
    static DWORD lastPing;
    bool ping = now - lastPing > 1000;
    if (ping) lastPing = now;
    for (int n = 1; n < g::MAX_CLIENTS; ++n) {
        if (!S->remote[n].active || !PlayerInGame(n)) {
            g_lastSeen[n] = 0;
            continue;
        }
        if (ping) {
            Writer w(M_PING);
            SendTo(S->remote[n].addr, w.buf, w.len);
        }
        if (!g_lastSeen[n]) g_lastSeen[n] = now;  // recien entrado o nucleo recargado
        if (now - g_lastSeen[n] > REMOTE_TIMEOUT) HostDropRemote(n);
    }
}

// Antes de que el host cargue un mapa (el checkpoint o uno nuevo) se sueltan los remotos y los cuerpos. Si quedaran
// conectados, la carga les manda comandos que nadie confirma ("Reliable command buffer overflow"); los arboles se
// liberan ahora, mientras su memoria sigue siendo valida. Los remotos cargan `map` y se vuelven a unir solos.
bool HostReloadPending()
{
    for (int n = 1; n < g::MAX_CLIENTS; ++n)
        if (S->reloadPending[n].delivery.active) return true;
    return false;
}

void HostReloadTick()
{
    if (S->role != HOST) return;
    DWORD now = GetTickCount();
    for (int n = 1; n < g::MAX_CLIENTS; ++n) {
        auto& pending = S->reloadPending[n];
        if (!reload_delivery::Due(pending.delivery, now)) continue;
        Writer w(M_RELOAD);
        w.Put(pending.delivery.token); w.Put(pending.movieCutoff);
        w.Put(pending.map, (int)strlen(pending.map) + 1);
        SendTo(pending.address, w.buf, w.len);
        reload_delivery::Sent(pending.delivery, now);
    }
}

void HostDropRemotes(const char* map, bool freeBodies)
{
    if (!++S->reloadToken.generation) ++S->reloadToken.generation;
    memset(S->selection.host,0,sizeof S->selection.host);memset(S->selection.producer,0,sizeof S->selection.producer);
    for(int n=1;n<g::MAX_CLIENTS;++n)SelectionResetStatus(n);
    // A new native world must supply its restored numeric data, never reuse a
    // pre-load kit or stale weapon/model IDs. Seats remain owned by their peers.
    for(int n=1;n<g::MAX_CLIENTS;++n)
        peer_inventory::Transition(S->inventories.slots[n],S->reloadToken,map);
    PreservationWorld(map);
    PublishSpawnTickets();
    S->movie.name[0] = 0; // a subsequent mission must not replay a delayed old film
    // Los cuerpos se liberan solo antes de un mapa nuevo (Hook_SpawnServer). Con la mision fallida el juego sigue
    // corriendo la pantalla de derrota y le pide al motor el DObj de los jugadores (trap -> 0x449bf0, que se cae si
    // ya no esta); al cargar partida el servidor ya se cerro (svs.clients en 0, esa memoria liberada: 0x45b8f0). En
    // esos casos la carga limpia todo y aca solo se olvidan.
    bool server = g::sv_state == 2 && g::svs_clients;
    for (int n = 0; n < g::MAX_CLIENTS; ++n) {
        if (S->bodyTree[n] && server && freeBodies) HostFreeBody(n);
        S->bodyTree[n] = nullptr;
        S->downed[n] = false;
    }
    for (int n = 1; n < g::MAX_CLIENTS; ++n) {
        if (!S->remote[n].active && !S->reloadPending[n].delivery.active) continue;
        auto& pending = S->reloadPending[n];
        if (S->remote[n].active) pending.address = S->remote[n].addr;
        pending.delivery = {S->reloadToken, 0, true, false};
        pending.movieCutoff = S->movie.serial;
        snprintf(pending.map, sizeof pending.map, "%s", map);
        if (server) *(int*)(g::Client(n) + g::CL_STATE) = 0;
        S->remote[n].active = false;
    }
    HostReloadTick();
}

#include "weapon_selection.inc"
#include "inventory_preservation.inc"

// g_reloading copia el tipo de salida del nivel (gamex86 0x2001e6b0): 1 = mision fallida (pantalla de "La mision
// ha fracasado" hasta que carga el checkpoint), 4 = nivel terminado (pantalla de victoria), 2 = justo antes de
// "spmap <siguiente>", 0x10 = otra salida. Aca solo el 1; el nivel siguiente lo atiende Hook_SpawnServer.
int g_hostWorldId;
int g_hostWorldTime;
bool g_hostWorldKnown;
void HostCheckReload()
{
    PreservationObserveReady();
    if (S->role != HOST) { g_hostWorldKnown = false; return; }
    // A nested engine syscall may pump networking while GAME_INIT is still
    // constructing the new world. Neither commit nor baseline that half-world.
    if(g::currentVM==g::gvm)return;
    auto& init=S->preservation.init;
    if(init.valid&&init.nativeReady&&!init.handled&&g::currentVM!=g::gvm&&g::sv_state==2&&g::sv_gameClients) {
        if(!init.announced) HostDropRemotes(g::CvarString("mapname"),false);
        init.handled=true;g_hostWorldKnown=false;
    }
    if (g::sv_state == 2 && g::svs_clients && g::sv_gameClients) {
        int id = CvarInt("sv_serverid");
        bool changed = g_hostWorldKnown && (id != g_hostWorldId || g::sv_time < g_hostWorldTime);
        g_hostWorldId = id; g_hostWorldTime = g::sv_time; g_hostWorldKnown = true;
        if (changed) {
            // Native loadgame can set and clear g_reloading entirely inside
            // one command execution. Catch its server generation before any
            // rolled-back snapshots reach a still-running remote cgame.
            Log("host: restored world generation %d time %d; reconnect remote clients", id, g::sv_time);
            HostDropRemotes(g::CvarString("mapname"), false);
            return;
        }
    }
    uint8_t* reloading = g::Cvar_FindVar("g_reloading");
    int value = reloading ? *(int*)(reloading + 0x20) : 0;
    if (value != 1 || !CoopActive()) return;
    Log("host: mision fallida (g_reloading %d), se sueltan los remotos hasta que cargue el checkpoint", value);
    HostDropRemotes(g::CvarString("mapname"), false);
}

// SV_SpawnServer(mapa, x) (0x44c1b0; unico llamador SV_Map_f en 0x448246): fin de nivel (spmap), map/devmap en la
// consola. Antes de que arranque el servidor nuevo, los remotos se sueltan y se les dice que mapa cargar.
const uintptr_t SPAWN_SERVER = g::A(0x44c1b0, 0x44e3f0), SPAWN_SERVER_CALL = g::A(0x448246, 0x44a439);

void __cdecl Hook_SpawnServer(const char* map, int x)
{
    if(suite::IsQA())Log("QA native SpawnServer engine=%s map=%s save_intent=%d fresh_ticket=%d",g::uo?"uo":"cod1",map,x,spawn_ticket::FreshMission(x));
    if (S && S->role == HOST) {
        Log("host: carga el mapa %s, los remotos lo cargan y vuelven", map);
        S->preservation.init.valid=false;
        HostDropRemotes(map, true);
        S->preservation.expectSpawnInit=true;
        g_hostWorldKnown=false;
    }
    ((void(__cdecl*)(const char*, int))SPAWN_SERVER)(map, x);
    HookDamage(true); // install fresh game-module hooks before another player can join
}

void HookSpawnServer(bool on)
{
    uint8_t* call = (uint8_t*)SPAWN_SERVER_CALL;
    uintptr_t want = on ? (uintptr_t)Hook_SpawnServer : SPAWN_SERVER;
    if (call[0] == 0xE8 && SPAWN_SERVER_CALL + 5 + *(int32_t*)(call + 1) != want) hook::PatchRel32(SPAWN_SERVER_CALL, (void*)want);
}

// ---------- joiner ----------

void JoinerSendJoin()
{
    if (!g_profileReady) return;
    if (!S->compatible) {
        if (suite::HandshakeExpired(GetTickCount(), S->joinStarted, S->lastJoinTry)) {
            CoopStatus("Host did not pass the suite handshake (offline or older mod). Update both installations.");
            Log("suite: handshake timed out");
            if (S->recoveringConnection) JoinerLeave("Could not reconnect to the host. Retry joining when the host is available.");
            else S->role = NONE;
            return;
        }
        Writer hello(suite::HELLO);
        SendTo(S->host, hello.buf, hello.len);
        S->lastJoinTry = GetTickCount();
        return;
    }
    if (!S->qport) {
        sockaddr_in local{}; int size = sizeof local;
        if (getsockname(S->sock, (sockaddr*)&local, &size)) return;
        S->qport = ntohs(local.sin_port);
    }
    Writer w(M_JOIN);
    w.Put<int>(S->qport);
    w.Put<int>(*(int*)(g::clc_netchan + g::NC_IN));
    w.Put<int>(g::clc_serverCommandSequence);
    w.Put<int>(g::clc_reliableSequence);
    const char* map = g::CvarString("mapname");  // el host contesta M_MAP si no es el suyo
    w.Put(map, (int)strlen(map) + 1);
    SendTo(S->host, w.buf, w.len);
    S->lastJoinTry = GetTickCount();
}

void QueueJoinerMap(const char* map)
{
    S->selection.peer={};S->selection.acceptedTicket=0;
    // All reload entry paths, including timeout recovery, hand ownership to
    // normal native world loading in the same way as an explicit host reload.
    if (g::uo) KeepOldTrees();
    memset(S->ownTree, 0, sizeof S->ownTree);
    S->recoveringConnection = false;
    S->gamestateReady = false;
    snprintf(S->pendingMap, sizeof S->pendingMap, "%s", map);
    S->previousLocalWorld = CvarInt("sv_serverid");
    S->mapLoadStarted = GetTickCount();
    S->waitingForMap = true;
    S->role = NONE; S->joined = S->frozen = false;
    S->movieWorldSuspended = false;
    char command[96];
    snprintf(command, sizeof command, "devmap %s\n", S->pendingMap);
    g::Cbuf_AddText(command);
}

void JoinerHijack()
{
    if (S->frozen || !S->rules.required || S->rules.received != S->rules.required) return;
    // sv_state 1 tambien sirve: al volver a entrar sin cerrar el juego el servidor local queda en 1 con el mapa
    // cargado, y pedir el mapa de nuevo era un ciclo sin fin
    if (g::sv_state == 0 || !g::cgvm || g::cls_state == 0 || _stricmp(S->hostMap, g::CvarString("mapname")) != 0) {
        // sin el mapa del host cargado (o un error del motor lo cerro): cargarlo y volver a entrar
        Log("joiner: mapa local '%s' (servidor %d), cargo %s y vuelvo a entrar", g::CvarString("mapname"), g::sv_state,
            S->hostMap);
        QueueJoinerMap(S->hostMap);
        return;
    }
    SetHostRules(S->rules.accepted); // exact accepted rules immediately before native prediction attaches
    FreeOldTrees();
    QACaptureNativeTrees();
    char barrierOption[8]{};
    bool barrierEnabled = g_qaDeferredEnabled && g_qaBorrowEnabled &&
        GetEnvironmentVariableA("CODCOOP_QA_DOBJ_BARRIER", barrierOption, sizeof barrierOption) && !strcmp(barrierOption, "1");
    auto barrier = qa_dobj_barrier::Run(barrierEnabled,
        g::uo && g::sv_state != 0 && g::sv_gentities && g::sv_gentitySize == 0x2d0 && g::cgvm,
        g::MAX_GENTITIES,
        [](unsigned entity) { return g::serverObjMap[entity] != 0; },
        [](unsigned entity, bool clear) { g::Com_ServerDObjFree((int)entity, clear); },
        [] { g::Com_SyncClientDObjs(); });
    if (barrierEnabled && !barrier.ran) {
        Log("QA DObj mapping barrier waiting for a valid local native world");
        return;
    }
    if (barrier.ran) Log("QA DObj mapping barrier detached=%u before host model IDs", barrier.detached);
    S->frozen = true;                              // el servidor local queda solo para colision y assets
    *(int*)(g::Client(0) + g::CL_STATE) = 0;      // que no acumule comandos que nadie confirma
    for (int i = 0; i < g::MAX_CONFIGSTRINGS; ++i)
        if (strcmp(g::ConfigString(i), S->cs[i]) != 0) g::SV_SetConfigstring(i, S->cs[i]);
    int state = g::cls_state;
    g::CL_NetchanSetup(ToNet(S->host));
    *(int*)(g::clc_netchan + g::NC_QPORT) = S->qport;
    g::cls_state = state;
    g::CL_ApplyConfigstrings(g::sv_configstrings);
    S->joined = true;
    Writer ready(M_WORLD_READY); SendTo(S->host, ready.buf, ready.len);
    Log("joiner: conectado al host como slot %d en %s", S->slot, S->hostMap);
    g::Com_Printf("^2COOP: connected to the host (player %d)\n", S->slot + 1);
}

// nombre de mapa que manda el host (va a la consola con devmap): solo letras, numeros, _ y -; si no, ""
const char* MapName(const Reader& r)
{
    static char name[64];
    name[0] = 0;
    int len = 0;
    for (const uint8_t* p = r.p; p < r.end && *p; ++p, ++len)
        if (len >= (int)sizeof name - 1 || !(isalnum(*p) || *p == '_' || *p == '-')) return name;
    if (r.p + len >= r.end) return name;  // sin terminador
    memcpy(name, r.p, len);
    name[len] = 0;
    return name;
}

void JoinerControl(uint8_t type, Reader r)
{
    if (S->movieWorldSuspended && (type == M_ENTS || type == M_DOBJ || type == M_ANIM || type == M_DOWNED)) return;
    switch (type) {
    case M_RULES: {
        uint32_t serial = r.Get<uint32_t>(); auto values = r.Get<host_rules::Values>();
        if (!r.Ok() || r.p != r.end || !serial) return;
        if (serial != S->rules.received && !host_rules::Newer(serial, S->rules.received)) return;
        if (!ApplyHostRules(serial, values)) {
            Writer bye(M_BYE); SendTo(S->host, bye.buf, bye.len);
            JoinerLeave("The host supplied an unsupported YAP gameplay setting. Correct the host settings before retrying.");
        } else S->rules.required = serial;
        break;
    }
    case M_CINEMATIC:
        if (S->joined) JoinerMovie(r);
        break;
    case weapon_selection::MESSAGE:
        SelectionPeerMessage(r);
        break;
    case suite::READY:
        if (!S->compatible && !S->joined) {
            S->compatible = true;
            Log("suite: host compatibility verified, requesting player slot");
            JoinerSendJoin();
        }
        break;
    case suite::REJECT: {
        const char* reason = (const char*)r.p;
        if (!memchr(r.p, 0, (size_t)(r.end - r.p))) return;
        Log("suite: rejected: %.200s", reason);
        CoopStatus("%.200s", reason);
        if (S->recoveringConnection) { JoinerLeave(reason); break; }
        S->role = NONE;
        S->compatible = false;
        break;
    }
    case M_ACCEPT: {
        if (S->joined || !S->compatible) return;
        int slot = r.Get<int>();
        int qport = r.Get<int>();
        int hostTime = r.Get<int>();
        auto world = r.Get<reload_delivery::Token>();
        uint32_t ruleSerial = r.Get<uint32_t>(); auto ruleValues = r.Get<host_rules::Values>();
        const char* map = MapName(r);
        if (!r.Ok() || hostTime < 0 || slot < 1 || slot >= g::MAX_CLIENTS || qport < 1 || qport > 65535 || !*map) return;
        r.p+=strlen(map)+1;
        uint32_t capability=r.Get<uint32_t>(),ticket=r.Get<uint32_t>();
        if(!weapon_selection::Capability(capability,ticket,r.Ok()&&r.p==r.end)) {
            JoinerLeave("The host core lacks required player-selection capability. Install the same complete suite.");return;
        }
        if (!reload_delivery::Valid(world)) return;
        if (S->reloadToken.session && !reload_delivery::Same(world, S->reloadToken) &&
            !reload_delivery::Newer(world, S->reloadToken)) return;
        if (!ruleSerial || !host_rules::Valid(ruleValues)) {
            JoinerLeave("The host supplied an unsupported YAP gameplay setting."); return;
        }
        if (S->rules.received && ruleSerial != S->rules.received && !host_rules::Newer(ruleSerial, S->rules.received)) return;
        if (!ApplyHostRules(ruleSerial, ruleValues)) {
            JoinerLeave("Could not preserve local YAP settings before joining."); return;
        }
        S->rules.required = ruleSerial;
        if(S->selection.acceptedTicket!=ticket||!reload_delivery::Same(world,S->reloadToken))S->selection.peer={};
        S->selection.acceptedTicket=ticket;
        S->reloadToken = world;
        if (S->recoveringConnection) {
            snprintf(S->hostMap, sizeof S->hostMap, "%s", map);
            Log("joiner: host recovered, reload %s before attaching the new world", S->hostMap);
            QueueJoinerMap(S->hostMap);
            return;
        }
        // A player can enter Coop after spending time in their local SP world.
        // Cgame rejects older host snapshots. Reload through the normal engine
        // path instead of altering its private snapshot/prediction structures.
        if (g::cl_snapServerTime > hostTime) {
            Writer leave(M_BYE); SendTo(S->host, leave.buf, leave.len);
            snprintf(S->hostMap, sizeof S->hostMap, "%s", map);
            Log("joiner: local clock %d ahead of host %d; reload before joining", g::cl_snapServerTime, hostTime);
            QueueJoinerMap(S->hostMap);
            return;
        }
        S->qport = (uint16_t)qport;
        S->slot = slot;
        snprintf(S->hostMap, sizeof S->hostMap, "%s", map);
        break;
    }
    case M_FULL:
        g::Com_Printf("^1COOP: the host is full (4 players)\n");
        CoopStatus("The host already has 4 players.");
        if (S->recoveringConnection) { JoinerLeave("The host has no free player slot. Retry joining when a slot is available."); break; }
        S->role = NONE;
        break;
    case M_MAP: {  // el host esta en otro mapa: cargarlo y volver a pedir lugar
        const char* map = MapName(r);
        if (S->joined || S->role != JOINER || !*map) return;
        if (!_stricmp(map, g::CvarString("mapname"))) return;  // respuesta vieja (pedidos en cola mientras el host cargaba)
        snprintf(S->hostMap, sizeof S->hostMap, "%s", map);
        Log("joiner: el host esta en %s, lo cargo y vuelvo a entrar", map);
        g::Com_Printf("^3COOP: the host is on %s, loading...\n", map);
        CoopStatus("Host found: loading %s...", map);
        QueueJoinerMap(map);
        break;
    }
    case M_CS:
        while (r.p + 4 <= r.end) {
            int i = r.Get<uint16_t>(), l = r.Get<uint16_t>();
            if (i >= g::MAX_CONFIGSTRINGS || l > 1000 || r.p + l > r.end) break;
            memcpy(S->cs[i], r.p, l);
            S->cs[i][l] = 0;
            r.p += l;
        }
        break;
    case M_CSDONE: {
        int sent = r.Get<uint16_t>(), have = 0;
        if (S->joined || !S->hostMap[0]) break;
        for (const auto& s : S->cs) have += s[0] != 0;
        if (r.Ok() && have < sent) {  // se perdio una parte: el reintento de M_JOIN la vuelve a pedir
            Log("joiner: hay %d de %d configstrings, se pide de nuevo", have, sent);
            break;
        }
        Log("joiner: gamestate completo (%d configstrings)", have);
        // Packet polling can run inside an already-started SV_Frame. Mutating
        // local DObjs here lets that old game frame run against host models.
        // Attach only at the next server-frame boundary, which will be skipped.
        S->gamestateReady = true;
        break;
    }
    case M_DOBJ:
        if (S->joined) JoinerApplyDObj(r);
        break;
    case M_BYE: {
        uint8_t reason = r.Get<uint8_t>();
        auto token = r.Get<reload_delivery::Token>();
        if (r.Ok() && r.p == r.end && reason == 1 && reload_delivery::AcceptClose(token, S->reloadToken))
            JoinerLeave("The host closed the co-op game.");
        break;
    }
    case M_ANIM: {
        if (!S->joined) return;
        while (r.p <= r.end && (size_t)(r.end - r.p) >= sizeof(animwire::Header)) {
            animwire::Header h{}; memcpy(&h, r.p, sizeof h); r.p += sizeof h;
            size_t bytes = (size_t)h.count * animwire::STATE_BYTES;
            if (bytes > (size_t)(r.end - r.p)) return;
            std::vector<uint8_t> complete;
            if (g_animAssembler.Feed(h, r.p, bytes, complete))
                JoinerApplyAnims(Reader{complete.data(), complete.data() + complete.size()});
            r.p += bytes;
        }
        break;
    }
    case M_RELOAD: {
        // El host carga un mapa: el checkpoint (su reloj retrocede y el cgame de aca cortaria con "Server time went
        // backwards") o el nivel siguiente. Se hace como al entrar: ese mapa local y despues unirse (cooprejoin).
        // Los DObj propios no se liberan: el servidor local corre un frame mas antes del devmap y le pide al motor
        // esos DObj (trap -> 0x449bf0 se caia), y despues el devmap limpia esa memoria. Solo se olvidan.
        auto token = r.Get<reload_delivery::Token>();
        uint32_t movieCutoff = r.Get<uint32_t>();
        if (!r.Ok()) return;
        const char* map = MapName(r);
        if (!*map || !reload_delivery::Valid(token)) return;
        bool duplicate = reload_delivery::Same(token, S->reloadToken);
        if (!duplicate && (!S->joined || !reload_delivery::Newer(token, S->reloadToken))) return;
        if (!duplicate) S->reloadToken = token; // the ACK header must echo the newly accepted world
        Writer ack(M_RELOAD_ACK); ack.Put(token); SendTo(S->host, ack.buf, ack.len);
        if (duplicate) return; // acknowledge again without reloading the world twice
        if (campaign_cinematics::Newer(movieCutoff, S->receivedMovie)) S->receivedMovie = movieCutoff;
        S->movieWorldSuspended = false;
        g_animAssembler.Reset();
        bool newMap = *map && _stricmp(map, S->hostMap) != 0;
        if (*map) snprintf(S->hostMap, sizeof S->hostMap, "%s", map);
        S->joined = S->frozen = false;
        S->role = NONE;  // hasta cooprejoin: no se manda nada mientras carga
        memset(S->downed, 0, sizeof S->downed);
        Log("joiner: el host carga %s (%s), lo cargo y vuelvo a entrar", S->hostMap, newMap ? "nivel nuevo" : "checkpoint");
        if (newMap) g::Com_Printf("^3COOP: the host moved on to %s, loading...\n", S->hostMap);
        else g::Com_Printf("^3COOP: the host went back to the last checkpoint, reconnecting...\n");
        QueueJoinerMap(S->hostMap);
        break;
    }
    case M_DOWNED: {
        uint8_t mask = r.Get<uint8_t>();
        for (int m = 0; m < g::MAX_CLIENTS; ++m) {
            bool d = mask >> m & 1;
            if (d == S->downed[m]) continue;
            S->downed[m] = d;
            DownedMessage(m, d, S->slot);
        }
        g_team = r.Get<uint8_t>();
        for (auto& p : g_teamPos)
            for (float& v : p) v = r.Get<float>();
        if (!r.Ok()) g_team = 0;
        break;
    }
    case M_ENTS: {
        if (!S->joined || !g::sv_gentities) return;  // sin servidor local (se cerro el mapa) no hay donde copiar
        int count = r.Get<uint16_t>();
        for (int k = 0; k < count && r.p + 2 + g::ENTSTATE_SIZE <= r.end; ++k) {
            int e = r.Get<uint16_t>();
            if (e < g::MAX_GENTITIES) memcpy(g::Entity(e), r.p, g::ENTSTATE_SIZE);
            r.p += g::ENTSTATE_SIZE;
        }
        break;
    }
    }
}

// Remoto conectado: M_PING al host cada segundo (con el menu abierto no salen usercmds) y, si el host no manda
// nada en HOST_TIMEOUT (se cerro o se corto), vuelta al menu principal.
void JoinerKeepAlive()
{
    if (!S->joined) return;
    DWORD now = GetTickCount();
    static DWORD lastPing;
    if (now - lastPing > 1000) {
        Writer w(M_PING);
        SendTo(S->host, w.buf, w.len);
        Writer ready(M_WORLD_READY); SendTo(S->host, ready.buf, ready.len);
        lastPing = now;
    }
    if (!g_hostSeen) g_hostSeen = now;  // nucleo recien recargado
    if (now - g_hostSeen < HOST_TIMEOUT) return;
    Log("joiner: host silent for %lu ms; waiting to reconnect", now - g_hostSeen);
    S->recoveringConnection = true;
    S->joined = S->compatible = S->gamestateReady = false;
    S->rules.required = 0;
    S->joinStarted = S->lastJoinTry = 0;
    memset(S->cs, 0, sizeof S->cs);
    CoopStatus("Connection interrupted. Waiting to reconnect to the host. Choose Leave to cancel.");
    JoinerSendJoin();
}

// Vuelta al menu principal. Los DObj propios se olvidan (como en M_RELOAD): el servidor local corre hasta que
// "disconnect" lo cierra y le pediria al motor los que se liberaran.
void JoinerLeave(const char* why)
{
    S->selection={};
    S->reloadToken = {};
    S->recoveringConnection = false;
    S->waitingForMap = false;
    S->pendingMap[0] = 0;
    S->host.sin_port = 0; // a queued cooprejoin must not revive a cancelled session
    RestoreHostRules(); S->rules.received = S->rules.required = 0;
    g_animAssembler.Reset();
    for (int e = 0; e < g::MAX_GENTITIES; ++e)
        if (S->ownTree[e] || g_qaBorrowed[e].tree) JoinerFreeDObj(e);
    // UO disconnect reaches native MT_Init (45fab0) through full shutdown.
    // Deferred indices belong to the old allocator and must never be freed
    // after a new session has rebuilt that pool, even at identical addresses.
    if (g_oldTreeCount) Log("joiner: forget %d deferred tree indices before native disconnect", g_oldTreeCount);
    g_oldTreeCount = 0;
    for (auto& borrowed : g_qaBorrowed) borrowed = {};
    for (auto& owner : g_qaNativeOwners) owner = {};
    S->joined = S->frozen = false;
    S->role = NONE;
    HookCgame(false);  // como un juego recien abierto: si no, el mapa local no termina de cargar al volver a entrar
    HookUsercmd(false);
    g_hostSeen = 0;
    memset(S->downed, 0, sizeof S->downed);
    g::Com_Printf("^3COOP: %s\n", why);
    CoopStatus("%s", why);
    g::Cbuf_AddText("disconnect\n");
}

// ---------- Steam (steam.h) ----------

// "Unirse a la partida" desde la lista de amigos de Steam: el texto viene del rich presence de otro, asi que
// solo se acepta exactamente "+coopjoin steam:<numero>"
void OnSteamJoin(const char* connect)
{
    const char* id = connect + strlen("+coopjoin steam:");
    if (strncmp(connect, "+coopjoin steam:", strlen("+coopjoin steam:")) || !*id || strspn(id, "0123456789") != strlen(id)) {
        Log("steam: pedido de union ignorado: '%.64s'", connect);
        return;
    }
    char cmd[64];
    snprintf(cmd, sizeof cmd, "coopjoin steam:%s\n", id);
    g::Cbuf_AddText(cmd);
}

// botones "Unirse a <amigo>" del menu desde el k-esimo: ocultos (el menu los esconde con coop_friendid = "0")
void HideFriendButtons(int k)
{
    for (; k <= 3; ++k) {
        char var[32];
        snprintf(var, sizeof var, "ui_coop_friend%d", k);
        g::Cvar_Set(var, "");
        snprintf(var, sizeof var, "coop_friendid%d", k);
        g::Cvar_Set(var, "0");
    }
}

// Cada frame: Steam (se reintenta si se abre despues), callbacks, rich presence del host y, cada 2 s, los
// amigos anfitriones para el menu Cooperativo (cvars ui_coop_friend1..3 = texto, coop_friendid1..3 = SteamID).
void SteamFrame()
{
    if (suite::IsQA() && getenv("CODCOOP_QA_NO_STEAM")) return;
    static bool wasUp, presence, triedOnce;
    bool up = steam::Start();
    if (up != wasUp || !triedOnce) {
        if (up) Log("steam: listo como '%s' (%I64u)", steam::Name(steam::MyId()), steam::MyId());
        else Log("steam: no disponible (%s), solo por IP", steam::error);
        if (!up) {
            g::Cvar_Set("ui_coop_steam", steam::needSteamLaunch ? "Start the game from Steam to invite friends."
                                                                : "Steam is closed: you can only join by IP.");
            HideFriendButtons(1);
        }
        wasUp = up;
        triedOnce = true;
    }
    if (!up) return;
    steam::Poll(OnSteamJoin);
    if ((S->role == HOST) != presence) {  // al crear partida y al dejar de ser anfitrion (coopleave)
        presence = S->role == HOST;
        char connect[64];
        snprintf(connect, sizeof connect, "+coopjoin steam:%I64u", steam::MyId());
        steam::SetPresence("codcoop", presence ? "host" : "");
        steam::SetPresence("connect", presence ? connect : "");
        steam::SetPresence("status", presence ? "Hosting CoD Coop" : "");
    }
    static DWORD lastScan;
    if (GetTickCount() - lastScan < 2000) return;
    lastScan = GetTickCount();
    struct { char text[3][96], id[3][24]; } now = {};
    static decltype(now) prev = {{"-"}};
    int found = 0;
    steam::ForEachHost([&](uint64_t id) {
        if (found == 3) return;
        char name[64];
        steam::Latin1(steam::Name(id), name, sizeof name);
        snprintf(now.text[found], sizeof now.text[found], "Join %s", name);
        snprintf(now.id[found], sizeof now.id[found], "%I64u", id);
        ++found;
    });
    if (!memcmp(&now, &prev, sizeof now)) return;  // solo si cambio la lista: Cvar_Set lo anuncia en la consola
    prev = now;
    for (int k = 0; k < 3; ++k) {
        char var[32];
        snprintf(var, sizeof var, "ui_coop_friend%d", k + 1);
        g::Cvar_Set(var, now.text[k]);
        snprintf(var, sizeof var, "coop_friendid%d", k + 1);
        g::Cvar_Set(var, now.id[k][0] ? now.id[k] : "0");
    }
    g::Cvar_Set("ui_coop_steam", found ? "Steam friends hosting a game:" : "Steam: none of your friends is hosting yet.");
}

// UO grenade spawn RVA 0x27a50 stores the thrower number at +0xfc and
// the thrower entity pointer at +0x14c. Both must agree before exporting it.
// GSC consumes these on the authoritative host; clients never supply ownership.
void HostMissileOwners()
{
    if (!g::uo || !g::sv_gentities || !g::sv_gameClients || g::sv_state != 2) return;
    static int sampledTime = -1;
    if (sampledTime == g::sv_time) return;
    sampledTime = g::sv_time;
    constexpr int BANKS = 128;
    static int previous[BANKS];
    static bool initialized;
    if (!initialized) { for (int& v : previous) v = -1; initialized = true; }
    int values[BANKS]; for (int& v : values) v = -1;
    int count = 0, overflow = 0;
    if (S->role != JOINER) for (int e = 0; e < g::MAX_GENTITIES; ++e) {
        uint8_t* entity = g::Entity(e);
        if (entity[0] != 3) continue;
        int owner = *(int*)(entity + 0xfc);
        if (owner < 0 || owner >= g::MAX_CLIENTS || !PlayerInGame(owner) ||
            *(uint8_t**)(entity + 0x14c) != g::Entity(owner)) continue;
        if (count == BANKS) { ++overflow; continue; }
        values[count++] = (e + 1) * 4 + owner;
    }
    for (int i = 0; i < BANKS; ++i) {
        if (values[i] == previous[i]) continue;
        previous[i] = values[i];
        char key[48], value[24];
        snprintf(key, sizeof key, "coop_owner_bank_%d", i);
        snprintf(value, sizeof value, "%d", values[i]);
        g::Cvar_Set(key, value);
    }
    static int previousCount = -1, previousOverflow = -1;
    if (count != previousCount) {
        char value[24]; snprintf(value, sizeof value, "%d", count);
        g::Cvar_Set("coop_owner_bank_count", value); previousCount = count;
    }
    if (overflow != previousOverflow) {
        char value[24]; snprintf(value, sizeof value, "%d", overflow);
        g::Cvar_Set("coop_owner_bank_overflow", value); previousOverflow = overflow;
        if (overflow) Log("ownership: more than %d simultaneous player missiles (%d unassigned)", BANKS, overflow);
    }
}

// ---------- comandos de consola ----------

void Cmd_CoopHost()
{
    RestoreHostRules();
    if (!PrepareIdentity()) return;
    PreservationObserveReady();
    if (S->role != HOST) {
        auto observedInit=S->preservation.init;
        bool observedSolo=S->role==NONE&&observedInit.valid&&observedInit.nativeReady&&observedInit.session==0&&g_gameLifecycleReady&&
            g::currentVM!=g::gvm&&g::sv_state==2&&g::cls_state==2&&g::svs_clients&&g::sv_gameClients&&
            observedInit.nativeWorldId==CvarInt("sv_serverid")&&!_stricmp(observedInit.map,g::CvarString("mapname"));
        HCRYPTPROV provider = 0;
        uint64_t nonce = 0;
        bool ready = CryptAcquireContextA(&provider, nullptr, nullptr, PROV_RSA_AES, CRYPT_VERIFYCONTEXT) &&
                     CryptGenRandom(provider, sizeof nonce, (BYTE*)&nonce) && nonce;
        if (provider) CryptReleaseContext(provider, 0);
        if (!ready) { CoopStatus("Could not initialize a new co-op session. Retry hosting."); return; }
        S->reloadToken = {nonce, 1};
        S->selection={};
        S->inventories={};
        S->preservation={};
        S->spawnTicketCounter=0;memset(S->spawnTicket,0,sizeof S->spawnTicket);FreshSpawnTicket(0);
        if(observedSolo) {
            observedInit.session=S->reloadToken.session;observedInit.world=S->reloadToken.generation;
            observedInit.announced=observedInit.handled=true;observedInit.committed=0;
            S->preservation.init=observedInit;S->preservation.serial=observedInit.serial;
            if(observedInit.intent!=0)PreservationWait(0);
            Log("inventory: hosting observed native init serial=%u intent=%d map=%s",observedInit.serial,observedInit.intent,observedInit.map);
        }
        memset(S->reloadPending, 0, sizeof S->reloadPending);
    }
    int port = g::cmd_argc > 1 ? atoi(g::Argv(1)) : 28960;
    if (!OpenSocket(port)) {
        g::Com_Printf("^1COOP: could not open UDP port %d\n", port);
        CoopStatus("Could not open UDP port %d (is another program using it?)", port);
        return;
    }
    S->role = HOST;
    const char* ip = LocalIp();
    char note[128];
    snprintf(note, sizeof note, "CO-OP: hosting %s:%d", ip, port);
    g::Cvar_Set("ui_coop_host", note);       // aviso corto del menu principal
    snprintf(note, sizeof note, "HOSTING on %s:%d - press Back, then New Game.", ip, port);
    g::Cvar_Set("ui_coop_host_info", note);  // ventana Cooperativo
    g::Com_Printf("^2COOP: hosting on %s:%d. Others: coopjoin %s\n", ip, port, ip);
    CoopStatus("Hosting on %s:%d. Back, then New Game. Friends join with coopjoin %s%s.", ip, port, ip,
               steam::up ? " or a Steam invite" : "");
}

// coopjoin <ip>[:puerto]; sin argumento usa la IP escrita en el menu Cooperativo (cvar coop_ip)
void Cmd_CoopJoin()
{
    S->selection={};
    S->reloadToken = {};
    S->recoveringConnection = false;
    RestoreHostRules();
    S->rules.received = S->rules.required = 0;
    S->suppressedClientFrames = 0;
    S->gamestateReady = false;
    S->waitingForMap = false;
    S->receivedMovie = 0; S->receivedMovieStatus = 0;
    S->movieWorldSuspended = false;
    g_animAssembler.Reset();
    if (!PrepareIdentity()) return;
    S->compatible = false;
    S->joinStarted = 0;
    const char* target = g::cmd_argc > 1 ? g::Argv(1) : g::CvarString("coop_ip");
    if (!*target) {
        g::Com_Printf("usage: coopjoin <ip>[:port]\n");
        CoopStatus("Type the host's IP.");
        return;
    }
    char host[128];
    strncpy(host, target, sizeof host - 1);
    host[sizeof host - 1] = 0;
    if (!OpenSocket(0)) return;
    if (!_strnicmp(host, "steam:", 6)) {  // coopjoin steam:<SteamID> (boton del menu o "Unirse a la partida" de Steam)
        uint64_t id = _strtoui64(host + 6, nullptr, 10);
        if (!steam::up || !id) {
            g::Com_Printf("^1COOP: %s\n", steam::up ? "usage: coopjoin steam:<SteamID>" : "Steam is not running");
            CoopStatus(steam::up ? "That Steam friend is not valid." : "Steam is not running.");
            return;
        }
        S->host = steam::Addr(S->steamPeer, id);
        steam::Latin1(steam::Name(id), host, sizeof host);
    } else {
        int port = 28960;
        if (char* c = strchr(host, ':')) { *c = 0; port = atoi(c + 1); }
        addrinfo hints{}, *res = nullptr;
        hints.ai_family = AF_INET;
        hints.ai_socktype = SOCK_DGRAM;
        if (getaddrinfo(host, nullptr, &hints, &res) != 0 || !res) {
            g::Com_Printf("^1COOP: could not find '%s'\n", host);
            CoopStatus("Could not find '%s'.", host);
            return;
        }
        S->host = *(sockaddr_in*)res->ai_addr;
        S->host.sin_port = htons((u_short)port);
        freeaddrinfo(res);
    }
    S->role = JOINER;
    S->joined = false;
    S->hostMap[0] = 0;
    memset(S->cs, 0, sizeof S->cs);  // el gamestate se junta de los M_CS de este intento
    JoinerSendJoin();
    if (steam::IsAddr(S->host)) {
        g::Com_Printf("COOP: joining %s via Steam...\n", host);
        CoopStatus("Looking for %s via Steam... (they must have chosen Host game and be playing)", host);
    } else {
        g::Com_Printf("COOP: joining %s:%d...\n", host, ntohs(S->host.sin_port));
        CoopStatus("Looking for the host at %s:%d... (they must have chosen Host game and be playing)",
                   host, ntohs(S->host.sin_port));
    }
}

// coopleave: boton "Desconectarse" del menu Cooperativo. El que se une vuelve al menu principal; el host suelta a
// todos y deja de ser anfitrion (la partida sigue para el solo). M_BYE avisa al otro lado para que no espere el corte.
void Cmd_CoopLeave()
{
    S->waitingForMap = false;
    Writer w(M_BYE);
    w.Put<uint8_t>(1); // intentional departure; empty/zero BYE is temporary clock/map recovery
    if (S->role == JOINER) {
        for (int k = 0; k < 3; ++k) SendTo(S->host, w.buf, w.len);  // UDP: el host atiende el primero
        JoinerLeave("You left the co-op game.");
    } else if (S->role == HOST) {
        w.Put(S->reloadToken);
        for (int n = 1; n < g::MAX_CLIENTS; ++n) {
            const auto& pending = S->reloadPending[n];
            bool loading = pending.address.sin_port && pending.delivery.token.session == S->reloadToken.session;
            if (S->remote[n].active)
                for (int k = 0; k < 3; ++k) SendTo(S->remote[n].addr, w.buf, w.len);
            if (loading && (!S->remote[n].active || pending.address.sin_addr.s_addr != S->remote[n].addr.sin_addr.s_addr ||
                            pending.address.sin_port != S->remote[n].addr.sin_port))
                for (int k = 0; k < 3; ++k) SendTo(pending.address, w.buf, w.len);
            if (S->remote[n].active && PlayerInGame(n)) HostDropRemote(n);
            S->remote[n].active = false;
        }
        memset(S->reloadPending, 0, sizeof S->reloadPending);
        S->inventories={};
        S->selection={};g::Cvar_Set("coop_select_api","0");
        if (QAHostBodyGCEnabled())
            for(int n=0;n<g::MAX_CLIENTS;++n) if(S->bodyTree[n]) QAFreeHostBody(n);
        S->role = NONE;
        g::Cvar_Set("coop_expected_players", "1");
        g_noPause = false;
        SkipUiPauseCheck(false);  // el menu vuelve a pausar como en el SP
        g::Cvar_Set("ui_coop_host", "");
        g::Cvar_Set("ui_coop_host_info", "");
        CoopStatus("You stopped hosting: the game goes on just for you.");
    } else {
        CoopStatus("You are not in a co-op game.");
    }
}

// coopjoinfriend <1..3>: boton "Unirse a <amigo>" del menu (SteamID en coop_friendid<n>, ver SteamFrame)
void Cmd_CoopJoinFriend()
{
    char var[32], cmd[64];
    snprintf(var, sizeof var, "coop_friendid%d", atoi(g::Argv(1)));
    const char* id = g::CvarString(var);
    if (!*id || !strcmp(id, "0")) return;
    snprintf(cmd, sizeof cmd, "coopjoin steam:%s\n", id);
    g::Cbuf_AddText(cmd);
}

// despues de recargar el mapa por M_RELOAD: volver a unirse al mismo host (lo reintenta cada 1 s)
void Cmd_CoopRejoin()
{
    if (S->waitingForMap) return;
    if (!PrepareIdentity()) return;
    S->compatible = false;
    S->joinStarted = 0;
    if (S->sock == INVALID_SOCKET || S->role != NONE || !S->host.sin_port) return;
    S->role = JOINER;
    S->suppressedClientFrames = 0;
    S->gamestateReady = false;
    S->joined = false;
    S->hostMap[0] = 0;
    memset(S->cs, 0, sizeof S->cs);
    JoinerSendJoin();
    g::Com_Printf("COOP: rejoining...\n");
}

void JoinerMapTick()
{
    if (!S->waitingForMap) return;
    if (GetTickCount() - S->mapLoadStarted > 240000) {
        S->waitingForMap = false;
        CoopStatus("Loading %s timed out. Retry joining the host.", S->pendingMap);
        Log("joiner: native map load timed out for %s", S->pendingMap);
        return;
    }
    if (g::sv_state != 2 || !g::cgvm || g::cls_state != 2 || g::cl_snapNum <= 0 ||
        CvarInt("sv_serverid") == S->previousLocalWorld ||
        _stricmp(S->pendingMap, g::CvarString("mapname"))) return;
    Log("joiner: native map %s ready, generation %d -> %d; rejoin now", S->pendingMap,
        S->previousLocalWorld, CvarInt("sv_serverid"));
    S->waitingForMap = false;
    Cmd_CoopRejoin();
}

void Cmd_CoopQAStart()
{
    if (!suite::IsQA() || !g::uivm || !PregameOpen()) return;
    // Same engine operations as uiScript playerstart / JoinerSkipPregame.
    int args[13] = {7, 0};
    g::CallVM(g::uivm, args);
    g::Cvar_Set("cl_paused", "0");
    g::Cvar_Set("cg_norender", "0");
    g::Cbuf_AddText("fade 0 0 0 0 3\n");
    Log("qa: start mission through engine UI");
}

// Read-only QA probe. Disabled in regular sessions; never advances gameplay itself.
void QATick()
{
    if (!suite::IsQA() || !S) return;
    QAExportModels();
    static DWORD last;
    DWORD now = GetTickCount();
    if (now - last < 250) return;
    last = now;
    std::string base = suite::GameDir();
    FILE* f = fopen((base + "qa-state.tmp").c_str(), "wb");
    if (!f) return;
    int trees = 0;
    for (auto* tree : S->ownTree) if (tree) ++trees;
    fprintf(f, "{\"tick\":%lu,\"role\":%d,\"joined\":%s,\"compatible\":%s,\"slot\":%d,\"server_time\":%d,\"snapshot_time\":%d,\"snapshot_num\":%d,\"trees\":%d,\"recovering_connection\":%s,\"map\":\"%s\",\"players\":[",
            now, S->role, S->joined ? "true" : "false", S->compatible ? "true" : "false", S->slot,
            g::sv_time, g::cl_snapServerTime, g::cl_snapNum, trees, S->recoveringConnection ? "true" : "false", g::CvarString("mapname"));
    for (int n = 0; n < g::MAX_CLIENTS; ++n) {
        bool valid = g::sv_state == 2 && g::svs_clients && g::sv_gameClients;
        uint8_t* ps = valid ? PlayerState(n) : nullptr;
        const float* pos = ps ? (const float*)(ps + 0x14) : nullptr;
        fprintf(f, "%s{\"slot\":%d,\"active\":%s,\"state\":%d,\"command_time\":%d,\"health\":%d,\"pm_type\":%d,\"linked\":%s,\"forward\":%d,\"downed\":%s,\"position\":[%.3f,%.3f,%.3f]}",
                n ? "," : "", n, S->remote[n].active ? "true" : "false",
                valid ? *(int*)(g::Client(n) + g::CL_STATE) : 0, ps ? *(int*)ps : 0,
                ps ? *(int*)(ps + g::PS_HEALTH) : 0, ps ? *(int*)(ps + 4) : -1,
                valid && *(uint8_t**)(g::Entity(n) + g::GE_LINK) ? "true" : "false",
                valid ? (int)*(int8_t*)(g::Client(n) + 0x30 + 0x14) : 0,
                S->downed[n] ? "true" : "false",
                pos ? pos[0] : 0, pos ? pos[1] : 0, pos ? pos[2] : 0);
    }
    unsigned movieAck = 0;
    for (int n = 1; n < g::MAX_CLIENTS; ++n) if (S->movie.ack[n] == 1) movieAck |= 1u << n;
    auto ruleValues = ReadHostRules();
    unsigned ruleAck = 0;
    for (int n = 1; n < g::MAX_CLIENTS; ++n) if (S->rules.serial && S->rules.ack[n] == S->rules.serial) ruleAck |= 1u << n;
    fprintf(f, "],\"rules\":{\"serial\":%u,\"required\":%u,\"ack_mask\":%u,\"saved_local\":%s,\"valid\":%s,\"sprint_scale\":%.9g,\"sprint_multiplier\":%.9g,\"jump_shot\":%u},",
            S->role == HOST ? S->rules.serial : S->rules.received, S->rules.required, ruleAck,
            S->rules.saved ? "true" : "false", host_rules::Valid(ruleValues) ? "true" : "false",
            std::isfinite(ruleValues.sprintScale) ? ruleValues.sprintScale : 0,
            std::isfinite(ruleValues.sprintMult) ? ruleValues.sprintMult : 0, ruleValues.jumpShot);
    fprintf(f, "\"deferred_models\":{\"enabled\":%s,\"init_count\":%u,\"approved\":%u,\"deferred\":%u,\"bound_cumulative\":%u,\"late_bindings\":%u,\"cs_count\":%d},",
        g_qaDeferredEnabled ? "true" : "false", g_qaInitCount, (unsigned)g_qaLedger.entries.size(), g_qaLedger.deferrals,
        g_qaLedger.bindings, g_qaLedger.lateBindings, g_qaDeferredEnabled ? QAModelCount() : 0);
    unsigned nativeBorrowed = 0;
    for (int e = 0; e < g::MAX_GENTITIES; ++e) if (QACurrentBorrow(e)) ++nativeBorrowed;
    fprintf(f, "\"native_tree_borrow\":{\"enabled\":%s,\"active\":%u,\"acquisitions\":%u},",
        g_qaBorrowEnabled ? "true" : "false", nativeBorrowed, g_qaBorrowCount);
    fprintf(f,"\"mt_epoch\":{\"enabled\":%s,\"value\":%u,\"queued_old_trees\":%d},",
        qa_mt_epoch::enabled ? "true" : "false",qa_mt_epoch::counter.value,g_oldTreeCount);
    fprintf(f,"\"world_wire\":{\"generation\":%u,\"stale_discarded\":%u,\"untagged_discarded\":%u,\"engine_sent\":%u,\"engine_received\":%u,\"stale_by_type\":{",
        S->reloadToken.generation,g_staleWorldPackets,g_untaggedEnginePackets,g_taggedEngineSent,g_taggedEngineReceived);
    bool firstStale = true;
    for (unsigned type = 0; type < 256; ++type) if (g_staleWorldTypes[type]) {
        fprintf(f,"%s\"%u\":%u",firstStale ? "" : ",",type,g_staleWorldTypes[type]); firstStale = false;
    }
    fprintf(f,"}},");
    fprintf(f,"\"host_body_gc\":{\"required\":%s,\"ready\":%s,\"enabled\":%s,\"tracked\":%u,\"freed\":%u,\"forgotten\":%u,\"mt_used_units8\":%u,\"mt_allocations\":%u},",
        S->memoryRequired?"true":"false",S->memoryReady?"true":"false",QAHostBodyGCEnabled()?"true":"false",S->hostBodies.count,S->hostBodies.freed,S->hostBodies.forgotten,
        g::uo?*(unsigned*)0x8f73f8:0,g::uo?*(unsigned*)0x8f71c4:0);
    fprintf(f,"\"peer_inventory\":[");
    for(int n=1;n<g::MAX_CLIENTS;++n) {
        const auto& record=S->inventories.slots[n];
        uint8_t* ps=g::sv_state==2&&g::sv_gameClients&&PlayerInGame(n)?g::PlayerState(n):nullptr;
        uint8_t digest[32]{};char hash[65]={};
        if(ps&&suite::Sha256(ps+g::PS_AMMO,g::PS_LOADOUT_END-g::PS_AMMO,digest))
            for(unsigned k=0;k<32;++k) snprintf(hash+k*2,3,"%02x",digest[k]);
        fprintf(f,"%s{\"slot\":%d,\"lease\":%llu,\"reserved\":%s,\"captured\":%s,\"installed\":%s,\"loaded_lease\":%llu,\"endpoint_port\":%u,\"weapon\":%d,\"viewmodel\":%d,\"numeric_sha256\":\"%s\",\"spawn_ticket\":%u}",n==1?"":",",n,
            (unsigned long long)record.lease,record.reserved?"true":"false",record.captured?"true":"false",record.installed?"true":"false",
            (unsigned long long)S->loadedInventoryLease[n],ntohs(record.endpoint.port),ps?*(int*)(ps+g::PS_WEAPON):0,ps?*(int*)(ps+g::PS_VIEWMODEL):0,hash,S->spawnTicket[n]);
    }
    fprintf(f,"],");
    fprintf(f,"\"weapon_selection\":{\"accepted_ticket\":%u,\"peer_serial\":%u,\"peer_weapon\":%u,\"peer_queued\":%s,\"peer_completed\":%s,\"host\":[",
        S->selection.acceptedTicket,S->selection.peer.request.serial,S->selection.peer.request.weapon,S->selection.peer.queued?"true":"false",S->selection.peer.completed?"true":"false");
    for(int n=1;n<g::MAX_CLIENTS;++n) {
        const auto& pending=S->selection.host[n];
        fprintf(f,"%s{\"slot\":%d,\"serial\":%u,\"ticket\":%u,\"weapon\":%u,\"active\":%s,\"ack\":%s,\"command_seen\":%s}",n==1?"":",",n,
            pending.request.serial,pending.request.ticket,pending.request.weapon,pending.active?"true":"false",pending.ack?"true":"false",pending.commandSeen?"true":"false");
    }
    fprintf(f,"]},");
    int fixture = CvarInt("coop_qa_render_entity");
    bool fixtureModel = false;
    if (fixture > 0 && fixture < g::MAX_GENTITIES && g::sv_state == 2) {
        if (uint8_t* object = g::ServerDObj(fixture))
            for (int k = 0; k < object[0x16] && k < 8; ++k) {
                uint8_t* model = *(uint8_t**)(object + g::DO_MODELS + k * 4);
                if (model && !_stricmp(SafeStr(*(char**)model), "v_rs_air_il2")) fixtureModel = true;
            }
    }
    fprintf(f, "\"qa_render_fixture\":{\"entity\":%d,\"dobj_model\":%s},", fixture, fixtureModel ? "true" : "false");
    fprintf(f, "\"local_fov\":%.9g,\"local_rawinput\":%d,", atof(g::CvarString("cg_fov")), CvarInt("m_rawinput"));
    fprintf(f, "\"movieplaying\":%d,\"cl_movieplaying\":%d,\"cls_state\":%d,\"movie_serial\":%u,\"movie_ack_mask\":%u,\"movie_receive_status\":%u,\"expected_players\":%d}\n",
            MoviePlaying() ? 1 : 0, CvarInt("cl_movieplaying"), g::cls_state, S->role == HOST ? S->movie.serial : S->receivedMovie,
            movieAck, S->receivedMovieStatus, CvarInt("coop_expected_players"));
    fclose(f);
    MoveFileExA((base + "qa-state.tmp").c_str(), (base + "qa-state.json").c_str(), MOVEFILE_REPLACE_EXISTING);
}

// Pruebas sin teclado: lo que se escriba en codcoop.cmd (o codcoop_join.cmd) va a la consola.
void PollCmdFile()
{
    static DWORD last;
    static char path[MAX_PATH];
    if (GetTickCount() - last < 250) return;
    last = GetTickCount();
    if (!path[0]) {
        GetModuleFileNameA(nullptr, path, MAX_PATH);
        strcpy(strrchr(path, '\\') + 1, strstr(GetCommandLineA(), "+coopjoin") ? "codcoop_join.cmd" : "codcoop.cmd");
    }
    FILE* f = fopen(path, "rb");
    if (!f) return;
    char text[2048];
    size_t n = fread(text, 1, sizeof text - 2, f);
    fclose(f);
    remove(path);
    text[n] = 0;
    strcat(text, "\n");
    Log("cmd: %s", text);
    g::Cbuf_AddText(text);
}

void Cmd_CoopInfo()
{
    uint8_t* gameClients = g::sv_gameClients;
    int gameClientSize = g::sv_gameClientSize;
    for (int n = 0; n < g::MAX_CLIENTS; ++n) {
        if (!g::svs_clients || !gameClients) break;
        const float* o = (const float*)(gameClients + n * gameClientSize + 0x14);  // ps.origin
        const int* uc = (const int*)(g::Client(n) + 0x30);  // lastUsercmd
        const int* ps = (const int*)(gameClients + n * gameClientSize);
        Log("slot %d: state=%d ps.origin=(%.0f %.0f %.0f) pm_type=%d health=%d commandTime=%d ucmd=%d %08x %08x", n,
            *(int*)(g::Client(n) + g::CL_STATE), o[0], o[1], o[2], ps[1], ps[0x39], ps[0], uc[0], uc[1], uc[5]);
        g::Com_Printf("slot %d: state=%d origin=(%.0f %.0f %.0f)\n", n, *(int*)(g::Client(n) + g::CL_STATE), o[0], o[1], o[2]);
    }
    // que tiene distinto el ps del jugador 2 respecto del host (primeros 0x400 bytes)
    if (gameClients && *(int*)(g::Client(1) + g::CL_STATE) == 1) {
        const int* a = (const int*)gameClients;
        const int* b = (const int*)(gameClients + gameClientSize);
        char line[1024];
        int len = 0;
        for (int i = 0; i < 0x100 && len < 900; ++i)
            if (a[i] != b[i]) len += snprintf(line + len, sizeof line - len, " +%x:%x/%x", i * 4, a[i], b[i]);
        Log("ps distinto (host/remoto):%s", line);
    }
}

// lleva al jugador n al lado del host (ps.origin; el juego lo copia a la entidad en el proximo think)
void Cmd_CoopBring()
{
    int n = atoi(g::Argv(1));
    uint8_t* gameClients = g::sv_gameClients;
    int size = g::sv_gameClientSize;
    if (n < 1 || n >= g::MAX_CLIENTS || !gameClients) return;
    float* dst = (float*)(gameClients + n * size + 0x14);
    const float* src = (const float*)(gameClients + 0x14);
    dst[0] = src[0] + 48;
    dst[1] = src[1];
    dst[2] = src[2] + 8;
    if (g::cmd_argc >= 5)  // cooptp-style: coopbring n x y z
        for (int i = 0; i < 3; ++i) dst[i] = (float)atof(g::Argv(2 + i));
    memset(dst + 3, 0, 12);  // velocidad
    Log("coopbring %d -> (%.0f %.0f %.0f)", n, dst[0], dst[1], dst[2]);
}

// Lista los DObj del servidor: modelos, arbol de animacion y nodos activos (para el tramo 2).
void Cmd_CoopDObj()
{
    const int16_t* serverObjMap = g::serverObjMap;
    int shown = 0;
    for (int e = 0; e < g::MAX_GENTITIES && shown < 60; ++e) {
        if (!serverObjMap[e]) continue;
        uint8_t* d = g::dobjPool + serverObjMap[e] * g::DOBJ_SIZE;
        char models[512];
        int len = 0;
        int nm = d[0x16];
        for (int i = 0; i < nm && i < 8; ++i) {
            uint8_t* m = *(uint8_t**)(d + g::DO_MODELS + i * 4);
            len += snprintf(models + len, sizeof models - len, " %s(p%d f%x o%d)", m ? SafeStr(*(char**)m) : "null",
                            d[g::DO_PARENTS + i], *(uint16_t*)(d + g::DO_FLAGS + i * 2), d[g::DO_ORDER + i]);
        }
        uint8_t* tree = *(uint8_t**)d;
        int active = 0, size = 0;
        const char* animName = "-";
        if (tree) {
            uint8_t* xanim = *(uint8_t**)tree;
            size = *(int*)(xanim + 4);
            animName = SafeStr(*(char**)xanim);
            for (int i = 0; i < size; ++i)
                if (*(uint16_t*)(tree + g::TREE_INFO + i * 2)) ++active;
        }
        const float* org = (const float*)(g::Entity(e) + 0xe0);  // r.currentOrigin
        Log("dobj ent %d (%.0f %.0f %.0f): modelos %d:%s arbol %p anims '%s' n=%d activos=%d u12=%d", e, org[0], org[1], org[2],
            nm, models, tree, animName, size, active, *(uint16_t*)(d + 0x12));
        // estado de cada nodo activo: cliente (tiempo, goalTime, goalWeight, weight, rate) / servidor (lo mismo)
        for (int i = 0; tree && e < g::MAX_CLIENTS && i < size; ++i) {
            uint16_t idx = *(uint16_t*)(tree + g::TREE_INFO + i * 2);
            if (!idx) continue;
            const float* f = (const float*)(g::xanimInfo + idx * 0x44);
            Log("  nodo %d: cli t=%.2f %.2f gt=%.2f gw=%.2f w=%.2f r=%.2f | srv t=%.2f %.2f gt=%.2f gw=%.2f w=%.2f r=%.2f", i, f[7],
                f[8], f[10], f[11], f[12], f[13], f[14], f[15], f[17], f[18], f[19], f[20]);
        }
        ++shown;
    }
    Log("dobj: %d infos de animacion en uso", *(int*)g::xanimInfo);
}

// prueba: coopgod <n> [0|1] -> el host le mantiene la vida al maximo al jugador n
void Cmd_CoopGod()
{
    int n = atoi(g::Argv(1));
    if (n < 0 || n >= g::MAX_CLIENTS) return;
    S->god[n] = g::cmd_argc > 2 ? atoi(g::Argv(2)) != 0 : !S->god[n];
    Log("coopgod %d = %d", n, S->god[n]);
}

// prueba: cooplook <n> <ent> -> jugador n a 150 unidades de la entidad y mirandola.
// La vista es SHORT2ANGLE(cmd.angles + ps.delta_angles): se ajusta delta_angles (ps+0x48, como Q3).
void Cmd_CoopLook()
{
    int n = atoi(g::Argv(1)), e = atoi(g::Argv(2));
    float dist = g::cmd_argc > 3 ? (float)atof(g::Argv(3)) : 150;
    if (n < 0 || n >= g::MAX_CLIENTS || e < 0 || e >= g::MAX_GENTITIES || !g::sv_gameClients) return;
    uint8_t* ps = g::PlayerState(n);
    const float* t = (const float*)(g::Entity(e) + g::GE_ORIGIN);  // r.currentOrigin
    float* o = (float*)(ps + 0x14);
    float dx = o[0] - t[0], dy = o[1] - t[1], len = sqrtf(dx * dx + dy * dy);
    if (len < 1) dx = -1, dy = 0, len = 1;
    o[0] = t[0] + dx / len * dist;
    o[1] = t[1] + dy / len * dist;
    o[2] = t[2] + 8;
    memset(ps + 0x20, 0, 12);  // velocidad
    float yaw = atan2f(-dy, -dx) * 180.0f / 3.14159265f;
    const int* cmdAngles = (const int*)(ps + g::GC_CMD + 8);  // gclient.pers.cmd.angles
    int* delta = (int*)(ps + g::PS_DELTA_ANGLES);
    float pitch = g::cmd_argc > 4 ? (float)atof(g::Argv(4)) : 0;  // positivo = hacia abajo
    delta[0] = ((int)(pitch * 65536 / 360) & 0xffff) - cmdAngles[0];
    delta[1] = ((int)(yaw * 65536 / 360) & 0xffff) - cmdAngles[1];
    Log("cooplook %d -> ent %d en (%.0f %.0f %.0f), yaw %.0f", n, e, o[0], o[1], o[2], yaw);
}

// prueba: coopstate <ent> -> vuelca el entityState (0x9c bytes) como enteros y floats
void Cmd_CoopState()
{
    int e = atoi(g::Argv(1));
    if (e < 0 || e >= g::MAX_GENTITIES || !g::sv_gentities) return;
    const uint8_t* st = g::Entity(e);
    const float* org = (const float*)(st + g::GE_ORIGIN);
    Log("state %d (r.currentOrigin %.1f %.1f %.1f):", e, org[0], org[1], org[2]);
    for (int i = 0; i < g::ENTSTATE_SIZE; i += 16) {
        char line[256];
        int len = snprintf(line, sizeof line, "  +%02x:", i);
        for (int k = i; k < i + 16 && k < g::ENTSTATE_SIZE; k += 4)
            len += snprintf(line + len, sizeof line - len, " %08x(%.1f)", *(const uint32_t*)(st + k), *(const float*)(st + k));
        Log("%s", line);
    }
    // centity del cgame (cg_entities 0x3012adc0, 0x178 c/u): +0 currentState, +0x138 currentValid, +0x150 lerpOrigin
    if (uint8_t* cg = g::uo ? nullptr : (uint8_t*)GetModuleHandleA("cgamex86.dll")) {  // UO: centity sin ubicar
        const uint8_t* cent = cg + 0x12adc0 + e * 0x178;
        const float* lo = (const float*)(cent + 0x150);
        Log("cent %d: eType %d eFlags %x valid %d lerpOrigin (%.1f %.1f %.1f) lerpAngles (%.1f %.1f %.1f) dobjCliente %d", e,
            cent[0], *(const int*)(cent + 0x10), *(const int*)(cent + 0x138), lo[0], lo[1], lo[2], lo[3], lo[4], lo[5],
            g::clientObjMap[e]);
    }
}

// prueba: coopcmd <n> -> ultimo usercmd del cliente n (client_t+0x30, 11 dwords)
// prueba: coopent <n> -> gentity n entera (0x2c8 bytes) en una linea, para comparar antes/despues
void Cmd_CoopCmd()
{
    int n = atoi(g::Argv(1));
    if (n < 0 || n >= g::MAX_CLIENTS || !g::svs_clients) return;
    const uint32_t* c = (const uint32_t*)(g::Client(n) + 0x30);
    Log("usercmd %d: %08x %08x %08x %08x %08x %08x %08x %08x %08x %08x %08x", n, c[0], c[1], c[2], c[3], c[4], c[5], c[6],
        c[7], c[8], c[9], c[10]);
}

void Cmd_CoopEnt()
{
    int e = atoi(g::Argv(1));
    if (e < 0 || e >= g::MAX_GENTITIES || !g::sv_gentities) return;
    const uint32_t* p = (const uint32_t*)g::Entity(e);
    char line[4096];
    int len = 0;
    for (int i = 0; i < g::sv_gentitySize / 4; ++i) len += snprintf(line + len, sizeof line - len, " %x:%x", i * 4, p[i]);
    Log("ent %d:%s", e, line);
}

// prueba: cooplists -> revisa las listas circulares de nodos de cada entidad (gentity+0x2b6 cabeza, flag 0x1000;
// nodos de 8 bytes {u16 tipo, u16 clave, u16 anterior, u16 siguiente} en *(gamex86 + 0x2dc1c0)). Si una queda
// rota, G_FreeEntity (al cargar partida) da vueltas para siempre.
void Cmd_CoopLists()
{
    uint8_t* game = (uint8_t*)GetModuleHandleA(g::GameDll());
    if (!game || !g::sv_gentities || g::uo) return;  // UO: nodos de caminos sin ubicar
    uint8_t* nodes = *(uint8_t**)(game + 0x2dc1c0);
    int bad = 0, lists = 0;
    for (int e = 0; e < g::sv_numEntities; ++e) {
        uint8_t* ent = g::Entity(e);
        uint16_t head = *(uint16_t*)(ent + 0x2b6);
        if (!head) continue;
        ++lists;
        uint16_t cur = head;
        int steps = 0;
        bool ok = true;
        do {
            uint16_t next = *(uint16_t*)(nodes + cur * 8 + 6);
            if (!next || *(uint16_t*)(nodes + next * 8 + 4) != cur || ++steps > 4096) { ok = false; break; }
            cur = next;
        } while (cur != head);
        if (!ok) {
            ++bad;
            Log("lista rota: ent %d (eType %d flags %x) cabeza %x en el nodo %x tras %d pasos", e, ent[0],
                *(int*)(ent + 0x134), head, cur, steps);
        }
    }
    Log("cooplists: %d listas, %d rotas", lists, bad);
}

// prueba: coopanims <texto> -> hojas del arbol generic_human cuyo nombre contiene el texto.
// XAnim: +0 nombre, +4 cantidad, +8 nodos de 8 bytes {u16 hijos, u16 padre, hoja: XAnimParts* (nombre en +0)}
void Cmd_CoopAnims()
{
    uint8_t* x = FindXAnim("generic_human.atr");
    if (!x) return;
    const char* filter = g::Argv(1);
    int size = *(int*)(x + 4), shown = 0;
    for (int i = 0; i < size && shown < 200; ++i) {
        uint8_t* node = x + 8 + i * 8;
        if (*(uint16_t*)node) continue;  // no es hoja
        uint8_t* parts = *(uint8_t**)(node + 4);
        const char* name = parts ? SafeStr(*(char**)parts) : "?";
        if (*filter && !strstr(name, filter)) continue;
        Log("anim %d (padre %d): %s", i, *(uint16_t*)(node + 2), name);
        ++shown;
    }
}

#include "session_switch.inc"

struct CmdDef {
    const char* name;
    void (*fn)();
};
const CmdDef kCmds[] = {
    {"coopswitch", Cmd_CoopSwitch}, {"coopswitchcancel", Cmd_CoopSwitchCancel}, {"coopswitchretry", Cmd_CoopSwitchRetry}, {"coopqastart", Cmd_CoopQAStart}, {"coophost", Cmd_CoopHost}, {"coopjoin", Cmd_CoopJoin}, {"coopinfo", Cmd_CoopInfo}, {"coopbring", Cmd_CoopBring},
    {"coopdobj", Cmd_CoopDObj}, {"coopgod", Cmd_CoopGod},   {"cooplook", Cmd_CoopLook}, {"coopstate", Cmd_CoopState},
    {"coopbodydraw", Cmd_CoopBodyDraw}, {"coopanims", Cmd_CoopAnims}, {"coopcmd", Cmd_CoopCmd}, {"coopent", Cmd_CoopEnt},
    {"coophealth", Cmd_CoopHealth}, {"coopkill", Cmd_CoopKill}, {"cooplists", Cmd_CoopLists},
    {"cooprejoin", Cmd_CoopRejoin}, {"coopendlevel", Cmd_CoopEndLevel}, {"coopweapons", Cmd_CoopWeapons}, {"coopuiclick", Cmd_CoopUiClick}, {"coopnet", Cmd_CoopNet},
    {"coopjoinfriend", Cmd_CoopJoinFriend}, {"coopgive", Cmd_CoopGive}, {"coopleave", Cmd_CoopLeave},
};

}  // namespace

#define EXPORT extern "C" __declspec(dllexport)
EXPORT const uint32_t Coop_Protocol = suite::PROTOCOL;

EXPORT uint32_t Coop_StateVersion() { return (uint32_t)sizeof(State) ^ (STATE_VERSION << 28); }
EXPORT int Coop_StateSize() { return (int)sizeof(State); }

EXPORT void Coop_Init(const CoreApi* api, void* state, int fresh)
{
    g_api = api;
    S = (State*)state;
    if (fresh) {
        S->sock = INVALID_SOCKET;
        S->role = NONE;
    }
    if (!fresh && S->role != NONE && !PrepareIdentity()) {
        S->role = NONE; S->joined = S->frozen = false;
    }
    HookArchiveVariables(true);
    HookQAEndRegistration(true);
    suite::Identity preparedIdentity{};std::string preparedError;
    bool prepared=g::uo&&(!suite::IsQA()||suite::PreparedQA())&&
        suite::LoadIdentity(g::uo,g::CvarString("fs_game"),preparedIdentity,preparedError);
    ConfigureBodyMemory(prepared);
    PublishActorEligibility();
    Log("nucleo listo (rol %d, %s)", S->role, fresh ? "estado nuevo" : "estado conservado");
    if (!steam::SelfTest()) Log("steam: FALLA la autoprueba de direcciones falsas / nombres");
}

EXPORT void Coop_Shutdown()
{
    SetCoopCvarChanged("coop_actor_api","0");
    for(int n=0;n<g::MAX_CLIENTS;++n) {
        char key[64];snprintf(key,sizeof key,"coop_actor_%d_state",n);
        SetCoopCvarChanged(key,"WAIT");
        snprintf(key,sizeof key,"coop_actor_%d_identity",n);
        SetCoopCvarChanged(key,"");
    }
    campaign_cinematics::observer=nullptr;
    g_archiveSwap.End();
    RestoreHostRules();
    HookArchiveVariables(false);
    if (!qa_mt_epoch::Sync(false,nullptr)) {
        HMODULE retained = nullptr;
        bool pinned = GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_PIN,
            reinterpret_cast<LPCSTR>(&qa_mt_epoch::Intercept),&retained);
        Log("QA MT epoch: retained later wrapper PIN=%d",pinned);
    }
    HookQADeferred(false);
    HookQAEndRegistration(false);
    if (!campaign_cinematics::Sync(g::gvm, false, nullptr)) {
        // A later plugin retained our syscall wrapper. Its forwarding code
        // must stay mapped, even though notifications have been disabled.
        HMODULE retained = nullptr;
        if (GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_PIN,
                             reinterpret_cast<LPCSTR>(&campaign_cinematics::Intercept), &retained))
            Log("cinematic: later plugin retains syscall chain; core pinned until process exit");
        else Log("cinematic: ERROR could not pin retained syscall chain (%lu)", GetLastError());
    }
    AbortSwitch("core reloaded");
    HookCgame(false);  // el puntero apunta a esta DLL, que se va a descargar
    HookDamage(false);
    HookSpawnServer(false);
    HookUsercmd(false);
    HookReliable(false);
    HookPlayerTrace(false);
    SkipUiPauseCheck(false);
    Log("nucleo descargado");
    g_api = nullptr;
}

EXPORT const char* Coop_Commands()
{
    static char list[512];  // nombres de los comandos separados por espacios
    if (!list[0])
        for (const CmdDef& c : kCmds) {
            strcat(list, c.name);
            strcat(list, " ");
        }
    return list;
}

EXPORT void Coop_Command(const char* name)
{
    for (const CmdDef& c : kCmds)
        if (!_stricmp(c.name, name)) return c.fn();
}

// ---------- ganchos (los llama ddraw.dll) ----------

EXPORT void __cdecl Coop_SendPacket(int sock, const void* data, int len, const netadr_t* to)
{
    if (S->sock == INVALID_SOCKET || len <= 0) return;
    if (sock == NS_CLIENT && !S->joined &&
        (S->role == JOINER || S->waitingForMap)) {
        auto destination = ToSock(*to);
        if (destination.sin_addr.s_addr == S->host.sin_addr.s_addr && destination.sin_port == S->host.sin_port)
            return; // old-world sequence numbers must not poison a newly allocated host netchan
    }
    // CoD SP Netchan_Transmit writes a literal zero qport (CoD1 0x43edfb).
    // The server routes clients by base address + qport, so several joiners
    // behind the same IP would otherwise all control the first remote slot.
    if (S->role == JOINER && sock == NS_CLIENT && S->qport && len >= 6) {
        std::vector<uint8_t> packet((const uint8_t*)data, (const uint8_t*)data + len);
        packet[4] = (uint8_t)S->qport;
        packet[5] = (uint8_t)(S->qport >> 8);
        auto framed = world_wire::Engine(g_identity, S->reloadToken, packet.data(), packet.size());
        if (!framed.empty()) { SendTo(ToSock(*to), framed.data(), (int)framed.size()); ++g_taggedEngineSent; }
    } else if (S->role == HOST && sock == NS_SERVER && FindSlot(ToSock(*to)) > 0) {
        auto framed = world_wire::Engine(g_identity, S->reloadToken, data, (size_t)len);
        if (!framed.empty()) { SendTo(ToSock(*to), framed.data(), (int)framed.size()); ++g_taggedEngineSent; }
    } else SendTo(ToSock(*to), data, len);
}

// Se llama cuando la cola loopback de `sock` esta vacia: devuelve paquetes UDP del motor y
// procesa los de control.
EXPORT int __cdecl Coop_GetPacket(int sock, msg_t* msg, netadr_t* from)
{
    // Native Com_Error uses longjmp. Recover borrowed writer pointers if an
    // I/O failure unwound its call without returning through our wrapper.
    g_archiveSwap.End();
    HookReliable(true);
    if (S->role == HOST) HookDamage(true);
    // Com_Error can unwind native asset registration out of JoinerHijack.
    // The engine has then destroyed the local world; retrying a half-attached
    // gamestate would leave the client frozen forever and reuse stale trees.
    if (S->role == JOINER && S->frozen && !S->joined && g::cls_state == 0) {
        Log("joiner: native world attachment failed: %s", g::CvarString("com_errorMessage"));
        ForgetMovieWorld();
        S->movieWorldSuspended = false;
        S->role = NONE;
        RestoreHostRules(); S->rules.received = S->rules.required = 0;
        S->frozen = S->compatible = S->gamestateReady = false;
        CoopStatus("Could not attach the host world. Check the game console and installed content before retrying.");
        g::Com_Printf("^1COOP: host world attachment failed; check the native error above before retrying.\n");
    }
    PollCmdFile();
    HostCheckReload();
    PreservationTick();
    PublishActorEligibility();
    JoinerMapTick();
    HostReloadTick();
    MovieTick();
    HostRulesTick();
    WeaponSelectionTick();
    QATick();
    SwitchTick();
    WriteSupervisorState();
    HostMissileOwners();
    StatsTick();
    SteamFrame();
    UiPausedFrame();
    MainlineContinue();
    MainlineStartMission();
    if (S->sock == INVALID_SOCKET) return 0;
    FlushDelayed();
    if (S->role == HOST && sock == NS_SERVER) {  // corre aunque el juego este en pausa
        HostCheckReload();
        HostNoPause();
    }
    const bool waitingReload = S->role == NONE && S->waitingForMap && sock == NS_CLIENT;
    if (!((S->role == HOST && sock == NS_SERVER) || (S->role == JOINER && sock == NS_CLIENT) || waitingReload)) return 0;
    if (S->role == JOINER && !S->joined && GetTickCount() - S->lastJoinTry > 1000) JoinerSendJoin();

    static uint8_t buf[0x10000];
    for (;;) {
        sockaddr_in a;
        int alen = sizeof a;
        int n = recvfrom(S->sock, (char*)buf, sizeof buf, 0, (sockaddr*)&a, &alen);
        if (n <= 0) {  // UDP vacio: lo que llego por Steam
            uint64_t id;
            if ((n = steam::Recv(buf, sizeof buf, &id)) > 0) a = steam::Addr(S->steamPeer, id);
        }
        if (n <= 0) {
            if (S->role == HOST) HostCheckRemotes();
            return 0;
        }
        const bool fromHost = a.sin_addr.s_addr == S->host.sin_addr.s_addr && a.sin_port == S->host.sin_port;
        const int peerSlot = S->role == HOST ? FindSlot(a) : -1;
        if (S->role == JOINER && !fromHost) continue;
        if (n >= 5 && *(uint32_t*)buf == CTRL) {
            ++g_statCtrl;
            const uint8_t type = buf[4];
            suite::Identity peer{};
            const bool hasIdentity = n >= 5 + (int)sizeof peer;
            if (hasIdentity) memcpy(&peer, buf + 5, sizeof peer);
            const char* mismatch = !hasIdentity ? "Older CoDCoop protocol; install the complete 0.6 suite." : suite::Difference(g_identity, peer);
            world_wire::Header frame{};
            const bool hasHeader = world_wire::Parse(buf, (size_t)n, frame);
            const auto token = hasHeader ? frame.world : reload_delivery::Token{};
            if (S->role == JOINER && type == suite::REJECT && hasIdentity && peer.protocol != suite::PROTOCOL) {
                // Protocol8 and earlier put the readable rejection immediately
                // after Identity. Preserve that explanation across the break.
                Reader legacy{buf + 5 + sizeof peer, buf + n};
                JoinerControl(type, legacy);
                continue;
            }
            if (S->role == HOST && (type == suite::HELLO || type == M_JOIN)) {
                if (!g_profileReady || mismatch || !hasHeader) {
                    if (hasIdentity && SwitchAllowsPending(peer.variant)) continue;
                    Writer reject(suite::REJECT, hasIdentity && peer.protocol == suite::PROTOCOL);
                    const char* why = !g_profileReady ? "Host suite has not been verified." :
                                      (mismatch ? mismatch : "Incomplete session header; update the complete suite.");
                    reject.Put(why, (int)strlen(why) + 1);
                    SendTo(a, reject.buf, reject.len);
                    continue;
                }
                if (type == suite::HELLO || !world_wire::Current(token, S->reloadToken)) {
                    Writer ready(suite::READY); SendTo(a, ready.buf, ready.len);
                    continue; // a join must echo the current negotiated world
                }
            } else if (S->role == HOST && peerSlot < 1 && type != M_RELOAD_ACK) continue;
            if (type != suite::REJECT && mismatch) continue;
            if (!hasHeader) continue;
            Reader r{buf + CONTROL_HEADER, buf + n};
            if (S->role == NONE && S->waitingForMap) {
                if (fromHost && !mismatch && type == M_RELOAD && world_wire::Current(token, S->reloadToken)) {
                    Reader pending = r;
                    auto token = pending.Get<reload_delivery::Token>();
                    if (pending.Ok() && reload_delivery::Same(token, S->reloadToken)) {
                        Writer ack(M_RELOAD_ACK); ack.Put(token); SendTo(S->host, ack.buf, ack.len);
                    }
                }
                if (fromHost && !mismatch && type == M_BYE && world_wire::Transition(token, S->reloadToken)) JoinerControl(type, r);
                continue;
            }
            if (S->role == HOST && !mismatch && type == M_RELOAD_ACK) {
                if (!world_wire::Current(token, S->reloadToken)) { StaleWorldPacket(type); continue; }
                Reader ack = r;
                auto token = ack.Get<reload_delivery::Token>();
                if (ack.Ok() && ack.p == ack.end) for (int slot = 1; slot < g::MAX_CLIENTS; ++slot) {
                    auto& pending = S->reloadPending[slot];
                    if (pending.address.sin_addr.s_addr == a.sin_addr.s_addr && pending.address.sin_port == a.sin_port &&
                        reload_delivery::Acknowledge(pending.delivery, token))
                        Log("reload: player %d acknowledged world %u", slot, token.generation);
                }
                continue;
            }
            if (S->role == JOINER && type == suite::READY) {
                if (S->joined || !reload_delivery::Valid(token)) continue;
                if (S->reloadToken.session == token.session && reload_delivery::Valid(S->reloadToken) &&
                    !world_wire::Transition(token, S->reloadToken)) { StaleWorldPacket(type); continue; }
                if (S->reloadToken.session && S->reloadToken.session != token.session) {
                    S->rules.received = S->rules.required = 0;
                    S->receivedMovie = 0; S->receivedMovieStatus = 0;
                }
                S->reloadToken = token;
                S->compatible = false; // READY refreshes a stale preflight too
            } else if (S->role == JOINER && (type == M_RELOAD || type == M_BYE)) {
                if (!world_wire::Transition(token, S->reloadToken)) { StaleWorldPacket(type); continue; }
                if (type == M_RELOAD) {
                    Reader embedded = r;
                    auto target = embedded.Get<reload_delivery::Token>();
                    if (!embedded.Ok() || !reload_delivery::Same(target, token)) continue;
                }
            } else if (type != suite::REJECT && !world_wire::Current(token, S->reloadToken)) {
                StaleWorldPacket(type); continue;
            }
            if (type == world_wire::ENGINE) {
                if (!((S->role == HOST && peerSlot > 0) ||
                      (S->role == JOINER && S->joined && !S->movieWorldSuspended))) continue;
                int bytes = (int)(r.end - r.p);
                if (bytes <= 0) continue;
                memmove(buf, r.p, (size_t)bytes); n = bytes;
                ++g_taggedEngineReceived;
                goto engine_packet;
            }
            if (SwitchControl(type, r, a)) continue;
            if (S->role == HOST && type == M_WORLD_READY && peerSlot > 0) {
                S->remote[peerSlot].worldReady = true;
                PublishActorEligibility(peerSlot);
                if (*S->movie.name && MoviePlaying()) SendMovie(peerSlot);
            }
            else if (S->role == HOST && type == M_RULES_ACK && peerSlot > 0) {
                uint32_t serial = r.Get<uint32_t>();
                if (r.Ok() && r.p == r.end && serial == S->rules.serial) S->rules.ack[peerSlot] = serial;
            }
            else if(S->role==HOST&&type==weapon_selection::ACK&&peerSlot>0) {
                uint32_t serial=r.Get<uint32_t>(),ticket=r.Get<uint32_t>();uint8_t status=r.Get<uint8_t>();
                auto& selection=S->selection.host[peerSlot];
                if(r.Ok()&&r.p==r.end&&selection.active&&selection.request.serial==serial&&selection.request.ticket==ticket&&ticket==S->spawnTicket[peerSlot]&&status<=2) {
                    if(!status)selection.ack=true;
                    else SelectionStatus(peerSlot,status==1?"WAIT_SNAPSHOT_OR_DEFINITION":"FAILED_PEER");
                }
            }
            else if (S->role == HOST && type == M_CINEMATIC_ACK && peerSlot > 0) {
                uint32_t serial = r.Get<uint32_t>(); uint8_t status = r.Get<uint8_t>();
                if (r.Ok() && serial == S->movie.serial && status <= 2 && *S->movie.name) {
                    if (S->movie.ack[peerSlot] != status)
                        Log("cinematic: player %d acknowledged sequence %u status %u", peerSlot, serial, status);
                    // A delayed queued ACK must not undo the playing ACK.
                    if (status > S->movie.ack[peerSlot]) S->movie.ack[peerSlot] = status;
                    if (status == 2) CoopStatus("Player %d is missing campaign movie %s. Repair the suite.", peerSlot + 1, S->movie.name);
                }
            }
            else if (S->role == HOST && type == M_JOIN) HostJoin(a, r);
            else if (S->role == HOST && type == M_BYE && peerSlot > 0) {
                bool explicitLeave = r.p < r.end && r.Get<uint8_t>() == 1;
                HostDropRemote(peerSlot, explicitLeave);
            }
            else if (S->role == JOINER) {
                if (type != suite::READY && type != suite::REJECT && !S->compatible) continue;
                g_hostSeen = GetTickCount();
                JoinerControl(type, r);
            }
            if (S->role == HOST && peerSlot > 0) g_lastSeen[peerSlot] = GetTickCount();
            continue;
        }
        ++g_untaggedEnginePackets;
        continue; // protocol9 never feeds untagged UDP data into a game world
engine_packet:
        // Engine datagrams are accepted only from the selected/allocated peer.
        if (S->role == HOST) {
            if (peerSlot < 1 || n < 6) continue;
            uint16_t qport; memcpy(&qport, buf + 4, 2);
            if (qport != *(int*)(g::Client(peerSlot) + g::CL_NETCHAN + g::NC_QPORT)) continue;
        }
        if (S->role == JOINER && (!S->compatible || !S->joined || S->movieWorldSuspended)) continue;
        if (S->role == HOST) g_lastSeen[peerSlot] = GetTickCount();
        else g_hostSeen = GetTickCount();
        if (n > msg->maxsize) continue;
        if (S->role == JOINER && !S->joined) continue;
        memcpy(msg->data, buf, n);
        msg->cursize = n;
        *from = ToNet(a);
        ++g_statRecv;
        return 1;
    }
}

// Despues de SV_SendClientMessages (que solo atiende al slot 0): snapshots + estados a los remotos.
EXPORT void __cdecl Coop_HostFrame()
{
    if (S->role != HOST) return;
    HostCheckReload();
    HookCgame(true);
    HookDamage(true);
    HookSpawnServer(true);
    HookUsercmd(true);
    HookPlayerTrace(true);
    PlayersNotSolidForPrediction();
    static int lastTime;
    int now = g::sv_time;
    float dt = (now - lastTime) / 1000.0f;
    lastTime = now;
    if (dt < 0 || dt > 0.2f) dt = 0;
    HostUpdateBodies();
    if(S->role!=HOST) return; // ownership failure stopped this session visibly
    HostAnimateBodies(dt);
    HostDownedFrame(dt);
    HostVehicles();
    if (CoopActive()) HostCatchUp(dt);
    uint8_t team = 0;  // quien esta en el mapa y donde (brujula de todos)
    float teamPos[g::MAX_CLIENTS][3] = {};
    for (int n = 0; n < g::MAX_CLIENTS; ++n) {
        if (!PlayerInGame(n)) continue;
        team |= 1 << n;
        memcpy(teamPos[n], PlayerState(n) + 0x14, 8);
        teamPos[n][2] = *(float*)(g::Entity(n) + 0x48);  // apos.trBase yaw
    }
    if (CoopActive()) DrawTeamOnCompass(team, teamPos, 0);
    for (int n = 0; n < g::MAX_CLIENTS; ++n) {
        if (!S->god[n] || !g::sv_gameClients || *(int*)(g::Client(n) + g::CL_STATE) != 1) continue;
        uint8_t* ps = g::PlayerState(n);
        *(int*)(ps + g::PS_HEALTH) = *(int*)(ps + g::PS_MAXHEALTH);              // ps.stats vida = maxima
        *(int*)(g::Entity(n) + g::GE_HEALTH) = *(int*)(ps + g::PS_MAXHEALTH);    // ent->health (ver ClientSpawn)
    }
    for (int n = 1; n < g::MAX_CLIENTS; ++n) {
        if (!S->remote[n].active) continue;
        uint8_t* cl = g::Client(n);
        if (*(int*)(cl + g::CL_STATE) != 1) { S->remote[n].active = false; continue; }
        FixClientNum(n);
        GiveHostLoadout(n);
        CopyHostViewmodel(n);
        g::SV_SendClientSnapshot(cl);
        ++g_statSnaps;
        Writer w(M_DOWNED);  // quien esta caido (el remoto filtra su prediccion y avisa) y la brujula
        uint8_t mask = 0;
        for (int m = 0; m < g::MAX_CLIENTS; ++m) mask |= S->downed[m] << m;
        w.Put<uint8_t>(mask);
        w.Put<uint8_t>(team);
        w.Put(teamPos, sizeof teamPos);
        SendTo(S->remote[n].addr, w.buf, w.len);
        SendEntities(n);
        SendDObjs(n);
    }
}

// En el que se une el servidor local no corre, pero el cliente del SP toma su reloj de sv.time
// (CL_Frame 0x40df80): lo avanzamos siguiendo al ultimo snapshot del host, un snapshot atras para interpolar.
EXPORT int __cdecl Coop_FrozenFrame(int msec)
{
    if (S->role == JOINER && !S->joined && S->gamestateReady) {
        S->gamestateReady = false;
        Log("joiner: attach complete gamestate at server-frame boundary");
        JoinerHijack();
    }
    // While looking for the host, do not let the independent singleplayer
    // simulation run ahead of it. Keep rendering and servicing the handshake.
    if (S->role == JOINER && !S->joined && g::sv_state == 2) return 1;
    if (!S->frozen) return 0;
    HookCgame(true);
    HookUsercmd(true);
    JoinerSkipPregame();
    JoinerKeepAlive();
    if (!S->frozen) return 0;  // se perdio el host
    if (S->movieWorldSuspended) return 1; // native movie owns rendering/world until host M_RELOAD
    DrawTeamOnCompass(g_team, g_teamPos, S->slot);
    int& t = S->frozenTime;
    int latest = g::cl_snapServerTime;
    int target = latest - 50;
    int prev = g::sv_time;
    t += msec;
    if (t < target - 300) t = target;  // al entrar o tras un corte: salto
    else if (t > latest) t = latest;   // nunca adelante del ultimo snapshot
    else if (t < target - 10) t += 1;  // se acerca de a poco
    g::sv_time = t;
    // El reloj del servidor del host manda: si esta en pausa (o el host no manda nada), t no
    // avanza y las animaciones se quedan quietas. Si corre, avanzan a la tasa del cliente.
    float dt = (t - prev) / 1000.0f;
    if (dt < 0.0f || dt > 0.2f) dt = 0.0f;
    JoinerAdvanceAnims(dt);
    g::Com_SyncClientDObjs();           // lo hace un trap del juego, que aca no corre
    return 1;
}
