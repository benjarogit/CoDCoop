#pragma once
#include <windows.h>
#include <wincrypt.h>
#include <cstdio>
#include <cstring>
#include <string>
#include "suite_protocol.h"

namespace suite {
inline std::string GameDir()
{
    char path[MAX_PATH];
    GetModuleFileNameA(nullptr, path, sizeof path);
    char* slash = strrchr(path, '\\');
    if (slash) slash[1] = 0;
    return path;
}
inline bool Sha256(const void* data, DWORD size, uint8_t out[32])
{
    HCRYPTPROV provider = 0;
    HCRYPTHASH hash = 0;
    bool ok = CryptAcquireContextA(&provider, nullptr, nullptr, PROV_RSA_AES, CRYPT_VERIFYCONTEXT) &&
              CryptCreateHash(provider, CALG_SHA_256, 0, 0, &hash) && CryptHashData(hash, (const BYTE*)data, size, 0);
    DWORD n = 32;
    if (ok) ok = CryptGetHashParam(hash, HP_HASHVAL, out, &n, 0) != FALSE;
    if (hash) CryptDestroyHash(hash);
    if (provider) CryptReleaseContext(provider, 0);
    return ok;
}
inline bool FileHash(const std::string& path, char out[65])
{
    FILE* f = fopen(path.c_str(), "rb");
    if (!f) return false;
    HCRYPTPROV provider = 0;
    HCRYPTHASH hash = 0;
    bool ok = CryptAcquireContextA(&provider, nullptr, nullptr, PROV_RSA_AES, CRYPT_VERIFYCONTEXT) &&
              CryptCreateHash(provider, CALG_SHA_256, 0, 0, &hash);
    BYTE buffer[65536], bytes[32];
    size_t n;
    while (ok && (n = fread(buffer, 1, sizeof buffer, f))) ok = CryptHashData(hash, buffer, (DWORD)n, 0) != FALSE;
    ok = ok && !ferror(f);
    DWORD length = sizeof bytes;
    if (ok) ok = CryptGetHashParam(hash, HP_HASHVAL, bytes, &length, 0) != FALSE;
    if (ok) for (int i = 0; i < 32; ++i) snprintf(out + i * 2, 3, "%02x", bytes[i]);
    if (hash) CryptDestroyHash(hash);
    if (provider) CryptReleaseContext(provider, 0);
    fclose(f);
    return ok;
}
inline bool Unhex(const char* s, uint8_t out[32])
{
    if (strlen(s) != 64) return false;
    for (int i = 0; i < 32; ++i) {
        int value = 0;
        for (int k = 0; k < 2; ++k) {
            char c = s[i * 2 + k];
            int d = c >= '0' && c <= '9' ? c - '0' : c >= 'a' && c <= 'f' ? c - 'a' + 10 : -1;
            if (d < 0) return false;
            value = value * 16 + d;
        }
        out[i] = (uint8_t)value;
    }
    return true;
}
inline bool IsQA()
{
    char flag[8] = {};
    return GetEnvironmentVariableA("CODCOOP_QA", flag, sizeof flag) == 1 && flag[0] == '1';
}
inline bool PreparedQA()
{
    char flag[8] = {};
    return IsQA() && GetEnvironmentVariableA("CODCOOP_QA_PROFILE", flag, sizeof flag) == 1 && flag[0] == '1';
}
inline bool LoadIdentity(bool uo, const char* fsGame, Identity& id, std::string& error)
{
    id = Identity{};
    id.protocol = PROTOCOL;
    id.engine = uo ? 2 : 1;
    const char* variant = !uo ? "cod1" : !*fsGame ? "uo" : !_stricmp(fsGame, "sp_improved") ? "sp_improved" : !_stricmp(fsGame, "UnitedFronts") ? "united_fronts" : "";
    if (!*variant || (!uo && *fsGame)) { error = "Unknown campaign variant; start a registered variant with CoDCoop Launcher."; return false; }
    id.variant = !strcmp(variant, "cod1") ? 1 : !strcmp(variant, "uo") ? 2 : !strcmp(variant, "sp_improved") ? 3 : 4;
    std::string dir = GameDir();
    char core[65] = {}, loader[65] = {};
    if (!FileHash(dir + "codcoop_core.dll", core) || !FileHash(dir + "ddraw.dll", loader)) {
        error = "Cannot verify Coop runtime files."; return false;
    }
    id.flags = IsQA() ? 1 : 0;
    if (IsQA() && !PreparedQA()) {
        id.flags = 1;
        std::string seed = std::string("isolated-QA/") + variant + "/" + core + "/" + loader;
        return Sha256(seed.data(), (DWORD)seed.size(), id.digest);
    }
    std::string ini = dir + "coop\\profile.ini";
    auto read = [&](const char* key) {
        char value[256] = {};
        GetPrivateProfileStringA("coop", key, "", value, sizeof value, ini.c_str());
        return std::string(value);
    };
    if (read("protocol") != std::to_string(PROTOCOL) || read("variant") != variant || read("engine") != (uo ? "uo" : "cod1")) {
        error = "Campaign is not prepared; run CoDCoop Launcher to verify the complete suite."; return false;
    }
    if (read("core_sha256") != core || read("loader_sha256") != loader || !Unhex(read("digest").c_str(), id.digest) || !Valid(id)) {
        error = "Coop files changed since verification; repair or restart using CoDCoop Launcher."; return false;
    }
    return true;
}

inline bool PrepareDirectLaunch(uint8_t variant)
{
    const wchar_t* variants[] = {L"cod1", L"uo", L"sp_improved", L"united_fronts"};
    if (IsQA() || variant == 0 || variant > 4) return false;

    wchar_t path[MAX_PATH];
    DWORD length = GetModuleFileNameW(nullptr, path, _countof(path));
    if (length == 0 || length >= _countof(path)) return false;
    std::wstring game(path, length);
    const auto slash = game.find_last_of(L'\\');
    if (slash == std::wstring::npos) return false;
    game.resize(slash + 1);
    const auto checker = game + L"coop\\suite-check.exe";
    // A trailing separator would escape the closing quote. The dot also
    // keeps the argument absolute when the game is at the root of a drive.
    std::wstring command = L"\"" + checker + L"\" prepare " + variants[variant - 1] + L" \"" + game + L".\"";
    STARTUPINFOW startup{};
    startup.cb = sizeof startup;
    PROCESS_INFORMATION child{};
    if (!CreateProcessW(checker.c_str(), command.data(), nullptr, nullptr, FALSE, CREATE_NO_WINDOW,
                        nullptr, game.c_str(), &startup, &child)) return false;
    CloseHandle(child.hThread);
    DWORD exitCode = 1;
    if (WaitForSingleObject(child.hProcess, 60000) == WAIT_OBJECT_0)
        GetExitCodeProcess(child.hProcess, &exitCode);
    else
        TerminateProcess(child.hProcess, 1);
    CloseHandle(child.hProcess);
    return exitCode == 0;
}
}
