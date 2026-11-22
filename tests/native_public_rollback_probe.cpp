#define _WIN32_WINNT 0x0A00
#include <windows.h>
#include <string>
#include <iostream>
static bool failRestoreCopy=false;
static BOOL WINAPI ProbeCopyFileW(LPCWSTR from,LPCWSTR to,BOOL exclusive) {
 if(failRestoreCopy&&std::wstring(to).find(L".coop-restore-pending.")!=std::wstring::npos){SetLastError(ERROR_ACCESS_DENIED);return FALSE;}
 return ::CopyFileW(from,to,exclusive);
}
#define CopyFileW ProbeCopyFileW
#include "../installer/installer.cpp"
int wmain(int argc,wchar_t** argv) {
 if(argc!=3)return 2;
 try {
  std::wstring action=argv[1],root=argv[2];
  if(action==L"record") {
   g_changes.clear();g_transactionActive=true;
   for(auto relative:{"ddraw.dll","Main/zzzz_coop_triggers.pk3","Main/config.cfg","Main/save/autosave/progress.svg","coop/new-runtime.txt"}) {
    auto path=suite::Resolve(root,relative);RememberFile(path);suite::Write(path,std::string("installed:")+relative);
   }
   g_transactionActive=false;SaveInstallJournal(root);std::cout<<"{\"ok\":true}\n";return 0;
  }
  if(action==L"rollback"||action==L"rollback-fail-mid") {failRestoreCopy=action==L"rollback-fail-mid";std::wstring error;bool ok=RollbackLastInstall(root,error);std::cout<<suite::Canonical({{"ok",ok},{"error",suite::Utf8(error)}})<<"\n";return ok?0:1;}
  return 2;
 } catch(const std::exception& e) {std::cout<<suite::Canonical({{"ok",false},{"error",e.what()}})<<"\n";return 1;}
}
