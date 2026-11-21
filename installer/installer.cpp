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
#define _WIN32_WINNT 0x0601
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <commctrl.h>
#include <shlobj.h>
#include <shellapi.h>
#include <ole2.h>
#include <shldisp.h>
#include <urlmon.h>
#include <string>
#include <vector>
#include <thread>
#include <atomic>
#include <cstdio>
#include <cmath>
#include <cwctype>

static const wchar_t* TITLE = L"Call of Duty Coop - Setup";
static const DWORD CODSP_SIZE = 1716224;   // CoDSP.exe 1.5: the mod uses fixed addresses of that exe
static const DWORD COD2SP_SIZE = 1761280;  // CoD2SP_s.exe 1.3, same

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
    IDC_PROGRESS, IDC_STATUS, IDC_INSTALL, IDC_QUIT
};

enum { L_DE = 0, L_EN = 1 };
enum { Q_LOW = 0, Q_MED, Q_HIGH };
enum { S_IDLE = 0, S_RUNNING, S_DONE, S_FAILED };
enum { COD1 = 1, UO = 2, COD2 = 4 };

#define WM_APP_STATUS (WM_APP + 1)  // wParam = percent (-1 = marquee), lParam = new wstring
#define WM_APP_DONE   (WM_APP + 2)  // wParam = 1 ok / 0 failed, lParam = new wstring (message)

static int g_ui = L_DE;       // language of this window (system language)
static int g_game = L_DE;     // language the game is installed in (radio buttons)
static int g_state = S_IDLE;
static HWND g_dlg = nullptr;

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
    return (cod1 ? COD1 : 0) | (cod1 && Exists(dir + L"\\CoDUOSP.exe") ? UO : 0) |
           (Exists(dir + L"\\CoD2SP_s.exe") ? COD2 : 0);
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
    bi.lpszTitle = L"Choose the game folder (the one with CoDSP.exe or CoD2SP_s.exe):";
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

static bool Download(const std::wstring& url, const std::wstring& path, const std::wstring& label)
{
    DeleteFileW(path.c_str());
    DownloadCB cb;
    cb.label = label;
    HRESULT hr = URLDownloadToFileW(nullptr, url.c_str(), path.c_str(), 0, &cb);
    if (FAILED(hr) || !Exists(path)) {
        DeleteFileW(path.c_str());
        return false;
    }
    return true;
}

// ---------------------------------------------------------------- unzip

// Windows 10/11 ships tar.exe (bsdtar), which also opens .zip
static bool ExtractZip(const std::wstring& zip, const std::wstring& dir, const std::wstring& label)
{
    Say(label, -1);
    CreateDirectoryW(dir.c_str(), nullptr);
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
            CreateDirectoryW(d.c_str(), nullptr);
            CopyTree(s, d, st, total, done);
            continue;
        }
        if (Exists(d) && FileSize(d) == fd.nFileSizeLow) {
            ++st.kept;
        } else {
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
        if (!Download(READY_URL, zip, L("Lade Call of Duty - UO Coop Ready (~1 GB)...",
                                        "Downloading Call of Duty - UO Coop Ready (~1 GB)..."))) {
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
    std::wstring src = FindLocalDir({L"german", L"CoD-UO-German-Language"});
    if (!src.empty()) return src;
    std::wstring zip = FindLocalFile({L"CoD-UO-German-Language.zip"});
    if (zip.empty()) {
        zip = TempPath(L"CoD-UO-German-Language.zip");
        if (!Download(GERMAN_URL, zip, L("Lade deutsches Sprachpaket (~630 MB)...",
                                         "Downloading the German language pack (~630 MB)..."))) {
            err = L("Das deutsche Sprachpaket konnte nicht geladen werden.",
                    "The German language pack could not be downloaded.");
            return L"";
        }
    }
    std::wstring tmp = TempPath(L"cod-german");
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
    if (!main.empty() && Exists(main + L"\\.cod-coop-german")) return true;

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
                MoveFileW((dst + L"\\" + n).c_str(), (bak + L"\\" + n).c_str());
            } else {
                DeleteFileW((dst + L"\\" + n).c_str());
            }
        }
        for (const std::wstring& n : ListDir(from)) {
            std::wstring low = n;
            for (wchar_t& c : low) c = (wchar_t)towlower(c);
            if (low.rfind(L"localized_", 0) != 0 || low.size() < 4 || low.substr(low.size() - 4) != L".pk3") continue;
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

// ---------------------------------------------------------------- extras

static void WriteLaunchers(const std::wstring& dir)
{
    const wchar_t* mods[][2] = {{L"sp_improved", L"Start-SP-Improved.bat"},
                                {L"UnitedFronts", L"Start-United-Fronts.bat"}};
    for (auto& m : mods) {
        if (FindChild(dir, m[0]).empty()) continue;
        std::string text = "@echo off\r\ncd /d \"%~dp0\"\r\nstart \"\" CoDUOSP.exe +set fs_game ";
        text += Narrow(m[0]);
        text += " +set com_introplayed 1\r\n";
        WriteAll(dir + L"\\" + m[1], text);
    }
}

static bool InstallExtras(const std::wstring& dir, bool sp, bool uf, bool map, std::wstring& err)
{
    std::wstring src = FindLocalDir({L"extras", L"CoD-SP-Extras"});
    if (src.empty()) {
        std::wstring zip = FindLocalFile({L"CoD-SP-Extras.zip"});
        if (zip.empty()) {
            zip = TempPath(L"CoD-SP-Extras.zip");
            if (!Download(EXTRAS_URL, zip, L("Lade Zusatzinhalte (~880 MB)...",
                                             "Downloading the extras (~880 MB)..."))) {
                err = L("Die Zusatzinhalte konnten nicht geladen werden.",
                        "The extras could not be downloaded.");
                return false;
            }
        }
        std::wstring tmp = TempPath(L"cod-extras");
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
    std::wstring name;
    std::wstring res;
    bool fullscreen = true;
    int fov = 80;
    int quality = Q_HIGH;
    bool sp = false, uf = false, map = false;
};
static Job g_job;
static std::wstring g_summary;

static void Line(const std::wstring& text) { g_summary += text + L"\r\n"; }

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
    std::wstring payload;
    if (cod1) {
        payload = PreparePayload(err);
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
            WriteResource(ids[i], path);
        }
        CreateDirectoryW((dir + L"\\uo").c_str(), nullptr);
        WriteResource(6, dir + L"\\uo\\pakz_coop.pk3");

        // German after the game files: the package ships English paks
        if (g_job.german) {
            if (!InstallGerman(dir, err)) return false;
            Line(L("Deutsches Sprachpaket installiert (Texte und Stimmen).",
                   "German language pack installed (texts and voices)."));
        }

        Say(L("Einstellungen werden geschrieben...", "Writing the settings..."), -1);
        WriteSettings(dir, g_job.name, g_job.res, g_job.fullscreen, g_job.fov, g_job.quality);
        Line(L("Einstellungen: ", "Settings: ") + g_job.res + L", " +
             (g_job.fullscreen ? L("Vollbild", "fullscreen") : L("Fenster", "window")) +
             L", FOV " + std::to_wstring(g_job.fov) + L", " +
             (g_job.quality == Q_LOW ? L("niedrig", "low")
                                     : g_job.quality == Q_MED ? L("mittel", "medium") : L("hoch", "high")) +
             L", Name \"" + g_job.name + L"\"");

        if (g_job.sp || g_job.uf || g_job.map) {
            if (!InstallExtras(dir, g_job.sp, g_job.uf, g_job.map, err)) return false;
            std::wstring what;
            if (g_job.sp) what += L"Singleplayer Improved";
            if (g_job.uf) what += std::wstring(what.empty() ? L"" : L", ") + L"United Fronts";
            if (g_job.map) what += std::wstring(what.empty() ? L"" : L", ") + L"UO Map Pack";
            Line(L("Zusatzinhalte installiert: ", "Extras installed: ") + what);
        }

        // the improper-quit marker makes the game ask "did your computer change?"
        DeleteFileW((dir + L"\\__CoDSP").c_str());
        DeleteFileW((dir + L"\\__CoDUOSP").c_str());

        Line(L("\r\nStart: CoDSP.exe (Menue \"Co-op\"), United Offensive: CoDUOSP.exe.",
               "\r\nStart: CoDSP.exe (menu \"Co-op\"), United Offensive: CoDUOSP.exe."));
        if (g_job.sp || g_job.uf)
            Line(L("Einzelspieler-Mods: Start-SP-Improved.bat / Start-United-Fronts.bat.",
                   "Singleplayer mods: Start-SP-Improved.bat / Start-United-Fronts.bat."));
        Line(L("\r\nIm Spiel: Co-op -> Host game -> Back -> New Game.\r\n"
               "Freunde: gleiche Version, dann Host IP -> Join oder Steam-Einladung.",
               "\r\nIn game: Co-op -> Host game -> Back -> New Game.\r\n"
               "Friends: same version, then Host IP -> Join or a Steam invite."));
    }

    if (games & COD2) {
        if (WrongSize(dir + L"\\CoD2SP_s.exe", COD2SP_SIZE)) {
            Line(L("Hinweis: CoD2SP_s.exe ist nicht 1.3 - der Co-op braucht 1.3.",
                   "Note: CoD2SP_s.exe is not 1.3 - the co-op needs 1.3."));
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
    return true;
}

static DWORD WINAPI Worker(LPVOID)
{
    std::wstring err;
    bool ok = RunInstall(err);
    std::wstring* msg = new std::wstring(ok ? g_summary : err);
    PostMessageW(g_dlg, WM_APP_DONE, ok ? 1 : 0, (LPARAM)msg);
    return 0;
}

// ---------------------------------------------------------------- UI

static std::vector<std::wstring> g_found;
static bool g_nameAuto = true;
static bool g_settingName = false;

static void EnableInputs(HWND dlg, BOOL on)
{
    for (int id : {IDC_LIST, IDC_BROWSE, IDC_DE, IDC_EN, IDC_NAME, IDC_RES, IDC_FULL,
                   IDC_FOV, IDC_Q, IDC_SP, IDC_UF, IDC_MAP})
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
    SetWindowTextW(GetDlgItem(dlg, IDC_ST_EXTRAS), L("Zusatzinhalte (optional)", "Extras (optional)"));
    SetWindowTextW(GetDlgItem(dlg, IDC_SP), L("Singleplayer Improved", "Singleplayer Improved"));
    SetWindowTextW(GetDlgItem(dlg, IDC_UF), L("United Fronts", "United Fronts"));
    SetWindowTextW(GetDlgItem(dlg, IDC_MAP), L("UO Map Pack", "UO map pack"));
    SetWindowTextW(GetDlgItem(dlg, IDC_EXNOTE),
                   L("Zusammen ~880 MB, wird nur bei Auswahl geladen.\r\n"
                     "Start ueber Start-SP-Improved.bat / Start-United-Fronts.bat.",
                     "About 880 MB together, downloaded only if selected.\r\n"
                     "Start with Start-SP-Improved.bat / Start-United-Fronts.bat."));
    if (g_state == S_IDLE) SetWindowTextW(GetDlgItem(dlg, IDC_INSTALL), L("Installieren", "Install"));
    SetWindowTextW(GetDlgItem(dlg, IDC_QUIT), L("Beenden", "Quit"));

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

    g_job.dir = g_found[sel];
    g_job.german = g_game == L_DE;
    g_job.name = player;
    g_job.res = res;
    g_job.fullscreen = IsDlgButtonChecked(dlg, IDC_FULL) == BST_CHECKED;
    g_job.fov = fov;
    g_job.quality = (int)SendMessageW(GetDlgItem(dlg, IDC_Q), CB_GETCURSEL, 0, 0);
    g_job.sp = IsDlgButtonChecked(dlg, IDC_SP) == BST_CHECKED;
    g_job.uf = IsDlgButtonChecked(dlg, IDC_UF) == BST_CHECKED;
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
        g_game = g_ui;

        Detect(g_found);
        HWND cb = GetDlgItem(dlg, IDC_RES);
        for (const wchar_t* r : {L"1280x720", L"1600x900", L"1920x1080", L"2560x1440", L"3440x1440", L"3840x2160"})
            SendMessageW(cb, CB_ADDSTRING, 0, (LPARAM)r);
        wchar_t desktop[32];
        swprintf(desktop, 32, L"%dx%d", GetSystemMetrics(SM_CXSCREEN), GetSystemMetrics(SM_CYSCREEN));
        AddResolution(dlg, desktop);

        SetDlgItemTextW(dlg, IDC_NAME, L"Soldier");
        CheckDlgButton(dlg, IDC_FULL, BST_CHECKED);
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
                MessageBoxW(dlg, L("In diesem Ordner liegt kein CoDSP.exe oder CoD2SP_s.exe.\n"
                                   "Bitte den Ordner waehlen, in dem Call of Duty installiert ist.",
                                   "That folder has no CoDSP.exe or CoD2SP_s.exe.\n"
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
            else if (g_state == S_DONE || g_state == S_FAILED) EndDialog(dlg, 0);
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
        SetProgress(dlg, 100);
        SetWindowTextW(GetDlgItem(dlg, IDC_STATUS),
                       ok ? L("Fertig.", "Done.") : L("Fehlgeschlagen.", "Failed."));
        SetWindowTextW(GetDlgItem(dlg, IDC_INSTALL), L("Schliessen", "Close"));
        MessageBoxW(dlg, text->c_str(), TITLE, ok ? MB_ICONINFORMATION : MB_ICONERROR);
        delete text;

        // Steam invites need Valve's free test app Spacewar (AppID 480), once per PC
        if (ok && MessageBoxW(dlg,
                              L("Steam-Einladungen (\"Join <Name>\" im Co-op-Menue) brauchen einmalig\n"
                                "Valves kostenlose Test-App Spacewar (AppID 480), mit laufendem Steam.\n\n"
                                "Steam jetzt oeffnen, um Spacewar zu installieren?",
                                "Steam invites (\"Join <name>\" in the Co-op menu) need Valve's free\n"
                                "test app Spacewar (AppID 480) once, with Steam running.\n\n"
                                "Open Steam now to install it?"),
                              TITLE, MB_YESNO | MB_ICONQUESTION) == IDYES)
            ShellExecuteW(nullptr, L"open", L"steam://install/480", nullptr, nullptr, SW_SHOWNORMAL);
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

    HRSRC r = FindResourceW(nullptr, MAKEINTRESOURCEW(200), MAKEINTRESOURCEW(5));  // RT_DIALOG
    if (!r) {
        MessageBoxW(nullptr, L"Installer resource missing.", TITLE, MB_ICONERROR);
        return 1;
    }
    DialogBoxParamW(GetModuleHandleW(nullptr), MAKEINTRESOURCEW(200), nullptr, DlgProc, 0);
    CoUninitialize();
    return 0;
}
