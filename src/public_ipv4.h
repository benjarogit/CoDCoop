#pragma once

#include <winsock2.h>
#include <ws2tcpip.h>
#include <winhttp.h>
#include <cstring>

namespace public_ipv4 {
inline bool Parse(char* text, char (&address)[INET_ADDRSTRLEN])
{
    auto length = strlen(text);
    while (length && (text[length - 1] == '\r' || text[length - 1] == '\n')) text[--length] = 0;
    IN_ADDR ip{};
    if (inet_pton(AF_INET, text, &ip) != 1) return false;
    const auto n = ntohl(ip.s_addr);
    const auto prefix = n >> 24;
    if (prefix == 0 || prefix == 10 || prefix == 127 || prefix >= 224 ||
        (n >> 22) == (0x64400000u >> 22) || (n >> 20) == (0xac100000u >> 20) ||
        (n >> 16) == 0xa9fe || (n >> 16) == 0xc0a8) return false;
    return inet_ntop(AF_INET, &ip, address, sizeof address) != nullptr;
}

inline bool Lookup(char (&address)[INET_ADDRSTRLEN])
{
    HINTERNET session = WinHttpOpen(L"CoDCoop", WINHTTP_ACCESS_TYPE_DEFAULT_PROXY,
                                    WINHTTP_NO_PROXY_NAME, WINHTTP_NO_PROXY_BYPASS, 0);
    if (!session) return false;
    WinHttpSetTimeouts(session, 3000, 3000, 5000, 5000);
    HINTERNET connection = WinHttpConnect(session, L"api.ipify.org", INTERNET_DEFAULT_HTTPS_PORT, 0);
    HINTERNET request = connection ? WinHttpOpenRequest(connection, L"GET", L"/", nullptr,
        WINHTTP_NO_REFERER, WINHTTP_DEFAULT_ACCEPT_TYPES, WINHTTP_FLAG_SECURE) : nullptr;
    DWORD redirect = WINHTTP_OPTION_REDIRECT_POLICY_NEVER, status = 0, size = sizeof status;
    bool ok = request && WinHttpSetOption(request, WINHTTP_OPTION_REDIRECT_POLICY, &redirect, sizeof redirect) &&
        WinHttpSendRequest(request, WINHTTP_NO_ADDITIONAL_HEADERS, 0, WINHTTP_NO_REQUEST_DATA, 0, 0, 0) &&
        WinHttpReceiveResponse(request, nullptr) &&
        WinHttpQueryHeaders(request, WINHTTP_QUERY_STATUS_CODE | WINHTTP_QUERY_FLAG_NUMBER,
                            WINHTTP_HEADER_NAME_BY_INDEX, &status, &size, WINHTTP_NO_HEADER_INDEX) && status == 200;
    char body[32]{};
    DWORD used = 0;
    while (ok && used < sizeof body - 1) {
        DWORD received = 0;
        ok = WinHttpReadData(request, body + used, DWORD(sizeof body - 1 - used), &received) != FALSE;
        if (!received) break;
        used += received;
    }
    if (request) WinHttpCloseHandle(request);
    if (connection) WinHttpCloseHandle(connection);
    WinHttpCloseHandle(session);
    return ok && used < sizeof body - 1 && Parse(body, address);
}
}
