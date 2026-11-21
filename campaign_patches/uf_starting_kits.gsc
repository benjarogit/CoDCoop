// QA-only actor-local starting-kit adapter. No lobby/transport exists here.
// Generated choice validation and cloned original UF processors follow below.
Start()
{
    if (isdefined(level.coop_kit_adapter_started)) return;
    if (!ReadHostPlan(true)) return;
    if (getcvar("coop_qa_kit_resources_only") == "1") return;
    level.coop_kit_adapter_started = true;
    thread WatchPlayers();
}

ReadHostPlan(prepare_resources)
{
    if (getcvar("coop_qa_kit_enable") != "1" || getcvar("coop_qa_kit_authority") != "host") return false;
    if (getcvar("coop_qa_kit_catalog") != Coop_CatalogIdentity()) { setcvar("coop_qa_kit_status", "FAIL_CATALOG"); return false; }
    if (getcvar("coop_qa_kit_map") != getcvar("mapname") || getcvar("coop_qa_kit_epoch") == "") { setcvar("coop_qa_kit_status", "FAIL_MAP_EPOCH"); return false; }
    if (getcvar("coop_qa_kit_commit") != "1") { setcvar("coop_qa_kit_status", "WAIT_APPROVAL"); return false; }
    level.coop_kit_epoch = getcvar("coop_qa_kit_epoch");
    level.coop_kits = [];
    for (slot = 0; slot < 4; slot++)
    {
        key = "coop_qa_kit_" + slot + "_";
        if (getcvar(key + "mode") == "") continue;
        kit = spawnstruct();
        kit.mode = getcvar(key + "mode");
        if (kit.mode == "automatic") continue; // Original authored path, never guessed.
        if (kit.mode != "manual") { setcvar("coop_qa_kit_status", "FAIL_MODE"); return false; }
        kit.family = getcvar(key + "family");
        fields = [];
        fields[0] = "grenade"; fields[1] = "pistol"; fields[2] = "primary"; fields[3] = "secondary";
        kit.numbers = [];
        for (i = 0; i < fields.size; i++)
        {
            if (getcvar(key + fields[i]) == "") { setcvar("coop_qa_kit_status", "FAIL_MISSING_SLOT"); return false; }
            number = getcvarint(key + fields[i]);
            if (getcvar(key + fields[i]) != ("" + number)) { setcvar("coop_qa_kit_status", "FAIL_NONCANONICAL_ENUM"); return false; }
            if (!Coop_ValidChoice(kit.family, fields[i], number)) { setcvar("coop_qa_kit_status", "FAIL_CHOICE"); return false; }
            kit.numbers[i] = number;
        }
        if (Coop_SpecialScript()) { setcvar("coop_qa_kit_status", "BLOCKED_ORIGINAL_SPECIAL_SCRIPT"); return false; }
        level.coop_kits[slot] = kit;
    }
    // Reserve the actual approved union before the normal registration boundary.
    if (prepare_resources)
        for (slot = 0; slot < 4; slot++)
            if (isdefined(level.coop_kits[slot]))
                Coop_PrecacheKit(level.coop_kits[slot]);
    setcvar("coop_qa_kit_verified_catalog", getcvar("coop_qa_kit_catalog"));
    setcvar("coop_qa_kit_verified_epoch", level.coop_kit_epoch);
    setcvar("coop_qa_kit_status", "PLAN_VALIDATED");
    return true;
}

SpawnIdentity(slot)
{
    names = [];
    names[0] = "coop_spawn_session_a"; names[1] = "coop_spawn_session_b";
    names[2] = "coop_spawn_session_c"; names[3] = "coop_spawn_ticket_" + slot;
    parts = []; numbers = [];
    for (i = 0; i < 4; i++)
    {
        parts[i] = getcvar(names[i]); numbers[i] = getcvarint(names[i]);
        if (parts[i] == "" || parts[i] != ("" + numbers[i])) return undefined;
        if (numbers[i] < 0) return undefined;
    }
    if (numbers[2] > 3 || numbers[3] <= 0 || (numbers[0] == 0 && numbers[1] == 0 && numbers[2] == 0)) return undefined;
    return parts[0] + "|" + parts[1] + "|" + parts[2] + "|" + slot + "|" + parts[3];
}

// Native publication is authoritative only for this exact live owner/world.
// Missing/stale/partial publication must never turn a cold save into a refill.
InventoryDisposition(slot, identity, world)
{
    if (!isdefined(identity) || world == "") return "WAIT";
    key = "coop_inventory_" + slot + "_";
    published_identity = getcvar(key + "identity");
    state = getcvar(key + "state");
    if (published_identity != (identity + "|" + world)) return "WAIT";
    if (published_identity != getcvar(key + "identity") || state != getcvar(key + "state")) return "WAIT";
    if (SpawnIdentity(slot) != identity || getcvar("coop_spawn_world") != world) return "WAIT";
    if (state != "FRESH" && state != "PRESERVED") return "WAIT";
    return state;
}

Coop_SpecialScript()
{
    switch (getcvar("mapname"))
    {
        case "training": case "sp_plane": case "ship_escape": case "ship":
        case "bomber": case "trainbridge": case "stalingrad": case "kuban1":
        case "redsquare": case "trench86": case "poland": case "truckride":
        case "airfield": case "sicily2": case "tankdrivecountry":
        case "tankdrivetown": case "kursk": case "kharkov1": return true;
    }
    return false;
}

WatchPlayers()
{
    wait 0.1;
    while (1)
    {
        players = getentarray("player", "classname");
        for (i = 0; i < players.size; i++)
        {
            player = players[i];
            slot = player getentitynumber();
            if (slot < 0 || slot > 3) continue;
            identity = SpawnIdentity(slot);
            if (!isdefined(identity)) { setcvar("coop_qa_kit_waiting_native_slot", slot); continue; }
            world = getcvar("coop_spawn_world");
            disposition = InventoryDisposition(slot, identity, world);
            if (disposition == "WAIT") { setcvar("coop_qa_kit_waiting_inventory_slot", slot); continue; }
            native_identity = identity + "|" + world;
            key = "coop_qa_kit_applied_" + slot;
            identity_key = "coop_qa_kit_identity_" + slot;
            if (disposition == "PRESERVED")
            {
                // A cold/cross-map save can replace external receipts from a
                // newer map. Native proof, not an old GSC receipt, owns ammo.
                if (getcvar(identity_key) != native_identity)
                {
                    setcvar(identity_key, native_identity);
                    println("COOP_UF_KIT_PRESERVED ", slot, " ", world);
                }
                continue; // No Apply, Give, Refill or player-field mutation.
            }
            if (getcvar("coop_qa_kit_" + slot + "_mode") != "manual") continue;
            if (getcvar(identity_key) == native_identity) continue;
            // A restored world's old plan must not select Alice's kit for Bob.
            // Validate once per immutable plan epoch, not once per actor/frame.
            if (getcvar("coop_qa_kit_epoch") != level.coop_kit_epoch || getcvar("coop_qa_kit_verified_epoch") != level.coop_kit_epoch)
                if (!ReadHostPlan(false)) continue;
            if (!isdefined(level.coop_kits[slot])) continue;
            if (!KitUnchanged(slot, level.coop_kits[slot])) { setcvar("coop_qa_kit_status", "FAIL_PLAN_MUTATED_WITHOUT_EPOCH"); continue; }
            if (SpawnIdentity(slot) != identity) continue;
            if (!isalive(player)) continue;
            if (slot > 0 && getcvar("coop_select_api") != "1") { setcvar("coop_qa_kit_select_wait_slot", slot); continue; }
            if (isdefined(player.coop_kit_applying) && player.coop_kit_applying == identity) continue;
            player.coop_kit_applying = identity;
            // Capture immutable actor context in this invocation, not mutable
            // entity fields/global fresh tickets that an old thread could use.
            context = spawnstruct(); context.identity = identity; context.slot = slot;
            context.a = getcvar("coop_spawn_session_a"); context.b = getcvar("coop_spawn_session_b"); context.c = getcvar("coop_spawn_session_c");
            context.ticket = getcvar("coop_spawn_ticket_" + slot);
            context.world = world; context.epoch = level.coop_kit_epoch;
            if (slot > 0 && context.world == "") { player.coop_kit_applying = undefined; continue; }
            if (!(player Apply(level.coop_kits[slot], context))) { player.coop_kit_applying = undefined; continue; }
            receipt = native_identity + "|" + level.coop_kit_epoch;
            player.coop_kit_epoch = receipt;
            setcvar(key, receipt);
            setcvar(identity_key, native_identity);
            println("COOP_UF_KIT_APPLIED ", slot, " ", level.coop_kits[slot].family);
        }
        wait 0.1;
    }
}

KitUnchanged(slot, kit)
{
    key = "coop_qa_kit_" + slot + "_";
    if (getcvar("coop_qa_kit_enable") != "1" || getcvar("coop_qa_kit_authority") != "host" || getcvar("coop_qa_kit_commit") != "1") return false;
    if (getcvar("coop_qa_kit_catalog") != Coop_CatalogIdentity() || getcvar("coop_qa_kit_map") != getcvar("mapname")) return false;
    if (getcvar(key + "family") != kit.family) return false;
    fields = []; fields[0] = "grenade"; fields[1] = "pistol"; fields[2] = "primary"; fields[3] = "secondary";
    for (i = 0; i < 4; i++) if (getcvar(key + fields[i]) != ("" + kit.numbers[i])) return false;
    return true;
}

Apply(kit, context)
{
    slot = self getentitynumber();
    if (slot != context.slot || InventoryDisposition(slot, context.identity, context.world) != "FRESH") return false;
    self takeallweapons();
    // Original force_weapons order: grenade, pistol, primary, secondary.
    for (i = 0; i < 4; i++) self Coop_Process(kit.family, kit.numbers[i], context);
    self Coop_RefillOriginal();
    return true;
}

Coop_SelectWeapon(weapon, context)
{
    slot = self getentitynumber();
    if (slot == 0) { self switchToWeapon(weapon); return; }
    if (slot < 1 || slot > 3 || !isdefined(context)) return;
    key = "coop_select_" + slot + "_";
    if (context.slot != slot || context.identity != SpawnIdentity(slot) || context.world != getcvar("coop_spawn_world") || context.epoch != getcvar("coop_qa_kit_verified_epoch"))
    {
        setcvar("coop_qa_kit_select_error_" + slot, "STALE_ACTOR_CONTEXT");
        return;
    }
    if (getcvar("coop_select_api") != "1" || !(self hasweapon(weapon)))
    {
        setcvar("coop_qa_kit_select_error_" + slot, "UNAVAILABLE_OR_NOT_OWNED");
        return;
    }
    sequence = getcvarint(key + "seq");
    if (getcvar(key + "world") != context.world || getcvar(key + "ticket") != context.ticket || getcvar(key + "session_a") != context.a || getcvar(key + "session_b") != context.b || getcvar(key + "session_c") != context.c)
        sequence = 0;
    if (sequence < 0 || sequence >= 2147483647) { setcvar("coop_qa_kit_select_error_" + slot, "SEQUENCE_EXHAUSTED"); return; }
    setcvar(key + "source", "uf_plan");
    setcvar(key + "name", weapon);
    setcvar(key + "ticket", context.ticket);
    setcvar(key + "session_a", context.a); setcvar(key + "session_b", context.b); setcvar(key + "session_c", context.c);
    setcvar(key + "world", context.world); setcvar(key + "epoch", context.epoch);
    // Last write commits the complete request. Native Core validates context,
    // owns reliable delivery/ack and waits for the actual own-player snapshot.
    setcvar(key + "seq", sequence + 1);
}
