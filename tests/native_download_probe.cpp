// Test-only console entry point; production installer functions are used unchanged.
#include "../installer/installer.cpp"
int wmain(int argc,wchar_t** argv) {
    if (argc!=5) return 2;
    DWORD size=0;
    if (!DownloadNumber(argv[4],size)) return 2;
    return DownloadPinned(argv[1],argv[2],L"Download test",suite::Utf8(argv[3]),size)?0:1;
}
