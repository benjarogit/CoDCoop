#pragma once
#include <type_traits>
namespace peer_vitals {
struct Saved { bool valid;int health,maxHealth; };
static_assert(std::is_trivial<Saved>::value && std::is_standard_layout<Saved>::value,
              "owned native vitals must remain plain data");
inline bool Capture(Saved& saved,int health,int entityHealth,int maxHealth,bool plain) {
    saved={};
    if(!plain||health<=0||maxHealth<=0||entityHealth!=health)return false;
    saved.valid=true;saved.health=health;saved.maxHealth=maxHealth;return true;
}
}
