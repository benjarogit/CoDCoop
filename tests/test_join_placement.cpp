#include "../src/join_placement.h"
#include <cassert>
#include <cstdio>

int main()
{
    // Sin entrada (joinedAt 0) no hay gracia.
    assert(!join_placement::GraceActive(1000, 0));
    // 3 s exactos: activa hasta 2999 ms, no en el limite.
    assert(join_placement::GraceActive(1000, 1000));
    assert(join_placement::GraceActive(3999, 1000));
    assert(!join_placement::GraceActive(4000, 1000));
    // Cuenta envolvente de 32 bits: la resta no se rompe al cruzar el wrap.
    assert(join_placement::GraceActive(0x80000000u, 0x80000000u - 2999));
    assert(!join_placement::GraceActive(0x80000000u, 0x80000000u - 3000));
    assert(join_placement::GraceActive(5, 0xffffffffu));

    // Colocacion: solo si esta mas lejos que el limite (2000 unidades en el juego).
    constexpr float LIMIT = 2000.0f;
    assert(!join_placement::NeedsPlacement(0.0f, LIMIT));
    assert(!join_placement::NeedsPlacement(LIMIT * LIMIT, LIMIT));
    assert(join_placement::NeedsPlacement(LIMIT * LIMIT + 1.0f, LIMIT));
    // Un punto en diagonal dentro del circulo no cuenta como lejos.
    const float inside = LIMIT * 0.7f;
    assert(!join_placement::NeedsPlacement(inside * inside + inside * inside, LIMIT));
    puts("join placement grace window and host-spot decision: PASS");
}
