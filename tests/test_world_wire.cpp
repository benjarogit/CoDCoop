#include "../src/world_wire.h"
#include <cassert>
#include <cstring>
#include <limits>

int main() {
    suite::Identity identity{};
    identity.protocol = suite::PROTOCOL;
    identity.engine = identity.variant = 1;
    identity.flags = 1; identity.digest[0] = 42;
    const uint8_t native[] = {1,0,0,0,23,0,77,88};
    reload_delivery::Token world{0x123456789abcdef0ULL, 7};
    auto packet = world_wire::Engine(identity, world, native, sizeof native);
    assert(packet.size() == world_wire::HEADER_BYTES + sizeof native);
    world_wire::Header header{};
    assert(world_wire::Parse(packet.data(), packet.size(), header));
    assert(header.type == world_wire::ENGINE && !suite::Difference(identity, header.identity));
    assert(world_wire::Current(header.world, world));
    assert(!std::memcmp(packet.data() + world_wire::HEADER_BYTES, native, sizeof native));
    for (size_t size = 0; size < world_wire::HEADER_BYTES; ++size)
        assert(!world_wire::Parse(packet.data(), size, header));
    packet[0] ^= 1; assert(!world_wire::Parse(packet.data(), packet.size(), header)); packet[0] ^= 1;
    assert(!world_wire::Parse(nullptr, packet.size(), header));
    assert(!world_wire::Parse(packet.data(), world_wire::UDP_LIMIT + 1, header));
    assert(!world_wire::Current({}, {}));
    assert(!world_wire::Current({world.session - 1, world.generation}, world));
    for (uint32_t generation = 1; generation < 20; ++generation) {
        auto replay = world; replay.generation = generation;
        assert(world_wire::Current(replay, world) == (generation == world.generation));
        assert(world_wire::Transition(replay, world) == (generation >= world.generation));
    }
    assert(!world_wire::Transition({world.session + 1, 8}, world));
    assert(world_wire::Engine(identity, {}, native, sizeof native).empty());
    assert(world_wire::Engine(identity, world, nullptr, 1).empty());
    assert(world_wire::Engine(identity, world, native, 0).empty());
    assert(world_wire::Engine(identity, world, native, std::numeric_limits<size_t>::max()).empty());
    auto bad = identity; --bad.protocol;
    assert(world_wire::Engine(bad, world, native, sizeof native).empty());
    std::vector<uint8_t> maximum(world_wire::UDP_LIMIT - world_wire::HEADER_BYTES, 0x5a);
    assert(world_wire::Engine(identity, world, maximum.data(), maximum.size()).size() == world_wire::UDP_LIMIT);
    maximum.push_back(0);
    assert(world_wire::Engine(identity, world, maximum.data(), maximum.size()).empty());
}
