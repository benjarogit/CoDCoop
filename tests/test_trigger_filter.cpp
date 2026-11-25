#include "../src/trigger_filter.h"
#include <cassert>
#include <cstdio>

int main()
{
    constexpr int MAX = 4;
    // El host (slot 0) siempre activa sus disparadores.
    assert(!trigger_filter::RemoteActivatorSlot(0, MAX, true));
    // Un remoto con cliente del motor no los activa.
    assert(trigger_filter::RemoteActivatorSlot(1, MAX, true));
    assert(trigger_filter::RemoteActivatorSlot(3, MAX, true));
    // Una entidad sin cliente no es un jugador: no se filtra.
    assert(!trigger_filter::RemoteActivatorSlot(1, MAX, false));
    // Slots fuera de rango no se tocan.
    assert(!trigger_filter::RemoteActivatorSlot(-1, MAX, true));
    assert(!trigger_filter::RemoteActivatorSlot(MAX, MAX, true));
    assert(!trigger_filter::RemoteActivatorSlot(99, MAX, true));
    puts("host-only level trigger filter: PASS");
}
