// Shared predicates, executed once by the authoritative mission script.
// The protagonist (level.player) still owns cinematic and narrative roles.
is_player(actor)
{
    if (!isdefined(actor))
        return false;
    players = getentarray("player", "classname");
    for (i = 0; i < players.size; i++)
    {
        if (players[i] == actor)
            return true;
    }
    return false;
}
