// Scoped ordinary player-operated mission objects. The authoritative script
// keeps the original single shared action and trigger lifetime.
wait_for_actor(trigger)
{
    while (1)
    {
        // A deleted trigger never authorizes a substitute world action.
        if (!isdefined(trigger)) { wait 1; continue; }
        trigger waittill("trigger", actor);
        if (!isdefined(actor)) continue;
        if (getcvar("coop_actor_api") == "1")
        {
            if (!maps\_coop_players::is_player(actor)) continue;
            if (!maps\_coop_brecourt_handoff::eligible(actor)) continue;
        }
        else if (actor != level.player) continue;
        return actor;
    }
}
