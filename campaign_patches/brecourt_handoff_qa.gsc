// QA-ONLY isolated native scene. Not a Brecourt playthrough. Setup moves
// actors once; all approach/use actions after READY must be real client input.
main()
{
    // Explicitly arrange the post-document prerequisite, not a gameplay fix.
    getent("player_notallowed_clip","targetname") notsolid();
    enemies = getaiarray("axis");
    setcvar("coop_brecourt_qa_removed_scene_axis",enemies.size);
    for (i = 0; i < enemies.size; i++) enemies[i] delete();
    thread maps\_bombs::main(2, &"BRECOURT_OBJECTIVE_BOMBS", "bomb_trigger", "Has_Explosives");
    thread observe_handoff();
    thread observe_explosives();
    thread observe_plant();
    thread observe_objective();
    thread observe_gate();
    setcvar("coop_brecourt_qa_status", "WAIT_REAL_HOST_AND_JOINER");
    while (1)
    {
        players = getentarray("player", "classname");
        host = undefined; remote = undefined;
        for (i = 0; i < players.size; i++)
        {
            slot = players[i] getentitynumber();
            if (slot == 0) host = players[i];
            if (slot == 1) remote = players[i];
        }
        if (getcvar("coop_actor_mode") == "HOST" && isdefined(host) && isdefined(remote))
            if (maps\_coop_brecourt_handoff::eligible(host) && maps\_coop_brecourt_handoff::eligible(remote)) break;
        wait 0.1;
    }
    // Arrange the post-goal precondition at the actual live NPC position.
    // Full original navigation to wounded_node2 is NOT tested by this fixture.
    node = spawnstruct(); node.origin = level.moody.origin; node.angles = level.moody.angles;
    level.coop_qa_handoff_node = node;
    level.moodyloc = node.origin;
    // The original pre-goal branch establishes these actor fields. UO's
    // can_shoot later restores old_maxsightdistsqrd; do not invent its value.
    level.moody maps\_utility::cant_shoot();
    level.moody.ignoreme = true;
    setcvar("coop_brecourt_qa_moody_setup_distance",distance(level.moody.origin,level.moodyloc));
    anchor = spawn("script_origin",node.origin);
    setcvar("coop_brecourt_qa_anchor",anchor getentitynumber());
    setcvar("coop_brecourt_qa_setup_host_distance",distance(host.origin,level.moodyloc));
    setcvar("coop_brecourt_qa_setup_remote_distance",distance(remote.origin,level.moodyloc));
    level.dummybomb = getentarray("dummybomb", "targetname");
    for (i = 0; i < level.dummybomb.size; i++)
        level.dummybomb[i].trigger = getent(level.dummybomb[i].target,"targetname");
    objective_add(3, "active", &"BRECOURT_OBJECTIVE_COVERFIRE", node.origin);
    setcvar("coop_brecourt_qa_status", "READY_ISOLATED_NOT_CAMPAIGN");
    sequence = "";
    while (getcvar("coop_brecourt_qa_run") != "1")
    {
        // Explicit fixture health boundaries; not a damage/death-life claim.
        if (getcvar("coop_brecourt_qa_health_boundary") == "1") remote.health = 1;
        if (getcvar("coop_brecourt_qa_health_boundary") == "0") remote.health = 0;
        request = getcvar("coop_brecourt_qa_probe_seq");
        if (request != "" && request != sequence)
        {
            actor = maps\_coop_brecourt_handoff::nearest_recipient(level.moodyloc,100);
            found = -1;
            if (isdefined(actor)) found = actor getentitynumber();
            setcvar("coop_brecourt_qa_probe_actor",found);
            setcvar("coop_brecourt_qa_remote_health",remote.health);
            setcvar("coop_brecourt_qa_remote_alive",isalive(remote));
            setcvar("coop_brecourt_qa_moody_distance",distance(level.moody.origin,level.moodyloc));
            setcvar("coop_brecourt_qa_host_distance",distance(host.origin,level.moodyloc));
            setcvar("coop_brecourt_qa_remote_distance",distance(remote.origin,level.moodyloc));
            setcvar("coop_brecourt_qa_probe_ack",request);
            sequence = request;
        }
        wait 0.1;
    }
    // This is the same factored original normal branch called by production.
    maps\brecourt::Coop_NormalHandoffAfterGoal(level.coop_qa_handoff_node);
    setcvar("coop_brecourt_qa_status", "ORIGINAL_NORMAL_HANDOFF_RETURNED");
}

observe_handoff()
{
    level waittill("coop_brecourt_handoff_recipient",actor);
    setcvar("coop_brecourt_qa_actor",actor getentitynumber());
    setcvar("coop_brecourt_qa_actor_health",actor.health);
    setcvar("coop_brecourt_qa_actor_identity",maps\_coop_brecourt_handoff::identity(actor getentitynumber()));
    setcvar("coop_brecourt_qa_host_distance_at_action",distance(level.player.origin,level.moodyloc));
}

observe_explosives()
{
    level waittill("Has_Explosives");
    setcvar("coop_brecourt_qa_original_has_explosives", "1");
    wait 0.1;
    bombs = getentarray("bomb_trigger", "targetname");
    ready = 0;
    for (i = 0; i < bombs.size; i++)
        if (isdefined(bombs[i].realOrigin) && bombs[i].origin == bombs[i].realOrigin) ready++;
    setcvar("coop_brecourt_qa_original_bombs_enabled", ready);
}

observe_plant()
{
    level waittill("bomb_trigger planted");
    setcvar("coop_brecourt_qa_original_bomb_planted", "1");
}

observe_objective()
{
    level waittill("coop_brecourt_qa_objective4_done");
    setcvar("coop_brecourt_qa_original_objective4_done", "1");
}

observe_gate()
{
    level waittill("coop_brecourt_handoff_gate_ready");
    setcvar("coop_brecourt_qa_gate_waiting", "1");
}
