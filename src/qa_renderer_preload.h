#pragma once
#include <string>
#include <vector>
#include <algorithm>
#include <cctype>
namespace qa_preload {
constexpr unsigned MAX_NAMES = 512;
constexpr unsigned MAX_BYTES = 32768;
inline bool ValidName(const std::string& name) {
    if (name.size() <= 7 || name.size() >= 64 || name.compare(0, 7, "xmodel/") ||
        name.find("..") != std::string::npos || name.find("//") != std::string::npos || name.back() == '/') return false;
    for (unsigned char c : name)
        if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') || c == '_' || c == '-' || c == '/' || c == '(' || c == ')')) return false;
    return true;
}
inline bool Add(std::vector<std::string>& names, const std::string& name) {
    if (!ValidName(name)) return false;
    for (const auto& old : names) {
        if (old.size() == name.size() && std::equal(old.begin(), old.end(), name.begin(),
            [](unsigned char a, unsigned char b) { return std::tolower(a) == std::tolower(b); })) return true;
    }
    if (names.size() >= MAX_NAMES) return false;
    names.push_back(name); return true;
}
inline bool Parse(const std::string& text, std::vector<std::string>& names) {
    names.clear();
    if (text.size() > MAX_BYTES) return false;
    size_t start = 0;
    while (start < text.size()) {
        size_t end = text.find('\n', start);
        if (end == std::string::npos) end = text.size();
        std::string name = text.substr(start, end - start);
        if (!name.empty() && name.back() == '\r') name.pop_back();
        if (!name.empty() && !Add(names, name)) { names.clear(); return false; }
        start = end + 1;
    }
    return !names.empty();
}
}
