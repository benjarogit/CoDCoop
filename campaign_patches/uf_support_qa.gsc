// QA-only observers inserted around the original world action, never a
// replacement explosion, timer, aircraft, projectile or owner assignment.
Coop_QAAirBomber(caller)
{
    if (getcvar("coop_uf_air_probe") != "arm") return;
    setcvar("coop_uf_air_calls", getcvarint("coop_uf_air_calls") + 1);
    if (isdefined(caller)) setcvar("coop_uf_air_caller", caller getentitynumber());
    else setcvar("coop_uf_air_caller", -1);
}
Coop_QAAirPlane(plane)
{
    if (getcvar("coop_uf_air_probe") != "arm") return;
    setcvar("coop_uf_air_plane", plane getentitynumber());
    setcvar("coop_uf_air_model", plane.model);
}
Coop_QAAirImpact()
{
    if (getcvar("coop_uf_air_probe") != "arm") return;
    setcvar("coop_uf_air_impacts", getcvarint("coop_uf_air_impacts") + 1);
}
Coop_QAAirProbe()
{
    while (getcvar("coop_uf_air_probe") != "arm") wait 0.1;
    players = getentarray("player", "classname");
    host = players[0];
    remote = players[1];
    if (getcvar("sp_ammo") == "1")
    {
        setcvar("coop_uf_air_phase", "FAIL_infinite_ammo_configuration");
        return;
    }
    if ((host getweaponslotweapon("grenade")) == "smokegrenade")
    {
        setcvar("coop_uf_air_phase", "FAIL_need_host_non_smoke_resource_regression");
        return;
    }
    if (!isdefined(level.stuka_type) || !isdefined(level.coop_air_assets_ready))
    {
        setcvar("coop_uf_air_phase", "FAIL_shared_air_resources_missing");
        return;
    }
    hostammo = host getweaponslotammo("grenade");
    oldgrenade = remote getweaponslotweapon("grenade");
    if (isdefined(oldgrenade) && oldgrenade != "none" && oldgrenade != "") remote takeweapon(oldgrenade);
    // Fixture selects an allowed UF item with its normal native inventory API;
    // no ammo setter, infinite-ammo switch or cooldown override is used.
    remote giveweapon("smokegrenade");
    before = remote getweaponslotammo("grenade");
    setcvar("coop_uf_air_ammo_before", before);
    setcvar("coop_uf_air_host_ammo_before", hostammo);
    setcvar("coop_uf_air_calls", 0);
    setcvar("coop_uf_air_impacts", 0);
    setcvar("coop_uf_air_plane", -1);
    setcvar("coop_uf_air_caller", -1);
    started = gettime();
    setcvar("coop_uf_air_phase", "READY_THROW");
    owner_seen = false;
    while (gettime() - started < 90000)
    {
        if (!owner_seen)
        {
            grenades = getentarray("grenade", "classname");
            for (i = 0; i < grenades.size; i++)
                if (grenades[i].model == "xmodel/w_us_grn_m18_game")
                {
                    owner = Coop_GrenadeOwner(grenades[i]);
                    if (isdefined(owner) && owner == remote)
                    {
                        owner_seen = true;
                        setcvar("coop_uf_air_projectile", grenades[i] getentitynumber());
                        setcvar("coop_uf_air_projectile_owner", owner getentitynumber());
                    }
                }
        }
        if (owner_seen && getcvarint("coop_uf_air_impacts") > 0)
        {
            after = remote getweaponslotammo("grenade");
            setcvar("coop_uf_air_ammo_after", after);
            setcvar("coop_uf_air_host_ammo_after", host getweaponslotammo("grenade"));
            setcvar("coop_uf_air_elapsed_ms", gettime() - started);
            if (after == before - 1 && (host getweaponslotammo("grenade")) == hostammo &&
                getcvarint("coop_uf_air_calls") == 1 && getcvarint("coop_uf_air_caller") == 1 &&
                getcvarint("coop_uf_air_plane") >= 0 && gettime() - started >= 20000)
                setcvar("coop_uf_air_phase", "PASS_remote_smoke_original_airstrike");
            else
                setcvar("coop_uf_air_phase", "FAIL_owner_cost_timing_or_duplicate");
            return;
        }
        wait 0.05;
    }
    setcvar("coop_uf_air_phase", "FAIL_no_owned_smoke_plane_or_original_impact");
}

// A normal native spotter call, a retry inside its authored 3-second fire time,
// and the original actor-local 180-second replenishment at normal timescale.
Coop_QAArtilleryProbe()
{
    while (getcvar("coop_uf_arty_probe") != "arm") wait 0.1;
    players = getentarray("player", "classname");
    host = players[0]; remote = players[1];
    if (getcvar("sp_ammo") == "1")
    {
        setcvar("coop_uf_arty_phase", "FAIL_infinite_ammo_configuration"); return;
    }
    hostammo = host getweaponslotammo("pistol");
    oldpistol = remote getweaponslotweapon("pistol");
    if (isdefined(oldpistol) && oldpistol != "none" && oldpistol != "") remote takeweapon(oldpistol);
    remote giveweapon("binoculars");
    before = remote getweaponslotammo("pistol");
    setcvar("coop_uf_arty_timescale", getcvar("timescale"));
    setcvar("coop_uf_arty_ammo_before", before);
    setcvar("coop_uf_arty_host_ammo_before", hostammo);
    if (before < 1) { setcvar("coop_uf_arty_phase", "FAIL_no_native_start_ammunition"); return; }
    eye = remote.origin + (0,0,60);
    clear = false;
    for (yaw = 0; yaw < 360 && !clear; yaw += 15)
    {
        forward = maps\_utility::vectorScale(anglestoforward((1,yaw,0)), 4096);
        trace = bullettrace(eye, eye + forward, false, remote);
        if (trace["fraction"] < 1 && distance(trace["position"], remote.origin) > 1500 && distance(trace["position"], host.origin) > 1500)
        {
            clear = true;
            remote setplayerangles((1,yaw,0));
            setcvar("coop_uf_arty_target_distance", distance(trace["position"], remote.origin));
        }
    }
    if (!clear) { setcvar("coop_uf_arty_phase", "FAIL_no_distant_visible_terrain"); return; }
    setcvar("coop_uf_arty_phase", "EQUIP");
    started = gettime();
    while ((remote getcurrentweapon()) != "binoculars" && gettime() - started < 7000) wait 0.1;
    if ((remote getcurrentweapon()) != "binoculars") { setcvar("coop_uf_arty_phase", "FAIL_normal_equip_input"); return; }
    setcvar("coop_uf_arty_phase", "READY_FIRE");
    started = gettime();
    while ((remote getweaponslotammo("pistol")) == before && gettime() - started < 10000) wait 0.05;
    first = gettime();
    if ((remote getweaponslotammo("pistol")) != before - 1)
    { setcvar("coop_uf_arty_phase", "FAIL_first_native_fire_cost"); return; }
    setcvar("coop_uf_arty_first_fire_time", first);
    wait 3.1;
    after = remote getweaponslotammo("pistol");
    setcvar("coop_uf_arty_ammo_after_early_retry", after);
    if (after != before - 1)
    { setcvar("coop_uf_arty_phase", "FAIL_early_retry_consumed_extra_token"); return; }
    setcvar("coop_uf_arty_phase", "WAIT_ORIGINAL_180_SECOND_REPLENISHMENT");
    while (gettime() - first < 182000)
    {
        current = remote getweaponslotammo("pistol");
        if (current >= before)
        {
            setcvar("coop_uf_arty_refill_elapsed_ms", gettime() - first);
            setcvar("coop_uf_arty_ammo_after_refill", current);
            setcvar("coop_uf_arty_host_ammo_after", host getweaponslotammo("pistol"));
            if (current == before && (host getweaponslotammo("pistol")) == hostammo && gettime() - first >= 179000)
                setcvar("coop_uf_arty_phase", "PASS_native_cost_cooldown_actor_refill");
            else setcvar("coop_uf_arty_phase", "FAIL_refill_timing_or_host_inventory");
            return;
        }
        wait 0.1;
    }
    setcvar("coop_uf_arty_phase", "FAIL_original_replenishment_missing");
}
