#include "../src/cinematics.h"
#include <cassert>
#include <cstdio>
#include <string>
namespace cc = campaign_cinematics;
static int forwards, notices;
static std::string last;
static intptr_t Original(const intptr_t*) { ++forwards; return 37; }
static void Notice(const char* name) { ++notices; last = name; }
static intptr_t LaterPlugin(const intptr_t* args) { return cc::Intercept(args); }
int main()
{
    char name[cc::NAME_BYTES];
    assert(cc::Newer(1, 0));
    assert(!cc::Newer(0, 0));
    assert(!cc::Newer(4, 4)); // received movie / reload cutoff, including same-map checkpoints
    assert(!cc::Newer(3, 4));
    assert(cc::Newer(5, 4));
    assert(cc::Newer(1, 0xffffffff)); // counter wrap skips zero
    assert(cc::Parse("cinematic cod_end.roq 0 force", name));
    assert(std::string(name) == "cod_end.roq");
    assert(cc::Parse("cinematic uo_intro.bik 0 force\n", name));
    for (auto command : {"cinematic ../cod_end.roq 0 force", "cinematic video/cod_end.roq 0 force",
            "cinematic cod_end.roq 0 force\nquit", "cinematic cod_end.roq;quit 0 force",
            "cinematic cod_end.roq 1 force", "cinematic cod_end.roq", "cinematic x 0 force"})
        assert(!cc::Parse(command, name));
    cc::Syscall first = Original;
    assert(cc::Sync(&first, true, Notice));
    intptr_t args[] = {0x29, 2, reinterpret_cast<intptr_t>("cinematic cod_end.roq 0 force")};
    assert(first(args) == 37 && forwards == 1 && notices == 1 && last == "cod_end.roq");
    args[0] = 0x2c; first(args); assert(forwards == 2 && notices == 1);
    args[0] = 0x29; args[1] = 0; first(args); assert(forwards == 3 && notices == 1);
    assert(cc::Sync(&first, false, nullptr));
    assert(first == Original); args[1] = 2; first(args); assert(notices == 1);
    // A new game VM replaces the allocation; detach only its active slot.
    cc::Syscall second = Original;
    assert(cc::Sync(&second, true, Notice));
    second(args); assert(notices == 2);
    // A plugin installed after us may still forward through Intercept. Never
    // re-chain that wrapper into itself, and report that unload is unsafe.
    second = LaterPlugin;
    assert(!cc::Sync(&second, true, Notice));
    assert(!cc::Sync(&second, false, nullptr));
    int priorForwards = forwards;
    assert(second(args) == 37 && forwards == priorForwards + 1 && notices == 2);
    second = cc::Intercept;
    cc::Sync(&second, false, nullptr);
    assert(second == Original);
    assert(cc::Sync(&second, true, Notice));
    second = Original; // engine recreated its VM at the same allocation
    assert(cc::Sync(&second, true, Notice));
    second(args); assert(notices == 3);
    assert(cc::Sync(&second, false, nullptr));
    puts("script cinematic origin, command safety, forwarding, role and VM lifetime: PASS");
}
