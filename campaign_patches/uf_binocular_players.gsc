// CoDCoop: initialize actor-local binocular accounting on the authoritative host.
// This code is inserted into the installed UF weapons script by the local builder.
// It deliberately leaves level.player and world-owned mission state untouched.
Coop_PrecacheMountModels()
{
    // Native item registration prepares each verified MG and its alternate.
    // World/pickup models use CS slots; first-person media uses weapon caches.
    precacheItem("mg30Cal");
    precacheItem("mg30cal_de");
    precacheItem("mg34");
    precacheItem("mg34_de");
    precacheItem("mg42");
    precacheItem("mg42_de");
    precacheItem("dp28");
}

Coop_InitMineResources()
{
    // UF normally prepares these only for the protagonist's current loadout.
    // A remote actor may carry a mine while the protagonist carries grenades.
    precacheItem("land_mine");
    precacheModel("xmodel/gamemodel_land_mine");
    level.mine = "xmodel/gamemodel_land_mine";
    level.mineSoundName = "minefield_click";
    level.mineBoomSound = 1;
    level.mineBoomSoundName = "mine_explode";
    level._effect["explode"] = loadfx("fx/weapon/explosions/grenade_flesh.efx");
}

Coop_BinocularPlayers()
{
    if (isdefined(level.coop_uf_players_started))
        return;
    level.coop_uf_players_started = true;
    wait 0.05;
    while (1)
    {
        players = getentarray("player", "classname");
        ready = 0;
        for (i = 0; i < players.size; i++)
        {
            player = players[i];
            if (isdefined(player) && isalive(player) && !isdefined(player.coop_binocular_worker))
            {
                player.coop_binocular_worker = true;
                player thread Binoculars_Ammo();
                player thread Infinite_Ammo();
                player thread Trigger_Mount();
                println("COOP_UF_BINOCULARS_START ", player getentitynumber());
            }
            if (isdefined(player.coop_binocular_worker))
                ready++;
        }
        if (!isdefined(level.coop_uf_worker_count) || level.coop_uf_worker_count != ready)
        {
            level.coop_uf_worker_count = ready;
            setcvar("coop_uf_workers", ready);
        }
        wait 0.25;
    }
}

// Native spawntriggermount(mins, maxs, crouched) creates a spatial mount
// trigger. Keep it close to its creator instead of sharing one world trigger.
Coop_MakeMount(stance)
{
    trigger = spawntriggermount(self.origin + (-24,-24,-24), self.origin + (24,24,72), stance);
    trigger.stance = stance;
    trigger.coop_creator = self;
    trigger.coop_origin = self.origin;
    trigger thread Coop_MountLifetime();
    println("COOP_UF_MOUNT_CREATE ", self getentitynumber());
    return trigger;
}

Coop_MountLifetime()
{
    while (isdefined(self.coop_creator) && isalive(self.coop_creator))
        wait 0.25;
    self delete();
}

// Native ownership is published only by the authoritative Coop host. Empty or
// cleared values are never interpreted as player zero. Let one host frame pass
// before observing a new missile to avoid reusing the previous entity's cvar.
Coop_GrenadeOwner(grenade)
{
    if (!isdefined(grenade.coop_owner_observed))
    {
        grenade.coop_owner_observed = gettime();
        return undefined;
    }
    if ((gettime() - grenade.coop_owner_observed) < 100)
        return undefined;
    count = getcvarint("coop_owner_bank_count");
    if (count < 0 || count > 128)
        return undefined;
    base = ((grenade getentitynumber()) + 1) * 4;
    ownernum = -1;
    for (bank = 0; bank < count; bank++)
    {
        key = "coop_owner_bank_" + bank;
        if (getcvar(key) == "")
            continue;
        encoded = getcvarint(key);
        if (encoded >= base && encoded < base + 4)
        {
            ownernum = encoded - base;
            break;
        }
    }
    if (ownernum == -1)
        return undefined;
    players = getentarray("player", "classname");
    for (i = 0; i < players.size; i++)
    {
        if (isdefined(players[i]) && (players[i] getentitynumber()) == ownernum)
            return players[i];
    }
    return undefined;
}

// Shared resource registration only: this neither gives equipment nor calls
// support. Register every bounded plane/FX option before local random loadouts.
Coop_PrecacheAirAssets()
{
    if (isdefined(level.coop_air_assets_ready)) return;
    precacheItem("binoculars");
    precacheItem("smokegrenade");
    precacheturret("Stuka_guns");
    precacheModel("xmodel/vehicle_plane_stuka");
    precacheModel("xmodel/vehicle_tank_panzeriv_machinegun");
    precacheModel("xmodel/o_ge_prp_stukabomb");
    precacheModel("xmodel/v_br_air_spitfire");
    precacheModel("xmodel/v_rs_air_il2");
    precacheModel("xmodel/v_us_air_p47");
    level.coop_air_fx[0] = loadfx("fx/explosions/vehicles/p47_bomb_snow_low.efx");
    level.coop_air_fx[1] = loadfx("fx/explosions/vehicles/spitfire_complete.efx");
    level.coop_air_fx[2] = loadfx("fx/explosions/vehicles/stuka_bomb.efx");
    level.coop_air_fx[3] = loadfx("fx/explosions/vehicles/stuka_bomb_low.efx");
    level.coop_air_fx[4] = loadfx("fx/explosions/vehicles/stuka_complete.efx");
    level.coop_air_fx[5] = loadfx("fx/map_bomber/fire_trail_fighter.efx");
    level.coop_air_fx[6] = loadfx("fx/UF/p47_bomb_snow.efx");
    level.coop_air_assets_ready = true;
}
