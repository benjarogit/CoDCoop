#pragma once
#include <cstdio>
#include <cstdint>
#include <cstring>
#include <vector>
namespace campaign_cinematics {
inline uint16_t Zip16(const unsigned char* p) { return uint16_t(p[0]) | uint16_t(p[1]) << 8; }
inline uint32_t Zip32(const unsigned char* p) { return uint32_t(Zip16(p)) | uint32_t(Zip16(p + 2)) << 16; }
// Membership check only: never decompress untrusted media or scan file payloads.
// Bounded standard PK3 central directory; ZIP64/multidisk are not game packages.
inline bool PackageHasMovie(const char* path, const char* member)
{
    FILE* f = fopen(path, "rb");
    if (!f) return false;
    struct Close { FILE* f; ~Close() { fclose(f); } } close{f};
    if (fseek(f, 0, SEEK_END)) return false;
    long length = ftell(f);
    if (length < 22) return false;
    long tailSize = length < 65557 ? length : 65557;
    std::vector<unsigned char> tail(static_cast<size_t>(tailSize));
    if (fseek(f, length - tailSize, SEEK_SET) || fread(tail.data(), 1, tail.size(), f) != tail.size()) return false;
    for (long at = tailSize - 22; at >= 0; --at) {
        const unsigned char* e = tail.data() + at;
        if (Zip32(e) != 0x06054b50 || at + 22 + Zip16(e + 20) != tailSize) continue;
        uint32_t bytes = Zip32(e + 12), offset = Zip32(e + 16);
        uint16_t count = Zip16(e + 10);
        if (Zip16(e + 4) || Zip16(e + 6) || Zip16(e + 8) != count ||
            bytes > 8 * 1024 * 1024 || uint64_t(offset) + bytes > uint64_t(length - tailSize + at)) return false;
        std::vector<unsigned char> directory(bytes);
        if (fseek(f, static_cast<long>(offset), SEEK_SET) ||
            fread(directory.data(), 1, bytes, f) != bytes) return false;
        size_t pos = 0;
        for (unsigned n = 0; n < count; ++n) {
            if (pos + 46 > directory.size()) return false;
            const unsigned char* item = directory.data() + pos;
            if (Zip32(item) != 0x02014b50) return false;
            size_t name = Zip16(item + 28), extra = Zip16(item + 30), comment = Zip16(item + 32);
            if (pos + 46 + name + extra + comment > directory.size()) return false;
            if (name == strlen(member)) {
                bool same = true;
                for (size_t k = 0; k < name; ++k) {
                    unsigned char a = item[46 + k], b = static_cast<unsigned char>(member[k]);
                    if (a >= 'A' && a <= 'Z') a += 'a' - 'A';
                    if (b >= 'A' && b <= 'Z') b += 'a' - 'A';
                    if (a != b) { same = false; break; }
                }
                if (same && Zip32(item + 24) > 0) return true;
            }
            pos += 46 + name + extra + comment;
        }
        return false;
    }
    return false;
}
}
