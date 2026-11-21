#include "../src/reload_delivery.h"
#include <cassert>
#include <cstdint>

int main() {
    using namespace reload_delivery;
    Pending pending{{123, 4}, 0, true, false};
    assert(Due(pending, 0));
    Sent(pending, 0);
    assert(!Due(pending, 499));
    assert(Due(pending, 500));
    assert(!Acknowledge(pending, {124, 4}));
    assert(!Acknowledge(pending, {123, 3}));
    assert(pending.active);
    assert(Acknowledge(pending, {123, 4}));
    assert(!Due(pending, 10000));
    assert(!Acknowledge(pending, {123, 4}));
    pending = {{123, 5}, UINT32_MAX - 100, true, true};
    assert(!Due(pending, 100));
    assert(Due(pending, 400));
    assert(Newer({123, 5}, {123, 4}));
    assert(!Newer({123, 4}, {123, 4}));
    assert(!Newer({123, 3}, {123, 4}));
    assert(!Newer({124, 5}, {123, 4}));
    assert(!Newer({123, 0}, {123, UINT32_MAX}));
    assert(Newer({123, 1}, {123, UINT32_MAX}));
    assert(AcceptClose({123, 4}, {123, 4}));
    assert(AcceptClose({123, 5}, {123, 4}));
    assert(!AcceptClose({124, 4}, {123, 4}));
    assert(!AcceptClose({123, 3}, {123, 4}));
    assert(!AcceptClose({0, 0}, {0, 0}));
}
