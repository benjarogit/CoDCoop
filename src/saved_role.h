#pragma once
#include <cstdint>
namespace saved_role {
enum : uint8_t { Unknown=0, Alive=1, Downed=2 };
inline bool Valid(uint8_t role){return role<=Downed;}
}
