#pragma once

// Disparadores del nivel: como en el SP, solo los activa el host. Los scripts del nivel actuan sobre
// level.player, que en coop es el host; si un remoto pisa una zona de muerte, los morteros le caen al host
// donde este. El remoto tampoco recorre disparadores en su ClientThink (armas, botiquines y "usar" van por
// otro lado).
namespace trigger_filter {

// El slot 0 es el host y una entidad sin cliente del motor no es un jugador.
inline bool RemoteActivatorSlot(int slot, int maxClients, bool hasClient)
{
    return slot >= 1 && slot < maxClients && hasClient;
}

}  // namespace trigger_filter
