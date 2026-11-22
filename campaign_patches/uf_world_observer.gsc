// Source-only reviewed witness prototype. NOT enabled by the production builder.
// Native coop_uf_native_* publisher is a proposed ABI pending Root review.
// Writes ONLY fixed observer CVars; no actors, game/level fields or rules change.
// preinit_world is the ID observed BEFORE native GAME_INIT, not final SVid.
// Root must latch this source snapshot before a possible post-init SVid update
// and bind its final native world by the SAME private init serial/epoch.
NativeEpoch()
{
    if (getcvar("coop_uf_native_api") != "1" || getcvar("coop_uf_native_mode") != "HOST") return undefined;
    if (getcvar("coop_uf_native_intent") != "0") return undefined;
    if (getcvar("coop_uf_native_map") != getcvar("mapname")) return undefined;
    if (!isdefined(level.script) || level.script != getcvar("coop_uf_native_map")) return undefined;
    if (getcvar("coop_uf_native_preinit_world") == "") return undefined;
    if (getcvar("coop_uf_native_init") == "" || getcvar("coop_uf_native_init") == "0") return undefined;
    if (getcvar("coop_uf_native_epoch") == "") return undefined;
    return getcvar("coop_uf_native_epoch");
}

Active()
{
    epoch = NativeEpoch();
    return isdefined(epoch) && epoch == getcvar("coop_uf_world_epoch") && getcvar("coop_uf_world_status") == "WAIT";
}

Begin()
{
    epoch = NativeEpoch();
    if (!isdefined(epoch)) return;
    if (getcvar("coop_uf_world_epoch") == epoch && getcvar("coop_uf_world_status") != "WAIT") return;
    setcvar("coop_uf_world_status", "WAIT");
    setcvar("coop_uf_world_epoch", epoch);
    setcvar("coop_uf_world_map", getcvar("mapname"));
    setcvar("coop_uf_world_preinit_world", getcvar("coop_uf_native_preinit_world"));
    setcvar("coop_uf_world_init_serial", getcvar("coop_uf_native_init"));
    setcvar("coop_uf_world_graph", GraphIdentity());
    setcvar("coop_uf_world_campaign_count", "-1");
    setcvar("coop_uf_world_last_index", "-1");
    setcvar("coop_uf_world_last_class", "");
    setcvar("coop_uf_world_climate_count", "-1");
    setcvar("coop_uf_world_winter", "0");
    setcvar("coop_uf_world_winter_index", "-1");
    setcvar("coop_uf_world_winter_class", "");
    setcvar("coop_uf_world_campaign_seen", "0");
    setcvar("coop_uf_world_climate_seen", "0");
    setcvar("coop_uf_world_campaign_world", "");
    setcvar("coop_uf_world_climate_world", "");
    setcvar("coop_uf_world_year_world", "");
    setcvar("coop_uf_world_cvars_seen", "0");
    setcvar("coop_uf_world_input_loadgame", getcvar("sp_loadgame"));
    setcvar("coop_uf_world_cmp_campaign", "");
    setcvar("coop_uf_world_cmp_climate", "");
    setcvar("coop_uf_world_cmp_year", "");
    setcvar("coop_uf_world_cmp_ally_nation", "");
    setcvar("coop_uf_world_cmp_axis_nation", "");
}

CampaignFacts(count, index, classname, actual_campaign)
{
    if (!Active()) return;
    setcvar("coop_uf_world_campaign_world", getcvar("sv_serverid"));
    setcvar("coop_uf_world_campaign_count", count);
    if (count < 0 || count > 4096 || index < -1 || index >= count) { setcvar("coop_uf_world_status", "ERROR_CAMPAIGN_BOUNDS"); return; }
    if ((index == -1 && classname != "") || (index >= 0 && !KnownCampaignClass(classname))) { setcvar("coop_uf_world_status", "ERROR_CAMPAIGN_CLASS"); return; }
    setcvar("coop_uf_world_last_index", index);
    setcvar("coop_uf_world_last_class", classname);
    setcvar("coop_uf_world_cmp_campaign", actual_campaign);
    setcvar("coop_uf_world_campaign_seen", "1");
}

ClimateFacts(count, index, classname, actual_climate)
{
    if (!Active()) return;
    setcvar("coop_uf_world_climate_world", getcvar("sv_serverid"));
    setcvar("coop_uf_world_climate_count", count);
    if (count < 0 || count > 4096 || index < -1 || index >= count) { setcvar("coop_uf_world_status", "ERROR_CLIMATE_BOUNDS"); return; }
    if ((index == -1 && classname != "") || (index >= 0 && !KnownWinterClass(classname))) { setcvar("coop_uf_world_status", "ERROR_WINTER_CLASS"); return; }
    setcvar("coop_uf_world_winter", index >= 0);
    setcvar("coop_uf_world_winter_index", index);
    setcvar("coop_uf_world_winter_class", classname);
    setcvar("coop_uf_world_cmp_climate", actual_climate);
    setcvar("coop_uf_world_climate_seen", "1");
}

CvarsObserved()
{
    if (!Active()) return;
    // Native nation CVars are already assigned. level.*nation is delayed1s.
    setcvar("coop_uf_world_cmp_ally_nation", getcvar("sp_ally_nation"));
    setcvar("coop_uf_world_cmp_axis_nation", getcvar("sp_axis_nation"));
    setcvar("coop_uf_world_cvars_seen", "1");
}

YearObserved()
{
    if (!Active()) return;
    setcvar("coop_uf_world_year_world", getcvar("sv_serverid"));
    if (getcvar("coop_uf_world_campaign_seen") != "1" || getcvar("coop_uf_world_climate_seen") != "1") { setcvar("coop_uf_world_status", "ERROR_STAGE_ORDER"); return; }
    if (getcvar("coop_uf_world_input_loadgame") != "1" && getcvar("coop_uf_world_cvars_seen") != "1") { setcvar("coop_uf_world_status", "ERROR_CVARS_STAGE"); return; }
    setcvar("coop_uf_world_cmp_year", getcvar("sp_year"));
    // Independent native consumer MUST validate graph/raw inputs/comparisons.
    // OBSERVED is a synchronous prefix snapshot, NEVER resource/lobby READY.
    epoch = NativeEpoch();
    if (!isdefined(epoch) || epoch != getcvar("coop_uf_world_epoch")) return;
    if (getcvar("coop_uf_world_preinit_world") != getcvar("coop_uf_native_preinit_world") || getcvar("coop_uf_world_init_serial") != getcvar("coop_uf_native_init") || getcvar("coop_uf_world_map") != getcvar("mapname")) return;
    setcvar("coop_uf_world_status", "OBSERVED");
}
