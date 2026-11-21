// Only the pinned classic CoD1/UO/SPI parachute routine starts this watcher
// after its original detach. UF's different authored/individual recipe never
// calls it. Preserve original giveWeapon semantics; never copy later Host ammo.
watch()
{
    if (isdefined(level.coop_pathfinder_equipment_watch)) return;
    level.coop_pathfinder_equipment_watch = true;
    while (getcvar("mapname") == "pathfinder")
    {
        if (getcvar("coop_actor_mode") == "HOST")
        {
            players = getentarray("player","classname");
            for (i = 0; i < players.size; i++) players[i] consider();
        }
        wait 0.1;
    }
}

consider()
{
    slot = self getentitynumber();
    if (slot < 1 || slot > 3) return;
    context = maps\_coop_brecourt_handoff::identity(slot);
    if (!isdefined(context)) return;
    native = "coop_inventory_" + slot + "_";
    key = "coop_pathfinder_loadout_" + slot + "_";
    state = getcvar(native + "state");
    if (getcvar(native + "identity") != context) return;
    if (state == "PRESERVED")
    {
        if (getcvar(key + "identity") != context || getcvar(key + "state") != "PRESERVED_NO_GIVE")
        {
            setcvar(key + "identity",context);
            setcvar(key + "state","PRESERVED_NO_GIVE");
        }
        return;
    }
    if (state != "FRESH" || !maps\_coop_brecourt_handoff::eligible(self)) return;
    if (getcvar(key + "identity") == context) return;
    if (getcvar("coop_select_pathfinder_api") != "1" || getcvar("coop_select_api") != "1")
    {
        if (getcvar(key + "state") != "WAIT_SELECTION_CAPABILITY_NO_GIVE")
            setcvar(key + "state","WAIT_SELECTION_CAPABILITY_NO_GIVE");
        return;
    }
    if (maps\_coop_brecourt_handoff::identity(slot) != context) return;
    // Current FRESH owner only: discard provisional native fallback equipment
    // so the exact original grant order and empty-before-grant condition apply.
    self takeallweapons();
    // Exact original classic parachute grant order, not a new pickup reward.
    self giveWeapon("m1carbine");
    self giveWeapon("thompson");
    self giveWeapon("colt");
    self giveWeapon("fraggrenade");
    self request_selection(context);
    setcvar(key + "identity",context);
    setcvar(key + "give_count",getcvarint(key + "give_count") + 1);
    setcvar(key + "state","FRESH_ORIGINAL_RECIPE_REQUESTED");
}

request_selection(context)
{
    slot = self getentitynumber();
    if (maps\_coop_brecourt_handoff::identity(slot) != context || !(self hasweapon("m1carbine"))) return;
    key = "coop_select_" + slot + "_";
    ticket = getcvar("coop_spawn_ticket_" + slot);world = getcvar("coop_spawn_world");
    a = getcvar("coop_spawn_session_a");b = getcvar("coop_spawn_session_b");c = getcvar("coop_spawn_session_c");
    sequence = getcvarint(key + "seq");
    if (getcvar(key + "ticket") != ticket || getcvar(key + "world") != world || getcvar(key + "session_a") != a || getcvar(key + "session_b") != b || getcvar(key + "session_c") != c) sequence = 0;
    if (sequence < 0 || sequence >= 2147483647) return;
    setcvar(key + "source","pathfinder_initial");
    setcvar(key + "name","m1carbine");setcvar(key + "epoch",0);
    setcvar(key + "ticket",ticket);setcvar(key + "world",world);
    setcvar(key + "session_a",a);setcvar(key + "session_b",b);setcvar(key + "session_c",c);
    if (maps\_coop_brecourt_handoff::identity(slot) != context) return;
    setcvar(key + "seq",sequence + 1); // complete fixed request commit LAST
}
