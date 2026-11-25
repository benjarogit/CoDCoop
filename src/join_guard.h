#pragma once
#include <cstdint>

// Ventana de entrada (0.6.0). En cuanto un peer esta cargando recursos, la
// partida ya no es una sesion de un solo jugador: si el host muere, el SP abre
// la pantalla de muerte y pausa el servidor (cl_paused 1, SV_Frame no avanza).
// Los que estan cargando no reciben nunca el gamestate y la sala queda trabada.
// Evidencia: run/qa-dawnville-m14-sample1 (host con vida -52, pm_type 4,
// deadscreen, cl_paused 1 y el reloj del servidor clavado en 41408, mientras
// los tres peers seguian preguntando).
//
// La ventana se define por estado nativo, no por un temporizador de partida: un
// bootstrap de recursos activo y fresco. Un asiento ya reservado no cuenta: esa
// reserva sobrevive a una desconexion temporal, y el host volveria inmortal en
// una partida en solitario con asientos guardados. Fuera de la ventana valen las
// reglas normales de caido y muerte del coop.
namespace join_guard {
// 120 s cubren una transferencia lenta con cuatro clientes y la carga nativa
// posterior; un peer caido deja de sostener la ventana como maximo en ese plazo.
constexpr uint32_t PEER_STALE_MS = 120000;

inline bool Fresh(uint32_t now, uint32_t last) { return uint32_t(now - last) <= PEER_STALE_MS; }

inline bool Window(bool host, bool coopActive, bool bootPeerFresh)
{
    return host && !coopActive && bootPeerFresh;
}

// Solo un golpe mortal se recorta a 1; todo dano que deja vida se aplica entero.
inline int Survive(int healthAfterDamage) { return healthAfterDamage > 0 ? healthAfterDamage : 1; }
}
