#pragma once
#include <cstdint>

namespace reload_delivery {
#pragma pack(push, 1)
struct Token { uint64_t session; uint32_t generation; };
#pragma pack(pop)
static_assert(sizeof(Token) == 12, "fixed reload token");
inline bool Valid(Token value) { return value.session && value.generation; }
inline bool Same(Token a, Token b) {
    return a.session == b.session && a.generation == b.generation;
}
inline bool Newer(Token candidate, Token known) {
    return Valid(candidate) && candidate.session == known.session &&
           int32_t(candidate.generation - known.generation) > 0;
}
inline bool AcceptClose(Token candidate, Token known) {
    return Valid(candidate) && Valid(known) && (Same(candidate, known) || Newer(candidate, known));
}
struct Pending {
    Token token;
    uint32_t sent;
    bool active;
    bool attempted;
};
inline bool Due(const Pending& pending, uint32_t now) {
    return pending.active && (!pending.attempted || uint32_t(now - pending.sent) >= 500);
}
inline void Sent(Pending& pending, uint32_t now) {
    pending.sent = now; pending.attempted = true;
}
inline bool Acknowledge(Pending& pending, Token token) {
    if (!pending.active || !Same(token, pending.token)) return false;
    pending.active = false;
    return true;
}
}
