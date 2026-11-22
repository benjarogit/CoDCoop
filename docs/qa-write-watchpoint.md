# Owned-process write-watchpoint helper

`tools/qa_write_watchpoint.cpp` is an isolated 32-bit Windows debugger, tested
under Wine against its own standalone fixture. It does not select/start a game,
modify Core, patch game code/data, alter timeouts or kill Wine processes.
The actual corrupted-definition writer is **not identified** until a real game
watchpoint hit is captured.

Required explicit inputs: **Windows** PID, exact full executable path returned
by QueryFullProcessImageName, one aligned 4-byte target given either as an
absolute address or as module name plus RVA, expected current u32 value, time
budget1..120000ms and an owned output filename. Module+RVA is resolved through a
read-only module snapshot and logged with its base before any attach, so a
relocated image does not require a guessed address. It verifies PID/path,
no debugger, committed/readable address and exact initial value before attach.
It repeats identity/initial checks at the initial debug breakpoint, rejects any
existing DR0..DR3 or enabled hardware breakpoints on any target thread, then
saves every thread's original debug registers and arms DR0 for one write4 field.
Newly created threads are similarly checked/armed. Maximum256 concurrent
threads; conflicts/failures cause cleanup, not replacement of existing watches.

Only the first matching actual single-step/DR0 event is captured. Output is JSON
lines containing native thread/PID, value, general registers, module/full path
and base/RVA,16stack words and48code bytes starting16bytes before EIP. Hardware
write traps occur **after** the instruction: `ip_after_write` is the following
instruction, not a guessed writing-instruction address. Decode the retained
code against the exact module binary to identify that instruction. No string
or call-chain interpretation is fabricated from stack words.

DebugSetProcessKillOnExit(FALSE) is required immediately after attach. On hit,
timeout, Ctrl-C or refusal/error, the helper restores each surviving thread's
original DR0/1/2/3/6/7 and reads them back, continues a pending debug event and
calls DebugActiveProcessStop. It reports restoration/detach booleans explicitly;
failed cleanup returns5, never a successful attribution. Target exit is also
reported. No guarantee is made if the debugger helper itself is forcibly killed
before cleanup; kill-on-exit remains disabled so that does not intentionally
terminate the target.

Exit0=watchpoint hit with successful cleanup;3=refused identity/context/conflict;
4=bounded no-hit/target exit/interrupt with successful cleanup;5=error or cleanup
failure;2=invalid CLI/output. A timeout is not proof that a game field is safe.
The fixture verifies target execution continues and exits0, including after a
hit, timeout and refusal. A second attach after timeout checks that no stale
hardware register or debugger ownership was left behind.

Build and owned-fixture acceptance:

```sh
i686-w64-mingw32-g++ -std=c++17 -O2 -Wall -Wextra -Wpedantic -Werror -static tools/qa_write_watchpoint.cpp -o run/write-watchpoint-final/watch.exe
i686-w64-mingw32-g++ -std=c++17 -O2 -Wall -Wextra -Wpedantic -Werror -static tests/qa_write_watchpoint_fixture.cpp -o run/write-watchpoint-final/fixture.exe
python3 tools/qa_write_watchpoint_fixture.py --output run/write-watchpoint-final --prefix /owned/idle/Wine-prefix
```

The fixture covers main-thread and newly-created-thread write988→0xff000000,
module+RVA resolution of the same field, no-write timeout plus clean reattach,
wrong executable/process path, wrong PID, wrong initial value, pre-existing
hardware breakpoint and existing debugger.
All process launching in that fixture is limited to its own `fixture.exe`.

An actual game attach must use the coordinated existing owned game/prefix and
its measured Windows PID/address. Example argument shape (placeholders are
**not** an authorized selection or current measured address):

```sh
WINEPREFIX=/owned/game-prefix WINEDEBUG=-all wine /owned/watch.exe \
 --pid WINDOWS_PID --exe 'Z:\owned\game\CoDUOSP.exe' \
 --module uo_gamex86.dll --rva MEASURED_FIELD_RVA \
 --expected 988 --timeout-ms 90000 --output 'Z:\owned\evidence\watch.jsonl'
```

The absolute-address form remains available for the standalone fixture and for
fields outside a module. Never pass both forms.

Do not attach merely because a similarly named game is open. Preserve exact
module/source hashes and the original failure evidence separately. This helper
adds diagnostic visibility, not a production fix or gameplay acceptance.
