#pragma once
#include "party_native_bridge_plan.h"
#include <set>

namespace party_native_bridge {
inline std::string Lower(std::string s){for(char& c:s)if(c>='A'&&c<='Z')c+=32;return s;}
inline bool SameJson(const party_native_json::Value& a,const party_native_json::Value& b){std::string x,y;return party_native_json::Canonical(a,x)&&party_native_json::Canonical(b,y)&&x==y;}
inline bool SetMatches(const party_native_json::Value* array,const std::set<std::string>& expected){if(!array||array->kind!=party_native_json::Value::Array||array->array.size()!=expected.size())return false;auto p=expected.begin();for(const auto& v:array->array)if(v.kind!=party_native_json::Value::String||v.string!=*p++)return false;return true;}
// This ports only the catalog's existing explicit kit/resource closure. The
// independent authoritativeWorld parameter must be produced by the native UF
// map/year resolver, NOT copied from the unverified party file by the caller.
template<class Hash>bool VerifyCatalogPlan(const Plan& plan,const party_native_json::Value& declaredWorld,const party_native_json::Value& fullPlan,
 const party_native_json::Value& installedCatalog,const party_native_json::Value& authoritativeWorld,Hash hash){
 using namespace party_native_json;
 std::string catalogBytes;Hex64 actual{};if(!SameJson(declaredWorld,authoritativeWorld)||!Canonical(installedCatalog,catalogBytes)||!hash(catalogBytes.data(),catalogBytes.size(),actual)||!Same(actual,plan.catalog))return false;
 auto families=installedCatalog.Find("families"),definitions=installedCatalog.Find("weapons");if(!families||families->kind!=Value::Object||!definitions||definitions->kind!=Value::Object)return false;
 std::set<std::string> weapons,server,media;
 auto addModel=[&](const Value* source,bool world)->bool{std::string name;if(!source||source->kind!=Value::Object||!String(source->Find("member"),name)||!qa_preload::ValidName(name))return false;name=Lower(name);media.insert(name);if(world)server.insert(name);return media.size()<=asset_bootstrap::MAX_NAMES;};
 if(!Valid(plan))return false;
 for(unsigned member=0;member<plan.roster.count;++member){unsigned slot=plan.roster.member[member].slot;const auto& kit=plan.kit[slot];if(!Text(kit.family,"abcdefghijklmnopqrstuvwxyz_"))return false;auto f=families->Find(kit.family);if(!f||f->kind!=Value::Object)return false;auto active=f->Find("active_campaign_menu"),menus=f->Find("menu_slots");if(!active||active->kind!=Value::Boolean||!active->boolean||!menus||!Keys(*menus,{"primary","secondary","pistol","grenade"}))return false;
  const char* names[]={"primary","secondary","pistol","grenade"};for(unsigned i=0;i<4;++i){auto menu=menus->Find(names[i]),choices=menu?menu->Find("choices"):nullptr;auto choice=choices?choices->Find(std::to_string(kit.choice[i]).c_str()):nullptr;auto weapon=choice?choice->Find("weapon"):nullptr;if(!weapon)return false;if(weapon->kind==Value::Null)continue;std::string name;if(!String(weapon,name))return false;name=Lower(name);if(name=="none")continue;if(!asset_bootstrap::ValidWeaponName(name))return false;weapons.insert(name);}
 }
 Value support;support.kind=Value::Array;
 auto supportRow=[&](std::initializer_list<std::pair<const char*,std::string>> fields){auto row=Value::Dict();for(const auto& field:fields)row.object[field.first]=Value::Text(field.second);support.array.push_back(std::move(row));};
 if(weapons.count("smokegrenade")){
  static const std::map<std::string,std::string> factions={{"us_air","v_us_air_p47"},{"us_inf","v_us_air_p47"},{"uk_air","v_br_air_spitfire"},{"uk_inf","v_br_air_spitfire"},{"uk_sas","v_br_air_spitfire"},{"uk_raf","v_br_air_spitfire"},{"nl_resist","v_br_air_spitfire"},{"ru","v_rs_air_il2"},{"ita","vehicle_plane_stuka"},{"ger_para","vehicle_plane_stuka"},{"ger_heer","vehicle_plane_stuka"},{"ger_ss","vehicle_plane_stuka"},{"ger_marine","vehicle_plane_stuka"}};
  std::string ally,campaign,map,plane;String(authoritativeWorld.Find("sp_ally"),ally);String(authoritativeWorld.Find("campaign"),campaign);String(authoritativeWorld.Find("map"),map);
  auto selected=factions.find(ally);if(selected!=factions.end())plane=selected->second;
  else if(campaign=="american")plane=(map=="sp_eugene"||map=="gfm_omaha")?"vehicle_plane_stuka":"v_us_air_p47";
  else if(campaign=="british")plane="v_br_air_spitfire";else if(campaign=="russian")plane="v_rs_air_il2";else return false;
  auto air=installedCatalog.Find("air_models");if(!air)return false;for(const auto& model:{plane,std::string("vehicle_tank_panzeriv_machinegun"),std::string("o_ge_prp_stukabomb")})if(!addModel(air->Find(model.c_str()),true))return false;
  weapons.insert("stuka_guns");supportRow({{"mechanic","airstrike"},{"aircraft",plane},{"authority","host-world"},{"caller","actual-projectile-owner"}});
 }
 if(weapons.count("land_mine"))supportRow({{"mechanic","mine"},{"authority","host-world"},{"owner","actual-projectile-owner"}});
 if(weapons.count("binoculars"))supportRow({{"mechanic","artillery"},{"availability","original per-player charge/cooldown rules"}});
 std::vector<std::string> pending(weapons.begin(),weapons.end());
 for(size_t i=0;i<pending.size();++i){if(pending.size()>127)return false;auto weapon=definitions->Find(pending[i].c_str());if(!weapon||weapon->kind!=Value::Object||weapon->Find("missing"))return false;auto models=weapon->Find("models"),fields=weapon->Find("server_model_fields"),alt=weapon->Find("alt_weapon");if(!models||models->kind!=Value::Object||!fields||fields->kind!=Value::Array||!alt)return false;
  for(const auto& field:fields->array){if(field.kind!=Value::String||!addModel(models->Find(field.string.c_str()),true))return false;}
  for(const auto& model:models->object)if(!addModel(&model.second,false))return false;
  if(alt->kind!=Value::Null){std::string name;if(!String(alt,name))return false;name=Lower(name);if(!asset_bootstrap::ValidWeaponName(name))return false;if(weapons.insert(name).second)pending.push_back(name);}
 }
 auto expectedSupport=fullPlan.Find("support");return SetMatches(fullPlan.Find("required_weapons"),weapons)&&SetMatches(fullPlan.Find("required_server_models"),server)&&SetMatches(fullPlan.Find("required_media_models"),media)&&expectedSupport&&SameJson(*expectedSupport,support);
}
}
