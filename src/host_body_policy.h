#pragma once
namespace host_body_policy {
// Override is QA-only: -1 absent,0 negative control,1 enabled. A normal
// verified UO profile cannot switch off required ownership protection.
inline bool Required(bool uo,bool qa,bool prepared,int overrideValue) {
    if(!uo) return false;
    if(!qa) return prepared;
    if(overrideValue==0) return false;
    if(overrideValue==1) return true;
    return prepared;
}
}
