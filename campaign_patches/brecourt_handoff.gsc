// Scoped ordinary Brecourt handoff; the original NPC animation/world action
// remains in its mission function. Native eligibility is authoritative: a
// downed Coop player is still isalive() and can have health 1.
identity(slot)
{
    if (getcvar("coop_actor_api") != "1") return undefined;
    mode = getcvar("coop_actor_mode");
    if (mode == "SOLO")
    {
        native_world = getcvar("sv_serverid");
        if (slot != 0 || native_world == "") return undefined;
        return "solo|" + native_world + "|0";
    }
    if (mode != "HOST") return undefined;
    names = [];
    names[0] = "coop_spawn_session_a";
    names[1] = "coop_spawn_session_b";
    names[2] = "coop_spawn_session_c";
    names[3] = "coop_spawn_ticket_" + slot;
    parts = []; numbers = [];
    for (i = 0; i < 4; i++)
    {
        parts[i] = getcvar(names[i]); numbers[i] = getcvarint(names[i]);
        if (parts[i] == "" || parts[i] != ("" + numbers[i]) || numbers[i] < 0) return undefined;
    }
    if (numbers[2] > 3 || numbers[3] <= 0 || (numbers[0] == 0 && numbers[1] == 0 && numbers[2] == 0)) return undefined;
    world = getcvar("coop_spawn_world");
    if (world == "") return undefined;
    return parts[0] + "|" + parts[1] + "|" + parts[2] + "|" + slot + "|" + parts[3] + "|" + world;
}

eligible(actor)
{
    if (!isdefined(actor) || !isalive(actor)) return false;
    slot = actor getentitynumber();
    if (slot < 0 || slot > 3) return false;
    // Caller enumerates actual classname=player entities, not arbitrary slots.
    expected = identity(slot);
    if (!isdefined(expected)) return false;
    key = "coop_actor_" + slot + "_";
    published = getcvar(key + "identity");
    state = getcvar(key + "state");
    if (state != "ELIGIBLE" || published != expected) return false;
    if (identity(slot) != expected || getcvar(key + "identity") != published || getcvar(key + "state") != state) return false;
    return true;
}

nearest_recipient(location, radius)
{
    players = getentarray("player", "classname");
    closest = undefined;
    best_distance = radius;
    best_slot = 4;
    for (i = 0; i < players.size; i++)
    {
        actor = players[i];
        if (!eligible(actor)) continue;
        range = distance(actor.origin, location);
        slot = actor getentitynumber();
        if (range > radius) continue;
        if (!isdefined(closest) || range < best_distance || (range == best_distance && slot < best_slot))
        {
            closest = actor;
            best_distance = range;
            best_slot = slot;
        }
    }
    return closest;
}

wait_for_recipient(location, radius)
{
    if (getcvar("coop_actor_api") != "1")
    {
        // Old Core/native standalone keeps exactly the old protagonist gate.
        // It never grants an unverified remote the ordinary interaction.
        while (distance(level.player.origin, location) > radius) wait 1;
        return level.player;
    }
    while (1)
    {
        actor = nearest_recipient(location, radius);
        if (isdefined(actor)) return actor;
        wait 1; // Preserve the original mission gate's polling cadence.
    }
}
