// Console-only test entry point into actual production installer retirement.
#include <iostream>
#include "../installer/installer.cpp"
int wmain(int argc,wchar_t** argv) {
    if (argc<4 || argc>5) return 2;
    if (argc==5 && std::wstring(argv[4])==L"de") g_ui=L_DE;
    try {
        const std::wstring action=argv[1],game=argv[2],overlay=argv[3];
        if (action==L"ui-preflight") PreflightCoopUiBanks(overlay);
        else if (action==L"ui-en" || action==L"ui-de" || action==L"ui-de-rollback") {
            g_changes.clear();g_transactionActive=true;ApplyCoopUiLanguage(game,action!=L"ui-en");
            if(action==L"ui-de-rollback")RollbackFiles();
        }
        else if (action==L"preflight") PreflightRetiredTriggerOverlays(game,overlay);
        else if (action==L"retire" || action==L"retire-rollback") {
            g_changes.clear();g_transactionActive=true;RetireOldPayload(game,overlay);
            if (action==L"retire-rollback") RollbackFiles();
        } else return 2;
        std::cout<<"{\"ok\":true,\"changes\":"<<g_changes.size()<<"}"<<std::endl;
        return 0;
    } catch (const std::exception& error) {
        if (g_transactionActive) RollbackFiles();
        std::cout<<suite::Json{{"ok",false},{"error",error.what()},{"changes",g_changes.size()}}.dump()<<std::endl;
        return 1;
    }
}
