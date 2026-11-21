// Test fixture only: the builder appends this file exclusively with --qa.
// Uses actual GSC inventory APIs and observes the normal asynchronous workers.
Coop_QAProbe()
{
    while (getcvar("coop_uf_probe") != "run")
        wait 0.1;
    players = getentarray("player", "classname");
    if (players.size < 2)
    {
        setcvar("coop_uf_probe_result", "FAIL_need_two_players");
        return;
    }
    for (i = 0; i < 2; i++)
    {
        oldpistol[i] = players[i] getweaponslotweapon("pistol");
        oldammo[i] = players[i] getweaponslotammo("pistol");
        if (isdefined(oldpistol[i]) && oldpistol[i] != "" && oldpistol[i] != "none")
            players[i] takeweapon(oldpistol[i]);
        players[i] giveweapon("binoculars");
        players[i] setweaponslotammo("pistol", 3 + 4 * i);
    }
    wait 0.4;
    players[0] setweaponslotammo("pistol", 2);
    wait 0.4;
    first = isdefined(players[0].coop_binocular_stockpile) && players[0].coop_binocular_stockpile == 2;
    separate = (players[1] getweaponslotammo("pistol")) == 7;
    players[1] setweaponslotammo("pistol", 6);
    wait 0.4;
    second = isdefined(players[1].coop_binocular_stockpile) && players[1].coop_binocular_stockpile == 6;
    firstunchanged = isdefined(players[0].coop_binocular_stockpile) && players[0].coop_binocular_stockpile == 2;
    mount0 = players[0] Coop_MakeMount(0);
    mount1 = players[1] Coop_MakeMount(1);
    mounts = isdefined(mount0) && isdefined(mount1) && mount0 != mount1;
    if (mounts)
        mounts = mount0.coop_creator == players[0] && mount1.coop_creator == players[1];
    if (isdefined(mount0)) mount0 delete();
    if (isdefined(mount1)) mount1 delete();
    for (i = 0; i < 2; i++)
    {
        players[i] takeweapon("binoculars");
        slot = players[i] getweaponslotweapon("pistol");
        if (isdefined(oldpistol[i]) && oldpistol[i] != "" && oldpistol[i] != "none" && (!isdefined(slot) || slot == "" || slot == "none"))
        {
            players[i] giveweapon(oldpistol[i]);
            players[i] setweaponslotammo("pistol", oldammo[i]);
        }
    }
    if (first && separate && second && firstunchanged && mounts)
    {
        setcvar("coop_uf_probe_result", "PASS_ammo_isolation_native_mounts");
        println("COOP_UF_QA PASS ammo_isolation_native_mounts");
    }
    else
    {
        setcvar("coop_uf_probe_result", "FAIL_ammo_isolation_or_mounts");
        println("COOP_UF_QA FAIL ", first, separate, second, firstunchanged, mounts);
    }
}

// Observe a projectile thrown through actual joiner input. This never creates a
// missile or writes the native registry: the engine must publish the ownership.
Coop_QAOwnerProbe()
{
    while (getcvar("coop_uf_owner_probe") != "arm")
        wait 0.1;
    players = getentarray("player", "classname");
    if (players.size < 2)
    {
        setcvar("coop_uf_owner_result", "FAIL_need_two_players");
        return;
    }
    remote = players[1];
    weapon = remote getweaponslotweapon("grenade");
    if (!isdefined(weapon) || weapon == "" || weapon == "none")
    {
        setcvar("coop_uf_owner_result", "FAIL_no_grenade_weapon");
        return;
    }
    remote giveMaxAmmo(weapon);
    setcvar("coop_uf_owner_weapon", weapon);
    println("COOP_UF_OWNER_READY ", weapon, " player ", remote getentitynumber());
    setcvar("coop_uf_owner_result", "READY");
    started = gettime();
    while (gettime() - started < 15000)
    {
        grenades = getentarray("grenade", "classname");
        for (i = 0; i < grenades.size; i++)
        {
            owner = Coop_GrenadeOwner(grenades[i]);
            if (isdefined(owner) && owner == remote)
            {
                println("COOP_UF_OWNER_PASS entity ", grenades[i] getentitynumber(), " owner ", owner getentitynumber());
                setcvar("coop_uf_owner_result", "PASS_actual_remote_projectile");
                return;
            }
        }
        wait 0.05;
    }
    setcvar("coop_uf_owner_result", "FAIL_no_owned_remote_projectile");
}

// Give a real remote actor the normal mine weapon, then wait for real input to
// pass through the engine and the production scanner/PlantMine handlers.
Coop_QAMineProbe()
{
    while (getcvar("coop_uf_mine_probe") != "arm") wait 0.1;
    players = getentarray("player", "classname");
    remote = players[1];
    host = players[0];
    if ((host getweaponslotweapon("grenade")) == "land_mine")
    {
        setcvar("coop_uf_mine_result", "FAIL_host_already_carries_mine");
        return;
    }
    oldweapon = remote getweaponslotweapon("grenade");
    oldammo = remote getweaponslotammo("grenade");
    hostorg = host.origin;
    if (!isdefined(remote.placedMines)) remote.placedMines = 0;
    before = remote.placedMines;
    if (isdefined(oldweapon) && oldweapon != "") remote takeweapon(oldweapon);
    remote giveweapon("land_mine");
    remote setweaponslotammo("grenade", 2);
    setcvar("coop_uf_mine_result", "READY");
    started = gettime();
    found = false;
    while (gettime() - started < 15000)
    {
        if (remote.placedMines > before)
        {
            if (isdefined(remote.mine[remote.placedMines]))
            {
                wait 0.5;
                found = isdefined(remote.mine[remote.placedMines]);
                break;
            }
        }
        wait 0.05;
    }
    if (found && distance(hostorg, host.origin) < 4)
    {
        println("COOP_UF_MINE_PASS remote ", remote getentitynumber(), " mine ", remote.mine[remote.placedMines] getentitynumber());
        setcvar("coop_uf_mine_result", "PASS_actual_remote_mine_host_unchanged");
        // The original pickup worker must create a real item and allow the
        // standing owner to collect it; do not notify/delete it to fake pickup.
        pickupstart = gettime();
        while (isdefined(remote.mine[remote.placedMines]) && gettime() - pickupstart < 6000)
            wait 0.1;
        if (!isdefined(remote.mine[remote.placedMines]) && (remote getweaponslotammo("grenade")) >= 2)
        {
            setcvar("coop_uf_mine_pickup", "PASS_actual_remote_pickup");
            before_second = remote.placedMines;
            setcvar("coop_uf_mine_detonation", "READY");
            second_start = gettime();
            while (remote.placedMines == before_second && gettime() - second_start < 15000)
                wait 0.05;
            if (remote.placedMines > before_second && isdefined(remote.mine[remote.placedMines]))
            {
                mine = remote.mine[remote.placedMines];
                targets = getaiarray("axis");
                target = undefined;
                for (i = 0; i < targets.size; i++)
                {
                    if (isalive(targets[i]) && targets[i].health > 1) { target = targets[i]; break; }
                }
                if (isdefined(target))
                {
                    oldorg = target.origin;
                    oldhealth = target.health;
                    // Fixture positioning of an existing live enemy establishes
                    // the proximity condition. Explosion and damage stay on the
                    // original UF worker, without fake trigger notifications.
                    target teleport(mine.origin + (16,0,0), target.angles, true);
                    setcvar("coop_uf_mine_enemy", target getentitynumber());
                    setcvar("coop_uf_mine_health_before", oldhealth);
                    setcvar("coop_uf_mine_initial_distance", distance(target.origin, mine.origin));
                    trigged = false;
                    detonation_start = gettime();
                    while (gettime() - detonation_start < 4000 && isdefined(mine))
                    {
                        if (isdefined(mine.trigged)) trigged = true;
                        wait 0.05;
                    }
                    damaged = !isdefined(target) || !isalive(target) || target.health < oldhealth;
                    setcvar("coop_uf_mine_trigger_observed", trigged);
                    setcvar("coop_uf_mine_exists_after", isdefined(mine));
                    setcvar("coop_uf_mine_wait_ms", gettime() - detonation_start);
                    if (isdefined(target)) setcvar("coop_uf_mine_health_after", target.health);
                    if (isdefined(target) && isdefined(mine)) setcvar("coop_uf_mine_final_distance", distance(target.origin, mine.origin));
                    setcvar("coop_uf_mine_ammo_after", remote getweaponslotammo("grenade"));
                    if (trigged && !isdefined(mine) && damaged)
                        setcvar("coop_uf_mine_detonation", "PASS_real_enemy_proximity_damage");
                    else
                        setcvar("coop_uf_mine_detonation", "FAIL_no_natural_explosion_damage");
                    if (isdefined(target) && isalive(target)) target teleport(oldorg, target.angles, true);
                }
                else setcvar("coop_uf_mine_detonation", "FAIL_no_live_axis_fixture_target");
            }
            else setcvar("coop_uf_mine_detonation", "FAIL_no_second_mine");
        }
        else
            setcvar("coop_uf_mine_pickup", "FAIL_mine_not_collected");
    }
    else
        setcvar("coop_uf_mine_result", "FAIL_remote_mine_or_host_origin");
    // Remove only test-created mines through the normal UF cleanup path.
    if (found && isdefined(remote.mine[remote.placedMines])) remote deleteMine(remote.placedMines);
    remote takeweapon("land_mine");
    if (isdefined(oldweapon) && oldweapon != "")
    {
        remote giveweapon(oldweapon);
        remote setweaponslotammo("grenade", oldammo);
    }
}

// Test-only native cinematic request, triggered only after real clients joined.
Coop_QAMovieProbe()
{
    while (getcvar("coop_qa_movie") != "run") wait 0.1;
    println("COOP_QA_NATIVE_CINEMATIC cod_end.roq");
    cinematic("cod_end.roq");
}

Coop_QAAIDamageWatch(attacker)
{
    self endon("coop_qa_ai_done");
    while (1)
    {
        self waittill("damage", damage, who);
        if (isdefined(who) && who == attacker && damage > 0)
        {
            self.coop_qa_ai_damaged = true;
            setcvar("coop_uf_ai_actual_attacker", who getentitynumber());
            setcvar("coop_uf_ai_actual_victim", self getentitynumber());
            setcvar("coop_uf_ai_damage_amount", damage);
            println("COOP_UF_AI_DAMAGE attacker ", who getentitynumber(), " victim ", self getentitynumber(), " amount ", damage);
            return;
        }
    }
}

// No enemy, target, goal, accuracy or damage assignment: native AI must select
// the real remote player and deliver its normal damage notification.
Coop_QAAIProbe()
{
    while (getcvar("coop_uf_ai_probe") != "arm") wait 0.1;
    players = getentarray("player", "classname");
    remote = players[1];
    host = players[0];
    targets = getaiarray("axis");
    target = undefined;
    for (i = 0; i < targets.size; i++)
        if (isalive(targets[i]) && targets[i].health > 1) { target = targets[i]; break; }
    if (!isdefined(target))
    {
        setcvar("coop_uf_ai_result", "FAIL_no_live_axis_fixture_target");
        return;
    }
    oldorg = target.origin;
    oldhealth = remote.health;
    remote.coop_qa_ai_damaged = undefined;
    remote thread Coop_QAAIDamageWatch(target);
    direction = vectornormalize(remote.origin - host.origin);
    destination = remote.origin + maps\_utility::vectorScale(direction, 32);
    facing = vectortoangles(remote.origin - destination);
    target teleport(destination, facing, true);
    setcvar("coop_uf_ai_fixture_actor", target getentitynumber());
    setcvar("coop_uf_ai_host_distance", distance(target.origin, host.origin));
    setcvar("coop_uf_ai_remote_distance", distance(target.origin, remote.origin));
    setcvar("coop_uf_ai_actor_health", target.health);
    setcvar("coop_uf_ai_health_before", oldhealth);
    if (isdefined(target.targetname)) setcvar("coop_uf_ai_actor_name", target.targetname);
    if (isdefined(target.script_noteworthy)) setcvar("coop_uf_ai_actor_note", target.script_noteworthy);
    if (isdefined(target.animname)) setcvar("coop_uf_ai_actor_animname", target.animname);
    if (isdefined(target.anim_mode)) setcvar("coop_uf_ai_actor_anim_mode", target.anim_mode);
    if (isdefined(target.anim_pose)) setcvar("coop_uf_ai_actor_pose", target.anim_pose);
    if (isdefined(target.team)) setcvar("coop_uf_ai_actor_team", target.team);
    if (isdefined(target.ignoreme)) setcvar("coop_uf_ai_actor_ignoreme", target.ignoreme);
    if (isdefined(host.ignoreme)) setcvar("coop_uf_ai_host_ignoreme", host.ignoreme);
    if (isdefined(remote.ignoreme)) setcvar("coop_uf_ai_remote_ignoreme", remote.ignoreme);
    if (isdefined(target.animscript)) setcvar("coop_uf_ai_actor_animscript", target.animscript);
    if (isdefined(target.script_state)) setcvar("coop_uf_ai_actor_script_state", target.script_state);
    if (isdefined(target.state)) setcvar("coop_uf_ai_actor_state", target.state);
    sight = bullettrace(target.origin + (0,0,60), remote.origin + (0,0,60), true, target);
    setcvar("coop_uf_ai_los_fraction", sight["fraction"]);
    if (isdefined(sight["entity"])) setcvar("coop_uf_ai_los_entity", sight["entity"] getentitynumber());
    println("COOP_UF_AI_FIXTURE actor ", target getentitynumber(), " host_distance ", distance(target.origin, host.origin), " remote_distance ", distance(target.origin, remote.origin));
    chosen = false;
    started = gettime();
    while (gettime() - started < 15000 && isalive(remote))
    {
        if (isdefined(target) && isdefined(target.enemy) && target.enemy == remote)
        {
            if (!chosen) println("COOP_UF_AI_CHOSE_REMOTE ", remote getentitynumber());
            chosen = true;
        }
        if (chosen && isdefined(remote.coop_qa_ai_damaged) && remote.health < oldhealth)
            break;
        wait 0.05;
    }
    setcvar("coop_uf_ai_chosen", chosen);
    setcvar("coop_uf_ai_health_after", remote.health);
    if (isdefined(target) && isdefined(target.enemy)) setcvar("coop_uf_ai_enemy_after", target.enemy getentitynumber());
    if (chosen && isdefined(remote.coop_qa_ai_damaged) && remote.health < oldhealth)
        setcvar("coop_uf_ai_result", "PASS_native_choice_attacker_damage");
    else
    {
        println("COOP_UF_AI_FAIL chosen ", chosen, " health ", oldhealth, " -> ", remote.health);
        setcvar("coop_uf_ai_result", "FAIL_native_choice_or_damage");
    }
    remote notify("coop_qa_ai_done");
    if (isdefined(target) && isalive(target)) target teleport(oldorg, target.angles, true);
}

// Actual remote inventory and real BSP terrain. Never synthesizes a mount:
// the production worker must create one after its unmodified placement checks.
Coop_QAMGProbe()
{
    while (getcvar("coop_uf_mg_probe") != "arm") wait 0.1;
    players = getentarray("player", "classname");
    remote = players[1];
    oldorg = remote.origin;
    oldangles = remote.angles;
    primary = remote getweaponslotweapon("primary");
    secondary = remote getweaponslotweapon("primaryb");
    if (!Coop_QAMGWeapon(primary) && !Coop_QAMGWeapon(secondary))
    {
        if (isdefined(primary) && primary != "none" && primary != "") remote takeweapon(primary);
        remote giveweapon("mg30cal");
    }
    if (Coop_QAMGWeapon(remote getweaponslotweapon("primary"))) slot = "primary";
    else if (Coop_QAMGWeapon(remote getweaponslotweapon("primaryb"))) slot = "primaryb";
    else
    {
        setcvar("coop_uf_mg_phase", "FAIL_no_MG_inventory_slot");
        return;
    }
    remote giveMaxAmmo("mg30cal");
    setcvar("coop_uf_mg_slot", slot);
    setcvar("coop_uf_mg_stance", remote getstance());
    setcvar("coop_uf_mg_phase", "EQUIP");
    equipstart = gettime();
    while (!Coop_QAMGWeapon(remote getcurrentweapon()) && gettime() - equipstart < 5000) wait 0.1;
    if (!Coop_QAMGWeapon(remote getcurrentweapon()))
    {
        setcvar("coop_uf_mg_weapon_at_equip_failure", remote getcurrentweapon());
        setcvar("coop_uf_mg_slot_at_equip_failure", remote getweaponslotweapon(slot));
        setcvar("coop_uf_mg_phase", "FAIL_normal_equip_input");
        return;
    }
    if ((remote getcurrentweapon()) == "mg30cal" || (remote getcurrentweapon()) == "mg30Cal")
        setcvar("coop_uf_mg_phase", "SELECT_DEPLOYABLE_MODE");
    modestart = gettime();
    while ((remote getcurrentweapon()) != "mg30cal_de" && (remote getcurrentweapon()) != "mg30Cal_de" && gettime() - modestart < 5000) wait 0.1;
    if ((remote getcurrentweapon()) != "mg30cal_de" && (remote getcurrentweapon()) != "mg30Cal_de")
    {
        setcvar("coop_uf_mg_weapon_at_mode_failure", remote getcurrentweapon());
        setcvar("coop_uf_mg_phase", "FAIL_normal_weapalt_input");
        return;
    }
    found = false;
    emplacements = getentarray("misc_mg42", "classname");
    if (!emplacements.size)
    {
        setcvar("coop_uf_mg_phase", "FAIL_no_authored_MG_cover");
        return;
    }
    cover = emplacements[0];
    center = cover.origin - maps\_utility::vectorScale(anglestoforward(cover.angles), 48);
    setcvar("coop_uf_mg_cover_entity", cover getentitynumber());
    // Search around real map-authored MG cover. Every candidate still passes
    // the unchanged shipped placement and barrel-clearance checks.
    for (radius = 0; radius <= 128 && !found; radius += 16)
    {
        for (bearing = 0; bearing < 360 && !found; bearing += 45)
        {
            offset = maps\_utility::vectorScale(anglestoforward((0,bearing,0)), radius);
            floortrace = bullettrace(center + offset + (0,0,80), center + offset + (0,0,-128), false, undefined);
            if (floortrace["fraction"] == 1) continue;
            candidate = floortrace["position"] + (0,0,1);
            remote setorigin(candidate);
            for (yaw = 0; yaw < 360 && !found; yaw += 45)
            {
                remote setplayerangles((0,yaw,0));
                if (remote BipodPlaceable())
                {
                    // Let actual player hull collision and gravity settle;
                    // a point trace alone does not establish a valid player pose.
                    before_settle = remote.origin;
                    wait 0.6;
                    if (distance(before_settle, remote.origin) > 4 || !(remote BipodPlaceable())) continue;
                    found = true;
                    setcvar("coop_uf_mg_support_settle_delta", distance(before_settle, remote.origin));
                    setcvar("coop_uf_mg_support_distance", distance(oldorg, candidate));
                    setcvar("coop_uf_mg_support_yaw", yaw);
                    break;
                }
            }
            wait 0.05;
        }
    }
    if (!found)
    {
        remote setorigin(oldorg);
        remote setplayerangles(oldangles);
        setcvar("coop_uf_mg_phase", "FAIL_no_valid_local_support");
        return;
    }
    started = gettime();
    while (!isdefined(remote.coop_mount_mg) && gettime() - started < 3000) wait 0.05;
    if (!isdefined(remote.coop_mount_mg) || remote.coop_mount_mg.coop_creator != remote)
    {
        setcvar("coop_uf_mg_phase", "FAIL_production_worker_no_mount");
        return;
    }
    setcvar("coop_uf_mg_mount_entity", remote.coop_mount_mg getentitynumber());
    setcvar("coop_uf_mg_clip_before", remote getweaponslotclipammo(slot));
    setcvar("coop_uf_mg_phase", "READY_NATIVE_DEPLOY");
    while (getcvar("coop_uf_mg_probe") != "fired") wait 0.05;
    setcvar("coop_uf_mg_ads_after", remote isads());
    setcvar("coop_uf_mg_clip_after", remote getweaponslotclipammo(slot));
    if ((remote isads()) && (remote getweaponslotclipammo(slot)) < getcvarint("coop_uf_mg_clip_before"))
        setcvar("coop_uf_mg_phase", "PASS_real_remote_ammo_consumed");
    else
        setcvar("coop_uf_mg_phase", "FAIL_real_remote_no_ammo_consumed");
}

Coop_QAMGWeapon(weapon)
{
    return isdefined(weapon) && (weapon == "mg30cal" || weapon == "mg30Cal" || weapon == "mg30cal_de" || weapon == "mg30Cal_de");
}
