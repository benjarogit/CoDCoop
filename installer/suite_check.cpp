#include "suite_check.h"
#include <cstdio>
int wmain(int argc,wchar_t** argv) {
    if (argc==2 && !wcscmp(argv[1],L"capabilities")) {
        printf("{\"kind\":\"codcoop_suite_checker\",\"schema\":1,\"protocol\":%u}\n",suite::PROTOCOL);
        return 0;
    }
    std::string error; bool ok=false;
    if (argc==3 && !wcscmp(argv[1],L"rollback")) ok=suite::Restore(argv[2],error);
    else if (argc==4 && !wcscmp(argv[1],L"prepare"))
        ok=suite::Prepare(argv[3],suite::Utf8(argv[2]),error);
    else if (argc==3 && (!wcscmp(argv[1],L"check") || !wcscmp(argv[1],L"seal")))
        ok=suite::Validate(argv[2],!wcscmp(argv[1],L"seal"),error);
    else { fprintf(stderr,"Usage: suite-check.exe capabilities or check|seal|rollback GAME_FOLDER or prepare VARIANT GAME_FOLDER\n"); return 2; }
    if (!ok) fprintf(stderr,"CoDCoop: %s\n",error.c_str());
    else puts("CoDCoop: operation complete");
    return ok?0:1;
}
