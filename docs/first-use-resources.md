# Isolated first-use resource helpers

`src/first_use_resources.h` is an **unwired policy/POD implementation**. It
does not patch Core, change a feature mask, alter a protocol, call an engine
function, write files, or prove full UF campaign capacity. The original native
audit is `run/approved-first-use-review/FINDINGS.md`.

The Store is58248 bytes on the tested Linux and MinGW32 builds. It has512
fixed64-byte model names,127 ordered native weapon definitions with alternate
indices and five model references,255 physical ID owners and four resource
receipts. No native/STL pointers survive DLL reload. The owning Core State
must bump its version/size before inclusion; no old-State layout continuity
is implied.

## Decisions and invariants

- `Pure` can return `DEFERRED_ZERO` only for one of six verified discard-only
  call sites, while loading, after an actual current native-cache callback.
  The callback must load/query the normal engine cache; a persisted pointer
  or a file containing a name is not proof. Failure returns `NORMAL_NATIVE`.
- The raw pinned Game SHA is9fd3665b…7bbeb32e. All20 caller fingerprints and
  the native cache/CS publication tail have relocation-aware byte checks.
  The ModelIndex entry must be original or an exact owned eight-byte jump.
  An unrecognized real binding ABI stops the registry rather than inventing0.
- Fourteen actual-use return paths retain real IDs. In-load calls and the
  native save-name remap are `NORMAL_NATIVE`. Outside load, an approved,
  currently cached Host model can yield `BIND_CACHED_EMPTY`; the caller must
  publish normally and successfully `Commit` before returning its ID.
- Native CS is read to find the first empty slot. Store bookkeeping never
  declares a native slot empty. Bound IDs are never evicted, reclaimed or
  changed within a world. Native drift or partial publication stops the Store.
- `Actual` explicitly handles `CoreHeldGun`; a deferred held-gun world model
  must receive an ID, rather than disappear through the old lookup-only path.
- `NativeValue` refuses numeric results for NORMAL_NATIVE, WAIT, STOP or a
  pending publication. Only verified pure calls may return0. Actual-use
  adapters must handle other decisions explicitly, never `return decision.id`.
- Context fences session/world, native init serial, Game and renderer epochs,
  map and Host/Peer authority. A same-world epoch change cannot call Begin to
  clear/reuse IDs. It needs the explicit lifecycle/rehandshake/reload path.
- Source flags distinguish original pure precache, actual native use,
  confirmed kit, authored world, verified peer contract and verified save
  manifest. Zero/unknown flags and unbounded names/counts are rejected.

## Recommended native integration sequence — not yet implemented

### 1. Begin before the first relevant native GAME_INIT call

Use the existing pre-VM seam in `qa_deferred_models.inc::QABeforeVM`, currently
shared by production preservation/bootstrap lifecycle. Preserve its existing
`PreservationBeforeInit`, world witness, saved-load HookLoad rearm,
inventory initialization and body-ownership work. Do not replace it wholesale.

Obtain a verified current Game module/PE image and raw-file SHA; construct a
short-lived CodeView from that actual readable image, its true loaded base and
the known owned hook target. Verify NativeLayout and all20 call-site patterns
before enabling the wrapper. Recheck after same-base module replacement.

`Context.world` is the authoritative Coop generation, **not** a guessed
pre-GAME_INIT `sv_serverid`. Bind the original native init serial and completed
world association exactly as the current preservation lifecycle does. Native
SV ID can change late on a fast restart. Cache epoch identifiers must come
from proven native cache/reset lifecycle; never reuse a base address as an
epoch. A reserved renderer-cycle identifier is not a cache proof until the
adapter observes that actual registration cycle and validates cached entries.

Begin once for the new authoritative world/init. A warm world whose original
precache calls were not observed is not a complete registry automatically;
use a proven reconstruction or ordinary reload. No fake fresh-init stamp.

### 2. Preserve the native ModelIndex and item ABI

The UO wrapper receives name inEBX and returns ID inEAX, with the original
return PC identifying the caller. Resolve Pure only for the exact six sites.
Other known sites use Actual, and unknown sites preserve the normal native
call. Original missing-asset, loading and capacity errors remain meaningful.

During initial load, run the original binding function, then record successful
Host bindings using `ObserveNativeBinding` with real CS and cached-slot-name
checks. This includes actual NPC bodies, attachments, pickups, viewhands and
the native save-name remap. No pointer is stored in the helper.

`resource_bootstrap.inc::BootNativeItems` must still forward its original
native routine once, retain its existing fingerprint/retired-wrapper checks,
then register all required native items/alternates in their original order
before GSC. Passing bool0 or skipping an item is not the optimization: only
the proven discarded model-index reservations are cached without physical IDs.

For a late Host `BIND_CACHED_EMPTY`, recheck the actual empty CS and freshly
validated XModel in the same context, then use the fingerprinted native layout:
write Game+0xd2e70[slot], call original SV_SetConfigstring(32+slot,name), set
Game+0x307f2c dirty1, and Commit against the actual CS/cache result. Do not set
initializing, disable strict renderer checks or overwrite a nonempty slot.
Any failed/partial publication ends the registry; preserve diagnostic state.

The Core HostBody/WeaponModelName/MakeBodyDObj path must request this actual
binding before constructing negative-ID gun parts. It must not silently return
an empty weapon name because a valid approved cache entry lacks an ID.

### 3. Capture complete resources and normal renderer registration

At the current BootExport/normal pre-EndRegistration seams, include original
pure-precache approvals, actual CS/DObjs, all approved owner kit/pickup/support
media and native registered weapon gun/hand/world/pickup/projectile names.
Preserve original optional gear and NPC resources. Source approval is not
restricted to models currently referenced on-screen.

Define the full native index→canonical-name/registered/alternate table. Each
registered definition needs `mediaComplete=true` and model references for all
its actual non-null model fields. Unregistered definitions may explicitly have
unresolved media; registration requires completing it before readiness. The
adapter must obtain these facts from actual definitions, not party JSON.
ObserveDefinitionCount must independently read the native count (including a
legitimate0); Complete requires that exact count and every contiguous definition.
Defining only1–2 entries cannot certify an actual94-definition table.

Before forwarding native EndRegistration, use normal native server XModel
cache and normal renderer R_RegisterModel(name,7), then validate both actual
cache lifetimes and mark their proofs. Do not assume a name in one private
array implies a valid model in the other cache. Preserve BootBeforeEnd's
existing check that renderer preload did not consume native model CS.

Only Complete→CaptureContract→canonical SHA verification→Seal can publish an
initial resource receipt. The SHA callback must include the complete canonical
model/ordered weapon/alternate/media description and trusted world/rule/plan
scope. Existing asset-bootstrap encoding does not by itself newly certify the
extra alternate/media metadata; native/wire integration must explicitly bind
and verify it. Merely calling Seal with a digest supplied by a peer is wrong.

### 4. Joiner local IDs and Host mapping are separate namespaces

Use a Peer Context from the beginning of its local GAME_INIT. Preserve normal
local actual-use IDs during that bootstrap, but **do not** call the Host-only
ObserveNativeBinding to record them as Host IDs. Native RNG/first-use order can
differ, so temporary local ID9 can legitimately become authoritative Host ID1.

Before initial Host CS replacement, keep the existing native DObj detach/sync
barrier and native actor/tree ownership. ArmPeerMap only through a callback
that proves that barrier for this context. Apply the authenticated full Host
map through the existing normal native path, including empty initial slots.

For subsequent reliable CS arrivals, Root's native-shadow adapter must prove
actual clientCS[id] is the approved authenticated Host name, then populate only
empty/same-name frozen SV/cache entries under its verified native layout. No
arbitrary name overwrite, raw flag toggle or invented cache pointer.

AdoptPeerBinding then checks the authenticated Host name/id, exact resource
receipt, actual client CS, actual frozen SV shadow and actual cached-slot name
before recording the Host binding. PeerDObj additionally checks renderer cache
and resource serial; a peer can never allocate its own late Host ID.

Custom UDP DObjs can arrive before native reliable CS. Retain bounded pending
representation work per entity/world, retry after actual native CS handling,
and drop stale world/serial work. Returning false from this helper is a wait,
not permission to claim an invisible gun/body rendered correctly. Keep original
world state and existing valid presentation while that specific change waits.

New resource revisions retain previous receipts for previous approved assets;
they do not clear existing bindings or kick the party. New assets/weapons wait
for their recipient's verified new receipt. A sender must use that recipient's
accepted serial; old-serial replays are rejected once it advances. Incremental
native/wire transactions and pending queues are **not implemented here**.

### 5. Save provenance and teardown must compose with existing observers

Do not replace `campaign_cinematics::observer=InventoryFSObserver` in
`save_provenance.inc` with a competing callback. Extend that existing dispatch
or explicitly compose a second observer through it while preserving movie,
ownership, role, pose/vitals and copy/rename behavior.

At native FS open0x15, retain strict save/*.svg path/handle/mode checks. Snapshot
the relevant approval/weapon description for that native save transaction.
At successful FS close0x25, hash the **completed native bytes** using the
existing InventoryFileHash discipline, then atomically write a separate bounded
approval manifest. Include save SHA, engine/variant/map, gameplay/package and
saved world-rule identity, source provenance, approved names and weapon/alt
media metadata. Runtime pointers, native IDs, cache epochs and peer ACKs must
not be restored as valid cache state.

Native saves finish through copy0x24 in the current observer; bind the manifest
to the actual copied target's completed hash, and handle rename/failed opens/
partial files consistently. Preserve `.coopowners` MetadataV2/legacy decode
unchanged; a resource manifest does not grant another member's inventory lease.

On native read-open, verify exact saved bytes/package/world provenance before
using the manifest to restore **approval names** into the new cache lifecycle.
Union saved-world resources with any newly confirmed owner plan through a
separate current contract; do not require the current roster to equal the old
saved roster or assign saved guest ownership by arrival order. Original native
oldID→newID remapping remains a real binding path, never a pure deferral.

SaveApproval explicitly reports missing/legacy/unverified manifest unresolved.
It does not serialize or migrate anything. Legacy dense saves include unused
original name reservations; proving their faithful migration remains necessary
for full save/resume acceptance. Preserve native Host progress, not silent IDs0.

End the Store before an unsupported DLL/module/cache transition, stop resource
delivery/queues through existing BootShutdown/teardown, restore only owned
hooks or PIN retained chains and require a fresh handshake/reload. Never
continue with stale native pointers or clear IDs inside the same world.

## Verification commands and scope

```sh
g++ -std=c++17 -O1 -Wall -Wextra -Wpedantic -Werror -g -fsanitize=address,undefined -fno-omit-frame-pointer tests/test_first_use_resources.cpp -o run/approved-first-use-review/test-first-use-asan
run/approved-first-use-review/test-first-use-asan
python3 tools/qa_first_use_code_map.py --game-dll /owned/game/uo_gamex86.dll --test-executable run/approved-first-use-review/test-first-use-asan --output run/approved-first-use-review/code-map-linux
i686-w64-mingw32-g++ -std=c++17 -O2 -static tests/test_first_use_resources.cpp -o run/approved-first-use-review/test-first-use-windows.exe
```

ASan/UBSan and MinGW32/Wine standalone fixtures pass: six pure versus14 binding
callers, actual pinned PE bytes, ASLR relocation and owned-hook rejection,
cache failures, model/weapon bounds, alt closure, first-use transaction/stable
IDs, current native empty-CS sourcing, capacity255, wrong world/epoch/transaction,
partial publication, temporary-peer versus Host ID order, client/shadow delay,
incremental resource receipts and missing/legacy save approval.

The actual DLL is read as PE data only; the code-map fixture never loads or
executes it. Synthetic cache/table callbacks test policy, not engine behavior.
Native gameplay, complete saved-approval manifests, actual dense four-role
registration, cumulative full-mission capacity and production promotion remain
the next integration gates. Existing source games/tests were not modified.
