#pragma once
#include <cstring>

// A live native client CS can arrive before its DObj, while the joiner's
// collision server is frozen. Never infer approval from a numeric model ID or
// replace a different nonempty shadow name. Context/approval and actual cache
// ownership must be verified by the caller on this engine thread.
namespace resource_model_shadow {
enum class Result {Ready,Wait,Conflict,Failed};
template<class Client,class Shadow,class Cache,class Publish>
Result Sync(bool approved,unsigned id,const char* name,Client client,Shadow shadow,Cache cached,Publish publish) {
    if(!approved||!id||id>255||!name||std::strncmp(name,"xmodel/",7))return Result::Wait;
    unsigned length=0;while(length<64&&name[length])++length;
    if(length<=7||length>=64)return Result::Wait;
    const char* actual=client(id);
    if(!actual||std::strcmp(actual,name))return Result::Wait;
    const char* previous=shadow(id);
    if(!previous)return Result::Failed;
    if(*previous&&std::strcmp(previous,name))return Result::Conflict;
    if(!cached(id,name,false))return Result::Wait;
    if(!std::strcmp(previous,name)&&cached(id,name,true))return Result::Ready;
    if(!publish(id,name))return Result::Failed;
    actual=client(id);previous=shadow(id);
    return actual&&previous&&!std::strcmp(actual,name)&&!std::strcmp(previous,name)&&cached(id,name,true)
        ?Result::Ready:Result::Failed;
}
}
