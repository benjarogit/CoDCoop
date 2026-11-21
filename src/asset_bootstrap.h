#pragma once
#include "qa_renderer_preload.h"
#include <array>
#include <cstdint>
#include <cstring>
#include <cstdio>

// Transport-independent approval transfer. No world-model IDs, allocators,
// executable paths or console commands are accepted here. The caller binds every packet to
// world_wire's current session/generation and verifies SHA256 before committing.
namespace asset_bootstrap {
constexpr unsigned MAX_NAMES = qa_preload::MAX_NAMES;
constexpr unsigned MAX_WEAPONS = 127; // UO IDs1..127; caller additionally enforces the engine's own limit
constexpr unsigned MAX_ENTRIES = MAX_NAMES + MAX_WEAPONS;
constexpr unsigned MAX_MODEL_BYTES = qa_preload::MAX_BYTES;
constexpr unsigned MAX_BYTES = 49152;
constexpr unsigned PART_BYTES = 1024;
constexpr unsigned MAX_PARTS = (MAX_BYTES + PART_BYTES - 1) / PART_BYTES;
#pragma pack(push, 1)
struct Description {
    uint32_t serial, bytes;
    uint16_t names, parts;
    uint8_t sha256[32];
    char map[64];
};
#pragma pack(pop)
static_assert(sizeof(Description) == 108, "fixed resource description");
inline bool ValidMap(const char (&map)[64]) {
    size_t length = 0;
    while (length < 64 && map[length]) {
        unsigned char c = (unsigned char)map[length++];
        if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
              (c >= '0' && c <= '9') || c == '_' || c == '-')) return false;
    }
    if (!length || length >= 64) return false;
    for (size_t i = length + 1; i < 64; ++i) if (map[i]) return false;
    return true;
}
inline bool Valid(const Description& value) {
    uint8_t nonzero = 0;
    for (uint8_t byte : value.sha256) nonzero |= byte;
    return value.serial && value.bytes && value.bytes <= MAX_BYTES && value.names && value.names <= MAX_ENTRIES &&
           value.parts == (value.bytes + PART_BYTES - 1) / PART_BYTES && nonzero && ValidMap(value.map);
}
inline bool Encode(const std::vector<std::string>& input, std::string& output, uint16_t& count) {
    if (input.empty() || input.size() > MAX_NAMES) return false;
    std::vector<std::string> names;
    for (auto name : input) {
        if (!qa_preload::ValidName(name)) return false;
        for (char& c : name) if (c >= 'A' && c <= 'Z') c = char(c + ('a' - 'A'));
        names.push_back(name);
    }
    std::sort(names.begin(), names.end());
    names.erase(std::unique(names.begin(), names.end()), names.end());
    std::string text;
    for (const auto& name : names) text += name + '\n';
    if (text.empty() || text.size() > MAX_MODEL_BYTES) return false;
    output = std::move(text); count = (uint16_t)names.size(); return true;
}
inline bool Decode(const uint8_t* data, unsigned size, unsigned count, std::vector<std::string>& output) {
    if (!data || !size || size > MAX_MODEL_BYTES || !count || count > MAX_NAMES) return false;
    std::string text((const char*)data, size);
    std::vector<std::string> names;
    if (!qa_preload::Parse(text, names) || names.size() != count) return false;
    std::string canonical; uint16_t encodedCount = 0;
    if (!Encode(names, canonical, encodedCount) || canonical != text || encodedCount != count) return false;
    output = std::move(names); return true;
}

struct Weapon {
    uint8_t index;
    std::string name;
    bool registered;
};
struct Resources {
    std::vector<std::string> models;
    // Complete native index table, not an alphabetically sorted set. Registration
    // order is not assumed to be identical merely because assets have the same names.
    std::vector<Weapon> weapons;
};
inline bool ValidWeaponName(const std::string& name) {
    if (name.empty() || name.size() >= 64 || name == "none") return false;
    for (unsigned char c : name)
        if (!((c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '_' || c == '-')) return false;
    return true;
}
inline bool EncodeResources(const Resources& input, std::string& output, uint16_t& count) {
    std::string modelText; uint16_t models = 0;
    if (!Encode(input.models, modelText, models) || input.weapons.size() > MAX_WEAPONS) return false;
    std::string text = "codcoop-assets-1\n";
    size_t start = 0;
    while (start < modelText.size()) {
        size_t end = modelText.find('\n', start);
        text += "m\t" + modelText.substr(start, end-start) + '\n'; start = end+1;
    }
    std::vector<std::string> seen;
    unsigned expected = 1;
    for (const auto& weapon : input.weapons) {
        if (weapon.index != expected++ || !ValidWeaponName(weapon.name) ||
            std::find(seen.begin(),seen.end(),weapon.name) != seen.end()) return false;
        seen.push_back(weapon.name);
        char prefix[16];
        std::snprintf(prefix,sizeof prefix,"w\t%03u\t%u\t",unsigned(weapon.index),weapon.registered ? 1u : 0u);
        text += prefix + weapon.name + '\n';
    }
    if (text.size() > MAX_BYTES) return false;
    output = std::move(text); count = uint16_t(models + input.weapons.size()); return true;
}
inline bool DecodeResources(const uint8_t* data, unsigned size, unsigned count, Resources& output) {
    if (!data || !size || size > MAX_BYTES || !count || count > MAX_ENTRIES) return false;
    const std::string text((const char*)data,size), prefix="codcoop-assets-1\n";
    if (text.compare(0,prefix.size(),prefix) || text.back() != '\n') return false;
    Resources decoded;
    size_t start=prefix.size(); bool weaponSection=false;
    while (start < text.size()) {
        size_t end=text.find('\n',start);
        const auto line=text.substr(start,end-start); start=end+1;
        if (line.compare(0,2,"m\t")==0 && !weaponSection) {
            if (decoded.models.size() >= MAX_NAMES) return false;
            decoded.models.push_back(line.substr(2));
        } else if (line.size() > 8 && line.compare(0,2,"w\t")==0) {
            weaponSection=true;
            if (decoded.weapons.size() >= MAX_WEAPONS || line[5]!='\t' || line[7]!='\t' ||
                (line[6]!='0' && line[6]!='1')) return false;
            unsigned index=0;
            for(unsigned i=2;i<5;++i) {
                if(line[i]<'0'||line[i]>'9') return false;
                index=index*10+unsigned(line[i]-'0');
            }
            if(index>MAX_WEAPONS) return false;
            decoded.weapons.push_back({uint8_t(index),line.substr(8),line[6]=='1'});
        } else return false;
    }
    std::string canonical; uint16_t entries=0;
    if (!EncodeResources(decoded,canonical,entries) || canonical != text || entries != count) return false;
    output=std::move(decoded); return true;
}

// Call only after normal native registration has finished. Do not remap native
// indices, overwrite WeaponDefs or grant ready on an unverified name-only union.
// The caller also compares the existing suite gameplay identity and world token.
template<class ReadName, class ReadRegistered>
inline bool MatchWeapons(const Resources& resources, unsigned nativeCount, unsigned engineLimit,
                         ReadName readName, ReadRegistered readRegistered) {
    if (!engineLimit || engineLimit>128 || nativeCount>=engineLimit || nativeCount!=resources.weapons.size()) return false;
    unsigned expected=1;
    for(const auto& weapon : resources.weapons) {
        if(weapon.index!=expected++ || !ValidWeaponName(weapon.name) ||
           readName(weapon.index)!=weapon.name || bool(readRegistered(weapon.index))!=weapon.registered) return false;
    }
    return true;
}
class Receiver {
    Description description{};
    std::array<uint8_t, MAX_BYTES> data{};
    std::array<bool, MAX_PARTS> received{};
    unsigned receivedParts = 0;
    bool present = false;
    void ClearParts() { received.fill(false); receivedParts = 0; }
public:
    void Reset() { description = {}; present = false; ClearParts(); }
    bool Start(const Description& next) {
        if (!Valid(next)) return false;
        if (present && next.serial == description.serial)
            return !std::memcmp(&next, &description, sizeof next); // identical retries retain received parts
        if (present && int32_t(next.serial - description.serial) <= 0) return false;
        description = next; present = true; ClearParts(); return true;
    }
    bool Add(uint32_t serial, unsigned part, const uint8_t* bytes, unsigned size) {
        if (!present || serial != description.serial || part >= MAX_PARTS || part >= description.parts || !bytes) return false;
        unsigned offset = part * PART_BYTES;
        unsigned expected = std::min(PART_BYTES, description.bytes - offset);
        if (size != expected) return false;
        if (received[part]) return !std::memcmp(data.data() + offset, bytes, size);
        std::memcpy(data.data() + offset, bytes, size); received[part] = true; ++receivedParts; return true;
    }
    bool Ready() const { return present && receivedParts == description.parts; }
    const Description& Header() const { return description; }
    template<class Verify> bool Finish(std::vector<std::string>& names, Verify verifySha256) {
        if (!Ready()) return false;
        std::vector<std::string> decoded;
        if (!verifySha256(data.data(), description.bytes, description.sha256) ||
            !Decode(data.data(), description.bytes, description.names, decoded)) {
            ClearParts(); return false; // a complete retransmission can recover from corrupt data
        }
        names = std::move(decoded); return true;
    }
    template<class Verify> bool FinishResources(Resources& resources, Verify verifySha256) {
        if (!Ready()) return false;
        Resources decoded;
        if (!verifySha256(data.data(),description.bytes,description.sha256) ||
            !DecodeResources(data.data(),description.bytes,description.names,decoded)) {
            ClearParts(); return false;
        }
        resources=std::move(decoded); return true;
    }
};
}
