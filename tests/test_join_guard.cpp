#include "../src/join_guard.h"
#include <cassert>
#include <cstdio>
int main()
{
    // Sin jugadores cargando no hay ventana: el host muere y el SP pausa como siempre.
    assert(!join_guard::Window(true, false, false));
    // Con un remote ya activo manda el coop normal (caido/levantar), no esta ventana.
    assert(!join_guard::Window(true, true, false));
    assert(!join_guard::Window(true, true, true));
    // Solo el host; un joiner local nunca queda protegido por esta regla.
    assert(!join_guard::Window(false, false, true));
    // Un bootstrap de recursos activo y fresco: hay alguien cargando.
    assert(join_guard::Window(true, false, true));

    // Frescura del bootstrap: 120 s, con cuenta envolvente de 32 bits.
    assert(join_guard::Fresh(1000, 1000));
    assert(join_guard::Fresh(121000, 1000));
    assert(!join_guard::Fresh(121001, 1000));
    assert(join_guard::Fresh(0x80000000u, 0x80000000u - join_guard::PEER_STALE_MS));
    assert(!join_guard::Fresh(0x80000000u, 0x80000000u - join_guard::PEER_STALE_MS - 1));
    assert(join_guard::Fresh(5, 0xffffffffu));  // ultimo paquete antes del wrap

    // Un golpe mortal se queda en 1; el resto del dano se aplica entero.
    assert(join_guard::Survive(1) == 1);
    assert(join_guard::Survive(37) == 37);
    assert(join_guard::Survive(0) == 1);
    assert(join_guard::Survive(-52) == 1);
    puts("join guard window, bootstrap freshness and lethal-damage clamp: PASS");
}
