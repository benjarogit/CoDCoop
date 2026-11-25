#pragma once

#include <cstdint>

// Un jugador que acaba de entrar (ClientBegin lo deja en el inicio del mapa) queda unos segundos sin recibir
// dano: los scripts del nivel ya dispararon contra "player" (el host) al verlo aparecer. Si entro lejos del
// host se lo coloca en su lugar antes del primer frame.
namespace join_placement {

constexpr uint32_t GRACE_MS = 3000;

// Ventana de gracia desde que alguien entro. Cuenta envolvente de 32 bits, como GetTickCount.
inline bool GraceActive(uint32_t now, uint32_t joinedAt) { return joinedAt != 0 && now - joinedAt < GRACE_MS; }

// El recien entrado esta lejos del host y hay que colocarlo (distancias al cuadrado, como Dist2).
inline bool NeedsPlacement(float distanceSquared, float limit) { return distanceSquared > limit * limit; }

}  // namespace join_placement
