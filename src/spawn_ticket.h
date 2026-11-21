#pragma once
#include <cstdint>
namespace spawn_ticket {
struct Session { uint32_t a,b,c; };
// Both native Map_f implementations normalize the .svg argument test to
// SpawnServer(map, savedGame): 0=fresh mission, 1=native saved-game load.
inline bool FreshMission(int savedGame) {return savedGame==0;}
inline Session Split(uint64_t nonce) {return {uint32_t(nonce&0x7fffffff),uint32_t((nonce>>31)&0x7fffffff),uint32_t(nonce>>62)};}
inline bool Next(uint32_t& counter,uint32_t& ticket) {
    if(counter>=0x7fffffff) return false;
    ticket=++counter;return true;
}
}
