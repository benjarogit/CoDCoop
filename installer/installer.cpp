// Instalador del coop: copia el mod y, si esta al lado, la carga lista de United Offensive 1.51 (game/).
// Mira que juego hay en la carpeta y copia lo de ese: Call of Duty (CoDSP.exe, y United Offensive si esta CoDUOSP.exe)
// o Call of Duty 2 (CoD2SP_s.exe).
// Uso: "Install CoD Coop.exe" [carpeta...]  (con carpetas no pregunta donde; asi se relanza como administrador)
#define _WIN32_WINNT 0x0601
#include <windows.h>
#include <shlobj.h>
#include <iterator>
#include <string>
#include <vector>

static const wchar_t* TITLE = L"Call of Duty Coop - Setup";
static const DWORD CODSP_SIZE = 1716224;     // CoDSP.exe 1.5: el mod usa direcciones fijas de ese exe
static const DWORD COD2SP_SIZE = 1761280;    // CoD2SP_s.exe 1.3, idem

struct File { int id; const wchar_t* dest; };
static const File COD1_FILES[] = {
    {1, L"ddraw.dll"}, {2, L"codcoop_core.dll"}, {3, L"main\\pakz_coop.pk3"}, {4, L"CoD Coop README.txt"},
    {5, L"steam_api.dll"},
};
static const File UO_FILES[] = {{6, L"uo\\pakz_coop.pk3"}};
static const File COD2_FILES[] = {{1, L"ddraw.dll"}, {7, L"cod2coop.dll"}, {8, L"main\\zz_coop2.iwd"},
                                  {4, L"CoD Coop README.txt"}, {5, L"steam_api.dll"}};

enum { COD1 = 1, UO = 2, COD2 = 4 };

static int Msg(UINT flags, const std::wstring& text) { return MessageBoxW(nullptr, text.c_str(), TITLE, flags); }

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

static int GamesIn(const std::wstring& dir)
{
    bool cod1 = Exists(dir + L"\\CoDSP.exe");  // United Offensive es una expansion: va en la misma carpeta
    return (cod1 ? COD1 : 0) | (cod1 && Exists(dir + L"\\CoDUOSP.exe") ? UO : 0) |
           (Exists(dir + L"\\CoD2SP_s.exe") ? COD2 : 0);
}

static std::wstring GameNames(int games)
{
    std::wstring s;
    if (games & COD1) s += L"Call of Duty";
    if (games & UO) s += L" + United Offensive";
    if (games & COD2) s += std::wstring(s.empty() ? L"" : L" + ") + L"Call of Duty 2";
    return s;
}

static std::wstring RegistryDir(const wchar_t* key)
{
    // el instalador es de 32 bits: esto lee WOW6432Node, donde lo pone el instalador del juego
    wchar_t buf[MAX_PATH] = L"";
    DWORD size = sizeof buf;
    if (RegGetValueW(HKEY_LOCAL_MACHINE, key, L"InstallPath", RRF_RT_REG_SZ, nullptr, buf, &size) != ERROR_SUCCESS)
        return L"";
    std::wstring dir = buf;
    while (!dir.empty() && dir.back() == L'\\') dir.pop_back();
    return dir;
}

static void AddUnique(std::vector<std::wstring>& list, const std::wstring& dir)
{
    if (dir.empty() || !IsDir(dir)) return;
    for (const std::wstring& d : list)
        if (!_wcsicmp(d.c_str(), dir.c_str())) return;
    list.push_back(dir);
}

// Steam: <SteamPath>/steamapps/common/Call of Duty, y las demas bibliotecas de libraryfolders.vdf
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
    HANDLE f = CreateFileW((steam + L"\\steamapps\\libraryfolders.vdf").c_str(), GENERIC_READ, FILE_SHARE_READ,
                           nullptr, OPEN_EXISTING, 0, nullptr);
    if (f != INVALID_HANDLE_VALUE) {
        DWORD n = GetFileSize(f, nullptr);
        std::string data(n, '\0');
        DWORD got = 0;
        ReadFile(f, &data[0], n, &got, nullptr);
        CloseHandle(f);
        // "path"		"D:\\SteamLibrary"
        for (size_t i = 0; (i = data.find("\"path\"", i)) != std::string::npos; ) {
            size_t a = data.find('"', i + 6);
            size_t b = a == std::string::npos ? a : data.find('"', a + 1);
            if (b == std::string::npos) break;
            std::string p = data.substr(a + 1, b - a - 1);
            std::wstring w;
            int len = MultiByteToWideChar(CP_UTF8, 0, p.c_str(), (int)p.size(), nullptr, 0);
            w.resize(len);
            MultiByteToWideChar(CP_UTF8, 0, p.c_str(), (int)p.size(), &w[0], len);
            libs.push_back(w);
            i = b + 1;
        }
    }
    for (const std::wstring& lib : libs) {
        AddUnique(list, lib + L"\\steamapps\\common\\Call of Duty");
        AddUnique(list, lib + L"\\steamapps\\common\\Call of Duty 2");
    }
}

// AnkerGames (y lanzadores parecidos): su biblioteca esta en %APPDATA%\\net.ankergames.launcher\\library.json
static void AddAnker(std::vector<std::wstring>& list)
{
    wchar_t appdata[MAX_PATH] = L"";
    if (!GetEnvironmentVariableW(L"APPDATA", appdata, MAX_PATH)) return;
    std::wstring json = std::wstring(appdata) + L"\\net.ankergames.launcher\\library.json";
    HANDLE f = CreateFileW(json.c_str(), GENERIC_READ, FILE_SHARE_READ, nullptr, OPEN_EXISTING, 0, nullptr);
    if (f == INVALID_HANDLE_VALUE) return;
    DWORD n = GetFileSize(f, nullptr);
    std::string data(n, '\0');
    DWORD got = 0;
    ReadFile(f, &data[0], n, &got, nullptr);
    CloseHandle(f);
    // "root": "D:\\\\Games\\\\AnkerGames\\\\Games\\\\Call of Duty (2003)-3278\\\\Call of Duty"
    for (size_t i = 0; (i = data.find("\"root\"", i)) != std::string::npos; ) {
        size_t a = data.find('"', i + 6);
        size_t b = a == std::string::npos ? a : data.find('"', a + 1);
        if (b == std::string::npos) break;
        std::string p = data.substr(a + 1, b - a - 1);
        std::string un;
        for (size_t k = 0; k < p.size(); ++k) {
            if (p[k] == '\\' && k + 1 < p.size() && p[k + 1] == '\\') { un += '\\'; ++k; }
            else un += p[k];
        }
        std::wstring w;
        int len = MultiByteToWideChar(CP_UTF8, 0, un.c_str(), (int)un.size(), nullptr, 0);
        w.resize(len);
        MultiByteToWideChar(CP_UTF8, 0, un.c_str(), (int)un.size(), &w[0], len);
        AddUnique(list, w);
        i = b + 1;
    }
}

static std::wstring PickDir()
{
    BROWSEINFOW bi{};
    bi.lpszTitle = L"Choose the game folder (the one with CoDSP.exe or CoD2SP_s.exe):";
    bi.ulFlags = BIF_RETURNONLYFSDIRS | BIF_NEWDIALOGSTYLE;
    PIDLIST_ABSOLUTE pidl = SHBrowseForFolderW(&bi);
    if (!pidl) return L"";
    wchar_t buf[MAX_PATH];
    bool ok = SHGetPathFromIDListW(pidl, buf);
    CoTaskMemFree(pidl);
    return ok ? buf : L"";
}

static std::string ReadAll(const std::wstring& path)
{
    std::string data;
    HANDLE f = CreateFileW(path.c_str(), GENERIC_READ, FILE_SHARE_READ, nullptr, OPEN_EXISTING, 0, nullptr);
    if (f == INVALID_HANDLE_VALUE) return data;
    data.resize(GetFileSize(f, nullptr));
    DWORD got = 0;
    ReadFile(f, &data[0], (DWORD)data.size(), &got, nullptr);
    CloseHandle(f);
    return data;
}

static std::string Resource(int id)
{
    HRSRC r = FindResourceW(nullptr, MAKEINTRESOURCEW(id), MAKEINTRESOURCEW(10));  // RT_RCDATA
    HGLOBAL g = r ? LoadResource(nullptr, r) : nullptr;
    return g ? std::string((const char*)LockResource(g), SizeofResource(nullptr, r)) : std::string();
}

// false con GetLastError() del archivo
static bool WriteResource(int id, const std::wstring& path)
{
    HRSRC r = FindResourceW(nullptr, MAKEINTRESOURCEW(id), MAKEINTRESOURCEW(10));  // RT_RCDATA
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

static bool WrongSize(const std::wstring& exe, DWORD size)
{
    WIN32_FILE_ATTRIBUTE_DATA a;
    return GetFileAttributesExW(exe.c_str(), GetFileExInfoStandard, &a) && a.nFileSizeLow != size;
}

static DWORD FileSize(const std::wstring& path)
{
    WIN32_FILE_ATTRIBUTE_DATA a;
    return GetFileAttributesExW(path.c_str(), GetFileExInfoStandard, &a) ? a.nFileSizeLow : 0;
}

// La carga lista (United Offensive 1.51 + mod) esta en game\ junto al instalador, o un nivel arriba
// (por ejemplo si el .exe se quedo dentro de la carpeta "Call of Duty - UO Coop Ready").
static std::wstring PayloadRoot()
{
    wchar_t self[MAX_PATH];
    GetModuleFileNameW(nullptr, self, MAX_PATH);
    std::wstring dir = DirName(self);
    for (const std::wstring& cand : {dir + L"\\game", dir + L"\\..\\game"}) {
        if (Exists(cand + L"\\CoDUOSP.exe") || Exists(cand + L"\\CoDSP.exe")) return cand;
    }
    return L"";
}

// .bak, .bak.1, .bak.2... sin pisar una copia anterior
static void Backup(const std::wstring& path)
{
    std::wstring bak = path + L".bak";
    for (int i = 1; Exists(bak); ++i) bak = path + L".bak." + std::to_wstring(i);
    MoveFileW(path.c_str(), bak.c_str());
}

struct CopyStats { int copied = 0, kept = 0, failed = 0; std::wstring error; };

static void CopyTree(const std::wstring& src, const std::wstring& dst, CopyStats& st)
{
    WIN32_FIND_DATAW fd;
    HANDLE h = FindFirstFileW((src + L"\\*").c_str(), &fd);
    if (h == INVALID_HANDLE_VALUE) return;
    do {
        std::wstring name = fd.cFileName;
        if (name == L"." || name == L"..") continue;
        std::wstring s = src + L"\\" + name, d = dst + L"\\" + name;
        if (fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) {
            CreateDirectoryW(d.c_str(), nullptr);
            CopyTree(s, d, st);
            continue;
        }
        if (Exists(d) && FileSize(d) == fd.nFileSizeLow) { ++st.kept; continue; }
        if (Exists(d)) Backup(d);
        if (!CopyFileW(s.c_str(), d.c_str(), FALSE)) { ++st.failed; if (st.error.empty()) st.error = d; continue; }
        ++st.copied;
    } while (FindNextFileW(h, &fd));
    FindClose(h);
}

enum Result { DONE, FAILED, RELAUNCHED };

// copia los archivos; sin permiso en una carpeta protegida (Archivos de programa) se relanza como administrador con
// todas las carpetas
static Result Install(const std::wstring& dir, int games, const std::vector<std::wstring>& all, CopyStats& st)
{
    // un ddraw.dll o steam_api.dll que no es el nuestro (otro mod, arreglo de video) se guarda como .bak
    std::wstring ddraw = dir + L"\\ddraw.dll", steamDll = dir + L"\\steam_api.dll";
    if (Exists(ddraw) && !Exists(ddraw + L".bak") && ReadAll(ddraw).find("codcoop_core.dll") == std::string::npos)
        MoveFileW(ddraw.c_str(), (ddraw + L".bak").c_str());
    if ((games & (COD1 | COD2)) && Exists(steamDll) && !Exists(steamDll + L".bak") && ReadAll(steamDll) != Resource(5))
        MoveFileW(steamDll.c_str(), (steamDll + L".bak").c_str());

    std::vector<File> files;
    if (games & COD1) files.insert(files.end(), std::begin(COD1_FILES), std::end(COD1_FILES));
    if (games & UO) files.insert(files.end(), std::begin(UO_FILES), std::end(UO_FILES));
    if (games & COD2) files.insert(files.end(), std::begin(COD2_FILES), std::end(COD2_FILES));
    if (games & (COD1 | COD2)) CreateDirectoryW((dir + L"\\main").c_str(), nullptr);
    if (games & UO) CreateDirectoryW((dir + L"\\uo").c_str(), nullptr);

    // la carga lista: United Offensive 1.51 y todos los paks, solo si el .exe viaja al lado
    std::wstring payload = PayloadRoot();
    if (!payload.empty() && (games & COD1)) {
        CopyStats p;
        CopyTree(payload, dir, p);
        st.copied += p.copied;
        st.kept += p.kept;
        st.failed += p.failed;
        if (st.error.empty()) st.error = p.error;
    }

    for (const File& f : files) {
        if (WriteResource(f.id, dir + L"\\" + f.dest)) continue;
        if (GetLastError() == ERROR_ACCESS_DENIED && !IsUserAnAdmin()) {
            wchar_t self[MAX_PATH];
            GetModuleFileNameW(nullptr, self, MAX_PATH);
            std::wstring args;
            for (const std::wstring& d : all) args += L"\"" + d + L"\" ";
            if ((INT_PTR)ShellExecuteW(nullptr, L"runas", self, args.c_str(), nullptr, SW_SHOWNORMAL) > 32) return RELAUNCHED;
        }
        ++st.failed;
        if (st.error.empty()) st.error = dir + L"\\" + f.dest;
    }
    return st.failed ? FAILED : DONE;
}

int WINAPI wWinMain(HINSTANCE, HINSTANCE, LPWSTR, int)
{
    CoInitializeEx(nullptr, COINIT_APARTMENTTHREADED);
    int argc = 0;
    wchar_t** argv = CommandLineToArgvW(GetCommandLineW(), &argc);
    std::vector<std::wstring> dirs;
    for (int i = 1; i < argc; ++i) dirs.push_back(argv[i]);

    if (dirs.empty()) {
        // 1) donde lo instalo su instalador (Call of Duty y Call of Duty 2 pueden estar los dos)
        std::vector<std::wstring> found;
        for (const wchar_t* key : {L"SOFTWARE\\Activision\\Call of Duty", L"SOFTWARE\\Activision\\Call of Duty 2"})
            AddUnique(found, RegistryDir(key));
        // 2) Steam (todas las bibliotecas) y AnkerGames
        AddSteam(found);
        AddAnker(found);
        // 3) una instalacion portable junto al instalador o en la carpeta que lo contiene
        wchar_t self[MAX_PATH];
        GetModuleFileNameW(nullptr, self, MAX_PATH);
        std::wstring here = DirName(self);
        AddUnique(found, here);
        AddUnique(found, DirName(here));

        // solo las carpetas que de verdad tienen el juego
        std::vector<std::wstring> games;
        for (const std::wstring& d : found)
            if (GamesIn(d)) games.push_back(d);

        if (games.size() == 1) {
            if (Msg(MB_YESNO | MB_ICONQUESTION, L"Co-op will be installed in:\n\n" + games[0] + L"\n  (" +
                                                 GameNames(GamesIn(games[0])) +
                                                 L")\n\nYes: install there\nNo: choose another folder") == IDYES)
                dirs.push_back(games[0]);
        } else if (games.size() > 1) {
            // Steam y AnkerGames (o una copia portable): preguntar cual
            for (const std::wstring& d : games) {
                int r = Msg(MB_YESNOCANCEL | MB_ICONQUESTION,
                            L"Co-op will be installed in:\n\n" + d + L"\n  (" + GameNames(GamesIn(d)) +
                            L")\n\nYes: install here\nNo: next one\nCancel: choose another folder");
                if (r == IDYES) { dirs.push_back(d); break; }
                if (r == IDCANCEL) break;
            }
        }
        while (dirs.empty()) {
            std::wstring d = PickDir();
            if (d.empty()) return 0;
            if (!GamesIn(d)) {
                Msg(MB_ICONWARNING, L"That folder has no CoDSP.exe or CoD2SP_s.exe.\n"
                                    L"Choose the folder where Call of Duty or Call of Duty 2 is installed.");
                continue;
            }
            dirs.push_back(d);
        }
    }
    for (std::wstring& d : dirs)
        while (!d.empty() && d.back() == L'\\') d.pop_back();  // "C:\" -> "C:" (va entre comillas al relanzar)

    // CoD 1.5 es obligatorio: el mod usa direcciones fijas de ese exe. Nada se escribe si no esta.
    for (const std::wstring& dir : dirs) {
        if (!(GamesIn(dir) & COD1) || !WrongSize(dir + L"\\CoDSP.exe", CODSP_SIZE)) continue;
        Msg(MB_ICONERROR,
            L"Call of Duty 1.5 is required and was not found.\n\n"
            L"  folder:    " + dir + L"\n"
            L"  CoDSP.exe: " + std::to_wstring(FileSize(dir + L"\\CoDSP.exe")) + L" bytes\n"
            L"  expected:  " + std::to_wstring(CODSP_SIZE) + L" bytes (version 1.5)\n\n"
            L"The co-op uses fixed addresses inside the 1.5 exe, so another version does not work.\n"
            L"Nothing was written.\n\n"
            L"How to get 1.5:\n"
            L"  * Steam: right-click Call of Duty -> Properties -> Installed Files ->\n"
            L"    \"Verify integrity of game files\".\n"
            L"  * Retail/GOG: install the official Call of Duty 1.5 patch, then run this installer again.\n"
            L"  * Or copy CoDSP.exe (1,716,224 bytes) from a PC where 1.5 already runs.");
        return 2;
    }

    int all = 0;
    CopyStats total;
    for (const std::wstring& dir : dirs) {
        int games = GamesIn(dir);
        if (!games) {
            Msg(MB_ICONERROR, L"No Call of Duty or Call of Duty 2 found in\n" + dir);
            return 1;
        }
        if ((games & COD2) && WrongSize(dir + L"\\CoD2SP_s.exe", COD2SP_SIZE) &&
            Msg(MB_YESNO | MB_ICONWARNING, L"Your CoD2SP_s.exe is not version 1.3, the one co-op needs: it may not work."
                                           L"\n\nInstall anyway?") != IDYES)
            return 0;

        std::wstring payload = PayloadRoot();
        if (!payload.empty() && (games & COD1) &&
            Msg(MB_OKCANCEL | MB_ICONINFORMATION,
                L"United Offensive 1.51 (about 1 GB) will now be copied into:\n\n" + dir +
                L"\n\nExisting files are kept as .bak. This can take a few minutes.") != IDOK)
            return 0;

        CopyStats st;
        Result r = Install(dir, games, dirs, st);
        if (r == RELAUNCHED) return 0;
        total.copied += st.copied;
        total.kept += st.kept;
        total.failed += st.failed;
        if (total.error.empty()) total.error = st.error;
        if (r == FAILED) {
            Msg(MB_ICONERROR, L"Could not write:\n" + total.error +
                              L"\n\nIf the game is running, close it and try again.");
            return 1;
        }
        all |= games;
    }

    std::wstring done = L"Done, co-op is installed.\n";
    if (total.copied || total.kept)
        done += L"\nCopied: " + std::to_wstring(total.copied) + L" files, already up to date: " +
                std::to_wstring(total.kept) + L".";
    if (all & COD1)
        done += std::wstring(L"\n\nCall of Duty: start it as usual, the main menu has a \"Co-op\" button.") +
                (all & UO ? L" United Offensive has it too (start CoDUOSP.exe)." : L"");
    if (all & COD2)
        done += L"\nCall of Duty 2: start it as usual, the main menu has a \"Co-op\" button.";
    Msg(MB_ICONINFORMATION, done + L"\n\nInstructions are in \"CoD Coop README.txt\", in the game folder.");

    // Steam invites ("Join <name>" in the Co-op menu) need Valve's free test app Spacewar (AppID 480) once per PC.
    if ((all & (COD1 | COD2)) &&
        Msg(MB_YESNO | MB_ICONQUESTION,
            L"Steam invites (\"Join <name>\" in the Co-op menu) need Valve's free test app\n"
            L"Spacewar (AppID 480) installed once on this PC, with Steam running.\n\n"
            L"Open Steam now to install it? (Skip this if it is already installed.)") == IDYES)
        ShellExecuteW(nullptr, L"open", L"steam://install/480", nullptr, nullptr, SW_SHOWNORMAL);
    return 0;
}
