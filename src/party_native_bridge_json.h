#pragma once
#include <cstdint>
#include <limits>
#include <map>
#include <string>
#include <vector>

// Ephemeral, bounded JSON for the fixed local party bridge. No allocation or
// STL value from this parser may be retained in the shared Core State.
namespace party_native_json {
constexpr size_t MAX_BYTES=131072,MAX_STRING=4096,MAX_NODES=8192,MAX_DEPTH=16;
inline void Utf8(std::string& out,unsigned c){if(c<128)out+=(char)c;else if(c<2048){out+=(char)(0xc0|(c>>6));out+=(char)(0x80|(c&63));}else if(c<65536){out+=(char)(0xe0|(c>>12));out+=(char)(0x80|((c>>6)&63));out+=(char)(0x80|(c&63));}else{out+=(char)(0xf0|(c>>18));out+=(char)(0x80|((c>>12)&63));out+=(char)(0x80|((c>>6)&63));out+=(char)(0x80|(c&63));}}
inline bool Point(const char*& p,const char* end,unsigned& c){if(p==end)return false;unsigned lead=(unsigned char)*p++;if(lead<128){c=lead;return true;}unsigned count=0,min=0;if(lead>=0xc2&&lead<=0xdf){count=1;min=128;c=lead&31;}else if(lead>=0xe0&&lead<=0xef){count=2;min=2048;c=lead&15;}else if(lead>=0xf0&&lead<=0xf4){count=3;min=65536;c=lead&7;}else return false;for(unsigned i=0;i<count;++i){if(p==end||((unsigned char)*p&0xc0)!=0x80)return false;c=(c<<6)|((unsigned char)*p++&63);}return c>=min&&c<=0x10ffff&&!(c>=0xd800&&c<=0xdfff);}
struct Value {
 enum Kind {Null,Boolean,Integer,String,Array,Object} kind=Null;
 bool boolean=false,negative=false;
 uint64_t integer=0;
 std::string string;
 std::vector<Value> array;
 std::map<std::string,Value> object;
 static Value Text(std::string s){Value v;v.kind=String;v.string=std::move(s);return v;}
 static Value Number(uint64_t n){Value v;v.kind=Integer;v.integer=n;return v;}
 static Value Bool(bool b){Value v;v.kind=Boolean;v.boolean=b;return v;}
 static Value Dict(){Value v;v.kind=Object;return v;}
 const Value* Find(const char* key)const{if(kind!=Object)return nullptr;auto i=object.find(key);return i==object.end()?nullptr:&i->second;}
};
class Parser {
 const char* p;const char* end;size_t nodes=0;
 void White(){while(p<end&&(*p==' '||*p=='\n'||*p=='\r'||*p=='\t'))++p;}
 static int Hex(char c){return c>='0'&&c<='9'?c-'0':c>='a'&&c<='f'?c-'a'+10:c>='A'&&c<='F'?c-'A'+10:-1;}
 bool Text(std::string& out){
  if(p==end||*p++!='"')return false;out.clear();
  while(p<end){unsigned char c=(unsigned char)*p++;
   if(c=='"')return true;
   if(c<32)return false;
   if(c>=128){--p;unsigned point=0;if(!Point(p,end,point))return false;Utf8(out,point);if(out.size()>MAX_STRING)return false;continue;}
   if(c=='\\'){
    if(p==end)return false;c=(unsigned char)*p++;
    switch(c){case '"':case '\\':case '/':break;case 'b':c='\b';break;case 'f':c='\f';break;case 'n':c='\n';break;case 'r':c='\r';break;case 't':c='\t';break;
     case 'u':{if(end-p<4)return false;unsigned n=0;for(int i=0;i<4;++i){int h=Hex(*p++);if(h<0)return false;n=n*16+h;}if(n>=0xd800&&n<=0xdbff){if(end-p<6||p[0]!='\\'||p[1]!='u')return false;p+=2;unsigned low=0;for(int i=0;i<4;++i){int h=Hex(*p++);if(h<0)return false;low=low*16+h;}if(low<0xdc00||low>0xdfff)return false;n=0x10000+((n-0xd800)<<10)+(low-0xdc00);}else if(n>=0xdc00&&n<=0xdfff)return false;Utf8(out,n);if(out.size()>MAX_STRING)return false;continue;}
     default:return false;
    }
   }
   if(out.size()==MAX_STRING)return false;out.push_back((char)c);
  }return false;
 }
 bool Read(Value& v,unsigned depth){
  White();if(p==end||depth>MAX_DEPTH||++nodes>MAX_NODES)return false;
  if(*p=='"'){v.kind=Value::String;return Text(v.string);}
  if(*p=='{'||*p=='['){bool object=*p++=='{';v.kind=object?Value::Object:Value::Array;White();char close=object?'}':']';
   if(p<end&&*p==close){++p;return true;}
   for(;;){std::string key;if(object){White();if(!Text(key)||v.object.count(key))return false;White();if(p==end||*p++!=':')return false;}
    Value item;if(!Read(item,depth+1))return false;if(object)v.object.emplace(std::move(key),std::move(item));else v.array.push_back(std::move(item));
    White();if(p==end)return false;if(*p==close){++p;return true;}if(*p++!=',')return false;
   }
  }
  for(auto pair:{std::pair<const char*,int>{"true",1},{"false",2},{"null",3}}){size_t n=std::char_traits<char>::length(pair.first);if(size_t(end-p)>=n&&!std::char_traits<char>::compare(p,pair.first,n)){p+=n;v.kind=pair.second==3?Value::Null:Value::Boolean;v.boolean=pair.second==1;return true;}}
  v.kind=Value::Integer;v.negative=*p=='-';if(v.negative&&++p==end)return false;
  if(*p<'0'||*p>'9')return false;bool zero=*p=='0';
  do{unsigned digit=*p++-'0';if(v.integer>(std::numeric_limits<uint64_t>::max()-digit)/10)return false;v.integer=v.integer*10+digit;
   if(zero)break;
  }while(p<end&&*p>='0'&&*p<='9');
  if(v.negative&&!v.integer)v.negative=false;return true;
 }
public:
 Parser(const char* bytes,size_t size):p(bytes),end(bytes+size){}
 bool Parse(Value& v){v={};if(!Read(v,0))return false;White();return p==end;}
};
inline bool Parse(const std::string& bytes,Value& out){if(bytes.empty()||bytes.size()>MAX_BYTES)return false;Value parsed;if(!Parser(bytes.data(),bytes.size()).Parse(parsed))return false;out=std::move(parsed);return true;}
inline bool Quote(std::string& out,const std::string& s){
 static const char hex[]="0123456789abcdef";out+='"';
 auto unit=[&](unsigned u){out+="\\u";for(int i=3;i>=0;--i)out+=hex[(u>>(i*4))&15];};
 const char* p=s.data();const char* end=p+s.size();while(p<end){unsigned c=0;if(!Point(p,end,c))return false;switch(c){case '"':out+="\\\"";break;case '\\':out+="\\\\";break;case '\b':out+="\\b";break;case '\f':out+="\\f";break;case '\n':out+="\\n";break;case '\r':out+="\\r";break;case '\t':out+="\\t";break;
  default:if(c<32||c>=127){if(c<65536)unit(c);else{c-=65536;unit(0xd800+(c>>10));unit(0xdc00+(c&1023));}}else out+=(char)c;
 }}out+='"';return true;
}
inline bool Emit(const Value& v,std::string& out,unsigned depth=0){
 if(depth>MAX_DEPTH||out.size()>MAX_BYTES)return false;
 switch(v.kind){case Value::Null:out+="null";break;case Value::Boolean:out+=v.boolean?"true":"false";break;
 case Value::Integer:if(v.negative&&v.integer)out+='-';out+=std::to_string(v.integer);break;
 case Value::String:if(v.string.size()>MAX_STRING||!Quote(out,v.string))return false;break;
 case Value::Array:{out+='[';bool first=true;for(const auto& item:v.array){if(!first)out+=',';first=false;if(!Emit(item,out,depth+1))return false;}out+=']';break;}
 case Value::Object:{out+='{';bool first=true;for(const auto& item:v.object){if(item.first.size()>MAX_STRING)return false;if(!first)out+=',';first=false;if(!Quote(out,item.first))return false;out+=':';if(!Emit(item.second,out,depth+1))return false;}out+='}';break;}
 default:return false;
 }return out.size()<=MAX_BYTES;
}
inline bool Canonical(const Value& v,std::string& out){std::string text;if(!Emit(v,text))return false;out=std::move(text);return true;}
inline bool Keys(const Value& v,std::initializer_list<const char*> names){if(v.kind!=Value::Object||v.object.size()!=names.size())return false;for(auto n:names)if(!v.Find(n))return false;return true;}
inline bool Unsigned(const Value* v,uint64_t max,uint64_t& out){if(!v||v->kind!=Value::Integer||v->negative||v->integer>max)return false;out=v->integer;return true;}
inline bool String(const Value* v,std::string& out){if(!v||v->kind!=Value::String)return false;out=v->string;return true;}
}
