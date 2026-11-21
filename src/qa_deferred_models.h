#pragma once
#include "qa_renderer_preload.h"
#include <cstdint>
namespace qa_deferred {
inline bool DiscardOnly(uintptr_t returnRva) {
    switch (returnRva) {
    case 0x3890a: case 0x1e7aa: case 0x1e7b5: case 0x1e7c0: case 0x1e7df: case 0x1e7f0: return true;
    default: return false;
    }
}
struct Entry { std::string name; void* cached = nullptr; unsigned id = 0; };
struct Ledger {
    std::vector<Entry> entries;
    unsigned deferrals = 0, lateBindings = 0, bindings = 0;
    Entry* Find(const std::string& name) {
        for (auto& e : entries) if (e.name.size() == name.size() &&
            std::equal(e.name.begin(), e.name.end(), name.begin(), [](unsigned char a, unsigned char b) { return std::tolower(a) == std::tolower(b); })) return &e;
        return nullptr;
    }
    Entry* Approve(const std::string& name) {
        if (!qa_preload::ValidName(name)) return nullptr;
        if (auto* old = Find(name)) return old;
        if (entries.size() >= qa_preload::MAX_NAMES) return nullptr;
        entries.push_back({name}); return &entries.back();
    }
    bool Bind(Entry& entry, unsigned id) {
        if (!id || id >= 256 || (entry.id && entry.id != id)) return false;
        for (const auto& other : entries) if (&other != &entry && other.id == id) return false;
        if (!entry.id) ++bindings;
        entry.id = id; return true;
    }
};
}
