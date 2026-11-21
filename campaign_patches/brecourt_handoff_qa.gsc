// QA-ONLY isolated native scene. Not a Brecourt playthrough. Setup moves
// actors once; all approach/use actions after READY must be real client input.
main()
{
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
    node = getnode("wounded_node2", "targetname");
    forward = anglestoforward((0,node.angles[1],0));
    level.moodyloc = node.origin;
    level.moody setorigin(node.origin);
    level.moody setgoalnode(node);
    host setorigin(node.origin + forward * 400);
    remote setorigin(node.origin + forward * 200);
    remote setplayerangles((0,node.angles[1]+180,0));
    level.dummybomb = getentarray("dummybomb", "targetname");
    for (i = 0; i < level.dummybomb.size; i++)
        level.dummybomb[i].trigger = getent(level.dummybomb[i].target,"targetname");
    thread maps\_bombs::main(2, &"BRECOURT_OBJECTIVE_BOMBS", "bomb_trigger", "Has_Explosives");
    thread observe_handoff();
    thread observe_explosives();
    thread observe_plant();
    setcvar("coop_brecourt_qa_status", "READY_ISOLATED_NOT_CAMPAIGN");
    sequence = "";
    while (getcvar("coop_brecourt_qa_run") != "1")
    {
        request = getcvar("coop_brecourt_qa_probe_seq");
        if (request != "" && request != sequence)
        {
            actor = maps\_coop_brecourt_handoff::nearest_recipient(level.moodyloc,100);
            found = -1;
            if (isdefined(actor)) found = actor getentitynumber();
            setcvar("coop_brecourt_qa_probe_actor",found);
            setcvar("coop_brecourt_qa_host_distance",distance(host.origin,level.moodyloc));
            setcvar("coop_brecourt_qa_remote_distance",distance(remote.origin,level.moodyloc));
            setcvar("coop_brecourt_qa_probe_ack",request);
            sequence = request;
        }
        wait 0.1;
    }
    // This is the same factored original normal branch called by production.
    maps\brecourt::Coop_NormalHandoff();
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
}

observe_plant()
{
    level waittill("bomb_trigger planted");
    setcvar("coop_brecourt_qa_original_bomb_planted", "1");
}
