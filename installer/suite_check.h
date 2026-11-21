#pragma once
// Native equivalent of tools/coop_suite.py seal/check. nlohmann/json 3.12.0 (MIT).
#include <windows.h>
#include <wincrypt.h>
#include <algorithm>
#include <fstream>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>
#include "vendor/json.hpp"
#include "../src/suite_protocol.h"

namespace suite {
using Json = nlohmann::json;
inline std::string Utf8(const std::wstring& value) {
    int n = WideCharToMultiByte(CP_UTF8, 0, value.data(), (int)value.size(), nullptr, 0, nullptr, nullptr);
    std::string out(n, '\0');
    WideCharToMultiByte(CP_UTF8, 0, value.data(), (int)value.size(), &out[0], n, nullptr, nullptr);
    return out;
}
inline std::wstring Wide(const std::string& value) {
    int n = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, value.data(), (int)value.size(), nullptr, 0);
    if (!n && !value.empty()) throw std::runtime_error("invalid UTF-8 path");
    std::wstring out(n, L'\0');
    MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, value.data(), (int)value.size(), &out[0], n);
    return out;
}
inline std::string Lower(std::string s) { for (char& c : s) if (c >= 'A' && c <= 'Z') c += 'a' - 'A'; return s; }
inline bool Hex(const std::string& s) { return s.size() == 64 && s.find_first_not_of("0123456789abcdef") == std::string::npos; }
inline std::wstring Resolve(const std::wstring& root, const std::string& rel) {
    if (rel.empty() || rel.front() == '/' || rel.find('\\') != std::string::npos || rel.find(':') != std::string::npos)
        throw std::runtime_error("unsafe package path: " + rel);
    std::wstring path = root;
    size_t start = 0;
    while (start < rel.size()) {
        size_t end = rel.find('/', start);
        std::string part = rel.substr(start, end == std::string::npos ? end : end-start);
        if (part.empty() || part == "." || part == "..") throw std::runtime_error("unsafe package path: " + rel);
        // Wine can contain both Main and main (or differently cased files).
        // Reject ambiguity even when the requested spelling exists exactly;
        // otherwise engine and checker can read different case aliases.
        std::wstring requested=Wide(part), actual=requested;
        WIN32_FIND_DATAW entry;
        HANDLE search=FindFirstFileW((path+L"\\*").c_str(),&entry);
        unsigned matches=0;
        if (search!=INVALID_HANDLE_VALUE) {
            do {
                if (CompareStringOrdinal(entry.cFileName,-1,requested.c_str(),-1,TRUE)==CSTR_EQUAL) {
                    actual=entry.cFileName;
                    ++matches;
                }
            } while (FindNextFileW(search,&entry));
            FindClose(search);
        }
        if (matches>1) throw std::runtime_error("ambiguous package path: "+rel);
        path += L"\\" + actual;
        DWORD attr = GetFileAttributesW(path.c_str());
        if (attr != INVALID_FILE_ATTRIBUTES && (attr & FILE_ATTRIBUTE_REPARSE_POINT))
            throw std::runtime_error("package reparse point: " + rel);
        if (end == std::string::npos) break;
        start = end + 1;
    }
    return path;
}
inline std::string Read(const std::wstring& path) {
    HANDLE file = CreateFileW(path.c_str(), GENERIC_READ, FILE_SHARE_READ, nullptr, OPEN_EXISTING, 0, nullptr);
    if (file == INVALID_HANDLE_VALUE) throw std::runtime_error("cannot open " + Utf8(path));
    DWORD size = GetFileSize(file, nullptr);
    if (size > 32*1024*1024) { CloseHandle(file); throw std::runtime_error("metadata too large"); }
    std::string out(size, '\0'); DWORD got = 0;
    BOOL ok = ReadFile(file, out.data(), size, &got, nullptr);
    CloseHandle(file);
    if (!ok || got != size) throw std::runtime_error("cannot read metadata");
    return out;
}
inline std::string Hash(const std::wstring& path, const std::string* data = nullptr) {
    HCRYPTPROV provider = 0; HCRYPTHASH hash = 0;
    if (!CryptAcquireContextW(&provider, nullptr, nullptr, PROV_RSA_AES, CRYPT_VERIFYCONTEXT) ||
        !CryptCreateHash(provider, CALG_SHA_256, 0, 0, &hash)) {
        if (provider) CryptReleaseContext(provider, 0);
        throw std::runtime_error("SHA-256 unavailable");
    }
    bool ok = true;
    if (data) ok = CryptHashData(hash, (const BYTE*)data->data(), (DWORD)data->size(), 0);
    else {
        HANDLE f = CreateFileW(path.c_str(), GENERIC_READ, FILE_SHARE_READ, nullptr, OPEN_EXISTING, 0, nullptr);
        if (f == INVALID_HANDLE_VALUE) ok = false;
        else {
            BYTE block[65536]; DWORD n;
            for (;;) {
                if (!ReadFile(f, block, sizeof block, &n, nullptr)) { ok = false; break; }
                if (!n) break;
                if (!CryptHashData(hash, block, n, 0)) { ok = false; break; }
            }
            CloseHandle(f);
        }
    }
    BYTE digest[32]; DWORD n = sizeof digest;
    ok = ok && CryptGetHashParam(hash, HP_HASHVAL, digest, &n, 0);
    CryptDestroyHash(hash); CryptReleaseContext(provider, 0);
    if (!ok) throw std::runtime_error("cannot hash " + Utf8(path));
    const char* digits="0123456789abcdef"; std::string out;
    for (BYTE b : digest) { out += digits[b >> 4]; out += digits[b & 15]; }
    return out;
}
inline std::string Canonical(const Json& value) { return value.dump(-1, ' ', true); }
inline void Write(const std::wstring& path, const std::string& value) {
    std::wstring tmp = path + L".tmp." + std::to_wstring(GetCurrentProcessId());
    HANDLE f = CreateFileW(tmp.c_str(), GENERIC_WRITE, 0, nullptr, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    DWORD n = 0;
    BOOL ok = f != INVALID_HANDLE_VALUE && WriteFile(f, value.data(), (DWORD)value.size(), &n, nullptr) && n == value.size();
    if (f != INVALID_HANDLE_VALUE) { FlushFileBuffers(f); CloseHandle(f); }
    if (!ok || !MoveFileExW(tmp.c_str(), path.c_str(), MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)) {
        DeleteFileW(tmp.c_str()); throw std::runtime_error("cannot write " + Utf8(path));
    }
}
inline void ScanPk3(const std::wstring& game, const std::string& relative, std::set<std::string>& names, bool jsonOnly=false) {
    std::wstring folder=Resolve(game, relative); WIN32_FIND_DATAW fd;
    HANDLE h=FindFirstFileW((folder+L"\\*").c_str(), &fd);
    if (h == INVALID_HANDLE_VALUE) return;
    try {
        do {
            std::string name=Utf8(fd.cFileName);
            if (name=="." || name==".." || name=="localized_backup") continue;
            if (fd.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT) throw std::runtime_error("package reparse point");
            std::string rel=relative+"/"+name;
            if (fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) ScanPk3(game, rel, names, jsonOnly);
            else if ((!jsonOnly && name.size()>=4 && Lower(name.substr(name.size()-4))==".pk3") ||
                     (name.size()>=5 && Lower(name.substr(name.size()-5))==".json" && (jsonOnly || Lower(rel).find("/eweapons/")!=std::string::npos))) {
                bool known=false;
                for (const auto& item:names) if (Lower(item)==Lower(rel)) { known=true; break; }
                if (!known) names.insert(rel);
            }
        } while (FindNextFileW(h, &fd));
    } catch (...) { FindClose(h); throw; }
    FindClose(h);
}
inline Json ApprovedLocalizations(const Json& manifest) {
    Json result=Json::object();
    if (!manifest.contains("approved_localizations")) return result;
    const auto& catalog=manifest.at("approved_localizations");
    if (!catalog.is_object()) throw std::runtime_error("invalid approved localization catalog");
    for (auto i=catalog.begin();i!=catalog.end();++i) {
        std::string name=Lower(i.key());
        auto slash=name.find('/');
        bool safe=slash!=std::string::npos && (name.substr(0,slash)=="main" || name.substr(0,slash)=="uo") &&
                  name.find('/',slash+1)==std::string::npos;
        std::string base=slash==std::string::npos ? "" : name.substr(slash+1);
        safe=safe && base.rfind("localized_",0)==0 && base.size()>14 && base.substr(base.size()-4)==".pk3";
        if (safe) {
            std::string stem=base.substr(10,base.size()-14);
            safe=!stem.empty() && stem.find_first_not_of("abcdefghijklmnopqrstuvwxyz0123456789_")==std::string::npos;
        }
        if (!safe || result.contains(name) || !i.value().is_array() || i.value().empty())
            throw std::runtime_error("invalid approved localization entry: "+i.key());
        for (const auto& hash:i.value())
            if (!hash.is_string() || !Hex(hash.get<std::string>()))
                throw std::runtime_error("invalid approved localization hash: "+i.key());
        result[name]=i.value();
    }
    return result;
}
inline Json Fingerprints(const Json& manifest, const Json& files) {
    const Json localizations=ApprovedLocalizations(manifest);
    Json result=Json::object();
    for (const auto& variant: manifest.at("variants")) {
        std::set<std::string> roots;
        for (const auto& root: variant.at("content_roots")) roots.insert(Lower(root.get<std::string>()));
        std::vector<std::vector<std::string>> entries;
        for (auto i=files.begin(); i!=files.end(); ++i) {
            std::string lower=Lower(i.key());
            bool included=lower==Lower(variant.at("exe").get<std::string>()) || lower=="ddraw.dll" || lower=="codcoop_core.dll";
            auto slash=lower.find('/');
            if (slash!=std::string::npos && roots.count(lower.substr(0,slash)) &&
                lower.size()>=4 && lower.substr(lower.size()-4)==".pk3") {
                bool approved=false;
                if (localizations.contains(lower))
                    for (const auto& hash:localizations.at(lower)) if (hash==i.value()) approved=true;
                if (!approved) included=true;
            }
            if (variant.at("yap").get<bool>() && (lower.rfind("plugins/yap/",0)==0 || lower.rfind("menuwide/",0)==0 || lower.rfind("yap_raw/",0)==0)) included=true;
            if (variant.at("yap").get<bool>() && lower.rfind("eweapons/",0)==0 && lower.size()>=5 && lower.substr(lower.size()-5)==".json") included=true;
            std::string prefix=variant.at("engine")=="uo" ? "uo_" : "";
            if (lower==prefix+"gamex86.dll" || lower==prefix+"cgamex86.dll" || lower==prefix+"uix86.dll") included=true;
            if (slash!=std::string::npos && roots.count(lower.substr(0,slash)) && lower.size()>=5 &&
                lower.substr(lower.size()-5)==".json" && lower.find("/eweapons/")!=std::string::npos) included=true;
            if (included) entries.push_back({lower,i.value().get<std::string>()});
        }
        std::sort(entries.begin(),entries.end()); std::string bytes=Canonical(entries);
        result[variant.at("id").get<std::string>()]=Hash(L"",&bytes);
    }
    return result;
}
inline Json EnglishInventory(const std::wstring& game) {
    auto path=Resolve(game,"coop/languages/en/manifest.json");
    if (GetFileAttributesW(path.c_str())==INVALID_FILE_ATTRIBUTES) return Json::object();
    Json inventory=Json::parse(Read(path)), result=Json::object();
    if (inventory.at("schema")!=1 || inventory.at("language")!="en" || !inventory.at("files").is_object() || inventory.at("files").empty())
        throw std::runtime_error("invalid canonical English inventory");
    for (auto i=inventory.at("files").begin();i!=inventory.at("files").end();++i) {
        const auto relative=i.key(); auto slash=relative.find('/');
        if (slash==std::string::npos || relative.find('/',slash+1)!=std::string::npos ||
            (relative.substr(0,slash)!="Main" && relative.substr(0,slash)!="uo")) throw std::runtime_error("unsafe English source path");
        auto base=relative.substr(slash+1);
        const std::string prefix="localized_english_";
        if (base.rfind(prefix,0)!=0 || base.size()<=prefix.size()+4 || base.substr(base.size()-4)!=".pk3" ||
            base.substr(prefix.size(),base.size()-prefix.size()-4).find_first_not_of("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_")!=std::string::npos)
            throw std::runtime_error("unsafe English source file");
        if (!i.value().is_object() || !i.value().contains("sha256") || !i.value().at("sha256").is_string()) throw std::runtime_error("invalid English source hash");
        std::string digest=i.value().at("sha256").get<std::string>();
        if (!Hex(digest)) throw std::runtime_error("invalid English source hash");
        result["coop/languages/en/"+relative]=digest;
    }
    return result;
}
inline bool Validate(const std::wstring& game, bool seal, std::string& error) {
    try {
        const std::wstring mp=Resolve(game,"coop/variants.json"), lp=Resolve(game,"coop/runtime-lock.json");
        Json manifest=Json::parse(Read(mp)), lock=Json::parse(Read(lp));
        std::string mh=Hash(mp);
        if (manifest.at("schema")!=1 || manifest.at("protocol")!=PROTOCOL || manifest.at("complete_suite_required")!=true ||
            lock.at("suite_version")!=manifest.at("suite_version") || lock.at("manifest_sha256")!=mh)
            throw std::runtime_error("unsupported or mismatched suite manifest/runtime lock");
        std::vector<std::string> ids;
        for (const auto& v: manifest.at("variants")) ids.push_back(v.at("id"));
        if (ids!=std::vector<std::string>{"cod1","uo","sp_improved","united_fronts"}) throw std::runtime_error("incomplete campaign set");
        for (const auto& variant:manifest.at("variants")) {
            std::string id=variant.at("id"), fs=variant.at("fs_game");
            if (fs.find_first_not_of("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_")!=std::string::npos)
                throw std::runtime_error("unsafe fs_game");
            std::string storage=(fs.empty()?(id=="cod1"?"Main":"uo"):fs)+"/save";
            if (variant.value("save_root",storage)!=storage)
                throw std::runtime_error("campaign save area does not match its native profile");
        }
        std::set<std::string> names;
        for (const auto& required:manifest.at("required")) names.insert(required.at("path"));
        for (const auto& variant:manifest.at("variants"))
            for (const auto& root:variant.at("content_roots")) ScanPk3(game,root.get<std::string>(),names);
        for (const char* key:{"ddraw.dll","codcoop_core.dll","steam_api.dll","plugins/yap/DDRAW.dll"})
            if (!lock.at("files").contains(key)) throw std::runtime_error("runtime lock missing required module");
        for (auto i=lock.at("files").begin(); i!=lock.at("files").end(); ++i) {
            if (!i.value().is_string() || !Hex(i.value().get<std::string>())) throw std::runtime_error("invalid runtime lock hash");
            // Runtime locks own canonical spelling for loose support files.
            // Wine resolves case aliases to the same bytes, not two resources.
            auto alias=std::find_if(names.begin(),names.end(),[&](const std::string& p){return Lower(p)==Lower(i.key());});
            if (alias!=names.end() && *alias!=i.key()) names.erase(alias);
            names.insert(i.key());
        }
        ScanPk3(game,"eWeapons",names,true);
        Json english=EnglishInventory(game);
        if (!english.empty() && !lock.at("files").contains("coop/languages/en/manifest.json"))
            throw std::runtime_error("canonical English inventory missing from runtime lock");
        for (auto i=english.begin();i!=english.end();++i) names.insert(i.key());
        Json files=Json::object();
        for (const auto& name:names) files[name]=Hash(Resolve(game,name));
        for (auto i=english.begin();i!=english.end();++i)
            if (files.at(i.key())!=i.value()) throw std::runtime_error("canonical English source changed: "+i.key());
        for (const auto& item:manifest.at("required")) {
            std::string path=item.at("path"); Json allowed=Json::array();
            if (item.contains("sha256_any")) allowed=item.at("sha256_any");
            else if (item.contains("sha256")) allowed.push_back(item.at("sha256"));
            if (!allowed.empty() && std::find(allowed.begin(),allowed.end(),files.at(path))==allowed.end())
                throw std::runtime_error("wrong pinned content: "+path);
        }
        for (auto i=lock.at("files").begin(); i!=lock.at("files").end(); ++i)
            if (files.at(i.key())!=i.value()) throw std::runtime_error("wrong runtime module: "+i.key());
        Json receipt={{"schema",1},{"suite_version",manifest.at("suite_version")},{"manifest_sha256",mh},
                      {"runtime_lock_sha256",Hash(lp)},{"files",files},{"variants",Fingerprints(manifest,files)}};
        const auto rp=Resolve(game,"coop/install.json");
        if (seal) {
            Write(rp,Canonical(receipt)+"\n");
            std::string selected=manifest.value("default_variant",std::string("sp_improved"));
            std::string engine;
            for (const auto& item:manifest.at("variants")) if (item.at("id")==selected) engine=item.at("engine");
            if (engine.empty()) throw std::runtime_error("unknown default campaign variant");
            Write(Resolve(game,"coop/profile.ini"),"[coop]\nprotocol="+std::to_string(PROTOCOL)+"\nvariant="+selected+"\nengine="+engine+"\ndigest="+
                  receipt.at("variants").at(selected).get<std::string>()+"\ncore_sha256="+files.at("codcoop_core.dll").get<std::string>()+
                  "\nloader_sha256="+files.at("ddraw.dll").get<std::string>()+"\n");
        } else if (Json::parse(Read(rp))!=receipt) throw std::runtime_error("installation changed since sealing");
        return true;
    } catch (const std::exception& e) { error=e.what(); return false; }
}
inline bool Prepare(const std::wstring& game,const std::string& variant,std::string& error) {
    if (variant!="cod1" && variant!="uo" && variant!="sp_improved" && variant!="united_fronts") {
        error="unknown campaign variant"; return false;
    }
    if (!Validate(game,false,error)) return false;
    try {
        Json manifest=Json::parse(Read(Resolve(game,"coop/variants.json")));
        Json receipt=Json::parse(Read(Resolve(game,"coop/install.json")));
        std::string engine;
        for (const auto& item:manifest.at("variants")) if (item.at("id")==variant) engine=item.at("engine");
        if (engine.empty()) throw std::runtime_error("campaign missing");
        Write(Resolve(game,"coop/profile.ini"),"[coop]\nprotocol="+std::to_string(PROTOCOL)+"\nvariant="+variant+"\nengine="+engine+
              "\ndigest="+receipt.at("variants").at(variant).get<std::string>()+
              "\ncore_sha256="+receipt.at("files").at("codcoop_core.dll").get<std::string>()+
              "\nloader_sha256="+receipt.at("files").at("ddraw.dll").get<std::string>()+"\n");
        return true;
    } catch (const std::exception& e) { error=e.what(); return false; }
}

inline std::wstring FullPath(const std::wstring& path) {
    DWORD needed=GetFullPathNameW(path.c_str(),0,nullptr,nullptr);
    if (!needed) throw std::runtime_error("cannot resolve backup path");
    std::wstring result(needed,L'\0');
    DWORD got=GetFullPathNameW(path.c_str(),needed,result.data(),nullptr);
    if (!got || got>=needed) throw std::runtime_error("invalid backup path");
    result.resize(got); return result;
}
inline bool PersonalPath(const std::wstring& path) {
    std::string lower=Lower(Utf8(path));
    std::replace(lower.begin(),lower.end(),'/', '\\');
    std::string base=lower.substr(lower.find_last_of('\\')+1);
    return base=="config.cfg" || base=="config_mp.cfg" || base=="uoconfig.cfg" || base=="autoexec.cfg" ||
           (base.size()>=4 && (base.substr(base.size()-4)==".svg" || base.substr(base.size()-4)==".sav")) ||
           lower.find("\\save\\")!=std::string::npos || lower.find("\\saves\\")!=std::string::npos || lower.find("\\players\\")!=std::string::npos;
}
inline bool Restore(const std::wstring& game,std::string& error) {
    try {
        Json journal=Json::parse(Read(Resolve(game,"coop/last-install-backup.json")));
        if (!journal.is_array()) throw std::runtime_error("invalid backup journal");
        std::wstring root=FullPath(game);
        while (root.size()>3 && (root.back()==L'\\' || root.back()==L'/')) root.pop_back();
        root+=L"\\";
        for (const auto& entry:journal) {
            auto path=FullPath(Wide(entry.at("path")));
            if (path.size()<=root.size() || _wcsnicmp(path.c_str(),root.c_str(),root.size())) throw std::runtime_error("backup destination escapes game folder");
            if (entry.at("existed").get<bool>()) {
                auto saved=FullPath(Wide(entry.at("backup")));
                if (saved.size()<=root.size() || _wcsnicmp(saved.c_str(),root.c_str(),root.size()) ||
                    GetFileAttributesW(saved.c_str())==INVALID_FILE_ATTRIBUTES) throw std::runtime_error("backup missing or outside game folder");
            }
        }
        for (auto it=journal.rbegin();it!=journal.rend();++it) {
            auto path=Wide(it->at("path"));
            if (PersonalPath(path)) continue;
            bool ok=it->at("existed").get<bool>() ? CopyFileW(Wide(it->at("backup")).c_str(),path.c_str(),FALSE)
                                                     : DeleteFileW(path.c_str()) || GetLastError()==ERROR_FILE_NOT_FOUND;
            if (!ok) throw std::runtime_error("backup restore failed: "+Utf8(path));
        }
        return true;
    } catch (const std::exception& e) { error=e.what(); return false; }
}

}
