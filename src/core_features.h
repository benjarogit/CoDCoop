#pragma once
#include <cstdint>
namespace core_features {
// Compiled API support, not proof that hooks/content are ready at runtime.
// Read directly from PE data exports; validators must never execute the DLL.
constexpr uint32_t OWNER_INVENTORY=1u;
constexpr uint32_t ACTOR_SELECTION=2u;
constexpr uint32_t ACTOR_ELIGIBILITY=4u;
constexpr uint32_t PATHFINDER_INITIAL=8u; // original recipe in variants1/2/3 only
constexpr uint32_t RESOURCE_BOOTSTRAP=16u; // compiled API, not runtime closure approval
constexpr uint32_t LOCALIZED_BANNERS=32u; // native key/literal formatting; owned locale bank also required
constexpr uint32_t COMPILED=OWNER_INVENTORY|ACTOR_SELECTION|ACTOR_ELIGIBILITY|PATHFINDER_INITIAL|RESOURCE_BOOTSTRAP|LOCALIZED_BANNERS;
}
