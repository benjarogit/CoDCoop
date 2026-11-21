// Included inside core.cpp's internal namespace: transition control shares the
// same validated peer/channel as gameplay. Only registered numeric variants cross
// the network; no executable path or console command is accepted from a peer.
constexpr uint8_t SWITCH_PREPARE = 'T', SWITCH_READY = 'Y', SWITCH_COMMIT = 'I', SWITCH_ACK = 'L', SWITCH_CANCEL = 'X';
struct SwitchTransaction {
    uint32_t id, retryRound;
    uint8_t target, participants, ready, committed;
    int phase; // 0 idle, 1 prepare, 2 save, 3 commit, 4 peer commit acknowledged
    DWORD started, sent;
    char map[64];
    int difficulty;
    FILETIME saveAfter;
};
SwitchTransaction g_switch{};
const char* VariantName(int n)
{
    static const char* names[] = {"", "cod1", "uo", "sp_improved", "united_fronts"};
    return n >= 1 && n <= 4 ? names[n] : "";
}
bool SwitchInProgress() { return g_switch.phase != 0; }
bool SwitchAllowsPending(uint8_t variant) { return g_switch.phase >= 3 && g_switch.target == variant; }
uint8_t SwitchParty()
{
    uint8_t members=1;
    for(int n=1;n<g::MAX_CLIENTS;++n) {
        const auto& seat=S->inventories.slots[n];
        // A transport timeout retains the seat. Only an explicit departure or
        // ending the session removes that owner from the confirmed party.
        if(S->remote[n].active || (seat.reserved&&seat.lease&&seat.world.session==S->reloadToken.session))
            members|=uint8_t(1<<n);
    }
    return members;
}
bool SwitchMemberAddress(const sockaddr_in& from)
{
    for(int n=1;n<g::MAX_CLIENTS;++n) {
        if(!(g_switch.participants&(1<<n)))continue;
        const auto& remote=S->remote[n];const auto& seat=S->inventories.slots[n];
        if(remote.active&&remote.addr.sin_addr.s_addr==from.sin_addr.s_addr&&remote.addr.sin_port==from.sin_port)return true;
        if(seat.reserved&&seat.lease&&seat.world.session==S->reloadToken.session&&
           seat.endpoint.address==from.sin_addr.s_addr&&seat.endpoint.port==from.sin_port)return true;
    }
    return false;
}
bool SupervisorPresent()
{
    WIN32_FILE_ATTRIBUTE_DATA data{};
    if (!GetFileAttributesExA((suite::GameDir() + "coop\\supervisor.json").c_str(), GetFileExInfoStandard, &data)) return false;
    FILETIME now; GetSystemTimeAsFileTime(&now);
    ULARGE_INTEGER a{}, b{};
    a.LowPart = now.dwLowDateTime; a.HighPart = now.dwHighDateTime;
    b.LowPart = data.ftLastWriteTime.dwLowDateTime; b.HighPart = data.ftLastWriteTime.dwHighDateTime;
    return a.QuadPart >= b.QuadPart && a.QuadPart - b.QuadPart < 150000000ULL;
}
void SwitchNotice(const char* action)
{
    std::string dir = suite::GameDir() + "coop\\";
    FILE* f = fopen((dir + "switch.tmp").c_str(), "wb");
    if (!f) { CoopStatus("Cannot write launcher transition request."); return; }
    sockaddr_in local{}; int len = sizeof local;
    getsockname(S->sock, (sockaddr*)&local, &len);
    char host[96] = "";
    if (S->role == JOINER) {
        if (steam::IsAddr(S->host)) snprintf(host, sizeof host, "steam:%llu", (unsigned long long)steam::IdOf(S->steamPeer, S->host));
        else snprintf(host, sizeof host, "%s:%d", inet_ntoa(S->host.sin_addr), ntohs(S->host.sin_port));
    }
    int players = 0; for (int i = 0; i < g::MAX_CLIENTS; ++i) if (g_switch.participants & (1 << i)) ++players;
    fprintf(f, "{\"action\":\"%s\",\"transaction\":%u,\"variant\":\"%s\",\"role\":\"%s\",\"host\":\"%s\",\"port\":%d,\"map\":\"%s\",\"difficulty\":%d,\"players\":%d}\n",
            action, g_switch.id, VariantName(g_switch.target), S->role == HOST ? "host" : "joiner", host,
            S->role == HOST ? ntohs(local.sin_port) : ntohs(S->host.sin_port), g_switch.map, g_switch.difficulty, players);
    fclose(f);
    MoveFileExA((dir + "switch.tmp").c_str(), (dir + "switch.json").c_str(), MOVEFILE_REPLACE_EXISTING);
    Log("switch: %s transaction=%u target=%s", action, g_switch.id, VariantName(g_switch.target));
}
void SendSwitch(const sockaddr_in& to, uint8_t type)
{
    Writer w(type);
    w.Put<uint32_t>(g_switch.id); w.Put<uint32_t>(g_switch.retryRound); w.Put<uint8_t>(g_switch.target);
    w.Put<uint8_t>(g_switch.participants); w.Put<int>(g_switch.difficulty); PutStr(w, g_switch.map);
    SendTo(to, w.buf, w.len);
}
void BroadcastSwitch(uint8_t type)
{
    for (int n = 1; n < g::MAX_CLIENTS; ++n)
        if (g_switch.participants & (1 << n)) SendSwitch(S->remote[n].addr, type);
}
void AbortSwitch(const char* reason)
{
    if (!g_switch.phase || g_switch.phase >= 3) return;
    if (S->role == HOST) BroadcastSwitch(SWITCH_CANCEL);
    else SendSwitch(S->host, SWITCH_CANCEL);
    SwitchNotice("cancel");
    CoopStatus("Campaign switch cancelled: %s", reason);
    Log("switch: cancelled: %s", reason);
    g_switch = SwitchTransaction{};
}
bool SwitchSafePoint()
{
    if (S->role != HOST || g::sv_state != 2 || !PlayerInGame(0) || PregameOpen() || LevelExiting()) return false;
    for (int n = 0; n < g::MAX_CLIENTS; ++n) {
        if (n && !(g_switch.participants & (1 << n))) continue;
        if (n && !S->remote[n].active) return false;
        if (!PlayerInGame(n) || S->downed[n]) return false;
        uint8_t* ps = PlayerState(n);
        if (!ps || *(int*)(ps + g::PS_HEALTH) <= 0 || *(int*)(ps + 4) != 0 ||
            *(uint8_t**)(g::Entity(n) + g::GE_LINK)) return false;
    }
    return true;
}
bool SwitchSaveWritten()
{
    const char* root = g_identity.variant == 1 ? "Main" : g_identity.variant == 2 ? "uo" : g_identity.variant == 3 ? "sp_improved" : "UnitedFronts";
    WIN32_FILE_ATTRIBUTE_DATA data{};
    std::string path = suite::GameDir() + root + "\\save\\coop_switch.svg";
    return GetFileAttributesExA(path.c_str(), GetFileExInfoStandard, &data) &&
           CompareFileTime(&data.ftLastWriteTime, &g_switch.saveAfter) >= 0 && data.nFileSizeLow > 0;
}
void Cmd_CoopSwitch()
{
    if (S->role != HOST || !g_profileReady) { CoopStatus("Only the host can select a campaign."); return; }
    int target = 0;
    for (int i = 1; i <= 4; ++i) if (!_stricmp(g::Argv(1), VariantName(i))) target = i;
    if (!target || target == g_identity.variant) { CoopStatus("Select a different registered campaign."); return; }
    if (!SupervisorPresent()) { CoopStatus("Start through CoDCoop Launcher for automatic campaign changes."); return; }
    if (g_switch.phase) { CoopStatus("A campaign change is already pending. Retry or cancel it first."); return; }
    g_switch.id = GetTickCount() ^ (GetCurrentProcessId() << 16);
    if (!g_switch.id) g_switch.id = 1;
    const char* map = g::cmd_argc > 2 && strcmp(g::Argv(2), "default") ? g::Argv(2) : target == 2 ? "bastogne1" : "training";
    size_t length = strlen(map);
    if (!length || length >= sizeof g_switch.map || strspn(map, "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-") != length) {
        CoopStatus("Invalid target mission name."); g_switch = SwitchTransaction{}; return;
    }
    int difficulty = g::cmd_argc > 3 ? atoi(g::Argv(3)) : CvarInt("g_gameskill");
    if (difficulty < 0 || difficulty > 3) { CoopStatus("Invalid difficulty."); g_switch = SwitchTransaction{}; return; }
    snprintf(g_switch.map, sizeof g_switch.map, "%s", map);
    g_switch.difficulty = difficulty;
    g_switch.target = (uint8_t)target;
    g_switch.phase = 1;
    g_switch.participants = SwitchParty();
    g_switch.started = GetTickCount();
    SwitchNotice("prepare");
    BroadcastSwitch(SWITCH_PREPARE);
    CoopStatus("Checking all players before changing campaign; waiting for a safe checkpoint.");
}
void Cmd_CoopSwitchCancel()
{
    if (g_switch.phase >= 3) { CoopStatus("The restart is committed; use Retry to recover the group."); return; }
    AbortSwitch("cancelled by a player");
}
void Cmd_CoopSwitchRetry()
{
    if (S->role != HOST || !g_switch.phase) return;
    if (g_switch.phase < 3) {
        if (!++g_switch.retryRound) ++g_switch.retryRound;
        g_switch.ready &= 1; // peers must acknowledge the new retry round
        g_switch.phase=1;
    }
    g_switch.started = GetTickCount();
    g_switch.sent = 0;
    if (g_switch.phase < 3) SwitchNotice("prepare");
    Log("switch: retry transaction=%u round=%u",g_switch.id,g_switch.retryRound);
    CoopStatus("Retrying the pending campaign change.");
}
bool SwitchControl(uint8_t type, Reader r, const sockaddr_in& from)
{
    if(type==M_JOIN&&S->role==HOST&&g_switch.phase&&!SwitchMemberAddress(from)) {
        Writer reject(suite::REJECT);
        const char* reason="A campaign change is pending. Wait for the squad to reconnect before joining.";
        reject.Put(reason,(int)strlen(reason)+1);SendTo(from,reject.buf,reject.len);
        return true; // never allocate an unconfirmed late member in the old world
    }
    if (type != SWITCH_PREPARE && type != SWITCH_READY && type != SWITCH_COMMIT && type != SWITCH_ACK && type != SWITCH_CANCEL) return false;
    uint32_t id = r.Get<uint32_t>();
    uint32_t retryRound = r.Get<uint32_t>();
    uint8_t target = r.Get<uint8_t>();
    uint8_t participants = r.Get<uint8_t>();
    int difficulty = r.Get<int>();
    char map[64];
    if (!GetStr(r, map, sizeof map) || !*map || strspn(map, "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-") != strlen(map) || difficulty < 0 || difficulty > 3) return true;
    if (!r.Ok() || !id || !*VariantName(target) || !(participants & 1) || participants > 15) return true;
    if (S->role == JOINER && type == SWITCH_PREPARE) {
        if (!SupervisorPresent()) {
            CoopStatus("The host requested a campaign change; start with CoDCoop Launcher to follow.");
            return true;
        }
        if (g_switch.phase && (g_switch.id != id || g_switch.target != target ||
            g_switch.participants != participants || g_switch.difficulty != difficulty || strcmp(g_switch.map,map))) return true;
        if (!g_switch.phase) {
            g_switch.id = id; g_switch.target = target; g_switch.participants = participants; g_switch.phase = 1;
            g_switch.started = GetTickCount();
            g_switch.retryRound = retryRound;
            g_switch.difficulty = difficulty;
            snprintf(g_switch.map, sizeof g_switch.map, "%s", map);
            SwitchNotice("prepare");
            CoopStatus("Host selected a new campaign. Verifying the full installation.");
        } else if (retryRound != g_switch.retryRound) {
            if (g_switch.phase >= 3 || int32_t(retryRound-g_switch.retryRound)<=0) return true;
            // Same immutable decision and completed local verification. Retry
            // refreshes the peer's wait too; it never silently drops a member
            // or starts another full hash pass while the old one is pending.
            g_switch.retryRound=retryRound;
            g_switch.started=GetTickCount();g_switch.sent=0;
            Log("switch: resumed transaction=%u round=%u",id,retryRound);
        }
    } else {
        if (!g_switch.phase || g_switch.id != id || g_switch.retryRound != retryRound || g_switch.target != target || g_switch.participants != participants || g_switch.difficulty != difficulty || strcmp(g_switch.map, map)) return true;
        int n = FindSlot(from);
        if (type == SWITCH_CANCEL) { AbortSwitch("a player cancelled"); return true; }
        if (S->role == HOST && n > 0) {
            if (type == SWITCH_READY) g_switch.ready |= (uint8_t)(1 << n);
            if (type == SWITCH_ACK && g_switch.phase == 3) g_switch.committed |= (uint8_t)(1 << n);
        }
        if (S->role == JOINER && type == SWITCH_COMMIT && g_switch.ready) {
            SendSwitch(S->host, SWITCH_ACK);
            if (g_switch.phase != 4) { g_switch.phase = 4; SwitchNotice("commit"); }
        }
    }
    return true;
}
void SwitchTick()
{
    if (!g_switch.phase) return;
    DWORD now = GetTickCount();
    if(S->role==HOST&&g_switch.phase<3&&SwitchParty()!=g_switch.participants) {
        AbortSwitch("the squad changed; confirm the campaign again for the current players");
        return;
    }
    if (!(g_switch.ready & 1)) {
        FILE* f = fopen((suite::GameDir() + "coop\\switch.ack").c_str(), "rb");
        if (f) {
            unsigned id = 0; int ok = 0;
            int read = fscanf(f, "%u %d", &id, &ok); fclose(f);
            if (read == 2 && id == g_switch.id) {
                if (!ok) { AbortSwitch("installation verification failed"); return; }
                g_switch.ready |= 1;
            }
        }
    }
    // A late negative verification must still cancel the old transaction.
    // Timing out pauses progression, not receipt processing or cancellation.
    if (now - g_switch.started > 120000) {
        CoopStatus("Campaign change is waiting for a player or save. Retry or cancel; nobody was skipped.");
        return;
    }
    if (S->role == JOINER) {
        if (now - g_switch.sent < 500) return;
        g_switch.sent = now;
        if (g_switch.phase == 4) SendSwitch(S->host, SWITCH_ACK);
        else if (g_switch.ready) SendSwitch(S->host, SWITCH_READY);
        return;
    }
    if (S->role != HOST) { AbortSwitch("session ended"); return; }
    if (g_switch.phase == 1 && (g_switch.ready & g_switch.participants) == g_switch.participants && SwitchSafePoint()) {
        GetSystemTimeAsFileTime(&g_switch.saveAfter);
        g::Cbuf_AddText("savegame coop_switch\n");
        g_switch.phase = 2;
        CoopStatus("All players ready. Saving the current campaign before restart.");
    }
    if (g_switch.phase == 2 && SwitchSaveWritten()) {
        g_switch.phase = 3;
        g_switch.sent = 0;
    }
    if (g_switch.phase == 3 && (g_switch.committed & (g_switch.participants & ~1)) == (g_switch.participants & ~1)) {
        SwitchNotice("commit");
        g_switch.phase = 4;
        return; // launcher owns the clean exit and restart
    }
    if (now - g_switch.sent > 500 && g_switch.phase != 4) {
        g_switch.sent = now;
        BroadcastSwitch(g_switch.phase == 3 ? SWITCH_COMMIT : SWITCH_PREPARE);
    }
}

void WriteSupervisorState()
{
    static DWORD last;
    DWORD now = GetTickCount();
    if (now - last < 500 || !SupervisorPresent()) return;
    last = now;
    static int previous[g::MAX_CLIENTS];
    static DWORD advanced[g::MAX_CLIENTS];
    int live = 0;
    if (S->role == HOST && g::sv_state == 2) {
        for (int n = 0; n < g::MAX_CLIENTS; ++n) {
            if (!PlayerInGame(n)) continue;
            int time = *(int*)PlayerState(n);
            if (time != previous[n]) { previous[n] = time; advanced[n] = now; }
            if (now - advanced[n] < 2000) ++live;
        }
    }
    std::string dir = suite::GameDir() + "coop\\";
    FILE* f = fopen((dir + "runtime-state.tmp").c_str(), "wb");
    if (!f) return;
    bool rendered = g::cgvm && g::cls_state == 2 && g::cl_snapNum > 0 && g::cl_snapServerTime > 0;
    bool switchWaiting=g_switch.phase && uint32_t(now-g_switch.started)>120000;
    fprintf(f, "{\"variant\":\"%s\",\"role\":\"%s\",\"joined\":%s,\"render_ready\":%s,\"live_players\":%d,\"tick\":%lu,\"map\":\"%s\",\"switch\":{\"transaction\":%u,\"phase\":%d,\"retry_round\":%u,\"waiting\":%s}}\n",
            VariantName(g_identity.variant), S->role == HOST ? "host" : S->role == JOINER ? "joiner" : "none",
            S->joined ? "true" : "false", rendered ? "true" : "false", live, now, g::CvarString("mapname"),
            g_switch.id,g_switch.phase,g_switch.retryRound,switchWaiting?"true":"false");
    fclose(f);
    MoveFileExA((dir + "runtime-state.tmp").c_str(), (dir + "runtime-state.json").c_str(), MOVEFILE_REPLACE_EXISTING);
}
