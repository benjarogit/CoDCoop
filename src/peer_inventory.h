#pragma once
#include <cstdint>
#include <cstring>
#include <type_traits>
#include "reload_delivery.h"
#include "peer_pose.h"
#include "peer_vitals.h"
#include "saved_role.h"

// Numeric loadout and separately guarded plain-player pose. No script
// references, HUD, vehicle links, pointers or complete playerState copies.
namespace peer_inventory {
constexpr unsigned SLOTS = 4, BYTES = 0x534 - 0x11c;
struct Endpoint { uint32_t address; uint16_t port; };
inline bool Same(Endpoint a, Endpoint b) { return a.address == b.address && a.port == b.port; }
struct Record {
    reload_delivery::Token world;
    Endpoint endpoint;
    uint32_t slot, size;
    uint64_t lease;
    char map[64];
    bool reserved, captured, installed;
    int weapon, viewmodel;
    uint8_t numeric[BYTES];
    peer_pose::Saved pose;
    peer_vitals::Saved vitals;
    uint8_t savedRole;
};
struct Store { Record slots[SLOTS]; };
static_assert(std::is_trivial<Store>::value && std::is_standard_layout<Store>::value,
              "inventory ownership must survive Core DLL reload");
inline bool Owner(const Record& r, unsigned slot, uint64_t session, Endpoint peer) {
    return r.reserved && slot > 0 && slot < SLOTS && r.slot == slot &&
           r.world.session == session && session && Same(r.endpoint, peer);
}
inline bool Current(const Record& r, unsigned slot, reload_delivery::Token world, Endpoint peer, const char* map) {
    return Owner(r,slot,world.session,peer) && reload_delivery::Same(r.world,world) && map && !std::strcmp(r.map,map);
}
inline bool ReservedDeparture(const Record& r,unsigned slot,reload_delivery::Token world,Endpoint peer,
                              const uint8_t* payload,unsigned bytes) {
    // A temporary map/reload disconnect retains its owner. Only an exact,
    // current-world intentional departure can release that inactive seat.
    return Owner(r,slot,world.session,peer)&&reload_delivery::Same(r.world,world)&&
           r.lease&&payload&&bytes==1&&payload[0]==1;
}
inline void Reserve(Record& r, unsigned slot, reload_delivery::Token world, Endpoint peer, const char* map, uint64_t lease=1) {
    r = {};
    if (!slot || slot >= SLOTS || !lease || !reload_delivery::Valid(world) || !peer.port || !map || std::strlen(map) >= sizeof r.map) return;
    r.world=world; r.endpoint=peer; r.slot=slot; r.lease=lease; r.reserved=true; std::strcpy(r.map,map);
}
inline void Transition(Record& r, reload_delivery::Token world, const char* map) {
    if (!r.reserved || r.world.session != world.session || !reload_delivery::Valid(world) || !map || std::strlen(map)>=sizeof r.map) { r={}; return; }
    r.world=world; std::strcpy(r.map,map); r.captured=r.installed=false; r.size=0;r.pose={};r.vitals={};r.savedRole=saved_role::Unknown;
}
inline bool Capture(Record& r, unsigned slot, reload_delivery::Token world, Endpoint peer, const char* map,
                    const void* bytes, unsigned size, int weapon, int viewmodel) {
    if (!Current(r,slot,world,peer,map) || !bytes || !size || size>BYTES) return false;
    std::memcpy(r.numeric,bytes,size); r.size=size; r.weapon=weapon; r.viewmodel=viewmodel;
    r.captured=true; r.installed=false; return true;
}
inline bool Restore(Record& r, unsigned slot, reload_delivery::Token world, Endpoint peer, const char* map,
                    void* bytes, unsigned size, int& weapon, int& viewmodel) {
    if (!Current(r,slot,world,peer,map) || !r.captured || !bytes || r.size!=size || size>BYTES) return false;
    std::memcpy(bytes,r.numeric,size); weapon=r.weapon; viewmodel=r.viewmodel; r.installed=true; return true;
}
}
