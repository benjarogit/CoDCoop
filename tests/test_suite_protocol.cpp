#include "../src/suite_protocol.h"
#include <cassert>
#include <cstdio>
int main()
{
    suite::Identity good{};
    good.protocol = suite::PROTOCOL;
    good.engine = 2;
    good.variant = 4;
    good.digest[0] = 42;
    assert(suite::Valid(good));
    assert(!suite::Difference(good, good));
    auto peer = good;
    peer.protocol = 5; assert(suite::Difference(good, peer));
    peer.protocol = suite::PROTOCOL - 1; assert(suite::Difference(good, peer)); // previous development wire format
    peer = good; peer.engine = 1; assert(!suite::Valid(peer));
    peer = good; peer.variant = 3; assert(suite::Difference(good, peer));
    peer = good; peer.flags = 1; assert(suite::Difference(good, peer));
    peer = good; peer.digest[31] = 1; assert(suite::Difference(good, peer));
    peer = good; peer.flags = 2; assert(!suite::Valid(peer));
    peer = good; peer.digest[0] = 0; assert(!suite::Valid(peer));
    uint32_t started = 0;
    assert(!suite::HandshakeExpired(uint32_t(1000), started, uint32_t(0)));
    assert(!suite::HandshakeExpired(uint32_t(120000), started, uint32_t(119000)));
    assert(suite::HandshakeExpired(uint32_t(122000), started, uint32_t(121000)));
    started = 1000;
    assert(!suite::HandshakeExpired(uint32_t(181000), started, uint32_t(2000)));
    assert(started == 181000); // blocking map load starts a fresh responsive search
    started = 0xfffffff0u;
    assert(!suite::HandshakeExpired(uint32_t(100), started, uint32_t(90)));
    puts("protocol negative cases: PASS");
}
