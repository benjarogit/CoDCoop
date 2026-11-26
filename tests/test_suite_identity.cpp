#include "../src/suite_identity.h"
#include <cassert>

int main(int argc, char** argv)
{
    if (argc == 2 && !strcmp(argv[1], "--direct-launch")) {
        suite::Identity identity{};
        std::string error;
        if (suite::LoadIdentity(false, "", identity, error)) return 3;
        if (!suite::PrepareDirectLaunch(identity.variant)) return 4;
        return suite::LoadIdentity(false, "", identity, error) ? 0 : 5;
    }
    const std::string root = suite::GameDir();
    FILE* marker = fopen((root + ".identity-test-owned").c_str(), "rb");
    if (!marker) return 2; // fixtures must never replace a real game's DLLs
    fclose(marker);
    for (const char* name : {"codcoop_core.dll", "ddraw.dll"}) {
        FILE* file = fopen((root + name).c_str(), "wb");
        assert(file); fputs("isolated identity fixture", file); fclose(file);
    }
    CreateDirectoryA((root + "coop").c_str(), nullptr);
    const std::string ini = root + "coop\\profile.ini";
    auto write = [&](const char* key, const char* value) {
        assert(WritePrivateProfileStringA("coop", key, value, ini.c_str()));
    };
    char core[65]{}, loader[65]{};
    assert(suite::FileHash(root + "codcoop_core.dll", core));
    assert(suite::FileHash(root + "ddraw.dll", loader));
    const std::string digest(64, '1');
    write("protocol", std::to_string(suite::PROTOCOL).c_str()); write("variant", "cod1"); write("engine", "cod1");
    write("digest", digest.c_str()); write("core_sha256", core); write("loader_sha256", loader);
    SetEnvironmentVariableA("CODCOOP_QA", nullptr);
    SetEnvironmentVariableA("CODCOOP_QA_PROFILE", nullptr);
    suite::Identity regular{}, prepared{}, raw{};
    std::string error;
    assert(suite::LoadIdentity(false, "", regular, error) && regular.flags == 0 && regular.digest[0] == 0x11);
    SetEnvironmentVariableA("CODCOOP_QA", "1");
    SetEnvironmentVariableA("CODCOOP_QA_PROFILE", "1");
    assert(suite::LoadIdentity(false, "", prepared, error) && prepared.flags == 1);
    assert(!memcmp(regular.digest, prepared.digest, sizeof regular.digest));
    assert(suite::Difference(regular, prepared)); // telemetry cannot join a normal session
    write("protocol", std::to_string(suite::PROTOCOL - 1).c_str());
    assert(!suite::LoadIdentity(false, "", prepared, error));
    write("protocol", std::to_string(suite::PROTOCOL).c_str());
    write("variant", "uo");
    assert(!suite::LoadIdentity(false, "", prepared, error));
    write("variant", "cod1"); write("core_sha256", digest.c_str());
    assert(!suite::LoadIdentity(false, "", prepared, error)); // prepared QA never bypasses runtime checks
    SetEnvironmentVariableA("CODCOOP_QA_PROFILE", nullptr);
    assert(suite::LoadIdentity(false, "", raw, error) && raw.flags == 1);
    assert(memcmp(raw.digest, regular.digest, sizeof raw.digest));
    write("core_sha256", core);
    SetEnvironmentVariableA("CODCOOP_QA_PROFILE", "1");
    assert(suite::LoadIdentity(false, "", prepared, error));
    assert(suite::Difference(raw, prepared)); // synthetic fixture identity differs from real sealed content
    DeleteFileA(ini.c_str());
    WritePrivateProfileStringA(nullptr, nullptr, nullptr, ini.c_str());
    assert(!suite::LoadIdentity(false, "", prepared, error));
    assert(!suite::LoadIdentity(false, "unregistered", prepared, error));
    puts("prepared profile identity, runtime validation and QA isolation: PASS");
}
