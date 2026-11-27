// Call of Duty + United Offensive Coop - Windows installer (GUI)
//
// One window, everything in it:
//   * detected installations (registry, every Steam library, AnkerGames, portable)
//     with "another folder..." next to the list
//   * game language (German language pack or English)
//   * player name, resolution, fullscreen, FOV, quality
//   * optional singleplayer extras (SP Improved, United Fronts, UO map pack)
//   * progress bar + status line, installs on a worker thread
//
// What it installs, in this order:
//   1. the ready package (United Offensive 1.51 + the mod): game\ next to the
//      .exe, a ZIP next to it, or one download from the release
//   2. Call of Duty 1.5 (CoDSP.exe) if the game has another version; the old
//      exe stays as CoDSP.exe.bak
//   3. the German language pack, if German was chosen (after the game files,
//      because the package ships English paks)
//   4. settings and the PCGamingWiki fixes (Main/config.cfg, uo/config.cfg)
//   5. the optional extras and their launchers
//
// Requires administrator rights (manifest): game folders usually live under
// Program Files / Steam. Nothing else has to be prepared by hand.
#define _WIN32_WINNT 0x0A00
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <commctrl.h>
#include <shlobj.h>
#include <shellapi.h>
#include <ole2.h>
#include <shldisp.h>
#include <urlmon.h>
#include <wininet.h>
#include <string>
#include <vector>
#include <thread>
#include <atomic>
#include <cstdio>
#include <cmath>
#include <cwctype>
#include "suite_check.h"

static const wchar_t* TITLE = L"Call of Duty Coop - Setup";
static const DWORD CODSP_SIZE = 1716224;   // CoDSP.exe 1.5: the mod uses fixed addresses of that exe
#ifdef COOP_EXPERIMENTAL_COD2
static const char COD2SP_BUILD[] = "Thu Mar 30 2006 07:35:42PM";
#endif

// Release files. If they sit next to the installer they are used as they are;
// otherwise they are downloaded once.
static const wchar_t* READY_URL =
    L"https://github.com/benjarogit/CoDCoop/releases/download/v0.5.4/Call-of-Duty-UO-Coop-Ready.zip";
static const wchar_t* GERMAN_URL =
    L"https://github.com/benjarogit/CoDCoop/releases/download/v0.5.4/CoD-UO-German-Language.zip";
static const wchar_t* EXTRAS_URL =
    L"https://github.com/benjarogit/CoDCoop/releases/download/v0.5.4/CoD-SP-Extras.zip";
static const wchar_t* READY_FOLDER = L"Call of Duty - UO Coop Ready";

// Dialog control ids (same numbers as installer.rc)
enum {
    IDC_HEAD = 100, IDC_ST_TARGET, IDC_LIST, IDC_BROWSE, IDC_INFO,
    IDC_ST_LANG, IDC_DE, IDC_EN, IDC_LANGNOTE,
    IDC_ST_SET, IDC_ST_NAME, IDC_NAME, IDC_ST_RES, IDC_RES, IDC_FULL,
    IDC_ST_FOV, IDC_FOV, IDC_FOVNOTE, IDC_ST_Q, IDC_Q,
    IDC_FIXNOTE, IDC_ST_EXTRAS, IDC_SP, IDC_UF, IDC_MAP, IDC_EXNOTE,
    IDC_PROGRESS, IDC_STATUS, IDC_INSTALL, IDC_QUIT, IDC_CONFIGURE = 130, IDC_ROLLBACK = 131
};

enum { L_DE = 0, L_EN = 1 };
enum { Q_LOW = 0, Q_MED, Q_HIGH };
enum { S_IDLE = 0, S_RUNNING, S_DONE, S_FAILED };
enum { COD1 = 1, UO = 2, COD2 = 4 };

#define WM_APP_STATUS (WM_APP + 1)  // wParam = percent (-1 = marquee), lParam = new wstring
#define WM_APP_DONE   (WM_APP + 2)  // wParam = 1 ok / 0 failed, lParam = new wstring (message)

static int g_ui = L_EN;       // language of this window (system language)
static int g_game = L_EN;     // language the game is installed in (radio buttons)
static int g_state = S_IDLE;
static std::wstring g_overlayOverride;
static HWND g_dlg = nullptr;

struct ChangedFile { std::wstring path, backup; bool existed; std::string backupHash; };
static std::vector<ChangedFile> g_changes;
static bool g_transactionActive=false;
static bool g_rollbackMode=false;
static void RememberFile(const std::wstring& path) {
    if (!g_transactionActive) return;
    for (const auto& change:g_changes) if (!_wcsicmp(change.path.c_str(),path.c_str())) return;
    DWORD attributes=GetFileAttributesW(path.c_str());
    bool exists=attributes!=INVALID_FILE_ATTRIBUTES;
    if (exists && (attributes&(FILE_ATTRIBUTE_DIRECTORY|FILE_ATTRIBUTE_REPARSE_POINT)))
        throw std::runtime_error("unsafe destination: "+suite::Utf8(path));
    std::wstring backup;
    if (exists) {
        const auto base=path+L".coop-backup."+std::to_wstring(GetCurrentProcessId())+L"."+std::to_wstring(g_changes.size());
        bool copied=false;
        for (unsigned attempt=0;attempt<1000;++attempt) {
            backup=base+(attempt?L"."+std::to_wstring(attempt):L"");
            if (CopyFileW(path.c_str(),backup.c_str(),TRUE)) { copied=true;break; }
            const DWORD error=GetLastError();
            if (error!=ERROR_FILE_EXISTS && error!=ERROR_ALREADY_EXISTS) break;
        }
        if (!copied) throw std::runtime_error("cannot back up "+suite::Utf8(path));
    }
    g_changes.push_back({path,backup,exists,exists?suite::Hash(backup):std::string()});
}
static void RollbackFiles() {
    for (auto i=g_changes.rbegin();i!=g_changes.rend();++i) {
        if (i->existed) CopyFileW(i->backup.c_str(),i->path.c_str(),FALSE);
        else DeleteFileW(i->path.c_str());
    }
    g_transactionActive=false;
}

static std::string Narrow(const std::wstring& w, UINT cp);
static std::wstring Widen(const std::string& s, UINT cp);

// Small helper for the bilingual UI: L("deutsch", "english"). The literals are
// UTF-8; a few rotating buffers keep nested calls independent.
static const wchar_t* L(const char* de, const char* en)
{
    static thread_local std::wstring buf[16];
    static thread_local int slot = 0;
    slot = (slot + 1) % 16;
    buf[slot] = Widen(g_ui == L_DE ? de : en, CP_UTF8);
    return buf[slot].c_str();
}

// ---------------------------------------------------------------- small helpers

static bool Exists(const std::wstring& path) { return GetFileAttributesW(path.c_str()) != INVALID_FILE_ATTRIBUTES; }

static bool IsDir(const std::wstring& path)
{
    DWORD a = GetFileAttributesW(path.c_str());
    return a != INVALID_FILE_ATTRIBUTES && (a & FILE_ATTRIBUTE_DIRECTORY);
}

static std::wstring DirName(const std::wstring& path)
{
    size_t p = path.find_last_of(L"\\/");
    return p == std::wstring::npos ? path : path.substr(0, p);
}

static std::wstring ExeDir()
{
    wchar_t self[MAX_PATH];
    GetModuleFileNameW(nullptr, self, MAX_PATH);
    return DirName(self);
}

static std::wstring TrimRight(std::wstring s, wchar_t c)
{
    while (!s.empty() && s.back() == c) s.pop_back();
    return s;
}

static std::string Narrow(const std::wstring& w, UINT cp)
{
    if (w.empty()) return std::string();
    int n = WideCharToMultiByte(cp, 0, w.c_str(), (int)w.size(), nullptr, 0, nullptr, nullptr);
    std::string s(n, '\0');
    WideCharToMultiByte(cp, 0, w.c_str(), (int)w.size(), &s[0], n, nullptr, nullptr);
    return s;
}

static std::string Narrow(const std::wstring& w) { return Narrow(w, CP_UTF8); }
static std::wstring Widen(const std::string& s) { return Widen(s, CP_UTF8); }

static std::wstring Widen(const std::string& s, UINT cp)
{
    if (s.empty()) return std::wstring();
    int n = MultiByteToWideChar(cp, 0, s.c_str(), (int)s.size(), nullptr, 0);
    std::wstring w(n, L'\0');
    MultiByteToWideChar(cp, 0, s.c_str(), (int)s.size(), &w[0], n);
    return w;
}

static std::string LowerAscii(std::string s)
{
    for (char& c : s) if (c >= 'A' && c <= 'Z') c = (char)(c - 'A' + 'a');
    return s;
}

// case-insensitive child lookup (the game may have Main\ or main\)
static std::wstring FindChild(const std::wstring& parent, const std::wstring& name)
{
    WIN32_FIND_DATAW fd;
    HANDLE h = FindFirstFileW((parent + L"\\*").c_str(), &fd);
    if (h == INVALID_HANDLE_VALUE) return L"";
    std::wstring found;
    do {
        if (!_wcsicmp(fd.cFileName, name.c_str())) { found = parent + L"\\" + fd.cFileName; break; }
    } while (FindNextFileW(h, &fd));
    FindClose(h);
    return found;
}

static std::vector<std::wstring> ListDir(const std::wstring& dir)
{
    std::vector<std::wstring> out;
    WIN32_FIND_DATAW fd;
    HANDLE h = FindFirstFileW((dir + L"\\*").c_str(), &fd);
    if (h == INVALID_HANDLE_VALUE) return out;
    do {
        if (!(fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY)) out.push_back(fd.cFileName);
    } while (FindNextFileW(h, &fd));
    FindClose(h);
    return out;
}

static std::string ReadAll(const std::wstring& path)
{
    std::string data;
    HANDLE f = CreateFileW(path.c_str(), GENERIC_READ, FILE_SHARE_READ, nullptr, OPEN_EXISTING, 0, nullptr);
    if (f == INVALID_HANDLE_VALUE) return data;
    DWORD size = GetFileSize(f, nullptr);
    if (size != INVALID_FILE_SIZE) {
        data.resize(size);
        DWORD got = 0;
        ReadFile(f, &data[0], size, &got, nullptr);
        data.resize(got);
    }
    CloseHandle(f);
    return data;
}

static bool WriteAll(const std::wstring& path, const std::string& data)
{
    RememberFile(path);
    HANDLE f = CreateFileW(path.c_str(), GENERIC_WRITE, 0, nullptr, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (f == INVALID_HANDLE_VALUE) return false;
    DWORD written = 0;
    bool ok = WriteFile(f, data.data(), (DWORD)data.size(), &written, nullptr) && written == data.size();
    CloseHandle(f);
    return ok;
}

static DWORD FileSize(const std::wstring& path)
{
    WIN32_FILE_ATTRIBUTE_DATA a;
    return GetFileAttributesExW(path.c_str(), GetFileExInfoStandard, &a) ? a.nFileSizeLow : 0;
}

static bool WrongSize(const std::wstring& exe, DWORD size)
{
    WIN32_FILE_ATTRIBUTE_DATA a;
    return GetFileAttributesExW(exe.c_str(), GetFileExInfoStandard, &a) && a.nFileSizeLow != size;
}

static std::wstring TempPath(const wchar_t* name)
{
    wchar_t buf[MAX_PATH];
    GetTempPathW(MAX_PATH, buf);
    return std::wstring(buf) + name;
}

static bool RunAndWait(const std::wstring& cmd)
{
    STARTUPINFOW si{};
    si.cb = sizeof si;
    PROCESS_INFORMATION pi{};
    std::wstring line = cmd;
    if (!CreateProcessW(nullptr, &line[0], nullptr, nullptr, FALSE, CREATE_NO_WINDOW, nullptr, nullptr, &si, &pi))
        return false;
    WaitForSingleObject(pi.hProcess, INFINITE);
    DWORD code = 1;
    GetExitCodeProcess(pi.hProcess, &code);
    CloseHandle(pi.hProcess);
    CloseHandle(pi.hThread);
    return code == 0;
}

// ---------------------------------------------------------------- resources

static std::string Resource(int id)
{
    HRSRC r = FindResourceW(nullptr, MAKEINTRESOURCEW(id), MAKEINTRESOURCEW(10));  // RT_RCDATA
    HGLOBAL g = r ? LoadResource(nullptr, r) : nullptr;
    return g ? std::string((const char*)LockResource(g), SizeofResource(nullptr, r)) : std::string();
}

// false with GetLastError() of the file
static bool WriteResource(int id, const std::wstring& path)
{
    RememberFile(path);
    HRSRC r = FindResourceW(nullptr, MAKEINTRESOURCEW(id), MAKEINTRESOURCEW(10));
    HGLOBAL g = r ? LoadResource(nullptr, r) : nullptr;
    if (!g) return false;
    HANDLE f = CreateFileW(path.c_str(), GENERIC_WRITE, 0, nullptr, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (f == INVALID_HANDLE_VALUE) return false;
    DWORD size = SizeofResource(nullptr, r), written = 0;
    bool ok = WriteFile(f, LockResource(g), size, &written, nullptr) && written == size;
    DWORD err = GetLastError();
    CloseHandle(f);
    SetLastError(err);
    return ok;
}

// ---------------------------------------------------------------- detection

static int GamesIn(const std::wstring& dir)
{
    bool cod1 = Exists(dir + L"\\CoDSP.exe");  // United Offensive is an expansion: same folder
    int detected=(cod1 ? COD1 : 0) | (cod1 && Exists(dir + L"\\CoDUOSP.exe") ? UO : 0);
#ifdef COOP_EXPERIMENTAL_COD2
    detected |= Exists(dir + L"\\CoD2SP_s.exe") ? COD2 : 0;
#endif
    return detected;
}

static std::wstring GameNames(int games)
{
    std::wstring s;
    if (games & COD1) s += L"Call of Duty";
    if (games & UO) s += std::wstring(s.empty() ? L"" : L" + ") + L"United Offensive";
    if (games & COD2) s += std::wstring(s.empty() ? L"" : L" + ") + L"Call of Duty 2";
    return s;
}

static std::wstring GameNamesShort(int games)
{
    std::wstring s;
    if (games & COD1) s += L"CoD";
    if (games & UO) s += std::wstring(s.empty() ? L"" : L" + ") + L"UO";
    if (games & COD2) s += std::wstring(s.empty() ? L"" : L" + ") + L"CoD 2";
    return s;
}

static std::wstring RegistryDir(const wchar_t* key)
{
    // 32-bit installer: this reads WOW6432Node, where the game's installer writes
    wchar_t buf[MAX_PATH] = L"";
    DWORD size = sizeof buf;
    if (RegGetValueW(HKEY_LOCAL_MACHINE, key, L"InstallPath", RRF_RT_REG_SZ, nullptr, buf, &size) != ERROR_SUCCESS)
        return L"";
    return TrimRight(buf, L'\\');
}

static void AddUnique(std::vector<std::wstring>& list, const std::wstring& dir)
{
    if (dir.empty() || !IsDir(dir)) return;
    for (const std::wstring& d : list)
        if (!_wcsicmp(d.c_str(), dir.c_str())) return;
    list.push_back(dir);
}

// Steam: <SteamPath>/steamapps/common/Call of Duty and every library in libraryfolders.vdf
static void AddSteam(std::vector<std::wstring>& list)
{
    wchar_t path[MAX_PATH] = L"";
    DWORD size = sizeof path;
    std::wstring steam;
    if (RegGetValueW(HKEY_CURRENT_USER, L"Software\\Valve\\Steam", L"SteamPath", RRF_RT_REG_SZ, nullptr, path, &size)
        == ERROR_SUCCESS)
        steam = path;
    if (steam.empty()) return;
    for (wchar_t& c : steam) if (c == L'/') c = L'\\';

    std::vector<std::wstring> libs{steam};
    std::string data = ReadAll(steam + L"\\steamapps\\libraryfolders.vdf");
    for (size_t i = 0; (i = data.find("\"path\"", i)) != std::string::npos; ) {
        size_t a = data.find('"', i + 6);
        size_t b = a == std::string::npos ? a : data.find('"', a + 1);
        if (b == std::string::npos) break;
        std::string p = data.substr(a + 1, b - a - 1);
        for (size_t k = 0; k + 1 < p.size(); ++k)
            if (p[k] == '\\' && p[k + 1] == '\\') p.erase(k, 1);
        libs.push_back(Widen(p));
        i = b + 1;
    }
    for (const std::wstring& lib : libs) {
        AddUnique(list, lib + L"\\steamapps\\common\\Call of Duty");
        AddUnique(list, lib + L"\\steamapps\\common\\Call of Duty 2");
    }
}

// AnkerGames and similar launchers: %APPDATA%\net.ankergames.launcher\library.json
static void AddAnker(std::vector<std::wstring>& list)
{
    wchar_t appdata[MAX_PATH] = L"";
    if (!GetEnvironmentVariableW(L"APPDATA", appdata, MAX_PATH)) return;
    std::string data = ReadAll(std::wstring(appdata) + L"\\net.ankergames.launcher\\library.json");
    for (size_t i = 0; (i = data.find("\"root\"", i)) != std::string::npos; ) {
        size_t a = data.find('"', i + 6);
        size_t b = a == std::string::npos ? a : data.find('"', a + 1);
        if (b == std::string::npos) break;
        std::string p = data.substr(a + 1, b - a - 1);
        for (size_t k = 0; k + 1 < p.size(); ++k)
            if (p[k] == '\\' && p[k + 1] == '\\') p.erase(k, 1);
        AddUnique(list, TrimRight(Widen(p), L'\\'));
        i = b + 1;
    }
}

static void Detect(std::vector<std::wstring>& out)
{
    std::vector<std::wstring> found;
    for (const wchar_t* key : {L"SOFTWARE\\Activision\\Call of Duty", L"SOFTWARE\\Activision\\Call of Duty 2"})
        AddUnique(found, RegistryDir(key));
    AddSteam(found);
    AddAnker(found);
    std::wstring here = ExeDir();
    AddUnique(found, here);
    AddUnique(found, DirName(here));

    // only folders that really contain the game; real installations first
    std::vector<std::wstring> real, other;
    for (const std::wstring& d : found) {
        if (!GamesIn(d)) continue;
        (IsDir(d + L"\\Main") ? real : other).push_back(d);
    }
    out.insert(out.end(), real.begin(), real.end());
    out.insert(out.end(), other.begin(), other.end());
}

static std::wstring PickDir(HWND owner)
{
    BROWSEINFOW bi{};
    bi.hwndOwner = owner;
    bi.lpszTitle = L"Choose the Call of Duty folder (the one with CoDSP.exe):";
    bi.ulFlags = BIF_RETURNONLYFSDIRS | BIF_NEWDIALOGSTYLE;
    PIDLIST_ABSOLUTE pidl = SHBrowseForFolderW(&bi);
    if (!pidl) return L"";
    wchar_t buf[MAX_PATH];
    bool ok = SHGetPathFromIDListW(pidl, buf);
    CoTaskMemFree(pidl);
    return ok ? TrimRight(buf, L'\\') : L"";
}

// ---------------------------------------------------------------- config.cfg

// value of "seta <key> \"...\"" or empty
static std::wstring ReadCvar(const std::wstring& cfg, const std::wstring& key)
{
    std::string data = ReadAll(cfg);
    std::string want = "seta " + LowerAscii(Narrow(key)) + " ";
    size_t pos = 0;
    while (pos < data.size()) {
        size_t nl = data.find('\n', pos);
        if (nl == std::string::npos) nl = data.size();
        std::string line = data.substr(pos, nl - pos);
        pos = nl + 1;
        std::string low = LowerAscii(line);
        size_t s = low.find_first_not_of(" \t\r");
        if (s == std::string::npos || low.compare(s, want.size(), want) != 0) continue;
        size_t a = line.find('"', s);
        if (a == std::string::npos) continue;
        size_t b = line.find('"', a + 1);
        if (b == std::string::npos) continue;
        return Widen(line.substr(a + 1, b - a - 1), 1252);
    }
    return L"";
}

static void SetCvars(const std::wstring& cfg, const std::vector<std::pair<std::wstring, std::wstring>>& kv)
{
    std::string data = ReadAll(cfg);
    std::vector<std::string> lines;
    size_t pos = 0;
    while (pos < data.size()) {
        size_t nl = data.find('\n', pos);
        if (nl == std::string::npos) nl = data.size();
        std::string line = data.substr(pos, nl - pos);
        if (!line.empty() && line.back() == '\r') line.pop_back();
        lines.push_back(line);
        pos = nl + 1;
    }
    for (const auto& p : kv) {
        std::string key = Narrow(p.first, 1252);
        std::string line = "seta " + key + " \"" + Narrow(p.second, 1252) + "\"";
        std::string want = "seta " + LowerAscii(key) + " ";
        bool done = false;
        for (std::string& old : lines) {
            std::string low = LowerAscii(old);
            size_t s = low.find_first_not_of(" \t");
            if (s != std::string::npos && low.compare(s, want.size(), want) == 0) {
                old = line;
                done = true;
                break;
            }
        }
        if (!done) lines.push_back(line);
    }
    std::string out;
    for (const std::string& line : lines) out += line + "\r\n";
    WriteAll(cfg, out);
}

static int RecommendedFov(const std::wstring& res)
{
    int w = 0, h = 0;
    if (swscanf(res.c_str(), L"%dx%d", &w, &h) != 2 || w <= 0 || h <= 0) return 80;
    double aspect = (double)w / (double)h;
    double fov = 2.0 * atan(tan(80.0 * 3.14159265358979323846 / 360.0) * aspect / (4.0 / 3.0));
    int out = (int)lround(fov * 180.0 / 3.14159265358979323846);
    if (out < 60) out = 60;
    if (out > 130) out = 130;
    return out;
}

static void WriteSettings(const std::wstring& dir, const std::wstring& name, const std::wstring& res,
                          bool fullscreen, int fov, int quality)
{
    std::wstring main = FindChild(dir, L"Main");
    if (main.empty()) return;
    int w = 0, h = 0;
    swscanf(res.c_str(), L"%dx%d", &w, &h);
    wchar_t buf[32];

    std::vector<std::pair<std::wstring, std::wstring>> v;
    v.push_back({L"name", name});
    v.push_back({L"cl_language", L"0"});
    v.push_back({L"r_mode", L"-1"});
    swprintf(buf, 32, L"%d", w);
    v.push_back({L"r_customwidth", buf});
    swprintf(buf, 32, L"%d", h);
    v.push_back({L"r_customheight", buf});
    v.push_back({L"r_customaspect", L"1"});
    v.push_back({L"r_fullscreen", fullscreen ? L"1" : L"0"});
    swprintf(buf, 32, L"%d", fov);
    v.push_back({L"cg_fov", buf});
    // PCGamingWiki fixes that are safe for everyone
    v.push_back({L"com_introplayed", L"1"});   // no intro videos on every start
    v.push_back({L"r_smp", L"1"});             // multicore renderer
    v.push_back({L"com_maxfps", L"125"});      // >144 fps makes footsteps inaudible
    v.push_back({L"com_hunkmegs", L"256"});    // UO quick-save crash
    v.push_back({L"r_ignorehwgamma", L"1"});   // alt-tab does not wash out the screen
    v.push_back({L"cg_nopredict", L"0"});      // no mouse lag / jittery weapon animations
    v.push_back({L"r_overBrightBits", L"0"});  // correct brightness in recordings

    if (quality == Q_LOW) {
        const wchar_t* kv[][2] = {
            {L"r_picmip", L"3"}, {L"r_picmip2", L"1"}, {L"r_lodbias", L"2"}, {L"r_lodscale", L"2"},
            {L"r_lodViewDist", L"-1"}, {L"r_detailtextures", L"0"}, {L"r_dlight", L"0"},
            {L"r_fastsky", L"1"}, {L"r_flares", L"0"}, {L"r_ext_texture_filter_anisotropic", L"1"},
            {L"r_texturebits", L"16"}, {L"r_colorbits", L"16"}, {L"r_depthbits", L"16"},
            {L"cg_shadows", L"0"}, {L"r_maxEntLights", L"4"},
        };
        for (auto& p : kv) v.push_back({p[0], p[1]});
    } else if (quality == Q_MED) {
        const wchar_t* kv[][2] = {
            {L"r_picmip", L"1"}, {L"r_picmip2", L"0"}, {L"r_lodbias", L"0"}, {L"r_lodscale", L"1"},
            {L"r_lodViewDist", L"-1"}, {L"r_detailtextures", L"1"}, {L"r_dlight", L"1"},
            {L"r_fastsky", L"0"}, {L"r_flares", L"1"}, {L"r_ext_texture_filter_anisotropic", L"4"},
            {L"r_texturebits", L"32"}, {L"r_colorbits", L"32"}, {L"r_depthbits", L"24"},
            {L"cg_shadows", L"0"}, {L"r_maxEntLights", L"4"},
        };
        for (auto& p : kv) v.push_back({p[0], p[1]});
    } else {
        const wchar_t* kv[][2] = {
            {L"r_picmip", L"0"}, {L"r_picmip2", L"0"}, {L"r_lodbias", L"-1"}, {L"r_lodscale", L"0"},
            {L"r_lodViewDist", L"-1"}, {L"r_detailtextures", L"1"}, {L"r_dlight", L"1"},
            {L"r_fastsky", L"0"}, {L"r_flares", L"1"}, {L"r_ext_texture_filter_anisotropic", L"16"},
            {L"r_texturebits", L"32"}, {L"r_colorbits", L"32"}, {L"r_depthbits", L"24"},
            {L"cg_shadows", L"1"}, {L"r_maxEntLights", L"8"},
        };
        for (auto& p : kv) v.push_back({p[0], p[1]});
    }

    SetCvars(main + L"\\config.cfg", v);
    SetCvars(main + L"\\config_mp.cfg", v);

    // United Offensive keeps its own config in uo/. Seed it from the main one so
    // the first UO start already has the same name, resolution and fixes.
    std::wstring uo = FindChild(dir, L"uo");
    if (!uo.empty()) {
        std::wstring uocfg = uo + L"\\config.cfg";
        if (!Exists(uocfg)) CopyFileW((main + L"\\config.cfg").c_str(), uocfg.c_str(), FALSE);
        SetCvars(uocfg, v);
        SetCvars(uo + L"\\config_mp.cfg", v);
    }
}

// ---------------------------------------------------------------- progress / UI messages

static void Say(const std::wstring& text, int percent = -1)
{
    if (g_dlg) PostMessageW(g_dlg, WM_APP_STATUS, (WPARAM)percent, (LPARAM)new std::wstring(text));
}

static void SetProgress(HWND dlg, int pct)
{
    HWND pb = GetDlgItem(dlg, IDC_PROGRESS);
    LONG style = GetWindowLongW(pb, GWL_STYLE);
    if (pct < 0) {
        if (!(style & PBS_MARQUEE)) {
            SetWindowLongW(pb, GWL_STYLE, style | PBS_MARQUEE);
            SetWindowPos(pb, nullptr, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED);
            SendMessageW(pb, PBM_SETMARQUEE, TRUE, 40);
        }
    } else {
        if (style & PBS_MARQUEE) {
            SendMessageW(pb, PBM_SETMARQUEE, FALSE, 0);
            SetWindowLongW(pb, GWL_STYLE, style & ~PBS_MARQUEE);
            SetWindowPos(pb, nullptr, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED);
        }
        SendMessageW(pb, PBM_SETPOS, (WPARAM)pct, 0);
    }
}

// ---------------------------------------------------------------- download

class DownloadCB : public IBindStatusCallback
{
public:
    std::wstring label;
    int last = -2;

    HRESULT STDMETHODCALLTYPE QueryInterface(REFIID riid, void** ppv) override
    {
        if (riid == IID_IUnknown || riid == IID_IBindStatusCallback) { *ppv = this; AddRef(); return S_OK; }
        *ppv = nullptr;
        return E_NOINTERFACE;
    }
    ULONG STDMETHODCALLTYPE AddRef() override { return 1; }
    ULONG STDMETHODCALLTYPE Release() override { return 1; }
    HRESULT STDMETHODCALLTYPE OnStartBinding(DWORD, IBinding*) override { return S_OK; }
    HRESULT STDMETHODCALLTYPE GetPriority(LONG*) override { return S_OK; }
    HRESULT STDMETHODCALLTYPE OnLowResource(DWORD) override { return S_OK; }
    HRESULT STDMETHODCALLTYPE OnProgress(ULONG progress, ULONG max, ULONG, LPCWSTR) override
    {
        int pct = max ? (int)((unsigned long long)progress * 100 / max) : -1;
        if (pct != last) {
            last = pct;
            Say(label, pct);
        }
        return S_OK;
    }
    HRESULT STDMETHODCALLTYPE OnStopBinding(HRESULT, LPCWSTR) override { return S_OK; }
    HRESULT STDMETHODCALLTYPE GetBindInfo(DWORD*, BINDINFO*) override { return S_OK; }
    HRESULT STDMETHODCALLTYPE OnDataAvailable(DWORD, DWORD, FORMATETC*, STGMEDIUM*) override { return S_OK; }
    HRESULT STDMETHODCALLTYPE OnObjectAvailable(REFIID, IUnknown*) override { return S_OK; }
};

static std::string ExpectedArchive(const std::wstring& name) {
    if (name.find(L"German") != std::wstring::npos) return "5f1113e82aa11c12c3769275a5048a5e3d0fe5e38fb5929c1305883cdf515b5c";
    if (name.find(L"Extras") != std::wstring::npos) return "9630d73e2e87331f8a115816cfda38636c10917211419a11d0d72b49c1366d3c";
    return "c5f22a300a4186ad07755e704606bde9e2dfc9fbb3c15ac214ea7d96ec5b2f3d";
}
static bool VerifyArchive(const std::wstring& path, const std::string& expected) {
    try { return suite::Hash(path)==expected; } catch (...) { return false; }
}
static bool DownloadNumber(const std::wstring& text, DWORD& value) {
    if (text.empty()) return false;
    uint64_t number=0;
    for (wchar_t c:text) {
        if (c<L'0' || c>L'9' || number>(uint64_t(MAXDWORD)-(c-L'0'))/10) return false;
        number=number*10+(c-L'0');
    }
    value=(DWORD)number; return true;
}
static bool DownloadRange(const std::wstring& range, DWORD offset, DWORD expectedSize, DWORD& responseEnd) {
    if (range.rfind(L"bytes ",0)!=0) return false;
    auto dash=range.find(L'-',6), slash=range.find(L'/',dash==std::wstring::npos?0:dash+1);
    if (dash==std::wstring::npos || slash==std::wstring::npos) return false;
    DWORD first=0,last=0,total=0;
    if (!DownloadNumber(range.substr(6,dash-6),first) || !DownloadNumber(range.substr(dash+1,slash-dash-1),last) ||
        !DownloadNumber(range.substr(slash+1),total) || first!=offset || total!=expectedSize || first>last || last>=total) return false;
    responseEnd=last+1; return true;
}
static bool DownloadPinned(const std::wstring& url, const std::wstring& path, const std::wstring& label,
                           const std::string& expected, DWORD expectedSize)
{
    if (!suite::Hex(expected) || !expectedSize) return false;
    const auto verifying = L("Download wird geprueft...", "Verifying the download...");
    if (Exists(path) && FileSize(path)==expectedSize) {
        Say(verifying);
        if (VerifyArchive(path,expected)) return true;
    }
    auto report = [&](DWORD received) {
        const int percent = (int)(uint64_t(received)*100/expectedSize);
        const auto mib = [](DWORD count) { return std::to_wstring(count / (1024*1024)); };
        Say(label + L" " + mib(received) + L" / " + mib(expectedSize) + L" MiB (" + std::to_wstring(percent) + L"%)", percent);
    };
    // WinINet is loaded dynamically so the existing build command stays valid.
    HMODULE library=LoadLibraryW(L"wininet.dll");
    if (!library) return false;
    auto open=(decltype(&InternetOpenW))GetProcAddress(library,"InternetOpenW");
    auto openUrl=(decltype(&InternetOpenUrlW))GetProcAddress(library,"InternetOpenUrlW");
    auto query=(decltype(&HttpQueryInfoW))GetProcAddress(library,"HttpQueryInfoW");
    auto read=(decltype(&InternetReadFile))GetProcAddress(library,"InternetReadFile");
    auto close=(decltype(&InternetCloseHandle))GetProcAddress(library,"InternetCloseHandle");
    if (!open || !openUrl || !query || !read || !close) { FreeLibrary(library); return false; }
    std::wstring part=path+L".part";
    DWORD offset=Exists(part)?FileSize(part):0;
    if (offset==expectedSize) {
        Say(verifying);
        if (VerifyArchive(part,expected)) {
            FreeLibrary(library);
            return MoveFileExW(part.c_str(),path.c_str(),MOVEFILE_REPLACE_EXISTING);
        }
    }
    if (offset>=expectedSize) { DeleteFileW(part.c_str()); offset=0; }
    report(offset);
    std::wstring headers=offset?L"Range: bytes="+std::to_wstring(offset)+L"-\r\n":L"";
    HINTERNET session=open(L"CoDCoop-Suite/0.6",INTERNET_OPEN_TYPE_PRECONFIG,nullptr,nullptr,0);
    HINTERNET request=session?openUrl(session,url.c_str(),headers.c_str(),(DWORD)headers.size(),
                                    INTERNET_FLAG_RELOAD|INTERNET_FLAG_NO_CACHE_WRITE,0):nullptr;
    bool ok=false;
    if (request) {
        DWORD status=0, size=sizeof status;
        if (query(request,HTTP_QUERY_STATUS_CODE|HTTP_QUERY_FLAG_NUMBER,&status,&size,nullptr) && (status==200 || status==206)) {
            bool rangeOk=true; DWORD responseEnd=expectedSize;
            if (status==206) {
                wchar_t range[128]={}; size=sizeof range;
                rangeOk=query(request,HTTP_QUERY_CONTENT_RANGE,range,&size,nullptr) && DownloadRange(range,offset,expectedSize,responseEnd);
            } else offset=0;
            wchar_t length[128]={}; size=sizeof length;
            if (query(request,HTTP_QUERY_CONTENT_LENGTH,length,&size,nullptr)) {
                DWORD declared=0;
                rangeOk=rangeOk && DownloadNumber(length,declared) && declared==responseEnd-offset;
            } else if (GetLastError()!=ERROR_HTTP_HEADER_NOT_FOUND) rangeOk=false;
            HANDLE file=rangeOk?CreateFileW(part.c_str(),GENERIC_WRITE,0,nullptr,offset?OPEN_EXISTING:CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr):INVALID_HANDLE_VALUE;
            if (file!=INVALID_HANDLE_VALUE) {
                SetFilePointer(file,offset,nullptr,FILE_BEGIN);
                BYTE block[65536]; DWORD got=0,written=0,total=offset;
                ok=true; int last=-1;
                while (true) {
                    if (!read(request,block,sizeof block,&got)) { ok=false; break; }
                    if (!got) break;
                    if (got>responseEnd-total || !WriteFile(file,block,got,&written,nullptr) || written!=got) { ok=false; break; }
                    total+=got; int pct=(int)((unsigned long long)total*100/expectedSize);
                    if (pct!=last) { report(total); last=pct; }
                }
                FlushFileBuffers(file); CloseHandle(file);
                if (total==expectedSize) Say(verifying);
                const bool verified=total==expectedSize && VerifyArchive(part,expected);
                ok=ok && verified;
                if (total==expectedSize && !verified) DeleteFileW(part.c_str());
                if (ok) ok=MoveFileExW(part.c_str(),path.c_str(),MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH);
            }
        }
        close(request);
    }
    if (session) close(session);
    FreeLibrary(library);
    return ok;
}
static bool Download(const std::wstring& url, const std::wstring& path, const std::wstring& label) {
    const DWORD expectedSize=url.find(L"German")!=std::wstring::npos?657419767:
                             url.find(L"Extras")!=std::wstring::npos?922302300:1036938510;
    return DownloadPinned(url,path,label,ExpectedArchive(url),expectedSize);
}

// ---------------------------------------------------------------- unzip

// Windows 10/11 ships tar.exe (bsdtar), which also opens .zip, and PowerShell
// or the shell can unpack it too. None of that is guaranteed (Windows 7, locked
// down machines, Wine), so the installer brings its own DEFLATE decoder and
// tries that first: no external program, no console window, constant memory
// (the biggest entry in the package is ~750 MB compressed and uncompressed).

static void MakeDirs(const std::wstring& path)
{
    std::wstring cur;
    for (size_t i = 0; i <= path.size(); ++i) {
        if (i == path.size() || (path[i] == L'\\' && i > 2)) {
            if (!cur.empty()) CreateDirectoryW(cur.c_str(), nullptr);
            if (i == path.size()) break;
        }
        if (i < path.size()) cur += path[i];
    }
}

struct InflateIn
{
    FILE* f;
    unsigned char buf[1 << 16];
    size_t pos = 0, len = 0;
    bool eof = false;
    int Next()
    {
        if (pos == len) {
            if (eof) return -1;
            len = fread(buf, 1, sizeof buf, f);
            pos = 0;
            if (!len) { eof = true; return -1; }
        }
        return buf[pos++];
    }
};

struct BitIn
{
    InflateIn* s;
    unsigned buf = 0;
    int cnt = 0;
    int Bits(int n)
    {
        while (cnt < n) {
            int c = s->Next();
            if (c < 0) return -1;
            buf |= (unsigned)c << cnt;
            cnt += 8;
        }
        int v = (int)(buf & ((1u << n) - 1));
        buf >>= n;
        cnt -= n;
        return v;
    }
    void Align()
    {
        int drop = cnt % 8;
        buf >>= drop;
        cnt -= drop;
    }
};

struct Huffman
{
    short count[16];
    short symbol[288];
};

static int HuffBuild(Huffman& h, const unsigned char* len, int n)
{
    for (int i = 0; i < 16; ++i) h.count[i] = 0;
    for (int i = 0; i < n; ++i) h.count[len[i]]++;
    int left = 1;
    for (int l = 1; l <= 15; ++l) {
        left <<= 1;
        left -= h.count[l];
        if (left < 0) return left;  // over-subscribed
    }
    short offs[16];
    offs[1] = 0;
    for (int l = 1; l < 15; ++l) offs[l + 1] = (short)(offs[l] + h.count[l]);
    for (int i = 0; i < n; ++i)
        if (len[i]) h.symbol[offs[len[i]]++] = (short)i;
    return left;
}

static int HuffDecode(BitIn& in, const Huffman& h)
{
    int code = 0, first = 0, index = 0;
    for (int l = 1; l <= 15; ++l) {
        int b = in.Bits(1);
        if (b < 0) return -1;
        code |= b;
        int count = h.count[l];
        if (code - first < count) return h.symbol[index + (code - first)];
        index += count;
        first = (first + count) << 1;
        code <<= 1;
    }
    return -1;
}

struct InflateOut
{
    FILE* f;
    unsigned char win[32768];
    unsigned wpos = 0;
    unsigned char out[1 << 16];
    size_t olen = 0;
    unsigned long long total = 0;
    bool ok = true;

    void Flush()
    {
        if (olen && fwrite(out, 1, olen, f) != olen) ok = false;
        olen = 0;
    }
    void Byte(unsigned char c)
    {
        win[wpos] = c;
        wpos = (wpos + 1) & 32767;
        out[olen++] = c;
        ++total;
        if (olen == sizeof out) Flush();
    }
    void Copy(unsigned dist, unsigned len)
    {
        unsigned from = (wpos - dist) & 32767;
        for (unsigned i = 0; i < len; ++i) Byte(win[(from + i) & 32767]);
    }
};

static const short kLenBase[29] = {3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 15, 17, 19, 23, 27, 31,
                                   35, 43, 51, 59, 67, 83, 99, 115, 131, 163, 195, 227, 258};
static const short kLenExtra[29] = {0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2,
                                    3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 0};
static const short kDistBase[30] = {1, 2, 3, 4, 5, 7, 9, 13, 17, 25, 33, 49, 65, 97, 129,
                                    193, 257, 385, 513, 769, 1025, 1537, 2049, 3073, 4097,
                                    6145, 8193, 12289, 16385, 24577};
static const short kDistExtra[30] = {0, 0, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6,
                                     7, 7, 8, 8, 9, 9, 10, 10, 11, 11, 12, 12, 13, 13};
static const short kClOrder[19] = {16, 17, 18, 0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3, 13, 2, 14, 1, 15};

// raw DEFLATE (RFC 1951), as stored in a .zip entry
static bool InflateRaw(FILE* in, FILE* out, unsigned long long expect)
{
    InflateIn src{in};
    BitIn bits{&src};
    InflateOut dst{out};
    int last;
    do {
        last = bits.Bits(1);
        if (last < 0) return false;
        int type = bits.Bits(2);
        if (type < 0 || type == 3) return false;
        if (type == 0) {
            bits.Align();
            int len = bits.Bits(16), nlen = bits.Bits(16);
            if (len < 0 || nlen < 0 || (len ^ 0xffff) != nlen) return false;
            for (int i = 0; i < len; ++i) {
                int c = bits.Bits(8);
                if (c < 0) return false;
                dst.Byte((unsigned char)c);
            }
            continue;
        }
        Huffman lit, dist;
        if (type == 1) {
            unsigned char l[288];
            int i = 0;
            for (; i < 144; ++i) l[i] = 8;
            for (; i < 256; ++i) l[i] = 9;
            for (; i < 280; ++i) l[i] = 7;
            for (; i < 288; ++i) l[i] = 8;
            HuffBuild(lit, l, 288);
            for (i = 0; i < 30; ++i) l[i] = 5;
            HuffBuild(dist, l, 30);
        } else {
            int hlit = bits.Bits(5), hdist = bits.Bits(5), hclen = bits.Bits(4);
            if (hlit < 0 || hdist < 0 || hclen < 0) return false;
            hlit += 257;
            hdist += 1;
            hclen += 4;
            unsigned char cl[19] = {0};
            for (int i = 0; i < hclen; ++i) {
                int v = bits.Bits(3);
                if (v < 0) return false;
                cl[kClOrder[i]] = (unsigned char)v;
            }
            Huffman clh;
            if (HuffBuild(clh, cl, 19) < 0) return false;
            unsigned char lens[320] = {0};
            int n = 0, all = hlit + hdist;
            while (n < all) {
                int sym = HuffDecode(bits, clh);
                if (sym < 0) return false;
                if (sym < 16) {
                    lens[n++] = (unsigned char)sym;
                    continue;
                }
                int rep, value = 0;
                if (sym == 16) {
                    if (!n) return false;
                    value = lens[n - 1];
                    rep = bits.Bits(2);
                    if (rep < 0) return false;
                    rep += 3;
                } else if (sym == 17) {
                    rep = bits.Bits(3);
                    if (rep < 0) return false;
                    rep += 3;
                } else {
                    rep = bits.Bits(7);
                    if (rep < 0) return false;
                    rep += 11;
                }
                while (rep-- && n < all) lens[n++] = (unsigned char)value;
            }
            if (HuffBuild(lit, lens, hlit) < 0) return false;
            if (HuffBuild(dist, lens + hlit, hdist) < 0) return false;
        }
        for (;;) {
            int sym = HuffDecode(bits, lit);
            if (sym < 0) return false;
            if (sym < 256) {
                dst.Byte((unsigned char)sym);
                continue;
            }
            if (sym == 256) break;
            sym -= 257;
            if (sym >= 29) return false;
            int len = kLenBase[sym];
            if (kLenExtra[sym]) {
                int e = bits.Bits(kLenExtra[sym]);
                if (e < 0) return false;
                len += e;
            }
            int ds = HuffDecode(bits, dist);
            if (ds < 0 || ds >= 30) return false;
            unsigned d = (unsigned)kDistBase[ds];
            if (kDistExtra[ds]) {
                int e = bits.Bits(kDistExtra[ds]);
                if (e < 0) return false;
                d += (unsigned)e;
            }
            if (d > dst.total) return false;
            dst.Copy(d, (unsigned)len);
        }
    } while (!last);
    dst.Flush();
    return dst.ok && (!expect || dst.total == expect);
}

struct ZipEntry
{
    std::string name;
    unsigned method = 0;
    unsigned long long csize = 0, usize = 0, off = 0;
};

static unsigned Rd16(const unsigned char* p) { return p[0] | p[1] << 8; }
static unsigned long long Rd32(const unsigned char* p)
{
    return (unsigned long long)p[0] | p[1] << 8 | p[2] << 16 | (unsigned long long)p[3] << 24;
}

static bool ReadZipIndex(FILE* f, std::vector<ZipEntry>& list)
{
    if (_fseeki64(f, 0, SEEK_END)) return false;
    long long size = _ftelli64(f);
    if (size < 22) return false;
    long long tail = size < 0x10016 ? size : 0x10016;
    std::vector<unsigned char> buf((size_t)tail);
    if (_fseeki64(f, size - tail, SEEK_SET) || fread(buf.data(), 1, buf.size(), f) != buf.size()) return false;
    long long eocd = -1;
    for (long long i = (long long)buf.size() - 22; i >= 0; --i)
        if (!memcmp(&buf[i], "PK\x05\x06", 4)) { eocd = i; break; }
    if (eocd < 0) return false;
    unsigned count = Rd16(&buf[eocd + 10]);
    unsigned long long cdSize = Rd32(&buf[eocd + 12]);
    unsigned long long cdOff = Rd32(&buf[eocd + 16]);
    if (!count || cdSize > (unsigned long long)size) return false;
    std::vector<unsigned char> cd((size_t)cdSize);
    if (_fseeki64(f, (long long)cdOff, SEEK_SET) || fread(cd.data(), 1, cd.size(), f) != cd.size()) return false;
    size_t p = 0;
    for (unsigned i = 0; i < count; ++i) {
        if (p + 46 > cd.size() || memcmp(&cd[p], "PK\x01\x02", 4)) return false;
        ZipEntry e;
        e.method = Rd16(&cd[p + 10]);
        e.csize = Rd32(&cd[p + 20]);
        e.usize = Rd32(&cd[p + 24]);
        unsigned nl = Rd16(&cd[p + 28]), xl = Rd16(&cd[p + 30]), cl = Rd16(&cd[p + 32]);
        e.off = Rd32(&cd[p + 42]);
        if (p + 46 + nl + xl + cl > cd.size()) return false;
        e.name.assign((const char*)&cd[p + 46], nl);
        p += 46 + nl + xl + cl;
        if (e.csize == 0xFFFFFFFFull || e.usize == 0xFFFFFFFFull || e.off == 0xFFFFFFFFull) continue;  // zip64
        list.push_back(e);
    }
    return true;
}

static bool UnzipBuiltin(const std::wstring& zip, const std::wstring& dir, const std::wstring& label)
{
    FILE* f = _wfopen(zip.c_str(), L"rb");
    if (!f) return false;
    std::vector<ZipEntry> list;
    bool ok = ReadZipIndex(f, list);
    unsigned long long totalBytes = 0;
    for (const ZipEntry& e : list) totalBytes += e.usize;
    unsigned long long done = 0;
    int lastPct = -2;
    for (size_t i = 0; ok && i < list.size(); ++i) {
        const ZipEntry& e = list[i];
        std::string name = e.name;
        for (char& c : name)
            if (c == '\\') c = '/';
        if (name.empty() || name[0] == '/' || name.find("..") != std::string::npos) { ok = false; break; }
        std::wstring path = dir + L"\\" + Widen(name, CP_UTF8);
        for (wchar_t& c : path)
            if (c == L'/') c = L'\\';
        if (name.back() == '/') {
            MakeDirs(path);
            continue;
        }
        size_t slash = path.find_last_of(L'\\');
        if (slash != std::wstring::npos) MakeDirs(path.substr(0, slash));
        unsigned char lh[30];
        if (_fseeki64(f, (long long)e.off, SEEK_SET) || fread(lh, 1, 30, f) != 30 ||
            memcmp(lh, "PK\x03\x04", 4)) { ok = false; break; }
        unsigned long long data = e.off + 30 + Rd16(&lh[26]) + Rd16(&lh[28]);
        FILE* out = _wfopen(path.c_str(), L"wb");
        if (!out || _fseeki64(f, (long long)data, SEEK_SET)) { ok = false; break; }
        if (e.method == 0) {
            unsigned char buf[1 << 16];
            unsigned long long left = e.csize;
            while (left && ok) {
                size_t n = (size_t)(left < sizeof buf ? left : sizeof buf);
                if (fread(buf, 1, n, f) != n || fwrite(buf, 1, n, out) != n) ok = false;
                left -= n;
            }
        } else if (e.method == 8) {
            ok = InflateRaw(f, out, e.usize);
        } else {
            ok = false;
        }
        fclose(out);
        done += e.usize;
        if (totalBytes) {
            int pct = (int)(done * 100 / totalBytes);
            if (pct != lastPct) { lastPct = pct; Say(label, pct); }
        }
    }
    fclose(f);
    return ok;
}

static bool ExtractZip(const std::wstring& zip, const std::wstring& dir, const std::wstring& label)
{
    Say(label, 0);
    CreateDirectoryW(dir.c_str(), nullptr);
    if (UnzipBuiltin(zip, dir, label)) return true;
    if (RunAndWait(L"tar.exe -xf \"" + zip + L"\" -C \"" + dir + L"\"")) return true;
    if (RunAndWait(L"powershell.exe -NoProfile -ExecutionPolicy Bypass -Command \"Expand-Archive -LiteralPath '" +
                   zip + L"' -DestinationPath '" + dir + L"' -Force\""))
        return true;

    // last resort: the shell's own zip support (works on every Windows, also 7)
    IShellDispatch* app = nullptr;
    CLSID clsid;
    if (FAILED(CLSIDFromProgID(L"Shell.Application", &clsid)) ||
        FAILED(CoCreateInstance(clsid, nullptr, CLSCTX_LOCAL_SERVER, IID_IShellDispatch, (void**)&app)) || !app)
        return false;

    VARIANT vDir, vZip, vItems;
    VariantInit(&vDir);
    VariantInit(&vZip);
    VariantInit(&vItems);
    vDir.vt = VT_BSTR;
    vDir.bstrVal = SysAllocString(dir.c_str());
    vZip.vt = VT_BSTR;
    vZip.bstrVal = SysAllocString(zip.c_str());
    Folder *folder = nullptr, *zipFolder = nullptr;
    FolderItems* items = nullptr;
    bool ok = false;
    if (SUCCEEDED(app->NameSpace(vDir, &folder)) && SUCCEEDED(app->NameSpace(vZip, &zipFolder)) &&
        SUCCEEDED(zipFolder->Items(&items)) && folder && items) {
        vItems.vt = VT_DISPATCH;
        vItems.pdispVal = items;
        items->AddRef();
        VARIANT vOpt;
        VariantInit(&vOpt);
        vOpt.vt = VT_I4;
        vOpt.lVal = 0x14;  // 4 = no progress dialog, 16 = "yes to all"
        if (SUCCEEDED(folder->CopyHere(vItems, vOpt))) {
            // CopyHere returns immediately; wait until the folder stops growing
            unsigned long long lastSize = 0;
            int stable = 0;
            for (int i = 0; i < 600 && stable < 4; ++i) {
                Sleep(500);
                unsigned long long total = 0;
                for (const std::wstring& n : ListDir(dir)) total += FileSize(dir + L"\\" + n);
                stable = (total == lastSize && total > 0) ? stable + 1 : 0;
                lastSize = total;
            }
            ok = lastSize > 0;
        }
    }
    if (zipFolder) zipFolder->Release();
    if (folder) folder->Release();
    app->Release();
    VariantClear(&vDir);
    VariantClear(&vZip);
    VariantClear(&vItems);  // releases the FolderItems reference
    return ok;
}

// ---------------------------------------------------------------- file copy

struct CopyStats { int copied = 0, kept = 0, failed = 0; std::wstring error; };

static void CountTree(const std::wstring& src, int& files, unsigned long long& bytes)
{
    WIN32_FIND_DATAW fd;
    HANDLE h = FindFirstFileW((src + L"\\*").c_str(), &fd);
    if (h == INVALID_HANDLE_VALUE) return;
    do {
        std::wstring name = fd.cFileName;
        if (name == L"." || name == L"..") continue;
        std::wstring s = src + L"\\" + name;
        if (fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) {
            CountTree(s, files, bytes);
            continue;
        }
        ++files;
        bytes += ((unsigned long long)fd.nFileSizeHigh << 32) | fd.nFileSizeLow;
    } while (FindNextFileW(h, &fd));
    FindClose(h);
}

// .bak, .bak.1, .bak.2... without overwriting an older copy
static void Backup(const std::wstring& path)
{
    RememberFile(path);
    std::wstring bak = path + L".bak";
    for (int i = 1; Exists(bak); ++i) bak = path + L".bak." + std::to_wstring(i);
    MoveFileW(path.c_str(), bak.c_str());
}

static void CopyTree(const std::wstring& src, const std::wstring& dst, CopyStats& st, int total, int& done)
{
    CreateDirectoryW(dst.c_str(), nullptr);
    WIN32_FIND_DATAW fd;
    HANDLE h = FindFirstFileW((src + L"\\*").c_str(), &fd);
    if (h == INVALID_HANDLE_VALUE) return;
    do {
        std::wstring name = fd.cFileName;
        if (name == L"." || name == L"..") continue;
        std::wstring s = src + L"\\" + name, d = dst + L"\\" + name;
        if (fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) {
            std::wstring lower=name;
            for (wchar_t& c:lower) c=(wchar_t)towlower(c);
            if (lower==L"save" || lower==L"saves" || lower==L"players" || lower==L"backups") continue;
            CreateDirectoryW(d.c_str(), nullptr);
            CopyTree(s, d, st, total, done);
            continue;
        }
        std::wstring low = name;
        for (wchar_t& c : low) c = (wchar_t)towlower(c);
        bool user = low == L"config.cfg" || low == L"config_mp.cfg" || low == L"uoconfig.cfg" || low == L"autoexec.cfg" ||
                    (low.size() >= 4 && (low.substr(low.size()-4)==L".sav" || low.substr(low.size()-4)==L".svg"));
        if (user) { ++st.kept; continue; }
        bool equal=false;
        if (Exists(d)) {
            if (user) equal=true;
            else if (FileSize(d)==fd.nFileSizeLow) {
                try { equal=suite::Hash(s)==suite::Hash(d); } catch (...) { equal=false; }
            }
        }
        if (equal) {
            ++st.kept;
        } else {
            RememberFile(d);
            if (Exists(d)) Backup(d);
            if (!CopyFileW(s.c_str(), d.c_str(), FALSE)) {
                ++st.failed;
                if (st.error.empty()) st.error = d;
            } else {
                ++st.copied;
            }
        }
        if (total > 0 && g_dlg) {
            int pct = (++done) * 100 / total;
            static int lastPct = -1;
            if (pct != lastPct) {
                lastPct = pct;
                Say(L("Spieldateien werden kopiert...", "Copying the game files..."), pct);
            }
        }
    } while (FindNextFileW(h, &fd));
    FindClose(h);
}

// ---------------------------------------------------------------- payload

static std::wstring LocalPayload()
{
    std::wstring dir = ExeDir();
    for (const std::wstring& cand : {dir + L"\\game", DirName(dir) + L"\\game"}) {
        if (Exists(cand + L"\\CoDUOSP.exe") || Exists(cand + L"\\CoDSP.exe")) return cand;
    }
    return L"";
}

static std::wstring FindLocalFile(const std::vector<std::wstring>& names)
{
    std::wstring dir = ExeDir();
    for (const std::wstring& base : {dir, DirName(dir)}) {
        for (const std::wstring& name : names) {
            std::wstring p = base + L"\\" + name;
            if (Exists(p)) return p;
        }
    }
    return L"";
}

static std::wstring FindLocalDir(const std::vector<std::wstring>& names)
{
    std::wstring dir = ExeDir();
    for (const std::wstring& base : {dir, DirName(dir)}) {
        for (const std::wstring& name : names) {
            std::wstring p = base + L"\\" + name;
            if (IsDir(p)) return p;
        }
    }
    return L"";
}

// folder that contains Main\localized_*.pk3 (the German pack)
static std::wstring FindGermanTree(const std::wstring& root, int depth = 0)
{
    std::wstring main = FindChild(root, L"Main");
    if (!main.empty()) {
        for (const std::wstring& n : ListDir(main))
            if (!_wcsnicmp(n.c_str(), L"localized_", 10)) return root;
    }
    if (depth >= 3) return L"";
    WIN32_FIND_DATAW fd;
    HANDLE h = FindFirstFileW((root + L"\\*").c_str(), &fd);
    if (h == INVALID_HANDLE_VALUE) return L"";
    std::wstring found;
    do {
        if (!(fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY)) continue;
        if (!wcscmp(fd.cFileName, L".") || !wcscmp(fd.cFileName, L"..")) continue;
        found = FindGermanTree(root + L"\\" + fd.cFileName, depth + 1);
        if (!found.empty()) break;
    } while (FindNextFileW(h, &fd));
    FindClose(h);
    return found;
}

// folder that contains sp_improved\ or UnitedFronts\ (the extras pack)
static std::wstring FindExtrasTree(const std::wstring& root, int depth = 0)
{
    if (!FindChild(root, L"sp_improved").empty() || !FindChild(root, L"UnitedFronts").empty()) return root;
    if (depth >= 3) return L"";
    WIN32_FIND_DATAW fd;
    HANDLE h = FindFirstFileW((root + L"\\*").c_str(), &fd);
    if (h == INVALID_HANDLE_VALUE) return L"";
    std::wstring found;
    do {
        if (!(fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY)) continue;
        if (!wcscmp(fd.cFileName, L".") || !wcscmp(fd.cFileName, L"..")) continue;
        found = FindExtrasTree(root + L"\\" + fd.cFileName, depth + 1);
        if (!found.empty()) break;
    } while (FindNextFileW(h, &fd));
    FindClose(h);
    return found;
}

static std::wstring PreparePayload(std::wstring& err)
{
    std::wstring payload = LocalPayload();
    if (!payload.empty()) return payload;

    std::wstring zip = FindLocalFile({L"Call-of-Duty-UO-Coop-Ready.zip", L"Call of Duty - UO Coop Ready.zip"});
    std::wstring tmp;
    if (zip.empty()) {
        zip = TempPath(L"cod-coop-ready.zip");
        if (!Download(READY_URL, zip, L("Download UO-Basispaket", "Downloading UO base pack"))) {
            err = L("Das Paket konnte nicht heruntergeladen werden.\n\n"
                    "Internetverbindung pruefen und noch einmal versuchen, oder\n"
                    "\"Call-of-Duty-UO-Coop-Ready.zip\" von\n"
                    "https://github.com/benjarogit/CoDCoop/releases/latest\n"
                    "herunterladen und neben den Installer legen.",
                    "The package could not be downloaded.\n\n"
                    "Check the internet connection and try again, or download\n"
                    "\"Call-of-Duty-UO-Coop-Ready.zip\" from\n"
                    "https://github.com/benjarogit/CoDCoop/releases/latest\n"
                    "and put it next to the installer.");
            return L"";
        }
        tmp = TempPath(L"cod-coop-ready");
    } else {
        tmp = TempPath(L"cod-coop-ready");
    }
    if (!VerifyArchive(zip,ExpectedArchive(READY_URL))) { err=L"Base package checksum mismatch"; return L""; }
    if (!ExtractZip(zip, tmp, L("Paket wird entpackt...", "Extracting the package..."))) {
        err = L("Das Paket konnte nicht entpackt werden.", "The package could not be extracted.");
        return L"";
    }
    for (const std::wstring& cand : {tmp + L"\\" + READY_FOLDER + L"\\game", tmp + L"\\game"}) {
        if (Exists(cand + L"\\CoDUOSP.exe")) return cand;
    }
    err = L("Das Paket hat ein unerwartetes Format.", "The package has an unexpected layout.");
    return L"";
}

// ---------------------------------------------------------------- language pack

static std::wstring PrepareGerman(std::wstring& err)
{
    std::wstring src; // German content is accepted only from the pinned ZIP.
    std::wstring zip = FindLocalFile({L"CoD-UO-German-Language.zip"});
    if (zip.empty()) {
        zip = TempPath(L"CoD-UO-German-Language.zip");
        if (!Download(GERMAN_URL, zip, L("Download deutsches Sprachpaket", "Downloading German language pack"))) {
            err = L("Das deutsche Sprachpaket konnte nicht geladen werden.",
                    "The German language pack could not be downloaded.");
            return L"";
        }
    }
    std::wstring tmp = TempPath(L"cod-german");
    if (!VerifyArchive(zip,ExpectedArchive(GERMAN_URL))) { err=L"Language package checksum mismatch"; return L""; }
    if (!ExtractZip(zip, tmp, L("Sprachpaket wird entpackt...", "Extracting the language pack..."))) {
        err = L("Das Sprachpaket konnte nicht entpackt werden.", "The language pack could not be extracted.");
        return L"";
    }
    src = FindGermanTree(tmp);
    if (src.empty()) err = L("Das Sprachpaket hat ein unerwartetes Format.",
                             "The language pack has an unexpected layout.");
    return src;
}

static bool InstallGerman(const std::wstring& dir, std::wstring& err)
{
    std::wstring main = FindChild(dir, L"Main");

    std::wstring src = PrepareGerman(err);
    if (src.empty()) return false;

    Say(L("Deutsches Sprachpaket wird installiert...", "Installing the German language pack..."), -1);
    for (const wchar_t* sub : {L"Main", L"uo"}) {
        std::wstring dst = FindChild(dir, sub);
        std::wstring from = FindChild(src, sub);
        if (dst.empty() || from.empty()) continue;
        std::wstring bak = dst + L"\\localized_backup";
        bool haveBackup = IsDir(bak);

        for (const std::wstring& n : ListDir(dst)) {
            std::wstring low = n;
            for (wchar_t& c : low) c = (wchar_t)towlower(c);
            if (low.rfind(L"localized_", 0) != 0 || low.size() < 4 || low.substr(low.size() - 4) != L".pk3") continue;
            if (!haveBackup) {
                CreateDirectoryW(bak.c_str(), nullptr);
                RememberFile(dst + L"\\" + n);
                MoveFileW((dst + L"\\" + n).c_str(), (bak + L"\\" + n).c_str());
            } else {
                RememberFile(dst + L"\\" + n);
                DeleteFileW((dst + L"\\" + n).c_str());
            }
        }
        for (const std::wstring& n : ListDir(from)) {
            std::wstring low = n;
            for (wchar_t& c : low) c = (wchar_t)towlower(c);
            if (low.rfind(L"localized_", 0) != 0 || low.size() < 4 || low.substr(low.size() - 4) != L".pk3") continue;
            RememberFile(dst + L"\\" + n);
            if (!CopyFileW((from + L"\\" + n).c_str(), (dst + L"\\" + n).c_str(), FALSE)) {
                err = L("Sprachdatei konnte nicht kopiert werden:\n", "Could not copy a language file:\n") +
                      dst + L"\\" + n;
                return false;
            }
        }
    }
    WriteAll(main + L"\\.cod-coop-german", "{\"installed\":\"setup\"}\r\n");
    return true;
}

static bool RestoreCanonicalEnglish(const std::wstring& dir, std::wstring& err)
{
    try {
        auto inventory=suite::EnglishInventory(dir);
        if (inventory.empty()) return true; // Existing English game, development overlay.
        for (auto i=inventory.begin();i!=inventory.end();++i)
            if (suite::Hash(suite::Resolve(dir,i.key()))!=i.value()) throw std::runtime_error("canonical English source changed: "+i.key());
        for (const wchar_t* sub:{L"Main",L"uo"}) {
            auto folder=FindChild(dir,sub);
            for (const auto& name:ListDir(folder)) {
                auto low=name;for(auto& c:low)c=(wchar_t)towlower(c);
                if (low.rfind(L"localized_",0)==0 && low.size()>4 && low.substr(low.size()-4)==L".pk3") {
                    auto file=folder+L"\\"+name;RememberFile(file);
                    if (!DeleteFileW(file.c_str())) throw std::runtime_error("cannot remove previous localization");
                }
            }
        }
        for (auto i=inventory.begin();i!=inventory.end();++i) {
            std::string relative=i.key().substr(std::string("coop/languages/en/").size());
            auto destination=suite::Resolve(dir,relative);RememberFile(destination);
            if (!CopyFileW(suite::Resolve(dir,i.key()).c_str(),destination.c_str(),FALSE) || suite::Hash(destination)!=i.value())
                throw std::runtime_error("cannot restore canonical English file: "+relative);
        }
        auto marker=suite::Resolve(dir,"Main/.cod-coop-german");RememberFile(marker);DeleteFileW(marker.c_str());
        return true;
    } catch (const std::exception& e) { err=Widen(e.what());return false; }
}

// ---------------------------------------------------------------- extras

static void WriteLaunchers(const std::wstring& dir)
{
    const wchar_t* profiles[][4]={{L"sp_improved",L"Start-CoD-Coop.bat",L"CoDUOSP.exe",L"sp_improved"},
        {L"cod1",L"Start-CoD-Classic.bat",L"CoDSP.exe",L""},
        {L"uo",L"Start-UO-Coop.bat",L"CoDUOSP.exe",L""},
        {L"sp_improved",L"Start-SP-Improved.bat",L"CoDUOSP.exe",L"sp_improved"},
        {L"united_fronts",L"Start-United-Fronts.bat",L"CoDUOSP.exe",L"UnitedFronts"}};
    for (const auto& profile:profiles) {
        std::string text="@echo off\r\ncd /d \"%~dp0\"\r\n"
            "if not exist \"%~dp0coop\\launcher\\CoD-Coop-Launcher.exe\" (echo Windows launcher missing. Repair with a Windows 0.6 package. & exit /b 2)\r\n"
            "start \"\" \"%~dp0coop\\launcher\\CoD-Coop-Launcher.exe\" --game \"%~dp0.\" --variant "+Narrow(profile[0])+"\r\n";
        if (!WriteAll(dir+L"\\"+profile[1],text)) throw std::runtime_error("cannot write campaign launcher");
    }
}

static bool WriteLauncherShortcut(const std::wstring& dir)
{
    IShellLinkW* link = nullptr;
    HRESULT result = CoCreateInstance(CLSID_ShellLink, nullptr, CLSCTX_INPROC_SERVER,
                                      IID_IShellLinkW, reinterpret_cast<void**>(&link));
    if (FAILED(result)) return false;
    const auto launcher = dir + L"\\coop\\launcher\\CoD-Coop-Launcher.exe";
    const auto args = L"--game \"" + dir + L"\\.\"";
    result = link->SetPath(launcher.c_str());
    if (SUCCEEDED(result)) result = link->SetArguments(args.c_str());
    if (SUCCEEDED(result)) result = link->SetWorkingDirectory(dir.c_str());
    IPersistFile* file = nullptr;
    if (SUCCEEDED(result)) result = link->QueryInterface(IID_IPersistFile, reinterpret_cast<void**>(&file));
    if (SUCCEEDED(result)) {
        result = file->Save((dir + L"\\CoDCoop.lnk").c_str(), TRUE);
        file->Release();
    }
    link->Release();
    return SUCCEEDED(result);
}

static bool InstallExtras(const std::wstring& dir, bool sp, bool uf, bool map, std::wstring& err)
{
    bool haveSp=VerifyArchive(dir+L"\\sp_improved\\sp_improved_1.5.pk3","25c1978fb48ec9324babed270be78d2f647e0d8a3e24c2415cd88aabb012e678");
    bool haveUf=VerifyArchive(dir+L"\\UnitedFronts\\ZUnitedFronts_1.1_beta.pk3","b4f6bb7d03477d7e77e5150af4ca88eeb3dee30e0f715edfa1e2338d3e9d1cbe");
    if ((!sp || haveSp) && (!uf || haveUf) && (!map || Exists(dir+L"\\uo\\uomappack00.pk3"))) {
        WriteLaunchers(dir);
        return true;
    }

    std::wstring src = g_overlayOverride.empty()?FindLocalDir({L"suite", L"extras", L"CoD-SP-Extras"}):g_overlayOverride;
    if (src.empty()) {
        std::wstring zip = FindLocalFile({L"CoD-SP-Extras.zip"});
        if (zip.empty()) {
            zip = TempPath(L"CoD-SP-Extras.zip");
            if (!Download(EXTRAS_URL, zip, L("Download Zusatzinhalte", "Downloading campaign extras"))) {
                err = L("Die Zusatzinhalte konnten nicht geladen werden.",
                        "The extras could not be downloaded.");
                return false;
            }
        }
        std::wstring tmp = TempPath(L"cod-extras");
        if (!VerifyArchive(zip,ExpectedArchive(EXTRAS_URL))) { err=L"Extras package checksum mismatch"; return false; }
        if (!ExtractZip(zip, tmp, L("Zusatzinhalte werden entpackt...", "Extracting the extras..."))) {
            err = L("Die Zusatzinhalte konnten nicht entpackt werden.",
                    "The extras could not be extracted.");
            return false;
        }
        src = FindExtrasTree(tmp);
    } else {
        src = FindExtrasTree(src);
    }
    if (src.empty()) {
        err = L("Das Zusatzpaket hat ein unerwartetes Format.", "The extras pack has an unexpected layout.");
        return false;
    }

    Say(L("Zusatzinhalte werden installiert...", "Installing the extras..."), -1);
    CopyStats st;
    if (sp) {
        std::wstring from = FindChild(src, L"sp_improved");
        if (!from.empty()) {
            int total = 0;
            unsigned long long bytes = 0;
            CountTree(from, total, bytes);
            int done = 0;
            CopyTree(from, dir + L"\\sp_improved", st, total, done);
        }
    }
    if (uf) {
        std::wstring from = FindChild(src, L"UnitedFronts");
        if (!from.empty()) {
            int total = 0;
            unsigned long long bytes = 0;
            CountTree(from, total, bytes);
            int done = 0;
            CopyTree(from, dir + L"\\UnitedFronts", st, total, done);
        }
    }
    if (map) {
        std::wstring uo = FindChild(dir, L"uo");
        std::wstring uosrc = FindChild(src, L"uo");
        std::wstring pak = uosrc.empty() ? L"" : FindChild(uosrc, L"uomappack00.pk3");
        if (!uo.empty() && !pak.empty() && !Exists(uo + L"\\uomappack00.pk3"))
            CopyFileW(pak.c_str(), (uo + L"\\uomappack00.pk3").c_str(), FALSE);
        std::wstring docs = FindChild(src, L"UODocs");
        if (!docs.empty()) {
            int total = 0;
            unsigned long long bytes = 0;
            CountTree(docs, total, bytes);
            int done = 0;
            CopyTree(docs, dir + L"\\UODocs", st, total, done);
        }
    }
    // the Kar98k FOV fix is part of the extras pack
    std::wstring main = FindChild(dir, L"Main");
    std::wstring fixdir = FindChild(src, L"Main");
    std::wstring fix = fixdir.empty() ? L"" : FindChild(fixdir, L"zzz_patch.pk3");
    if (!main.empty() && !fix.empty() && !Exists(main + L"\\zzz_patch.pk3"))
        CopyFileW(fix.c_str(), (main + L"\\zzz_patch.pk3").c_str(), FALSE);

    WriteLaunchers(dir);
    if (st.failed) {
        err = L("Zusatzdatei konnte nicht kopiert werden:\n", "Could not copy an extras file:\n") + st.error;
        return false;
    }
    return true;
}

// ---------------------------------------------------------------- 1.5

static bool EnsureCod15(const std::wstring& dir, const std::wstring& payload)
{
    std::wstring exe = dir + L"\\CoDSP.exe";
    if (!WrongSize(exe, CODSP_SIZE)) return true;
    if (Exists(exe)) Backup(exe);
    if (!payload.empty() && FileSize(payload + L"\\CoDSP.exe") == CODSP_SIZE &&
        CopyFileW((payload + L"\\CoDSP.exe").c_str(), exe.c_str(), FALSE))
        return true;
    if (WriteResource(9, exe) && !WrongSize(exe, CODSP_SIZE)) return true;
    return false;
}

// ---------------------------------------------------------------- the actual install

struct Job {
    std::wstring dir;
    bool german = false;
    std::wstring name=L"Player";
    std::wstring res=L"1920x1080";
    bool fullscreen = true;
    int fov = 96;
    int quality = Q_HIGH;
    bool sp = true, uf = true, map = false, configure = false;
};
static Job g_job;
static std::wstring g_summary;

static void Line(const std::wstring& text) { g_summary += text + L"\r\n"; }

static bool RetiredTriggerName(const std::string& base) {
    return base=="zzzzz_codcoop_triggers.pk3" || base=="zzzzz_coop_triggers.pk3";
}
static std::map<std::string,suite::Json> PayloadPins(const suite::Json& files) {
    if (!files.is_object()) throw std::runtime_error("invalid previous or replacement payload ownership");
    std::map<std::string,suite::Json> result;
    for (auto it=files.begin();it!=files.end();++it) {
        auto lower=suite::Lower(it.key());
        if (!result.emplace(lower,it.value()).second) throw std::runtime_error("ambiguous payload ownership path: "+it.key());
    }
    return result;
}
static bool PayloadDigest(const suite::Json& value) {
    if (!value.is_string()) return false;
    auto hash=value.get<std::string>();
    return hash.size()==64 && std::all_of(hash.begin(),hash.end(),[](char c){return (c>='0'&&c<='9')||(c>='a'&&c<='f');});
}
static suite::Json CoopUiRequirement(const std::wstring& root) {
    auto manifest=suite::Json::parse(suite::Read(root+L"\\coop\\variants.json"));
    suite::Json item;
    for (const auto& row:manifest.at("required")) if (row.value("kind",std::string())=="coop_localization") {
        if (!item.is_null()) throw std::runtime_error("ambiguous CoDCoop UI localization requirement");
        item=row;
    }
    if (item.is_null()) {
        if ((manifest.value("core_features_required",0u)&32u)!=0) throw std::runtime_error("mandatory CoDCoop UI locale requirement missing");
        return item;
    }
    const std::string path="Main/localized_english_codcoop_ui.pk3";
    auto en=item.at("locales").at("en"),de=item.at("locales").at("de");
    suite::Json allowed={en.at("sha256"),de.at("sha256")};
    if (item.at("path")!=path || item.at("sha256_any")!=allowed || manifest.at("approved_localizations").at(path)!=allowed ||
        !PayloadDigest(en.at("sha256")) || !PayloadDigest(de.at("sha256"))) throw std::runtime_error("invalid CoDCoop UI locale pins");
    return item;
}
static void ValidateCoopUiFile(const std::wstring& path,const suite::Json& pin) {
    const std::string data=suite::Read(path),name="localizedstrings/english/codcoop.str";
    if (!pin.at("size").is_number_unsigned() || data.size()!=pin.at("size").get<size_t>() || data.size()>16384 || suite::Hash(path)!=pin.at("sha256"))
        throw std::runtime_error("CoDCoop UI locale bank missing or changed: "+suite::Utf8(path));
    auto word=[&](size_t at)->uint16_t {if(at>data.size() || data.size()-at<2)throw std::runtime_error("truncated CoDCoop locale ZIP");return uint8_t(data[at])|(uint16_t(uint8_t(data[at+1]))<<8);};
    auto dword=[&](size_t at)->uint32_t {return uint32_t(word(at))|(uint32_t(word(at+2))<<16);};
    if (data.size()<98 || dword(0)!=0x04034b50 || word(6)!=0 || word(8)!=0 || word(26)!=name.size() || word(28)!=0 ||
        dword(18)!=dword(22) || dword(18)>data.size()-30-name.size() || data.substr(30,name.size())!=name) throw std::runtime_error("CoDCoop locale must contain one owned stored resource");
    size_t central=30+name.size()+dword(18),end=central+46+name.size();
    if (end+22!=data.size() || dword(central)!=0x02014b50 || word(central+8)!=0 || word(central+10)!=0 ||
        dword(central+20)!=dword(18) || dword(central+24)!=dword(22) || word(central+28)!=name.size() || word(central+30)!=0 || word(central+32)!=0 ||
        dword(central+42)!=0 || data.substr(central+46,name.size())!=name || dword(end)!=0x06054b50 || word(end+4)!=0 || word(end+6)!=0 ||
        word(end+8)!=1 || word(end+10)!=1 || dword(end+12)!=46+name.size() || dword(end+16)!=central || word(end+20)!=0)
        throw std::runtime_error("CoDCoop locale must contain exactly one owned stored resource");
}
static void PreflightCoopUiBanks(const std::wstring& root) {
    auto item=CoopUiRequirement(root);if(item.is_null())return;
    for (const std::string language:{"en","de"}) ValidateCoopUiFile(suite::Resolve(root,"coop/languages/"+language+"/Main/localized_english_codcoop_ui.pk3"),item.at("locales").at(language));
    ValidateCoopUiFile(suite::Resolve(root,"Main/localized_english_codcoop_ui.pk3"),item.at("locales").at("en"));
}
static void ApplyCoopUiLanguage(const std::wstring& game,bool german) {
    auto item=CoopUiRequirement(game);if(item.is_null())return;
    std::string language=german?"de":"en";
    auto source=suite::Resolve(game,"coop/languages/"+language+"/Main/localized_english_codcoop_ui.pk3");
    const auto& pin=item.at("locales").at(language);ValidateCoopUiFile(source,pin);
    auto destination=suite::Resolve(game,"Main/localized_english_codcoop_ui.pk3");RememberFile(destination);
    if (!CopyFileW(source.c_str(),destination.c_str(),FALSE)) throw std::runtime_error("cannot install selected CoDCoop UI locale");
    ValidateCoopUiFile(destination,pin);
}
static void PreflightRetiredTriggerOverlays(const std::wstring& game,const std::wstring& overlay) {
    const auto newPath=overlay+L"\\coop\\runtime-lock.json";
    if (!Exists(newPath)) return;
    auto current=PayloadPins(suite::Json::parse(suite::Read(newPath)).at("files"));
    std::map<std::string,suite::Json> old;
    const auto oldPath=game+L"\\coop\\runtime-lock.json";
    if (Exists(oldPath)) old=PayloadPins(suite::Json::parse(suite::Read(oldPath)).at("files"));
    std::set<std::string> required;
    auto manifestPath=overlay+L"\\coop\\variants.json";
    if (Exists(manifestPath)) {
        auto manifest=suite::Json::parse(suite::Read(manifestPath));
        for (const auto& item:manifest.at("required")) required.insert(suite::Lower(item.at("path").get<std::string>()));
    }
    for (const std::string folder:{"Main","uo","sp_improved","UnitedFronts"}) {
        const auto replacement=folder+"/zzzz_coop_triggers.pk3", lower=suite::Lower(replacement);
        auto pin=current.find(lower);
        if (pin==current.end() && !required.count(lower)) continue;
        auto file=suite::Resolve(overlay,replacement);DWORD attr=GetFileAttributesW(file.c_str());
        if (pin==current.end() || !PayloadDigest(pin->second) || attr==INVALID_FILE_ATTRIBUTES ||
            (attr&(FILE_ATTRIBUTE_DIRECTORY|FILE_ATTRIBUTE_REPARSE_POINT)) || suite::Hash(file)!=pin->second.get<std::string>())
            throw std::runtime_error(suite::Utf8(std::wstring(L("Das neue Missionspaket fehlt oder wurde veraendert: ","Replacement mission overlay is missing or changed: "))+Widen(replacement)));
        for (const std::string base:{"zzzzz_codcoop_triggers.pk3","zzzzz_coop_triggers.pk3"}) {
            const auto rel=folder+"/"+base, key=suite::Lower(rel);
            if (current.count(key)) continue;
            auto path=suite::Resolve(game,rel);DWORD attributes=GetFileAttributesW(path.c_str());
            if (attributes==INVALID_FILE_ATTRIBUTES) continue;
            auto previous=old.find(key);
            if ((attributes&(FILE_ATTRIBUTE_DIRECTORY|FILE_ATTRIBUTE_REPARSE_POINT)) || previous==old.end() ||
                !PayloadDigest(previous->second) || suite::Hash(path)!=previous->second.get<std::string>())
                throw std::runtime_error(suite::Utf8(std::wstring(L("Vorheriges Missionspaket ist veraendert oder nicht paketverwaltet. Bitte sichern und vor dem Update ausdruecklich entfernen: ",
                    "Previous mission overlay is modified or not payload-owned; back it up and remove it explicitly before updating: "))+Widen(rel)));
        }
    }
}
static void RetireOldPayload(const std::wstring& game,const std::wstring& overlay) {
    PreflightRetiredTriggerOverlays(game,overlay);
    auto oldPath=game+L"\\coop\\runtime-lock.json", newPath=overlay+L"\\coop\\runtime-lock.json";
    if (!Exists(oldPath) || !Exists(newPath)) return;
    auto old=suite::Json::parse(suite::Read(oldPath)).at("files");
    auto current=suite::Json::parse(suite::Read(newPath)).at("files");
    std::set<std::string> keep;
    for (auto it=current.begin();it!=current.end();++it) keep.insert(suite::Lower(it.key()));
    for (auto it=old.begin();it!=old.end();++it) {
        std::string lower=suite::Lower(it.key());
        std::string base=lower.substr(lower.find_last_of('/')+1);
        bool generated=(lower.size()>=4 && lower.substr(lower.size()-4)==".pk3" && (base.find("codcoop")!=std::string::npos || RetiredTriggerName(base) || base=="zzzz_coop_triggers.pk3" || base=="zzzz_coop_campaign.pk3")) || lower.rfind("coop/launcher/",0)==0;
        if (!generated || keep.count(lower)) continue;
        auto path=suite::Resolve(game,it.key());
        if (suite::PersonalPath(path)) continue;
        if (Exists(path) && it.value().is_string() && suite::Hash(path)==it.value().get<std::string>()) {
            RememberFile(path);
            if (!DeleteFileW(path.c_str())) throw std::runtime_error("cannot retire previous runtime file");
        }
    }
}

static bool RunInstall(std::wstring& err)
{
    const std::wstring& dir = g_job.dir;
    int games = GamesIn(dir);
    if (!games) {
        err = L("In diesem Ordner liegt kein Call of Duty (CoDSP.exe).",
                "There is no Call of Duty (CoDSP.exe) in that folder.");
        return false;
    }

    bool cod1 = (games & COD1) != 0;
    std::wstring overlay = g_overlayOverride.empty()?FindLocalDir({L"suite"}):g_overlayOverride;
    if (!cod1 || overlay.empty() || !Exists(overlay + L"\\coop\\variants.json") ||
        !Exists(overlay + L"\\coop\\runtime-lock.json")) {
        err = L("Ein vollstaendiges 0.6-Paket im Ordner suite neben dem Installer ist erforderlich. CoD 2 bleibt experimentell.",
                "A complete 0.6 payload in the suite folder next to the installer is required. CoD 2 remains experimental.");
        return false;
    }
    if (!Exists(overlay+L"\\coop\\launcher\\CoD-Coop-Launcher.exe")) {
        err=L("Das Paket enthaelt keinen Windows-Launcher. Ein Linux-Paket ist keine vollstaendige Windows-Installation.",
              "The payload has no Windows launcher. A Linux payload is not a complete Windows installation.");
        return false;
    }
    std::wstring currentMain=FindChild(dir,L"Main");
    if (!g_job.german && !currentMain.empty() && Exists(currentMain+L"\\.cod-coop-german") &&
        !Exists(overlay+L"\\coop\\languages\\en\\manifest.json") && !Exists(dir+L"\\coop\\languages\\en\\manifest.json")) {
        err=L("Zum Wechsel auf Englisch fehlen gepruefte englische Sprachdateien. Deutsch beibehalten oder zuerst die englische Basis wiederherstellen.",
              "Verified English language files are needed to switch this German installation. Keep German or restore the English base first.");
        return false;
    }
    PreflightCoopUiBanks(overlay);
    PreflightRetiredTriggerOverlays(dir,overlay); // before downloads or transaction mutation
    auto suiteManifest=suite::Json::parse(suite::Read(overlay+L"\\coop\\variants.json"));
    for (const auto& item:suiteManifest.at("required")) {
        if (item.value("kind",std::string())!="base_content" || item.value("engine",std::string())!="cod1") continue;
        std::string relative=item.at("path");
        if (!Exists(suite::Resolve(dir,relative)) && !Exists(suite::Resolve(overlay,relative))) {
            err=L("Urspruengliche CoD-Kampagnendaten fehlen: ","Original CoD campaign content is missing: ")+Widen(relative)+
                L(". Die vollstaendige eigene CoD-1.5-Installation oder ein geprueftes Vollpaket wiederherstellen. Das UO-Ready-ZIP enthaelt diese CoD-Basis nicht.",
                  ". Restore your complete owned CoD 1.5 installation or use a verified full suite payload. The UO Ready ZIP does not supply this original base content.");
            return false;
        }
    }
    g_changes.clear();
    g_transactionActive=true;
    RetireOldPayload(dir,overlay);
    if (suiteManifest.contains("ignored_placeholder")) {
        const auto& item=suiteManifest.at("ignored_placeholder");
        if (item.value("path",std::string())=="Main/pakb.pk3" && item.value("size",0)==1) {
            auto path=suite::Resolve(dir,"Main/pakb.pk3");
            if (FileSize(path)==1 && suite::Hash(path)==item.at("sha256")) {
                RememberFile(path);
                if (!DeleteFileW(path.c_str())) throw std::runtime_error("cannot remove invalid one-byte pakb placeholder");
            }
        }
    }
    std::wstring payload;
    if (cod1) {
        payload = Exists(dir + L"\\CoDUOSP.exe") ? overlay : PreparePayload(err);
        if (payload.empty()) return false;
    }

    if (cod1) {
        if (WrongSize(dir + L"\\CoDSP.exe", CODSP_SIZE)) {
            Say(L("Call of Duty 1.5 wird installiert...", "Installing Call of Duty 1.5..."), -1);
            if (!EnsureCod15(dir, payload)) {
                err = L("Call of Duty 1.5 konnte nicht installiert werden.\n\n  Ordner:    ",
                        "Call of Duty 1.5 could not be installed.\n\n  folder:    ") + dir +
                      L"\n  CoDSP.exe: " + std::to_wstring(FileSize(dir + L"\\CoDSP.exe")) +
                      L" Bytes\n" + L("  erwartet:  ", "  expected:  ") + std::to_wstring(CODSP_SIZE) +
                      L" Bytes (1.5)";
                return false;
            }
            Line(L("Call of Duty 1.5 installiert (alte Exe als CoDSP.exe.bak).",
                   "Call of Duty 1.5 installed (the old exe is CoDSP.exe.bak)."));
        }

        Say(L("Spieldateien werden kopiert...", "Copying the game files..."), 0);
        int total = 0;
        unsigned long long bytes = 0;
        CountTree(payload, total, bytes);
        int done = 0;
        CopyStats st;
        CopyTree(payload, dir, st, total, done);
        if (st.failed) {
            err = L("Datei konnte nicht kopiert werden:\n", "Could not copy a file:\n") + st.error +
                  L("\n\nLaeuft das Spiel noch? Bitte schliessen und noch einmal versuchen.",
                    "\n\nIs the game still running? Close it and try again.");
            return false;
        }
        Line(L("Spieldateien: ", "Game files: ") + std::to_wstring(st.copied) +
             L(" kopiert, ", " copied, ") + std::to_wstring(st.kept) + L(" schon aktuell.", " up to date."));

        // a ddraw.dll or steam_api.dll that is not ours (another mod, a video fix)
        std::wstring ddraw = dir + L"\\ddraw.dll", steamDll = dir + L"\\steam_api.dll";
        if (Exists(ddraw) && !Exists(ddraw + L".bak") &&
            ReadAll(ddraw).find("codcoop_core.dll") == std::string::npos)
            MoveFileW(ddraw.c_str(), (ddraw + L".bak").c_str());
        if (Exists(steamDll) && !Exists(steamDll + L".bak") && ReadAll(steamDll) != Resource(5))
            MoveFileW(steamDll.c_str(), (steamDll + L".bak").c_str());

        // the files the .exe carries inside (they are newer than the package)
        const int ids[] = {1, 2, 3, 5};
        const wchar_t* dest[] = {L"ddraw.dll", L"codcoop_core.dll", L"Main\\pakz_coop.pk3", L"steam_api.dll"};
        std::wstring mainDir = FindChild(dir, L"Main");
        if (mainDir.empty()) { CreateDirectoryW((dir + L"\\Main").c_str(), nullptr); mainDir = dir + L"\\Main"; }
        for (int i = 0; i < 4; ++i) {
            std::wstring path = (i == 2) ? mainDir + L"\\pakz_coop.pk3" : dir + L"\\" + dest[i];
            if (Exists(path)) Backup(path);
            if (!WriteResource(ids[i], path)) { err=L"Could not write embedded Coop module"; return false; }
        }
        CreateDirectoryW((dir + L"\\uo").c_str(), nullptr);
        if (Exists(dir + L"\\uo\\pakz_coop.pk3")) Backup(dir + L"\\uo\\pakz_coop.pk3");
        if (!WriteResource(6, dir + L"\\uo\\pakz_coop.pk3")) { err=L"Could not write UO menu"; return false; }

        Say(L("Einstellungen werden geschrieben...", "Writing the settings..."), -1);
        bool changedSettings=g_job.configure || !Exists(dir + L"\\Main\\config.cfg");
        if (changedSettings)
            WriteSettings(dir, g_job.name, g_job.res, g_job.fullscreen, g_job.fov, g_job.quality);
        if (changedSettings) Line(L("Einstellungen: ", "Settings: ") + g_job.res + L", " +
             (g_job.fullscreen ? L("Vollbild", "fullscreen") : L("Fenster", "window")) +
             L", FOV " + std::to_wstring(g_job.fov) + L", " +
             (g_job.quality == Q_LOW ? L("niedrig", "low")
                                     : g_job.quality == Q_MED ? L("mittel", "medium") : L("hoch", "high")) +
             L", Name \"" + g_job.name + L"\"");
        else Line(L("Vorhandene persoenliche Einstellungen bleiben erhalten.", "Existing personal settings preserved."));

        if (g_job.sp || g_job.uf || g_job.map) {
            if (!InstallExtras(dir, g_job.sp, g_job.uf, g_job.map, err)) return false;
            std::wstring what;
            if (g_job.sp) what += L"Singleplayer Improved";
            if (g_job.uf) what += std::wstring(what.empty() ? L"" : L", ") + L"United Fronts";
            if (g_job.map) what += std::wstring(what.empty() ? L"" : L", ") + L"UO Map Pack";
            Line(L("Zusatzinhalte installiert: ", "Extras installed: ") + what);
        }

        // The source overlay is applied LAST: embedded 0.5 compatibility
        // resources must never replace the pinned development core.
        {
            CopyStats overlayStats; int total=0, done=0; unsigned long long bytes=0;
            CountTree(overlay,total,bytes); CopyTree(overlay,dir,overlayStats,total,done);
            if (g_job.german) {
                if (!InstallGerman(dir,err)) return false;
            } else if (!RestoreCanonicalEnglish(dir,err)) return false;
            ApplyCoopUiLanguage(dir,g_job.german);
            std::string why;
            RememberFile(dir+L"\\coop\\install.json");
            RememberFile(dir+L"\\coop\\profile.ini");
            // Seal validates all pinned content and writes its receipt/profile in one pass.
            Say(L("Installation wird geprueft...", "Verifying the installation..."));
            if (overlayStats.failed || !suite::Validate(dir,true,why)) {
                err=L("Vollstaendigkeitspruefung fehlgeschlagen: ", "Full-suite verification failed: ")+Widen(why);
                return false;
            }
            Line(L("Alle erforderlichen Coop-Pakete geprueft. Spieltests sind separat dokumentiert.",
                   "All required Coop packages verified. Gameplay tests are documented separately."));
        }
        // the improper-quit marker makes the game ask "did your computer change?"
        DeleteFileW((dir + L"\\__CoDSP").c_str());
        DeleteFileW((dir + L"\\__CoDUOSP").c_str());

        RememberFile(dir + L"\\CoDCoop.lnk");
        if (WriteLauncherShortcut(dir))
            Line(L("\r\nZum Spielen CoDCoop im Spielordner oeffnen.",
                   "\r\nTo play, open CoDCoop in the game folder."));
        else
            Line(L("\r\nZum Spielen Start-CoD-Coop.bat im Spielordner oeffnen.",
                   "\r\nTo play, open Start-CoD-Coop.bat in the game folder."));
    }

#ifdef COOP_EXPERIMENTAL_COD2
    if (games & COD2) {
        // Steam may ship the same single-player build in a differently sized executable.
        const auto cod2Image = ReadAll(dir + L"\\CoD2SP_s.exe");
        if (cod2Image.find("%s %s build %s %s") != std::string::npos &&
            cod2Image.find(COD2SP_BUILD) == std::string::npos) {
            Line(L("Hinweis: CoD2 Coop braucht die Einzelspieler-Version aus Patch 1.2 oder 1.3.",
                   "Note: CoD2 Coop requires the single-player build from patch 1.2 or 1.3."));
        }
        Say(L("Call of Duty 2...", "Call of Duty 2..."), -1);
        CreateDirectoryW((dir + L"\\main").c_str(), nullptr);
        WriteResource(1, dir + L"\\ddraw.dll");
        WriteResource(7, dir + L"\\cod2coop.dll");
        WriteResource(8, dir + L"\\main\\zz_coop2.iwd");
        WriteResource(4, dir + L"\\CoD Coop README.txt");
        WriteResource(5, dir + L"\\steam_api.dll");
        Line(L("Call of Duty 2 installiert (Menue \"Co-op\").", "Call of Duty 2 installed (menu \"Co-op\")."));
    }
#endif
    return true;
}

 #include "installer_rollback.h"

static DWORD WINAPI Worker(LPVOID)
{
    const HRESULT com = CoInitializeEx(nullptr, COINIT_APARTMENTTHREADED);
    std::wstring err;
    bool ok=false;
    try { ok=g_rollbackMode?RollbackLastInstall(g_job.dir,err):RunInstall(err); }
    catch (const std::exception& e) { err=Widen(e.what()); }
    if (!g_rollbackMode) {
        if (!ok) RollbackFiles();
        else {
            g_transactionActive=false;
            try { SaveInstallJournal(g_job.dir); }
            catch (const std::exception& e) { err=Widen(e.what()); ok=false; RollbackFiles(); }
        }
    } else if(ok) g_summary=L("Letzte Installation zurueckgenommen. Aktuelle Einstellungen und Spielstaende wurden behalten.","Last installation rolled back. Current settings and saves were retained.");
    std::wstring* msg = new std::wstring(ok ? g_summary : err);
    PostMessageW(g_dlg, WM_APP_DONE, ok ? 1 : 0, (LPARAM)msg);
    if (SUCCEEDED(com)) CoUninitialize();
    return 0;
}

// ---------------------------------------------------------------- UI

static std::vector<std::wstring> g_found;
static bool g_nameAuto = true;
static bool g_settingName = false;

static void EnableInputs(HWND dlg, BOOL on)
{
    for (int id : {IDC_LIST, IDC_BROWSE, IDC_DE, IDC_EN, IDC_NAME, IDC_RES, IDC_FULL,
                   IDC_FOV, IDC_Q, IDC_MAP, IDC_CONFIGURE, IDC_ROLLBACK})
        EnableWindow(GetDlgItem(dlg, id), on);
}

static void ApplyLanguage(HWND dlg)
{
    SetWindowTextW(dlg, L"Call of Duty Coop - Setup");
    SetWindowTextW(GetDlgItem(dlg, IDC_HEAD),
                   L("Call of Duty + United Offensive - Co-op", "Call of Duty + United Offensive - Co-op"));
    SetWindowTextW(GetDlgItem(dlg, IDC_ST_TARGET), L("Installation", "Installation"));
    SetWindowTextW(GetDlgItem(dlg, IDC_BROWSE), L("Anderer Ordner...", "Another folder..."));
    SetWindowTextW(GetDlgItem(dlg, IDC_ST_LANG), L("Spielsprache", "Game language"));
    SetWindowTextW(GetDlgItem(dlg, IDC_DE), L("Deutsch (Text und Stimmen)", "German (texts and voices)"));
    SetWindowTextW(GetDlgItem(dlg, IDC_EN), L("English", "English"));
    SetWindowTextW(GetDlgItem(dlg, IDC_LANGNOTE),
                   L("Deutsch laedt einmalig das Sprachpaket (~630 MB).\r\n"
                     "English ist im Paket schon enthalten.",
                     "German downloads the language pack once (~630 MB).\r\n"
                     "English is already in the package."));
    SetWindowTextW(GetDlgItem(dlg, IDC_ST_SET), L("Einstellungen", "Settings"));
    SetWindowTextW(GetDlgItem(dlg, IDC_ST_NAME), L("Name:", "Name:"));
    SetWindowTextW(GetDlgItem(dlg, IDC_ST_RES), L("Aufloesung:", "Resolution:"));
    SetWindowTextW(GetDlgItem(dlg, IDC_FULL), L("Vollbild", "Fullscreen"));
    SetWindowTextW(GetDlgItem(dlg, IDC_ST_FOV), L("FOV:", "FOV:"));
    SetWindowTextW(GetDlgItem(dlg, IDC_FOVNOTE), L("(Hor+ automatisch)", "(Hor+ automatic)"));
    SetWindowTextW(GetDlgItem(dlg, IDC_ST_Q), L("Qualitaet:", "Quality:"));
    SetWindowTextW(GetDlgItem(dlg, IDC_FIXNOTE),
                   L("Setzt automatisch die PCGamingWiki-Fixes: kein Intro, Multicore, maxfps 125,\r\n"
                     "kein Maus-Lag, korrekte Helligkeit nach Alt+Tab, maximales Modell-Detail.",
                     "Applies the PCGamingWiki fixes: no intro, multicore, maxfps 125,\r\n"
                     "no mouse lag, correct brightness after Alt+Tab, max model detail."));
    SetWindowTextW(GetDlgItem(dlg, IDC_ST_EXTRAS), L("Vollstaendiger Coop-Umfang", "Complete Coop suite"));
    SetWindowTextW(GetDlgItem(dlg, IDC_SP), L("Singleplayer Improved", "Singleplayer Improved"));
    SetWindowTextW(GetDlgItem(dlg, IDC_UF), L("United Fronts", "United Fronts"));
    SetWindowTextW(GetDlgItem(dlg, IDC_MAP), L("UO Map Pack", "UO map pack"));
    SetWindowTextW(GetDlgItem(dlg, IDC_EXNOTE),
                   L("SP Improved + United Fronts + YAP sind erforderlich.\r\nUO Map Pack: separater Multiplayer-Zusatz.",
                     "SP Improved + United Fronts + YAP are required.\r\nUO Map Pack: separate multiplayer addition."));
    if (g_state == S_IDLE) SetWindowTextW(GetDlgItem(dlg, IDC_INSTALL), L("Installieren", "Install"));
    SetWindowTextW(GetDlgItem(dlg, IDC_QUIT), L("Beenden", "Quit"));
    SetWindowTextW(GetDlgItem(dlg, IDC_ROLLBACK), L("Letzte Installation zuruecknehmen", "Roll back last install"));

    SetWindowTextW(GetDlgItem(dlg, IDC_CONFIGURE), L("Vorhandene Einstellungen aendern", "Change existing settings"));
    HWND q = GetDlgItem(dlg, IDC_Q);
    int sel = (int)SendMessageW(q, CB_GETCURSEL, 0, 0);
    SendMessageW(q, CB_RESETCONTENT, 0, 0);
    SendMessageW(q, CB_ADDSTRING, 0, (LPARAM)L("Niedrig", "Low"));
    SendMessageW(q, CB_ADDSTRING, 0, (LPARAM)L("Mittel", "Medium"));
    SendMessageW(q, CB_ADDSTRING, 0, (LPARAM)L("Hoch", "High"));
    if (sel < 0) sel = Q_HIGH;
    SendMessageW(q, CB_SETCURSEL, sel, 0);
}

static void UpdateFov(HWND dlg)
{
    wchar_t res[32] = L"";
    GetDlgItemTextW(dlg, IDC_RES, res, 32);
    SetDlgItemInt(dlg, IDC_FOV, RecommendedFov(res), FALSE);
}

// values of the selected installation -> name / resolution / FOV / quality
static void LoadFromInstall(HWND dlg)
{
    int sel = (int)SendMessageW(GetDlgItem(dlg, IDC_LIST), LB_GETCURSEL, 0, 0);
    if (sel < 0 || sel >= (int)g_found.size()) return;
    std::wstring dir = g_found[sel];
    std::wstring main = FindChild(dir, L"Main");
    std::wstring cfg = main.empty() ? L"" : FindChild(main, L"config.cfg");

    std::wstring name = cfg.empty() ? L"" : ReadCvar(cfg, L"name");
    if (!name.empty() && g_nameAuto) {
        g_settingName = true;
        SetDlgItemTextW(dlg, IDC_NAME, name.c_str());
        g_settingName = false;
        g_nameAuto = false;
    }

    std::wstring w = cfg.empty() ? L"" : ReadCvar(cfg, L"r_customwidth");
    std::wstring h = cfg.empty() ? L"" : ReadCvar(cfg, L"r_customheight");
    if (!w.empty() && !h.empty()) {
        std::wstring res = w + L"x" + h;
        SetDlgItemTextW(dlg, IDC_RES, res.c_str());
    }
    std::wstring fov = cfg.empty() ? L"" : ReadCvar(cfg, L"cg_fov");
    if (!fov.empty()) {
        int v = _wtoi(fov.c_str());
        if (v >= 60 && v <= 130) SetDlgItemInt(dlg, IDC_FOV, v, FALSE);
        else UpdateFov(dlg);
    } else {
        UpdateFov(dlg);
    }
    std::wstring picmip = cfg.empty() ? L"" : ReadCvar(cfg, L"r_picmip");
    if (!picmip.empty()) {
        int v = _wtoi(picmip.c_str());
        SendMessageW(GetDlgItem(dlg, IDC_Q), CB_SETCURSEL, v <= 0 ? Q_HIGH : v == 1 ? Q_MED : Q_LOW, 0);
    }
    std::wstring fs = cfg.empty() ? L"" : ReadCvar(cfg, L"r_fullscreen");
    if (!fs.empty()) CheckDlgButton(dlg, IDC_FULL, _wtoi(fs.c_str()) ? BST_CHECKED : BST_UNCHECKED);

    std::wstring info = dir;
    int games = GamesIn(dir);
    if (games) info += L"   [" + GameNames(games) + L"]";
    if (!(games & UO)) info += L("  -  United Offensive fehlt (wird mitinstalliert)",
                                 "  -  United Offensive missing (will be installed)");
    SetWindowTextW(GetDlgItem(dlg, IDC_INFO), info.c_str());
}

static void PopulateList(HWND dlg, const std::wstring& select)
{
    HWND lb = GetDlgItem(dlg, IDC_LIST);
    SendMessageW(lb, LB_RESETCONTENT, 0, 0);
    int sel = -1;
    for (size_t i = 0; i < g_found.size(); ++i) {
        std::wstring text = g_found[i] + L"   [" + GameNamesShort(GamesIn(g_found[i])) + L"]";
        SendMessageW(lb, LB_ADDSTRING, 0, (LPARAM)text.c_str());
        if (!select.empty() && !_wcsicmp(g_found[i].c_str(), select.c_str())) sel = (int)i;
    }
    if (sel < 0 && !g_found.empty()) sel = 0;
    if (sel >= 0) {
        SendMessageW(lb, LB_SETCURSEL, sel, 0);
        LoadFromInstall(dlg);
    }
}

static void AddResolution(HWND dlg, const std::wstring& res)
{
    HWND cb = GetDlgItem(dlg, IDC_RES);
    for (int i = 0; i < (int)SendMessageW(cb, CB_GETCOUNT, 0, 0); ++i) {
        wchar_t buf[32] = L"";
        SendMessageW(cb, CB_GETLBTEXT, i, (LPARAM)buf);
        if (!_wcsicmp(buf, res.c_str())) { SendMessageW(cb, CB_SETCURSEL, i, 0); return; }
    }
    SendMessageW(cb, CB_ADDSTRING, 0, (LPARAM)res.c_str());
    SendMessageW(cb, CB_SETCURSEL, SendMessageW(cb, CB_GETCOUNT, 0, 0) - 1, 0);
}

static void OnInstall(HWND dlg)
{
    int sel = (int)SendMessageW(GetDlgItem(dlg, IDC_LIST), LB_GETCURSEL, 0, 0);
    if (sel < 0 || sel >= (int)g_found.size()) {
        MessageBoxW(dlg, L("Bitte eine Installation in der Liste auswaehlen.",
                           "Please select an installation in the list."),
                    TITLE, MB_ICONWARNING);
        return;
    }
    wchar_t name[128] = L"";
    GetDlgItemTextW(dlg, IDC_NAME, name, 128);
    std::wstring player = name;
    while (!player.empty() && player.front() == L' ') player.erase(player.begin());
    while (!player.empty() && player.back() == L' ') player.pop_back();
    if (player.empty()) {
        MessageBoxW(dlg, L("Bitte einen Spielernamen eingeben.", "Please enter a player name."),
                    TITLE, MB_ICONWARNING);
        SetFocus(GetDlgItem(dlg, IDC_NAME));
        return;
    }
    wchar_t res[32] = L"";
    GetDlgItemTextW(dlg, IDC_RES, res, 32);
    int w = 0, h = 0;
    if (swscanf(res, L"%dx%d", &w, &h) != 2 || w < 640 || h < 480 || w > 7680 || h > 4320) {
        MessageBoxW(dlg, L("Die Aufloesung muss wie 1920x1080 aussehen.",
                           "The resolution must look like 1920x1080."),
                    TITLE, MB_ICONWARNING);
        SetFocus(GetDlgItem(dlg, IDC_RES));
        return;
    }
    int fov = (int)GetDlgItemInt(dlg, IDC_FOV, nullptr, FALSE);
    if (fov < 60 || fov > 130) {
        MessageBoxW(dlg, L("Der FOV muss zwischen 60 und 130 liegen.", "The FOV must be between 60 and 130."),
                    TITLE, MB_ICONWARNING);
        SetFocus(GetDlgItem(dlg, IDC_FOV));
        return;
    }

    g_rollbackMode=false;
    g_job.dir = g_found[sel];
    g_job.german = g_game == L_DE;
    g_job.name = player;
    g_job.res = res;
    g_job.fullscreen = IsDlgButtonChecked(dlg, IDC_FULL) == BST_CHECKED;
    g_job.fov = fov;
    g_job.quality = (int)SendMessageW(GetDlgItem(dlg, IDC_Q), CB_GETCURSEL, 0, 0);
    g_job.sp = g_job.uf = true;
    g_job.configure = IsDlgButtonChecked(dlg, IDC_CONFIGURE) == BST_CHECKED;
    g_job.map = IsDlgButtonChecked(dlg, IDC_MAP) == BST_CHECKED;
    g_summary.clear();
    g_state = S_RUNNING;
    EnableInputs(dlg, FALSE);
    EnableWindow(GetDlgItem(dlg, IDC_QUIT), FALSE);
    EnableWindow(GetDlgItem(dlg, IDC_INSTALL), FALSE);
    SetWindowTextW(GetDlgItem(dlg, IDC_STATUS), L("Startet...", "Starting..."));
    SetProgress(dlg, -1);
    CloseHandle(CreateThread(nullptr, 0, Worker, nullptr, 0, nullptr));
}

static void OnRollback(HWND dlg) {
    int sel=(int)SendMessageW(GetDlgItem(dlg,IDC_LIST),LB_GETCURSEL,0,0);
    if(sel<0||sel>=(int)g_found.size()){MessageBoxW(dlg,L("Bitte zuerst eine Installation auswaehlen.","Choose an installation first."),TITLE,MB_ICONWARNING);return;}
    if(MessageBoxW(dlg,L("Dateien der letzten abgeschlossenen Installation wiederherstellen?\nAktuelle Einstellungen und Spielstaende werden behalten.\nVeraenderte Laufzeitdateien oder Sicherungen verhindern die Ruecknahme.","Restore files from the last completed installation?\nCurrent settings and saves are kept.\nChanged runtime files or backups prevent rollback."),TITLE,MB_YESNO|MB_ICONQUESTION|MB_DEFBUTTON2)!=IDYES)return;
    g_job.dir=g_found[sel];g_rollbackMode=true;g_state=S_RUNNING;g_summary.clear();EnableInputs(dlg,FALSE);EnableWindow(GetDlgItem(dlg,IDC_QUIT),FALSE);EnableWindow(GetDlgItem(dlg,IDC_INSTALL),FALSE);
    SetWindowTextW(GetDlgItem(dlg,IDC_STATUS),L("Sicherung wird geprueft...","Checking backup..."));SetProgress(dlg,-1);CloseHandle(CreateThread(nullptr,0,Worker,nullptr,0,nullptr));
}

static INT_PTR CALLBACK DlgProc(HWND dlg, UINT msg, WPARAM wParam, LPARAM lParam)
{
    switch (msg) {
    case WM_INITDIALOG: {
        g_dlg = dlg;
        g_state = S_IDLE;
        SetProgress(dlg, -1);

        // language: German Windows or an already German installation -> German
        LANGID ui = GetUserDefaultUILanguage();
        g_ui = (PRIMARYLANGID(ui) == LANG_GERMAN) ? L_DE : L_EN;
        g_game = L_EN;

        Detect(g_found);
        HWND cb = GetDlgItem(dlg, IDC_RES);
        for (const wchar_t* r : {L"1280x720", L"1600x900", L"1920x1080", L"2560x1440", L"3440x1440", L"3840x2160"})
            SendMessageW(cb, CB_ADDSTRING, 0, (LPARAM)r);
        wchar_t desktop[32];
        swprintf(desktop, 32, L"%dx%d", GetSystemMetrics(SM_CXSCREEN), GetSystemMetrics(SM_CYSCREEN));
        AddResolution(dlg, desktop);

        SetDlgItemTextW(dlg, IDC_NAME, L"Soldier");
        CheckDlgButton(dlg, IDC_FULL, BST_CHECKED);
        CheckDlgButton(dlg, IDC_SP, BST_CHECKED);
        CheckDlgButton(dlg, IDC_UF, BST_CHECKED);
        EnableWindow(GetDlgItem(dlg, IDC_SP), FALSE);
        EnableWindow(GetDlgItem(dlg, IDC_UF), FALSE);
        CheckDlgButton(dlg, IDC_DE, g_game == L_DE ? BST_CHECKED : BST_UNCHECKED);
        CheckDlgButton(dlg, IDC_EN, g_game == L_DE ? BST_UNCHECKED : BST_CHECKED);
        SendMessageW(GetDlgItem(dlg, IDC_Q), CB_SETCURSEL, Q_HIGH, 0);

        ApplyLanguage(dlg);
        PopulateList(dlg, L"");
        if (g_found.empty()) {
            SetWindowTextW(GetDlgItem(dlg, IDC_INFO),
                           L("Keine Installation gefunden - bitte \"Anderer Ordner...\" waehlen.",
                             "No installation found - please choose \"Another folder...\"."));
        } else {
            // German pack already there? then German stays selected
            int sel = (int)SendMessageW(GetDlgItem(dlg, IDC_LIST), LB_GETCURSEL, 0, 0);
            if (sel >= 0) {
                std::wstring main = FindChild(g_found[sel], L"Main");
                bool german = !main.empty() && (Exists(main + L"\\.cod-coop-german") ||
                                                !FindChild(main, L"localized_german_pak0.pk3").empty());
                g_game = german ? L_DE : L_EN;
                CheckDlgButton(dlg, IDC_DE, g_game == L_DE ? BST_CHECKED : BST_UNCHECKED);
                CheckDlgButton(dlg, IDC_EN, g_game == L_DE ? BST_UNCHECKED : BST_CHECKED);
            }
        }
        UpdateFov(dlg);
        SetFocus(GetDlgItem(dlg, IDC_INSTALL));
        return FALSE;
    }
    case WM_COMMAND: {
        int id = LOWORD(wParam), code = HIWORD(wParam);
        switch (id) {
        case IDC_LIST:
            if (code == LBN_SELCHANGE) LoadFromInstall(dlg);
            return TRUE;
        case IDC_BROWSE: {
            std::wstring d = PickDir(dlg);
            if (d.empty()) return TRUE;
            if (!GamesIn(d)) {
                MessageBoxW(dlg, L("In diesem Ordner liegt kein CoDSP.exe.\n"
                                   "Bitte den Ordner waehlen, in dem Call of Duty installiert ist.",
                                   "That folder has no CoDSP.exe.\n"
                                   "Choose the folder where Call of Duty is installed."),
                            TITLE, MB_ICONWARNING);
                return TRUE;
            }
            bool known = false;
            for (const std::wstring& x : g_found) if (!_wcsicmp(x.c_str(), d.c_str())) known = true;
            if (!known) g_found.insert(g_found.begin(), d);
            PopulateList(dlg, d);
            return TRUE;
        }
        case IDC_DE:
            if (code == BN_CLICKED) g_game = L_DE;
            return TRUE;
        case IDC_EN:
            if (code == BN_CLICKED) g_game = L_EN;
            return TRUE;
        case IDC_NAME:
            if (code == EN_CHANGE && !g_settingName) g_nameAuto = false;
            return TRUE;
        case IDC_RES:
            if (code == CBN_SELCHANGE) UpdateFov(dlg);
            return TRUE;
        case IDC_INSTALL:
            if (g_state == S_IDLE) OnInstall(dlg);
            else if (g_state == S_DONE && !g_rollbackMode)
                ShellExecuteW(dlg, L"open", g_job.dir.c_str(), nullptr, nullptr, SW_SHOWNORMAL);
            else if (g_state == S_DONE || g_state == S_FAILED) EndDialog(dlg, 0);
            return TRUE;
        case IDC_ROLLBACK:
            if(g_state!=S_RUNNING)OnRollback(dlg);
            return TRUE;
        case IDC_QUIT:
        case IDCANCEL:
            if (g_state == S_RUNNING) return TRUE;  // do not abandon a running install
            EndDialog(dlg, 0);
            return TRUE;
        }
        return FALSE;
    }
    case WM_CLOSE:
        if (g_state == S_RUNNING) return TRUE;
        EndDialog(dlg, 0);
        return TRUE;
    case WM_APP_STATUS: {
        std::wstring* text = (std::wstring*)lParam;
        SetWindowTextW(GetDlgItem(dlg, IDC_STATUS), text->c_str());
        SetProgress(dlg, (int)wParam);
        delete text;
        return TRUE;
    }
    case WM_APP_DONE: {
        std::wstring* text = (std::wstring*)lParam;
        bool ok = wParam != 0;
        g_state = ok ? S_DONE : S_FAILED;
        EnableInputs(dlg, TRUE);
        EnableWindow(GetDlgItem(dlg, IDC_QUIT), TRUE);
        EnableWindow(GetDlgItem(dlg, IDC_INSTALL), TRUE);
        SetProgress(dlg, ok ? 100 : 0);
        SetWindowTextW(GetDlgItem(dlg, IDC_STATUS),
                       ok ? L("Fertig.", "Done.") : L("Fehlgeschlagen.", "Failed."));
        SetWindowTextW(GetDlgItem(dlg, IDC_INSTALL), ok && !g_rollbackMode
                       ? L("Spielordner oeffnen", "Open game folder") : L("Schliessen", "Close"));
        MessageBoxW(dlg, text->c_str(), TITLE, ok ? MB_ICONINFORMATION : MB_ICONERROR);
        delete text;

        return TRUE;
    }
    }
    return FALSE;
}

int WINAPI wWinMain(HINSTANCE, HINSTANCE, LPWSTR, int)
{
    SetProcessDPIAware();
    CoInitializeEx(nullptr, COINIT_APARTMENTTHREADED);
    INITCOMMONCONTROLSEX icc{sizeof icc, ICC_PROGRESS_CLASS | ICC_STANDARD_CLASSES};
    InitCommonControlsEx(&icc);

    // Unattended deployment uses exactly the GUI's worker implementation.
    // No release URL, executable or command is accepted from the network.
    int argc=0; LPWSTR* argv=CommandLineToArgvW(GetCommandLineW(),&argc);
    bool unattended=false,repairRequested=false,configureRequested=false;
    for (int i=1;argv && i<argc;++i) {
        if (!wcscmp(argv[i],L"--yes")) unattended=true;
        else if (!wcscmp(argv[i],L"--rollback")) g_rollbackMode=true;
        else if (!wcscmp(argv[i],L"--game") && i+1<argc) g_job.dir=argv[++i];
        else if (!wcscmp(argv[i],L"--suite-source") && i+1<argc) g_overlayOverride=argv[++i];
        else if (!wcscmp(argv[i],L"--language") && i+1<argc) {
            std::wstring lang=argv[++i];
            if (lang!=L"de" && lang!=L"en") { LocalFree(argv); return 2; }
            g_job.german=lang==L"de";
        } else if (!wcscmp(argv[i],L"--repair")) {repairRequested=true;g_job.configure=false;}
        else if (!wcscmp(argv[i],L"--configure")) {configureRequested=true;g_job.configure=true;}
        else { LocalFree(argv); return 2; }
    }
    if (argv) LocalFree(argv);
    if ((repairRequested&&configureRequested)||(g_rollbackMode&&(repairRequested||configureRequested)))return 2;
    if (unattended) {
        if (g_job.dir.empty() || (g_rollbackMode?!g_overlayOverride.empty():g_overlayOverride.empty())) return 2;
        std::wstring error; bool ok=false;
        try { ok=g_rollbackMode?RollbackLastInstall(g_job.dir,error):RunInstall(error); }
        catch (const std::exception& e) { error=Widen(e.what()); }
        if (!g_rollbackMode) {
            if (!ok) RollbackFiles();
            else {
                g_transactionActive=false;
                try { SaveInstallJournal(g_job.dir); }
                catch (const std::exception& e) { error=Widen(e.what());RollbackFiles();ok=false; }
            }
        }
        auto message=ok?(g_rollbackMode?std::string("CoDCoop: rollback complete; current personal settings and saves retained.\n"):std::string("CoDCoop: installation complete; required suite files verified.\n")):std::string("CoDCoop: ")+suite::Utf8(error)+"\n";
        HANDLE output=GetStdHandle(ok?STD_OUTPUT_HANDLE:STD_ERROR_HANDLE);DWORD written=0;
        if(output&&output!=INVALID_HANDLE_VALUE)WriteFile(output,message.data(),(DWORD)message.size(),&written,nullptr);
        CoUninitialize();
        return ok?0:1;
    }
    if (g_rollbackMode || !g_job.dir.empty() || !g_overlayOverride.empty()) return 2;
    HRSRC r = FindResourceW(nullptr, MAKEINTRESOURCEW(200), MAKEINTRESOURCEW(5));  // RT_DIALOG
    if (!r) {
        MessageBoxW(nullptr, L"Installer resource missing.", TITLE, MB_ICONERROR);
        return 1;
    }
    DialogBoxParamW(GetModuleHandleW(nullptr), MAKEINTRESOURCEW(200), nullptr, DlgProc, 0);
    CoUninitialize();
    return 0;
}
