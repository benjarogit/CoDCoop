// Native helper/worker contract fixture. This process is NOT the game/Core.
#include "../src/party_native_bridge_catalog.h"
#include <fstream>
#include <iostream>
#ifdef _WIN32
#include "../src/party_native_bridge_win.h"
#else
#include <openssl/sha.h>
#endif
using namespace party_native_bridge;
static bool Hash(const char* bytes,size_t size,Hex64& out){
#ifdef _WIN32
 return NativeSha256(bytes,size,out);
#else
 unsigned char digest[32];if(!SHA256((const unsigned char*)bytes,size,digest))return false;static const char hex[]="0123456789abcdef";out={};for(unsigned i=0;i<32;++i){out.text[i*2]=hex[digest[i]>>4];out.text[i*2+1]=hex[digest[i]&15];}return true;
#endif
}
static bool read(const char* path,std::string& out){std::ifstream f(path,std::ios::binary);if(!f)return false;out.assign(std::istreambuf_iterator<char>(f),{});return out.size()<=party_native_json::MAX_BYTES;}
int main(int argc,char**argv){
 if(argc==2&&std::string(argv[1])=="--hash"){
  std::string input;char buffer[4096];while(std::cin){std::cin.read(buffer,sizeof buffer);input.append(buffer,(size_t)std::cin.gcount());if(input.size()>party_native_json::MAX_BYTES)return 7;}Hex64 digest{};if(!Hash(input.data(),input.size(),digest))return 6;std::cout<<digest.text;return 0;
 }
 if(argc==6&&std::string(argv[1])=="--plan"){
  std::string input,rawCatalog,rawWorld;if(!read(argv[2],input)||!read(argv[3],rawCatalog)||!read(argv[4],rawWorld))return 2;
  party_native_json::Value catalog,world;if(!party_native_json::Parse(rawCatalog,catalog)||!party_native_json::Parse(rawWorld,world))return 3;
  std::string canonical;Hex64 catalogSha{},package{};if(!party_native_json::Canonical(catalog,canonical)||!Hash(canonical.data(),canonical.size(),catalogSha)||std::strlen(argv[5])!=64)return 4;
  std::memcpy(package.text,argv[5],64);Plan plan{};
  bool valid=ParsePlan(input,catalogSha,package,Hash,[&](const Plan& p,const auto& declared,const auto& full){return VerifyCatalogPlan(p,declared,full,catalog,world,Hash);},plan);
  if(!valid){std::cout<<"{\"valid\":false}";return 1;}
  std::cout<<"{\"valid\":true,\"revision\":"<<plan.revision<<",\"members\":"<<int(plan.roster.count)<<",\"plan_sha256\":\""<<plan.planSha.text<<"\"}";return 0;
 }
#ifdef _WIN32
 if(argc==3&&std::string(argv[1])=="--wine-path"){
  auto convert=(char*(__cdecl*)(const wchar_t*))GetProcAddress(GetModuleHandleW(L"kernel32.dll"),"wine_get_unix_file_name");if(!convert)return 9;
  std::string raw=argv[2];std::wstring path(raw.begin(),raw.end());char* unixName=convert(path.c_str());if(!unixName)return 10;std::cout<<unixName;HeapFree(GetProcessHeap(),0,unixName);return 0;
 }
 if(argc==3&&std::string(argv[1])=="--fixed-io"){
  std::string narrow=argv[2];std::wstring game(narrow.begin(),narrow.end());FixedFiles files(game);
  std::string text="{\"kind\":\"native-contract-fixture\",\"runtime_ready\":false}",got;
  auto fail=[](const char* stage){std::cerr<<stage<<" WinError="<<GetLastError();return 5;};
  if(!files.Ensure())return fail("ensure");
  if(!files.Write(Record::Host0,text))return fail("write");if(!files.Read(Record::Host0,got)||got!=text)return fail("read");
  if(files.Write(Record::Party,text)||files.Write(Record::Ack0,text)||files.Write((Record)999,text))return fail("producer ownership");
  if(files.Read((Record)999,got)||files.Remove(Record::Party))return fail("fixed record namespace");
  std::string replacement="{\"kind\":\"replacement\",\"runtime_ready\":false}";
  if(!files.Write(Record::Host0,replacement)||!files.Read(Record::Host0,got)||got!=replacement)return fail("atomic replace");
  auto host=game+L"\\coop\\party-bridge\\host-0.json";
  HANDLE held=CreateFileW(host.c_str(),GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,0,nullptr);if(held==INVALID_HANDLE_VALUE)return fail("hold original");
  bool incorrectlyReplaced=files.Write(Record::Host0,text);CloseHandle(held);
  if(incorrectlyReplaced||!files.Read(Record::Host0,got)||got!=replacement)return fail("failed replacement changed original");
  std::ofstream oversized(narrow+"\\coop\\party-bridge\\host-1.json",std::ios::binary);oversized<<std::string(party_native_json::MAX_BYTES+1,'x');oversized.close();
  if(files.Read(Record::Host1,got)||!files.Remove(Record::Host1))return fail("oversized read");
  if(!files.Remove(Record::Host0))return fail("remove");
  Hex64 hash{},nonce{};if(!NativeSha256(text.data(),text.size(),hash)||!NativeRandomNonce(nonce))return 6;std::cout<<"{\"valid\":true,\"sha256\":\""<<hash.text<<"\"}";return 0;
 }
 if(argc==3&&std::string(argv[1])=="--reject-client-path"){
  std::string narrow=argv[2],got;FixedFiles files(std::wstring(narrow.begin(),narrow.end()));
  return files.Read(Record::Client,got)||files.Write(Record::Client,"{}")?8:0;
 }
#endif
 return 2;
}
