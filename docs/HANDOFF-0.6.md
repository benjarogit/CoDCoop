# CoDCoop 0.6 handoff / Übergabe

Date / Datum: 2026-11-21. Development branch: `feat/0.6.0-coop-suite`.
Starting point: `801dfd4` (published v0.5.4 assets are unchanged).
Local source checkpoint: `4a6d36f` (WIP, not pushed or released).

## Current checkpoint / Aktueller Arbeitsstand

This section supersedes older “current” counts and mutable run-directory paths
below. Source is still in development; no stable release has been published.

- Frozen reproducible runtime: core
  `1a0bc53fb1fb01b09409b654f6bf8e4073d4bb548a43b07db5ac2fbcd17c100d`,
  loader `85fc865c0ccb50e277b3ccaa0cf16b846c740ac1c1b826eebaaef56900dd4c69`.
  Exact source, binaries, hashes and rebuild instructions are preserved in
  `run/runtime-archive-final/`. Current Core source also contains explicitly
  gated QA model experiments; do not attribute frozen-runtime results to them.
- Protocol7 synchronizes the reviewed YAP sprint/jump rules, including typed
  validation, acknowledgements, live corrections and restoring personal values
  on leave. A native config-writer hook also preserves original archived values
  when a player quits directly while connected. Actual writeconfig, direct quit,
  subsequent standalone startup and rejoin/input passed on the frozen core:
  `run/mainline-credits-qa/proof-archive-rules-1a0b-PASS-1795277060720289776/`
  and `proof-host-rules-1a0b-PASS-1795277126070468178/`.
- Stock UO Bastogne opening/Jeep scenario: two real instances, 153.5 units of
  remote movement, two genuine checkpoint reloads, stable observation and clean
  exits PASS on the frozen core (`run/qa-checkpoint/`). This is a targeted test,
  not a complete mission or blanket resolution of all allocator failures.
  Earlier CoD1 checkpoint evidence is archived under
  `run/qa-checkpoint/history/1795276128600133246/`.
- Four real CoD1 players plus a genuine checkpoint reload PASS on core `efbf`
  (`run/qa-cod1-four/`); all three remotes moved independently and rejoined.
  The older `1de73345` four-player proof is in its
  `history/1795275259442448296/` directory.
- UF actual remote mechanics have separate preserved evidence: MG placement
  through normal alternate-fire/ADS and clip consumption
  (`run/uf-script-qa/history/mg-itemcache-efbf-pass-1795276036315976145/`);
  one smoke-funded P47 call with original impacts
  (`airstrike-itemcache-final-pass-1795276234515570026/`); binocular artillery,
  20 owned native missiles and the original 180-second refill
  (`artillery-180s-pass-1795277774811289618/`). These used 512MB hunk memory;
  the final installer-default 256MB run remains a gate.
- Source includes a local individual-equipment chooser and verified original
  menu/asset catalog. It currently saves preferences only. Current protocol7
  does not yet apply independent kits or publish a ready lobby; the UI correctly
  refuses to advertise that missing capability. Frozen GUI bundles predate this
  chooser and must be rebuilt after native integration.
- Packaging is deliberately held: universal resource precaching exceeds the
  native 255-model limit in dense UF maps. Selected fixed-kit runs fit, but a
  valid four-role union reaches 262/258/259 entries on Noville/Foy/Tropez and
  cannot fulfill the individual-kit requirement with the old policy.
- QA-only renderer-cache preload has actual positive/negative two-peer proof:
  the missing aircraft renders with no new world-model IDs. A deferred-first-use
  registry now tests allocating IDs only when native callers consume them.
  Noville showed capacity progress; Foy exposed a 9494-byte animation-tree
  allocation failure. Tropez reached 175.3 units of actual peer movement but
  checkpoint reconstruction failed; an attempted preload timing change also
  caused a renderer access violation. All are unresolved experiments, retained
  as failures. No ID recycling, capacity widening or disabled native guards is
  accepted as a fix. Native tree ownership and save/cache reconstruction are
  the immediate investigation targets.
- Follow-up first-use proof PASS on Pathfinder, core
  `01efbe99493cc89c5ae67bf21818135ecfa4d54acb423c1d7bb3386a1ddd6dae`:
  real peer movement (170.3 units), native checkpoint/load, reconnection,
  advancing commands, stable observation and clean exits. The preload includes
  the catalog-derived 39-media-model union of four legal distinct kits; actual
  independent kit application is not implemented by this proof. Immutable
  evidence is in
  `run/mainline-credits-qa/proof-deferred-PATHFINDER-FOUR-KIT-CHECKPOINT-PASS-1795281672369739291/`;
  exact source is in `run/deferred-first-use-prototype/01efbe99493cc89c5ae67bf21818135ecfa4d54acb423c1d7bb3386a1ddd6dae/source/`.
  Foy/tree allocation and dense-map acceptance remain open.
- The full mission playthrough matrix, native Windows10/11, mixed systems and
  separate-account Steam acceptance remain open. Only this Linux machine is
  available. Do not label a Wine installer run as native Windows acceptance.
- Current parent Python discovery: 147 cases, 135 passed and 12 opt-in native
  cases skipped (`run/unit-current.log`). The native identity and checker runs
  have separate evidence; the skip count is not a substitute for those runs.
  Two additional packet-evidence oracle tests passed separately. Later roster
  additions require a new full count before source freeze.
- Individual roster contract now exists in `tools/uf_equipment_roster.py`:
  only the owning slot submits its kit, host owns world/membership, catalog and
  approved resource-plan hashes are checked, and changing kit/world/membership
  invalidates every ready acknowledgement. Nine focused contract tests passed.
  This is a validated source contract, not yet native lobby or kit-application
  evidence. Fixture: `run/uf-individual-roster-contract.json`.
- Frozen `1a0b` targeted network regression FAIL:
  `run/qa-partition/history/1795282035417881839/` records two
  real peers, training→Pathfinder, a measured 2002.394ms s2c partition and all
  three reload controls dropped. The link recovered, but the peer remained in
  the old world and disconnected after the native 15001ms host timeout.
  Repeated confirmed transition delivery is required. This first wrapper run
  predates its self-hash field; runtime hashes and the pinned relay revision are
  in the underlying provenance. The probe now also checks actual partition
  duration; do not relabel the negative as a successful recovery test.
- Development source is now `0.6.0-dev.3`, protocol8. It adds a random session
  nonce, ordered reload generations, endpoint-bound acknowledgements and
  500ms retries that survive dropping native remote slots. Duplicate controls
  are acknowledged without loading twice, including while local map startup
  is pending. Older development protocols are deliberately incompatible.
  Full old-world packet tagging and long blocking cold loads remain separate
  open network gates.
- Protocol8 repeat PASS on core
  `57f7cdad6e12e687625b26bd1eb8e37d4a14d712a980df6f0872888b57589f4e`
  in `run/qa-partition/history/1795282242007701990/`: measured 2000.286ms partition, actual reload packet
  dropped, automatic reconnection, 172.5 units of genuine remote movement,
  additional ordinary movement/stability and clean exits. No manual rejoin or
  target-mission start click was injected. Source snapshot and runtime are in
  `run/reliable-reload-prototype/`; source/model experiments remain QA-gated.
  All eight focused protocol/animation/control C++ sanitizer tests passed.
- Reverse-direction partition also PASS on `57f7`: the peer's acknowledgement
  was actually dropped, retries recovered automatically and the peer processed
  exactly one map change (`run/qa-partition/history/1795282597982890083/`). Full packet evidence is retained;
  native remote input, stable observation and clean exits passed again.
- The same `57f7` runtime passed four actual CoD1 players with two consecutive
  native checkpoint reloads (`run/qa-cod1-four/`). Native protocol8 checker
  interoperability: all11 cases PASS in162.331s
  (`run/native-protocol8-checker.log`); native identity/CryptoAPI case PASS
  in5.412s (`run/native-identity-protocol8.log`). These are Wine tests, not
  native Windows hardware acceptance.
- Known follow-up: explicitly cancelling hosting while a reload is pending
  must notify pending inactive endpoints and stop their local rejoin wait.
  This path is not yet covered by the successful delivery/recovery proofs.
- Latest complete Python discovery:169 cases,157 passed,12 opt-in native
  cases skipped (`run/unit-protocol8-final.log`). The12 native cases passed
  separately in the identity/checker runs above. Equipment/UI focused run:
  33 PASS under pinned Ubuntu22/Python3.10/PySide6
  (`run/uf-roster-ubuntu-tests.log`). Source projection remains explicitly
  capability-gated and does not claim native equipment application.
- Stronger four-player checkpoint repeat PASS on `57f7`
  (`run/qa-cod1-four/`): each of three real peers moved after each of two native
  reloads using distinct forward/back/sideways commands, in addition to advancing
  clocks and clean exits. The first screenshot had overlapping players because
  native rejoin respawned them together; the stronger probe separates them and
  the fresh joiner screenshot was inspected with clear world/player rendering.
  Exact executed runner SHA `431963e2456d3110c1a8ded6eee0255bf16f44254d002eb406087410818aa4e7`
  is preserved as `run/reliable-reload-prototype/source/tools/qa_coop-postload-proof.py`.
  Current runner additionally checks the forward/back input sign.
- Foy first-use/native-tree borrowing QA PASS on core
  `93d47274f761da07dd1ea4229b718f5ba8bf81ba7fd613d39212af044650dd0f`:
  natural truck intro,181.6-unit actual peer movement, stable snapshots and
  clean exits. Immutable evidence:
  `run/mainline-credits-qa/proof-deferred-FOY-NATIVE-BORROW-PASS-1795282593854955297/`.
  Sixteen native borrowed trees and five Core-owned humanoid replacements were
  active. Borrowing requires all explicit QA flags; it is not a production fix.
  Subsequent256MB firing/checkpoint test on `a31c4640` correctly FAILed with
  native renderer access violation `50c0d2` after deferred-tree cleanup.
- Important RE correction: the97 prepared native cache trees (911,542 bytes)
  are HUNK-backed, not MT-backed. Native traps0x58/0x59 use different allocators.
  Core replacements consume the separate512KB MT script pool. Native borrowed
  HUNK blocks must never reach MT_FreeIndex; the earlier inference that all97
  native blocks already occupied MT was wrong.
- Host cancellation now sends session-bound close notices to loading endpoints,
  stops queued automatic rejoin and clears deferred MT indices before native
  disconnect. The first oracle looked in the wrong log and was interrupted;
  the corrected test proved cancellation but then exposed a fresh-session hang
  at deferred-tree freeing. Native RE confirmed disconnect→full shutdown→MT_Init
  at45fab0 resets the allocator, invalidating those old indices. Corrected core
  `68192351789148e3a74eb47a7ecb0003d4ca0321db664632d3694ea9c719ffa8`
  passed the complete targeted repeat in `run/qa-partition/`: cancellation
  before remote-slot reallocation, authenticated host-close notice, five seconds
  with automatic rejoin stopped, explicit fresh session, real remote movement,
  stable observation and clean exits. Source/runtime are frozen separately in
  `run/reload-cancel-final/`. Earlier wrong-log oracle ABORTED evidence is in
  `history/1795282683996027911/`; the corrected-oracle fresh-session hang FAIL
  remains in `history/1795283172475386184/`. Full campaign/network acceptance is
  still open.
- Longer-outage recovery: core `68192351` correctly FAILed a real20s bidirectional
  outage across a same-map native restart (disconnect after15015ms). First
  auto-recovery prototype `e1764497` reached the map but FAILed command-clock
  advancement. Relay evidence showed old client sequence1513…1518 followed by
  fresh1…166, poisoning the newly allocated native netchan. Core
  `5a12a783109577d8b13ef83db281607b79b085bc2ca85344775e22e550116b6a`
  suppresses old-world native sends until attachment. The repeat PASSed:
  visible logical reconnect wait,20,000.339ms outage,36 actual reload messages
  dropped, normal automatic world reload,159.5-unit native remote movement,
  stable observation and clean exits (`run/qa-chaos/`). Immutable source/runtime:
  `run/reconnect-final/`. Negatives are preserved in its history
  `1795283713762113551/` and `1795284105770298508/`. Older6cbb bad-WiFi proof
  formerly at the root is now `run/qa-chaos/history/1795283608037899792/`.
- Native256MB dense-map first-use/borrow proofs now also include actual firing
  and checkpoint movement on Noville and Tropez, core `b4594765`:
  `run/mainline-credits-qa/proof-deferred-NOVILLE-256-FIRE-CHECKPOINT-PASS-1795283674959002564/`
  and `proof-deferred-TROPEZ-256-FIRE-CHECKPOINT-PASS-1795283901978398451/`.
  Final host CS counts220/198; they remain within255 without changing native guards.
- Causal mapping-invariant probe: local native DObjs retained their old model
  IDs while client-CS changed to host IDs. Delaying only post-checkpoint DObj
  packets for2s exposed15 model-name mismatches during cls2 rendering. QA-only
  detach/sync before host CS mapping on `5a12` produced zero mismatches across78
  observed render states, with265 actual DObj packets withheld,111 local DObjs
  detached, real firing/movement before and after checkpoint and clean exits.
  Proof: `run/mainline-credits-qa/proof-deferred-FOY-256-MAPPING-BARRIER-PASS-1795284283778387233/`.
  Same-DLL feature-off control is in progress. This establishes an invariant
  repair, not yet the root-cause resolution of the intermittent renderer crash.
- Native DObj destruction ABI was corrected independently: both engines read
  a stack bool that the old wrapper omitted. A real 32-bit Wine stub tested
  2000 true/false calls and stack preservation. This repair does not close the
  Foy allocation failure, which still reproduces on the corrected protocol7
  prototype. Borrowing Game-owned trees requires explicit ownership handling.

## User decisions / Nutzerentscheidungen

- Full pinned suite for every player: CoD1, UO, SP Improved1.5, United Fronts1.1beta, YAPr169.
- Up to4 players; host world authority, all players participate in suitable objectives.
- Host-owned saves; no host migration/save distribution.
- Host chooses variants, mission and difficulty; group follows with safe saving/restart.
- Confirmed equipment decision: United Fronts players select their own starting
  equipment from the mod's supported choices. Different roles are planned
  together before mission start; the host does not impose one common kit.
  The shared resource contract must include all chosen kits, readiness and
  before-start validation against the native world-model limit.
- Recommended mainline starts with CoD1 and continues seamlessly into UO, retaining AI improvements.
- Mainline uses SP Improved's UO-engine route; classic profiles and UF remain separate.
- Improved AI belongs to the recommended Coop baseline across the CoD→UO route,
  rather than requiring players to enable an unrelated singleplayer extra.
  Preserve the pinned mod's AI behavior; adapt its single-player assumptions so
  remote players participate. Do not claim that every addon contributes an AI
  upgrade without comparing its actual scripts/data/native patches.
- English default docs, equal German docs, both languages in changelog/release notes.
- Mixed German/English gameplay installations; unlocalized custom content retains original language.
- Windows10/11x64, Linuxx86_64 Wine/Proton; CoD2 experimental, outside completion target.
- Graphical Linux installer plus terminal; full suite mandatory rather than optional extras.
- Native Windows, multi-account Steam and complete campaign tests remain final acceptance gates.
- Hardware confirmed by the user: only this Linux machine is currently available.
  Windows setup executed through Wine does not close native Windows acceptance.

## Implemented foundation / Umgesetzte Grundlage

- `content/variants.json`: pinned versions, required variants/runtime/overlays and mainline definition.
- `tools/coop_suite.py` + native installer checker: full receipts, hash checks, game-content
  fingerprints independent of localization/GUI-platform files, preparation of guarded runtime profiles.
  Only reviewed language path/hash pairs are exempt from gameplay comparison;
  unknown or modified `localized_*.pk3` files contribute to the fingerprint.
- Protocol7 preflight before assigning slots. Old clients cannot feed gameplay state to new hosts.
  Development suite `0.6.0-dev.2` adds host-authoritative YAP movement/prediction
  rules; older protocol6 runtime proofs below remain explicitly version-bound.
- Same-IP routing correction: SP engine writes literal zero qport; each remote now has its own
  identifier, host resolves collisions and accepts raw datagrams only from allocated matching peers.
- Bounded control packets and atomic animation-fragment assembly (loss/reorder/duplicate tests;
  unfinished pending entries are bounded and evicted rather than starving newly visible actors).
- UO loader loads `plugins/yap/DDRAW.dll` before Coop hooks and checks prologues.
  Upstream requires uppercase basename; YAP stays loaded during core hot reload.
- Local-only reviewed script builders preserve each mod's menu and generate selected mission
  activator adaptations. UF actor-local ammo, mines and mount work is in reviewed transformations.
- UO grenade ownership is derived from proven native owner number+entity pointer, not proximity.
  Fixed-size encoded banks prevent growing one cvar for every entity index.
- Native Linux/Windows launcher GUI, difficulty/map selection and confirmed host-only switching.
  Source supervisor owns the game process, validates installations and coordinates restarts.
- Transactional setup, resumable checked downloads, preservation of personal cfg/saves,
  failed-install restoration and public rollback. Linux graphical setup/AppImage is built.
- Real-client QA adapters for native checkpoint reloads, delayed host startup and
  the pinned Co-op Anything UDP chaos relay (revision recorded in development
  commands). Retries archive results, native runtime and engine logs; stale PASS
  files are not reused. Scripts reject native runtime/snapshot errors explicitly.

## Runtime evidence / Laufzeitnachweise

All game runs used isolated copies. No game DLL, config or save in the live installation was changed.

- CoD1, two real instances: preflight, joined state, real user-command advancement, movement, clean exit PASS.
- CoD1, four real instances behind oneIP: independently controlled slots1/2/3, movement and clean exit PASS
  after the qport correction. Earlier four-player test correctly failed and exposed the bug.
- Delayed-host regression PASS: real joiner started35seconds before the host,
  then exchanged advancing user commands, moved and shut down cleanly.
  Native backward snapshot time had previously disconnected its renderer.
  Waiting joins now stop the independent local world clock; an already advanced
  local world reloads normally before attaching to older host snapshots.
  Evidence: `run/qa-cod1/result.json`, pinned runtime in its provenance.
- SP Improved + YAP + Coop: two real instances connected, snapshots and animation clocks advanced.
- United Fronts + YAP + generated overlays: two real instances, clocks, movement and clean exit PASS.
- UF mechanics fixture: separate binocular ammo bookkeeping and distinct native mount entities PASS.
  Deliberately restoring shared bookkeeping produces an actual FAIL; detector negative-control PASS.
- UF real remote grenade/mine PASS: native projectile ownership, normal placement
  without moving the host, normal pickup/ammunition restoration, a second mine's
  normal proximity detonation and actual enemy health loss. Shared AI melee now
  recognizes a remote player's stance instead of reading an AI-only field.
  Positive proof: `run/uf-script-qa/`; separate shared-stockpile negative-control
  proof: `run/uf-negative-qa/`. Mine damage to an enemy alone is not proof that AI
  independently targets and damages a remote player; that has a separate observer.
- Autonomous hostile AI→remote damage PASS: an existing enemy was positioned
  near the actual remote, farther from the host. No target/enemy/goal/accuracy
  assignments or artificial damage calls were made. Native AI chose that remote,
  and the observer verified a real damage notification from that exact enemy
  plus remote health loss. Two-client smoke and clean shutdown also passed.
  Evidence: `run/uf-ai-qa/history/1795267034608368616/`, core
  `90c2e8eb1aad20ee594687de0afbe749ec812aaa77ac14d6ed839cb1742128d7`.
  This proves that observation only. Subsequent script inspection found scripted
  one-health actors in the initial Pathfinder scene, so it is not sufficient
  evidence for ordinary healthy combat AI. A separate Brecourt test with an
  existing healthy enemy, visible targetable remote and hidden host did not
  acquire or damage the remote in fifteen game seconds. Native sentient/target
  enumeration and line-of-sight diagnosis established that native AI actually
  iterates all sentients. A later controlled Brecourt run with a verified clear
  trace reached genuine remote acquisition and damage; see the newer proof below.
  No target or accuracy assignments were used to force either result.
- Shared native scripted-film→world reload PASS on core
  `8c5f8ead031644ed4959e0e3193a76769276e72d09e6f2f128dc31b773d34026`:
  both actual UO-engine players played `cod_end.roq`, remote playback ACK arrived,
  both reached natural film end, normal host map loading rejoined both worlds,
  real remote movement/stable observation/clean exit passed. The first test
  exposed stale animation-tree cleanup after the native film had cleared the
  world; the fix forgets the freed world and suspends its state application while
  retaining party controls. Archived evidence:
  `run/uf-script-qa/history/1795269816358340004/`.
- Frozen source-supervisor group restart PASS: CoD1/training→SP Improved/pathfinder,
  both actual processes restarted, host wrote its checkpoint, both engines reported
  requested difficulty2, actual remote commands advanced, both supervisors resumed,
  clean shutdown. An added unreceipted PK3 correctly cancelled preparation while
  both players remained active. `run/switch-real-qa/result.json` records frozen tool
  hashes and core `c24a9b1d…8286194`; it is not proof for later rebuilt binaries.
- Natural original CoD credits→UO continuation PASS with two real instances on
  core `12562819b50e6ff5383680df43203c17db11e983c43b6dad3e41debbe225bdc9`:
  normal credits completion, original victory Continue action, both clients on
  `bastogne1`, rejoin, readiness-gated mission start, original Jeep introduction,
  real remote movement, stable observation and clean shutdown. Credits used4x
  engine timescale, then returned to1x; transition took99.383wall seconds.
  Evidence: `run/mainline-credits-qa/`. This is a targeted transition test, not
  a full Berlin mission or complete campaign playthrough.
- Native Windows setup executed under Wine on a3.6GB game copy; native and Python receipt checks PASS.
  All8 existing personal cfg/save files retained identical hashes. This is not native Windows hardware QA.
- Native/Python receipt interoperability, same-size corruption, eWeapons JSON, rollback and lowercase
  paths tested. Python unit tests and native protocol/fragment tests run from development commands.
- Installation sealing now prepares its initial runtime profile from the same
  freshly hashed receipt, avoiding repeated full reads in one setup operation.
  Independent check/prepare/launch still hash content again; no timestamp cache.

Evidence is under ignored `run/` directories; exact current binaries and each run's scope are in
its `provenance.json`/`result.json`. Do not attribute an older run to a later rebuilt DLL.

### Latest regression results / Aktuelle Regressionstests

- Core `19470452cdbebf4fea70eb1c5e438a2a43d03c759cc5c4b831cc217699d74641`:
  three and five consecutive real UO checkpoint reloads PASS, with two actual
  players reconnecting and advancing snapshots after every reload. CoD1 also
  passed three reloads (`run/qa-checkpoint/result.json`). These tests exposed
  and fixed absent reliable buffers for saved remotes, server-time rollback,
  deferred same-map loads and the secondary cgame server-simulation syscall.
- Core `1de73345e5efe9e6e2634ce481ebe057073d261e5c2c738a49ee3622abc25870`:
  four-player CoD1 smoke PASS with three independent remote movements,
  advancing commands, stable observation and clean shutdown (`run/qa-cod1-four/`).
- Core `84790c2fcba9ef35dab13a7be12dcfcc6d1db2e7fa0a331540eff8c4fc110b6a`:
  two-player real Co-op Anything `bad_wifi` relay smoke PASS
  (`run/qa-chaos/history/1795273945569903274/`).
  Preserved scheduling logs show 86/1393 client-to-server and 254/5746
  server-to-client packets dropped, plus duplication and scheduled reordering.
  Exact log hash/counts are in `network-summary.json`; this is not Steam or
  impaired checkpoint/map-transition certification.
- A later mainline retry reached UO and accepted real remote input but correctly
  failed its error gate: game DLL reload at the same address lost the GetEnt
  hook. Core `8cbe87c19949988dacfb87030a12584e3be4179c5b88839961d6d38713cf0d4d`
  rearms fresh native prologues and reports failed native world attachment
  instead of silently retrying a half-attached world. Its targeted retest PASS:
  both players saw progressing original credits, naturally reached Bastogne
  after 137.475 seconds, completed the opening scene, accepted real remote
  input and shut down cleanly. Native script/asset/clock error count was zero.
  The initial expected party size was one and grew from the actual joining
  player, rather than a test-only forced party size. Evidence:
  `run/mainline-credits-qa/{result.json,mainline-probe.json}` and both-player
  early/middle/late captures under `credits-captures/1795272560008934078/`.
- The same `8cbe87c1` core also passed the complete targeted movie regression:
  actual native playback on both players, playing acknowledgement, natural end,
  regular host world reload, reconnection, real remote input, stable observation
  and clean shutdown. `run/qa-movie-final/{movie-probe.json,result.json}` preserve
  this newer result separately from the older film proof.
- Current Python suite: 111 cases, PASS with nine environment-dependent skips
  (the opt-in native Wine identity/checker cases).
  Separate native Wine identity/CryptoAPI tests passed; no native Windows game
  test is implied. Final artifact hashes remain pending source freeze.
- Pinned `19470452` core with the reviewed thirteen-model UF early-precache
  overlay: healthy Brecourt enemy 129 independently acquired actual remote 1
  and dealt 43 native damage (600 to 557 health). Read-only GSC line-of-sight
  and external native process reads confirmed the remote's valid sentient/team,
  visible perception record, actual enemy pointer and actor state transition.
  No target/goal/flags/accuracy or artificial damage assignment was used. The
  prior negative remains preserved; this proves one controlled ordinary combat
  case rather than all enemies or missions. Exact DLLs, QA overlays, native
  read-only helper source/binary, observations and fresh images are archived in
  `run/uf-script-qa/history/1795273220045343268/`; the prior healthy negative
  remains under `1795272974986328327/`.
- Core `6cbb0f969b46357067bf05c8f02801f3206367feeaf44071592c48038c0a069d`:
  explicit leave now correctly reduces the agreed party from two to one; clock
  resync and timeout departures keep reserved participants. The real party
  regression then exposed a separate host-only startup race: a normal UI action
  fired before native UI settled, native pause returned and the world remained
  at 300 ms. The test correctly FAILed its next-mission gate. Evidence:
  `run/qa-party-final/history/1795274057785701111/`.
  Core `a1bbd793a7102a34bd8c1e559ea639e5734d997726c1fa68840b09a204e19fc2`
  adds stable native readiness and bounded startup retry. Its first repeat
  completed departure, host-only start and real rejoin/input but the final error
  oracle counted the intentional native `ERROR: Getrennt` notice as an unexpected
  disconnect. The probe now acknowledges exactly one observed notice after its
  own explicit leave command, with an empty pre-departure error baseline. All
  other errors and second disconnects still fail. Full repeat PASS on `a1bbd793`:
  explicit leave, normal host-only next mission start, real rejoin, 221.7 units
  of actual remote input, stable observation and clean exits. Exact evidence:
  `run/qa-party-final/{party-probe.json,result.json}`.
- The same `a1bbd793` core passed the natural two-player credits→Bastogne route
  again in 97.009 seconds, with both credit displays progressing, normal opening
  scene release, real remote input, zero unexpected native errors and clean exits.
  Immutable proof: `run/mainline-credits-qa/proof-a1bb-PASS/`.
- Core `6cbb0f96` also passed two real checkpoint reloads through the actual
  Co-op Anything `bad_wifi` relay, including advancing peer commands after each,
  real movement and clean shutdown (`run/qa-chaos/`). Its scheduling log records
  184/3079 client-to-server and 238/5412 server-to-client drops, duplication and
  reordered schedules. This tests that particular impaired route; exhaustive
  delayed old-world packets and deliberate loss of every reload control remain open.

## Open acceptance / Offene Abnahme

This development change is NOT a full-campaign certification. Required remaining proof includes:

- Natural full original campaign→credits→UO route, and complete per-mission playthrough coverage.
- Safe group campaign changes with both real processes restarting/rejoining and failure/cancel recovery.
- UF complete terrain-dependent MG use and artillery/airstrike damage.
- All mission objectives/interactions, vehicles, checkpoint/save-load stress and rejoin scenarios.
- Complete real-client network impairment/recovery coverage, including delayed
  old-world packets across checkpoint/map changes. Relay startup alone is not a
  successful gameplay/network test. Initial parent setup attempts were interrupted
  or hit Wine-prefix initialization timeout under concurrent disk load; those
  results remain preserved and are not gameplay PASS evidence.
- Healthy combat AI acquisition, broad NPC/mission coverage and comparative AI
  behavior. The earlier scripted-scene observation is insufficient for this gate;
  static increased ally bravery is not a hit-rate test.
- Film playback and natural completion have targeted runtime proof. Full campaign
  movie/mission coverage and impaired-network delayed-packet behavior remain open.
- The first network handshake must survive blocking cold map loads. A new timer
  resets after a long engine-poll gap; unit cases cover active timeout, a blocked
  load and tick wrap. The original cold-load failure is preserved in AI/movie QA.
- Reproduction/stress verification of upstream UO issue1 `MT_AllocIndex: failed allocation of9206 bytes`.
  Do not add a second free to ordinary UO XAnimFreeTree: native code already calls MT_FreeIndex.
- Actual Windows10/11 hardware, mixed-OS peers, and Steam across separate accounts.
- Final launcher/AppImage/Windows bundles rebuilt after source freeze, fresh platform-specific payloads,
  QA-only script fixtures excluded, all checksums matched. No stable0.6 release before these gates pass.

## Reproduction / Reproduzieren

Tools and evidence / Werkzeuge und Nachweise:

- Native builds: 32-bit MinGW-w64; Python suite tools; PySide6/PyInstaller for
  graphical installers and launchers. Portable Linux builds use a pinned,
  isolated Ubuntu 22.04 container and inspect every bundled ELF's glibc floor.
- Runtime: real game processes under Wine, owned Xvfb displays and separate
  prefixes, logs/state probes/screenshots, plus exact preserved DLL hashes.
  Source copies and QA scripts are separate from the live game installation.
- Co-op Anything: pinned checkout and actual UDP chaos relay used in the
  successful impaired-network smoke above; procedures are adapted to this
  engine rather than counted as gameplay evidence by themselves.
- Native reverse engineering in this iteration uses the existing notes and
  concrete Capstone/objdump instruction evidence. The available REA 6.4 setup
  expects Ghidra 12.1 while this machine has Ghidra 12.2; do not describe these
  new traces as a successful REA/Ghidra execution. Fixing that tool mismatch
  remains separate from the proven binary findings.

See [development commands](development-0.6.md), [campaign compatibility](campaign-compatibility.md),
[YAP notes](yap-compatibility.md) and [launcher](launcher.md).

Build/runtime tools are under `tools/`; the source tree has no checked-in game assets.
Use a fresh `tools/stage_suite.py` output after modifying any locked runtime/source files.
For a canonical complete distribution, include base files rather than assuming unrelated starting
installations have identical gameplay PK3s. Never merge Windows/Linux Qt `_internal` trees.
