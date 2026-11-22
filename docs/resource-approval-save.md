# Saved resource approval manifest codec (isolated building block)

`src/resource_approval_save.h` does not install hooks, read or write files,
change `.coopowners` V2, or enable runtime capabilities. It adds a portable,
bounded approval manifest for a future native save lifecycle adapter. Missing
and legacy manifests remain explicitly unresolved; this is not SVG palette
migration or a completed save/resume implementation.

The binding contains the **completed native SVG SHA-256**, engine (`cod1` or
`uo`), registered variant/map, gameplay identity, package identity and exact
**saved** world-rule identity, each identity represented by a nonzero SHA-256.
The native adapter must derive these from verified completed data. Decoding
compares every field against its independently verified expected binding.
Engine/profile pairs are restricted to `cod1`/`cod1` and `uo` with `uo`,
`sp_improved` or `united_fronts`. Incomplete definitions may carry no media
references, including unregistered definitions.
No current kit-plan equality is required: current roster/kit resources must be
unioned separately after saved approvals are restored.

Version1 wire format is explicit little endian with no ABI padding: magic
`COOPRAP\0`, u16 version, zero u16 reserved flags, u32 total size, three
u8-length ASCII strings, four 32-byte binding hashes, u16 model/weapon counts,
sorted model entries (name + u16 source flags), ordered native weapon entries
(name + u8 registered/media-complete bits + u8 alternate index + five u16 model
references), and a SHA-256 trailer over all preceding bytes. References are
**approval-list positions**, not model IDs. Models are sorted lexicographically;
weapons retain their actual native index order. Five media references preserve
gun/hand/world/pickup/projectile roles; zero means absent. All names are canonical
ASCII; embedded NUL, non-ASCII/invalid UTF-8, uppercase model/weapon names,
duplicates, unknown flags, absent alternate/media targets and incomplete
registered definitions are rejected. Maximum512 models,127 weapons,63-byte
names,65536 total bytes. Full source flags are retained.

`Capture` requires a complete, current first-use Store, including an actually
observed complete native definition count and cache proofs. It copies no model
IDs, cache pointers/epochs, runtime session/world IDs, peer receipts, ACKs,
transactions, ownership leases or inventory. `Encode` builds privately and
updates output/length only on success. `Decode` verifies the actual SHA callback,
strict grammar/exact consumption and binding before assigning its output.
Every failure leaves the caller's output unchanged. SHA is integrity binding,
not authentication of an untrusted package or substitute for ownership checks.

Recommended future adapter sequence:

1. Compose with existing native FS observers. On successful completed native
   save/close, hash actual SVG bytes, bind verified package/gameplay/saved rules,
   capture the complete registry, encode and atomically publish a separate
   manifest. Failed/partial saves publish no successful manifest. Preserve
   existing `.coopowners` V2 writes and native inventory/pose/vitals handling.
2. On load, hash the exact completed SVG and validate saved context independently;
   call `Decode` with that binding. Missing/version/invalid/digest/context failure
   is explicit unresolved, never permission to drop names or map them to0.
3. Start a genuinely new native registry/cache lifecycle. `RestoreApprovals`
   requires an entirely zeroed destination Store, matching map and a supplied
   **native adapter fresh-lifecycle proof**. That callback must reject the old
   active world's reused context; this codec cannot observe native cache epochs.
   Restore adds approval names/source flags only. Every cache stamp, bound ID,
   native weapon registration/observed count and peer receipt remains zero.
   Saved weapon metadata remains in `Manifest` solely for subsequent native
   ordered-definition/item/alternate/media verification, not a fake registration.
4. Reconstruct actual normal native item/model/renderer state and native save
   old-ID→new-ID mapping; union any newly confirmed kit resources separately.
   Re-capture, verify and seal the new resource contract before peer readiness.
   No prior cache/ACK/lease is restored; no ID eviction/recycling/width changes.

The standalone fixture uses actual OpenSSL EVP SHA-256 on Linux and Windows
CryptoAPI SHA-256 under32-bit Wine, including the independent standard `abc`
known-answer vector. Both produce the same canonical manifest bytes/hash.
Tests cover every truncation and single-byte corruption, re-signed structural
negatives, exact context mismatches, failure output preservation, duplicate/
source/alternate/media errors, maximum counts/lengths and fresh-only restoration.

```sh
g++ -std=c++17 -O1 -Wall -Wextra -Wpedantic -Werror -g -fsanitize=address,undefined -fno-omit-frame-pointer tests/test_resource_approval_save.cpp -lcrypto -o run/resource-approval-save/test-save-asan
run/resource-approval-save/test-save-asan
i686-w64-mingw32-g++ -std=c++17 -O2 -Wall -Wextra -Wpedantic -Werror -static tests/test_resource_approval_save.cpp -ladvapi32 -o run/resource-approval-save/test-save-windows.exe
# Use an owned idle Wine prefix, no game processes or global wineserver changes.
WINEPREFIX=/owned/prefix WINEDEBUG=-all wine run/resource-approval-save/test-save-windows.exe
```

These are codec tests, not native gameplay, native Windows hardware, filesystem
atomic-save, dense-map migration or cross-process saved-owner acceptance.
