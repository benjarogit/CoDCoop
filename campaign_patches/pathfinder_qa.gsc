// QA-only read-only mission observation. No flags/objectives/inventory writes,
// no actor/object movement, and no replacement of the normal original intro.
main()
{
    thread observe_legbag();
    thread observe_beacon();
    thread observe_objectives();
    thread observe_landing();
    bag = getent("legbag", "targetname");
    beacon = getent("beacon", "targetname");
    level.coop_pathfinder_qa_bag_origin = bag.origin;
    setcvar("coop_pathfinder_qa_bag_entity",bag getentitynumber());
    setcvar("coop_pathfinder_qa_beacon_entity",beacon getentitynumber());
    setcvar("coop_pathfinder_qa_bag_x",bag.origin[0]);
    setcvar("coop_pathfinder_qa_bag_y",bag.origin[1]);
    setcvar("coop_pathfinder_qa_bag_z",bag.origin[2]);
    setcvar("coop_pathfinder_qa_beacon_x",beacon.origin[0]);
    setcvar("coop_pathfinder_qa_beacon_y",beacon.origin[1]);
    setcvar("coop_pathfinder_qa_beacon_z",beacon.origin[2]);
    setcvar("coop_pathfinder_qa_status","NATURAL_INTRO_OBSERVATION_ONLY");
    wait 0.1;
    previous_pistol = undefined;
    while (1)
    {
        pistol = level.player getweaponslotammo("pistol");
        if (!isdefined(previous_pistol) || pistol != previous_pistol)
        {
            setcvar("coop_pathfinder_qa_host_pistol_stock",pistol);
            setcvar("coop_pathfinder_qa_host_pistol_time",gettime());
            setcvar("coop_pathfinder_qa_host_pistol_world",getcvar("coop_spawn_world"));
            setcvar("coop_pathfinder_qa_host_pistol_inventory_state",getcvar("coop_inventory_0_state"));
            previous_pistol = pistol;
        }
        setcvar("coop_pathfinder_qa_bag_exists",isdefined(bag));
        setcvar("coop_pathfinder_qa_beacon_model",beacon.model);
        if (isdefined(level.flag["legbag"])) setcvar("coop_pathfinder_qa_legbag_flag",level.flag["legbag"]);
        if (isdefined(level.flag["flares set"])) setcvar("coop_pathfinder_qa_beacon_flag",level.flag["flares set"]);
        wait 0.1;
    }
}

observe_landing()
{
    level waittill("coop_pathfinder_qa_landed");
    setcvar("coop_pathfinder_qa_original_landed",1);
}

observe_legbag()
{
    level waittill("coop_pathfinder_legbag_actor",actor);
    setcvar("coop_pathfinder_qa_legbag_actor",actor getentitynumber());
    setcvar("coop_pathfinder_qa_legbag_host_distance",distance(level.player.origin,level.coop_pathfinder_qa_bag_origin));
    setcvar("coop_pathfinder_qa_legbag_actor_identity",maps\_coop_brecourt_handoff::identity(actor getentitynumber()));
}

observe_beacon()
{
    level waittill("coop_pathfinder_beacon_actor",actor);
    setcvar("coop_pathfinder_qa_beacon_actor",actor getentitynumber());
    setcvar("coop_pathfinder_qa_beacon_host_distance",distance(level.player.origin,getent("beacon","targetname").origin));
    setcvar("coop_pathfinder_qa_beacon_actor_identity",maps\_coop_brecourt_handoff::identity(actor getentitynumber()));
}

observe_objectives()
{
    counts = []; counts[1] = 0; counts[2] = 0;
    while (1)
    {
        level waittill("coop_pathfinder_objective_done",objective);
        counts[objective]++;
        setcvar("coop_pathfinder_qa_objective_" + objective + "_count",counts[objective]);
    }
}
