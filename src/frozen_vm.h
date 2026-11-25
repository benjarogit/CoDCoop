#pragma once

// El juego local del que se une no corre (servidor congelado), pero el cgame le pide vmMain 10 y 11 con el
// tiempo libre de CPU: seguian vivos los scripts y vehiculos del mapa local. Ademas, M_ENTS escribe los
// estados de las entidades del host sobre los del mapa local (tipo incluido), y al cerrar ese mapa
// (G_ShutdownGame, vmMain 1) el juego buscaba el arbol de un actor que no existe y se caia. Los estados
// locales se guardan al conectarse y se reponen antes de cerrar.
namespace frozen_vm {

// vmMain 10/11 (marcos de cliente) no llegan al juego local congelado; el resto sigue.
inline bool BlockLocalGameCall(int cmd, bool frozen, bool sameVm) { return frozen && sameVm && (cmd == 10 || cmd == 11); }

// G_ShutdownGame sobre el mapa local: reponer los estados que M_ENTS piso.
inline bool RestoreBeforeClose(int cmd, bool sameVm, bool saved) { return cmd == 1 && sameVm && saved; }

}  // namespace frozen_vm
