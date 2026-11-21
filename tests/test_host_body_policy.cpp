#include "../src/host_body_policy.h"
#include <cassert>
int main(){
 using host_body_policy::Required;
 assert(Required(true,false,true,-1));assert(Required(true,false,true,0));
 assert(!Required(true,false,false,-1));assert(!Required(false,false,true,1));
 assert(!Required(true,true,false,-1));assert(!Required(true,true,false,0));assert(Required(true,true,false,1));
 assert(Required(true,true,true,-1));assert(!Required(true,true,true,0));
}
