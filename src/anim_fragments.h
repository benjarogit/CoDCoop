#pragma once
#include <array>
#include <algorithm>
#include <cstdint>
#include <cstring>
#include <map>
#include <vector>
namespace animwire {
constexpr int STATE_BYTES = 24, MAX_NODES = 4096, MAX_ENTITIES = 2048;
#pragma pack(push, 1)
struct Header { uint16_t entity, total, start, count; uint32_t stamp; };
#pragma pack(pop)
static_assert(sizeof(Header) == 12, "fixed animation fragment header");
class Assembler {
    struct Pending {
        uint32_t stamp = 0;
        uint16_t total = 0, received = 0;
        std::vector<uint8_t> bytes, seen;
    };
    std::array<uint32_t, MAX_ENTITIES> applied{};
    std::map<uint16_t, Pending> pending;
public:
    void Reset() { pending.clear(); applied.fill(0); }
    bool Feed(const Header& h, const uint8_t* data, size_t length, std::vector<uint8_t>& complete)
    {
        complete.clear();
        if (h.entity >= MAX_ENTITIES || h.total > MAX_NODES || h.start > h.total ||
            h.count > h.total - h.start || (h.count == 0 && h.total != 0) ||
            length != (size_t)h.count * STATE_BYTES || h.stamp <= applied[h.entity]) return false;
        auto found = pending.find(h.entity);
        if (found != pending.end() && h.stamp < found->second.stamp) return false;
        if (found == pending.end() && pending.size() >= 64) {
            // Lost fragments from actors that left visibility must not starve
            // every newly visible actor until the next map load.
            auto oldest = std::min_element(pending.begin(), pending.end(),
                [](const auto& a, const auto& b) { return a.second.stamp < b.second.stamp; });
            pending.erase(oldest);
        }
        Pending& p = pending[h.entity];
        if (p.stamp != h.stamp) {
            p = Pending{}; p.stamp = h.stamp; p.total = h.total;
            p.bytes.resize((size_t)h.total * STATE_BYTES); p.seen.resize(h.total);
        }
        if (p.total != h.total) return false;
        for (int i = 0; i < h.count; ++i) {
            int index = h.start + i;
            if (!p.seen[index]) { p.seen[index] = 1; ++p.received; }
            memcpy(p.bytes.data() + (size_t)index * STATE_BYTES, data + (size_t)i * STATE_BYTES, STATE_BYTES);
        }
        if (p.received != p.total) return false;
        // The engine apply routine consumes its original entity/count record.
        complete.resize(4 + p.bytes.size());
        memcpy(complete.data(), &h.entity, 2); memcpy(complete.data() + 2, &h.total, 2);
        if (!p.bytes.empty()) memcpy(complete.data() + 4, p.bytes.data(), p.bytes.size());
        applied[h.entity] = h.stamp;
        pending.erase(h.entity);
        return true;
    }
};
}
