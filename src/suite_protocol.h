#pragma once
#include <cstdint>
#include <cstring>

namespace suite {
constexpr uint32_t PROTOCOL = 8;
constexpr uint8_t HELLO = 'H', READY = 'K', REJECT = 'V';
// The engine can block its first network pump for minutes while loading assets.
// A timeout measures a responsive search, not time spent inside that load.
template<typename Tick>
inline bool HandshakeExpired(Tick now, Tick& started, Tick lastPoll)
{
    if (!started || (lastPoll && uint32_t(now - lastPoll) > 10000)) started = now;
    return uint32_t(now - started) > 120000;
}
#pragma pack(push, 1)
struct Identity {
    uint32_t protocol;
    uint8_t engine;   // 1 = CoDSP, 2 = CoDUOSP
    uint8_t variant;  // manifest wire_id, never a pathname from a peer
    uint16_t flags;   // 1 = isolated QA, never compatible with regular installs
    uint8_t digest[32];
};
#pragma pack(pop)
static_assert(sizeof(Identity) == 40, "fixed wire identity");
inline bool Valid(const Identity& id)
{
    if (id.protocol != PROTOCOL || id.flags > 1 || id.variant < 1 || id.variant > 4) return false;
    if (id.engine != (id.variant == 1 ? 1 : 2)) return false;
    uint8_t nonzero = 0;
    for (uint8_t b : id.digest) nonzero |= b;
    return nonzero != 0;
}
inline const char* Difference(const Identity& local, const Identity& peer)
{
    if (peer.protocol != PROTOCOL) return "Different CoDCoop protocol; install the same suite version.";
    if (!Valid(peer)) return "Invalid campaign identity.";
    if (local.engine != peer.engine) return "Different game engine; select the same campaign variant.";
    if (local.variant != peer.variant) return "Different campaign variant; select the host's variant.";
    if (local.flags != peer.flags) return "A QA session cannot join a regular game.";
    if (memcmp(local.digest, peer.digest, sizeof local.digest)) return "Different gameplay files or runtime; repair the complete suite.";
    return nullptr;
}
}
