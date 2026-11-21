#pragma once
#include "suite_protocol.h"
#include "reload_delivery.h"
#include <cstddef>
#include <cstring>
#include <vector>

namespace world_wire {
constexpr uint32_t CONTROL = 0xfffffffe;
constexpr uint8_t ENGINE = 'z';
constexpr size_t UDP_LIMIT = 65507;
#pragma pack(push, 1)
struct Header {
    uint32_t marker;
    uint8_t type;
    suite::Identity identity;
    reload_delivery::Token world;
};
#pragma pack(pop)
constexpr size_t HEADER_BYTES = sizeof(Header);
static_assert(HEADER_BYTES == 57, "fixed protocol9 frame header");
inline bool Parse(const void* data, size_t size, Header& header) {
    if (!data || size < HEADER_BYTES || size > UDP_LIMIT) return false;
    std::memcpy(&header, data, sizeof header);
    return header.marker == CONTROL;
}
inline bool Current(reload_delivery::Token candidate, reload_delivery::Token known) {
    return reload_delivery::Valid(candidate) && reload_delivery::Valid(known) &&
           reload_delivery::Same(candidate, known);
}
inline bool Transition(reload_delivery::Token candidate, reload_delivery::Token known) {
    return reload_delivery::AcceptClose(candidate, known);
}
inline std::vector<uint8_t> Engine(const suite::Identity& identity, reload_delivery::Token world,
                                   const void* data, size_t size) {
    if (!suite::Valid(identity) || !reload_delivery::Valid(world) || !data || !size || size > UDP_LIMIT - HEADER_BYTES)
        return {};
    std::vector<uint8_t> packet(HEADER_BYTES + size);
    Header header{CONTROL, ENGINE, identity, world};
    std::memcpy(packet.data(), &header, HEADER_BYTES);
    std::memcpy(packet.data() + HEADER_BYTES, data, size);
    return packet;
}
}
