#pragma once
#ifdef _WIN32
#include "party_native_bridge.h"
#include <windows.h>
#include <wincrypt.h>
#include <aclapi.h>
#include <vector>

namespace party_native_bridge {
inline bool NativeSha256(const char* data,size_t bytes,Hex64& out){
 if(!data||bytes>party_native_json::MAX_BYTES)return false;HCRYPTPROV provider=0;HCRYPTHASH hash=0;BYTE digest[32];DWORD count=32;
 bool ok=CryptAcquireContextW(&provider,nullptr,nullptr,PROV_RSA_AES,CRYPT_VERIFYCONTEXT)&&CryptCreateHash(provider,CALG_SHA_256,0,0,&hash)&&CryptHashData(hash,(const BYTE*)data,(DWORD)bytes,0)&&CryptGetHashParam(hash,HP_HASHVAL,digest,&count,0)&&count==32;
 if(hash)CryptDestroyHash(hash);if(provider)CryptReleaseContext(provider,0);if(!ok)return false;Hex64 result{};static const char hex[]="0123456789abcdef";
 for(unsigned i=0;i<32;++i){result.text[i*2]=hex[digest[i]>>4];result.text[i*2+1]=hex[digest[i]&15];}out=result;return true;
}
inline bool NativeRandomNonce(Hex64& out){
 HCRYPTPROV provider=0;BYTE bytes[32];bool ok=CryptAcquireContextW(&provider,nullptr,nullptr,PROV_RSA_AES,CRYPT_VERIFYCONTEXT)&&CryptGenRandom(provider,sizeof bytes,bytes);
 if(provider)CryptReleaseContext(provider,0);if(!ok)return false;Hex64 nonce{};static const char hex[]="0123456789abcdef";for(unsigned i=0;i<32;++i){nonce.text[2*i]=hex[bytes[i]>>4];nonce.text[2*i+1]=hex[bytes[i]&15];}if(!Valid(nonce))return false;out=nonce;return true;
}
enum class Record {Host0,Host1,Host2,Ack0,Ack1,Ack2,Client,HostReady,Party};
inline const wchar_t* RecordName(Record record){
 switch(record){case Record::Host0:return L"host-0.json";case Record::Host1:return L"host-1.json";case Record::Host2:return L"host-2.json";case Record::Ack0:return L"ack-0.json";case Record::Ack1:return L"ack-1.json";case Record::Ack2:return L"ack-2.json";case Record::Client:return L"client.json";case Record::HostReady:return L"host-ready.json";case Record::Party:return L"party.json";}return nullptr;
}
inline bool NativeProduces(Record r){return r==Record::Host0||r==Record::Host1||r==Record::Host2||r==Record::Client||r==Record::HostReady;}
class FixedFiles {
 std::wstring root;
 std::vector<BYTE> tokenUser;
 PSID User()const{return tokenUser.empty()?nullptr:((TOKEN_USER*)tokenUser.data())->User.Sid;}
 // Wine intentionally resolves external POSIX links before returning apparent
 // DOS handle names, without marking them as Win32 reparse points. Its native
 // conversion reports the resolved Unix target; compare it with the resolved
 // parent plus the fixed leaf. Native Windows instead uses reparse/handle checks.
 bool WineNoLink(const std::wstring& path)const{
  auto convert=(char*(__cdecl*)(const wchar_t*))GetProcAddress(GetModuleHandleW(L"kernel32.dll"),"wine_get_unix_file_name");
  if(!convert)return !GetProcAddress(GetModuleHandleW(L"ntdll.dll"),"wine_get_version");auto slash=path.find_last_of(L"\\/");if(slash==std::wstring::npos||slash+1==path.size())return false;
  char* parent=convert(path.substr(0,slash).c_str());char* actual=convert(path.c_str());bool ok=false;
  if(parent&&actual){std::wstring leaf=path.substr(slash+1);char utf8[512];int count=WideCharToMultiByte(CP_UTF8,WC_ERR_INVALID_CHARS,leaf.c_str(),-1,utf8,sizeof utf8,nullptr,nullptr);if(count>0){std::string expected=parent;while(expected.size()>1&&expected.back()=='/')expected.pop_back();expected+='/';expected+=utf8;ok=expected==actual;}}
  if(parent)HeapFree(GetProcessHeap(),0,parent);if(actual)HeapFree(GetProcessHeap(),0,actual);return ok;
 }
 bool Owner(HANDLE handle)const{
  PSID owner=nullptr;PACL acl=nullptr;PSECURITY_DESCRIPTOR descriptor=nullptr;
  bool ok=User()&&GetSecurityInfo(handle,SE_FILE_OBJECT,OWNER_SECURITY_INFORMATION|DACL_SECURITY_INFORMATION,&owner,nullptr,&acl,nullptr,&descriptor)==ERROR_SUCCESS&&owner&&EqualSid(owner,User())&&acl;
  if(ok)for(unsigned i=0;i<acl->AceCount;++i){void* raw=nullptr;if(!GetAce(acl,i,&raw)){ok=false;break;}auto header=(ACE_HEADER*)raw;if(header->AceType==ACCESS_DENIED_ACE_TYPE)continue;
   if(header->AceType!=ACCESS_ALLOWED_ACE_TYPE){ok=false;break;}auto ace=(ACCESS_ALLOWED_ACE*)raw;auto sid=(PSID)&ace->SidStart;
   const DWORD writes=FILE_WRITE_DATA|FILE_APPEND_DATA|FILE_WRITE_EA|FILE_WRITE_ATTRIBUTES|FILE_DELETE_CHILD|DELETE|WRITE_DAC|WRITE_OWNER|GENERIC_WRITE|GENERIC_ALL;
   if((ace->Mask&writes)&&!EqualSid(sid,User())&&!IsWellKnownSid(sid,WinLocalSystemSid)&&!IsWellKnownSid(sid,WinBuiltinAdministratorsSid)){ok=false;break;}
  }
  if(descriptor)LocalFree(descriptor);return ok;
 }
 bool Directory(const std::wstring& path,bool privateOwner)const{
  HANDLE handle=CreateFileW(path.c_str(),FILE_READ_ATTRIBUTES|READ_CONTROL,FILE_SHARE_READ|FILE_SHARE_WRITE|FILE_SHARE_DELETE,nullptr,OPEN_EXISTING,FILE_FLAG_BACKUP_SEMANTICS|FILE_FLAG_OPEN_REPARSE_POINT,nullptr);
  if(handle==INVALID_HANDLE_VALUE)return false;BY_HANDLE_FILE_INFORMATION info{};bool ok=GetFileInformationByHandle(handle,&info)&&(info.dwFileAttributes&FILE_ATTRIBUTE_DIRECTORY)&&!(info.dwFileAttributes&FILE_ATTRIBUTE_REPARSE_POINT)&&WineNoLink(path)&&(!privateOwner||Owner(handle));CloseHandle(handle);return ok;
 }
 bool Safe()const{
  if(root.empty()||!User())return false;auto slash=root.find_last_of(L'\\');return slash!=std::wstring::npos&&Directory(root.substr(0,slash),false)&&Directory(root,true);
 }
 bool ExactPath(HANDLE handle,const std::wstring& expected)const{
  wchar_t finalPath[32768];DWORD length=GetFinalPathNameByHandleW(handle,finalPath,32768,FILE_NAME_NORMALIZED|VOLUME_NAME_DOS);
  if(!length||length>=32768)return false;std::wstring actual(finalPath,length);if(actual.compare(0,4,L"\\\\?\\")==0)actual.erase(0,4);
  return CompareStringOrdinal(actual.c_str(),-1,expected.c_str(),-1,TRUE)==CSTR_EQUAL&&WineNoLink(expected);
 }
 bool Regular(HANDLE handle,const std::wstring& path,BY_HANDLE_FILE_INFORMATION& info)const{return GetFileInformationByHandle(handle,&info)&&!(info.dwFileAttributes&(FILE_ATTRIBUTE_REPARSE_POINT|FILE_ATTRIBUTE_DIRECTORY))&&Owner(handle)&&ExactPath(handle,path)&&Safe();}
 bool RemovePath(const std::wstring& path)const{
  HANDLE h=CreateFileW(path.c_str(),DELETE|READ_CONTROL|FILE_READ_ATTRIBUTES,FILE_SHARE_READ|FILE_SHARE_WRITE|FILE_SHARE_DELETE,nullptr,OPEN_EXISTING,FILE_FLAG_OPEN_REPARSE_POINT,nullptr);
  if(h==INVALID_HANDLE_VALUE)return GetLastError()==ERROR_FILE_NOT_FOUND;BY_HANDLE_FILE_INFORMATION info{};bool ok=Regular(h,path,info);CloseHandle(h);return ok&&DeleteFileW(path.c_str());
 }
public:
 // game comes exclusively from the verified installation, never a network field.
 explicit FixedFiles(const std::wstring& game){
  HANDLE token=nullptr;DWORD size=0;if(!OpenProcessToken(GetCurrentProcess(),TOKEN_QUERY,&token))return;
  GetTokenInformation(token,TokenUser,nullptr,0,&size);if(size&&size<=4096){tokenUser.resize(size);if(!GetTokenInformation(token,TokenUser,tokenUser.data(),size,&size))tokenUser.clear();}CloseHandle(token);
  wchar_t full[32768];DWORD n=GetFullPathNameW(game.c_str(),32768,full,nullptr);if(!n||n>=32700||!User())return;root.assign(full,n);while(!root.empty()&&(root.back()==L'\\'||root.back()==L'/'))root.pop_back();root+=L"\\coop\\party-bridge";
 }
 bool Ensure(){
  if(root.empty()||!User())return false;auto coop=root.substr(0,root.find_last_of(L'\\'));if(!Directory(coop,false)&&(!CreateDirectoryW(coop.c_str(),nullptr)||!Directory(coop,false)))return false;
  if(Directory(root,true))return true;
  EXPLICIT_ACCESSW access{};access.grfAccessPermissions=GENERIC_ALL;access.grfAccessMode=SET_ACCESS;access.grfInheritance=SUB_CONTAINERS_AND_OBJECTS_INHERIT;access.Trustee.TrusteeForm=TRUSTEE_IS_SID;access.Trustee.TrusteeType=TRUSTEE_IS_USER;access.Trustee.ptstrName=(LPWSTR)User();
  PACL acl=nullptr;SECURITY_DESCRIPTOR descriptor{};SECURITY_ATTRIBUTES attributes{sizeof attributes,&descriptor,FALSE};
  bool ready=SetEntriesInAclW(1,&access,nullptr,&acl)==ERROR_SUCCESS&&InitializeSecurityDescriptor(&descriptor,SECURITY_DESCRIPTOR_REVISION)&&SetSecurityDescriptorOwner(&descriptor,User(),FALSE)&&SetSecurityDescriptorDacl(&descriptor,TRUE,acl,FALSE)&&SetSecurityDescriptorControl(&descriptor,SE_DACL_PROTECTED,SE_DACL_PROTECTED);
  bool created=ready&&CreateDirectoryW(root.c_str(),&attributes);if(acl)LocalFree(acl);return created&&Directory(root,true);
 }
 bool Read(Record record,std::string& out)const{
  auto name=RecordName(record);if(!name||!Safe())return false;auto path=root+L"\\"+name;HANDLE h=CreateFileW(path.c_str(),GENERIC_READ|READ_CONTROL,FILE_SHARE_READ|FILE_SHARE_WRITE|FILE_SHARE_DELETE,nullptr,OPEN_EXISTING,FILE_FLAG_OPEN_REPARSE_POINT,nullptr);
  if(h==INVALID_HANDLE_VALUE)return false;BY_HANDLE_FILE_INFORMATION before{},after{};bool ok=Regular(h,path,before)&&!before.nFileSizeHigh&&before.nFileSizeLow&&before.nFileSizeLow<=party_native_json::MAX_BYTES;std::string bytes;
  if(ok){bytes.resize(before.nFileSizeLow);DWORD got=0;ok=ReadFile(h,bytes.data(),before.nFileSizeLow,&got,nullptr)&&got==before.nFileSizeLow&&Regular(h,path,after)&&before.dwVolumeSerialNumber==after.dwVolumeSerialNumber&&before.nFileIndexHigh==after.nFileIndexHigh&&before.nFileIndexLow==after.nFileIndexLow&&before.nFileSizeLow==after.nFileSizeLow&&before.nFileSizeHigh==after.nFileSizeHigh&&!CompareFileTime(&before.ftLastWriteTime,&after.ftLastWriteTime);}
  CloseHandle(h);if(!ok)return false;out=std::move(bytes);return true;
 }
 bool Write(Record record,const std::string& bytes){
  auto name=RecordName(record);if(!NativeProduces(record)||!name||bytes.empty()||bytes.size()>party_native_json::MAX_BYTES||!Ensure())return false;
  auto path=root+L"\\"+name,temp=path+L".native-pending";if(!RemovePath(temp))return false;
  HANDLE h=CreateFileW(temp.c_str(),GENERIC_WRITE|READ_CONTROL|FILE_READ_ATTRIBUTES,0,nullptr,CREATE_NEW,FILE_ATTRIBUTE_NORMAL|FILE_FLAG_OPEN_REPARSE_POINT,nullptr);
  if(h==INVALID_HANDLE_VALUE)return false;BY_HANDLE_FILE_INFORMATION info{};DWORD written=0;bool ok=Regular(h,temp,info)&&WriteFile(h,bytes.data(),(DWORD)bytes.size(),&written,nullptr)&&written==bytes.size()&&FlushFileBuffers(h);CloseHandle(h);
  if(!ok){RemovePath(temp);return false;}DWORD attributes=GetFileAttributesW(path.c_str());if(attributes!=INVALID_FILE_ATTRIBUTES){HANDLE existing=CreateFileW(path.c_str(),READ_CONTROL|FILE_READ_ATTRIBUTES,FILE_SHARE_READ|FILE_SHARE_WRITE|FILE_SHARE_DELETE,nullptr,OPEN_EXISTING,FILE_FLAG_OPEN_REPARSE_POINT,nullptr);bool safe=existing!=INVALID_HANDLE_VALUE&&Regular(existing,path,info);if(existing!=INVALID_HANDLE_VALUE)CloseHandle(existing);if(!safe){RemovePath(temp);return false;}}
  if(!Safe()||!MoveFileExW(temp.c_str(),path.c_str(),MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH)){RemovePath(temp);return false;}return true;
 }
 bool Remove(Record record)const{auto name=RecordName(record);return record!=Record::Party&&name&&Safe()&&RemovePath(root+L"\\"+name);}
};
}
#endif
