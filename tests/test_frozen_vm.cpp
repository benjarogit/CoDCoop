#include "../src/frozen_vm.h"
#include <cassert>
#include <cstdio>

int main()
{
    // vmMain 10/11 del juego local congelado no corren; el resto si.
    assert(frozen_vm::BlockLocalGameCall(10, true, true));
    assert(frozen_vm::BlockLocalGameCall(11, true, true));
    assert(!frozen_vm::BlockLocalGameCall(9, true, true));
    assert(!frozen_vm::BlockLocalGameCall(12, true, true));
    // Sin congelar (host, joiner ya conectado) no se bloquea nada.
    assert(!frozen_vm::BlockLocalGameCall(10, false, true));
    assert(!frozen_vm::BlockLocalGameCall(11, false, true));
    // Otro VM (cgame, UI) no se toca.
    assert(!frozen_vm::BlockLocalGameCall(10, true, false));

    // G_ShutdownGame repone los estados locales solo si se guardaron y es el mismo VM.
    assert(frozen_vm::RestoreBeforeClose(1, true, true));
    assert(!frozen_vm::RestoreBeforeClose(1, true, false));
    assert(!frozen_vm::RestoreBeforeClose(1, false, true));
    assert(!frozen_vm::RestoreBeforeClose(2, true, true));
    assert(!frozen_vm::RestoreBeforeClose(10, true, true));
    puts("frozen local VM call block and shutdown restore: PASS");
}
