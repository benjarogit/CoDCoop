#include <set>
// Guarded public rollback of the last completed native setup transaction.
// Included after installer helpers; no paths/commands come from network input.
static std::wstring BackupRoot(const std::wstring &folder) {
  auto root = suite::FullPath(folder);
  wchar_t canonical[32768];
  DWORD count = GetLongPathNameW(root.c_str(), canonical, 32768);
  if (!count || count >= 32768)
    throw std::runtime_error("cannot resolve rollback installation");
  root.assign(canonical, count);
  while (root.size() > 3 && (root.back() == L'\\' || root.back() == L'/'))
    root.pop_back();
  return root;
}
static bool BackupWineNoLink(const std::wstring &path) {
  auto convert = (char *(__cdecl *)(const wchar_t *))GetProcAddress(
      GetModuleHandleW(L"kernel32.dll"), "wine_get_unix_file_name");
  if (!convert)
    return !GetProcAddress(GetModuleHandleW(L"ntdll.dll"), "wine_get_version");
  auto slash = path.find_last_of(L"\\/");
  if (slash == std::wstring::npos)
    return false;
  char *parent = convert(path.substr(0, slash).c_str());
  char *actual = convert(path.c_str());
  bool ok = false;
  if (parent && actual) {
    std::string expected = parent;
    while (expected.size() > 1 && expected.back() == '/')
      expected.pop_back();
    expected += '/';
    expected += suite::Utf8(path.substr(slash + 1));
    ok = expected == actual;
  }
  if (parent)
    HeapFree(GetProcessHeap(), 0, parent);
  if (actual)
    HeapFree(GetProcessHeap(), 0, actual);
  return ok;
}
static void BackupRelativeSyntax(const std::string &relative) {
  if (relative.empty() || relative.front() == '/' || relative.back() == '/' ||
      relative.find('\\') != std::string::npos ||
      relative.find(':') != std::string::npos || relative.size() > 32700 ||
      std::any_of(relative.begin(), relative.end(), [](unsigned char c) {
        return c < 32 || c == 127 || c == '*' || c == '?' || c == '"' ||
               c == '<' || c == '>' || c == '|';
      }))
    throw std::runtime_error("unsafe rollback path");
  size_t part = 0;
  while (part < relative.size()) {
    auto end = relative.find('/', part);
    auto leaf =
        relative.substr(part, end == std::string::npos ? end : end - part);
    if (leaf.empty() || leaf == "." || leaf == ".." || leaf.back() == '.' ||
        leaf.back() == ' ')
      throw std::runtime_error("ambiguous rollback path");
    auto stem = suite::Lower(leaf.substr(0, leaf.find('.')));
    if (stem == "con" || stem == "prn" || stem == "aux" || stem == "nul" ||
        (stem.size() == 4 &&
         (stem.rfind("com", 0) == 0 || stem.rfind("lpt", 0) == 0) &&
         stem[3] >= '1' && stem[3] <= '9'))
      throw std::runtime_error("reserved rollback path");
    if (end == std::string::npos)
      break;
    part = end + 1;
  }
}
static std::wstring BackupPath(const std::wstring &root,
                               const std::string &relative) {
  BackupRelativeSyntax(relative);
  auto path = suite::Resolve(root, relative);
  auto check = root;
  if (GetFileAttributesW(root.c_str()) == INVALID_FILE_ATTRIBUTES ||
      !BackupWineNoLink(root) ||
      GetFileAttributesW(root.c_str()) & FILE_ATTRIBUTE_REPARSE_POINT)
    throw std::runtime_error("unsafe rollback root");
  auto actual = suite::Utf8(path.substr(root.size() + 1));
  std::replace(actual.begin(), actual.end(), '\\', '/');
  size_t at = 0;
  while (at < actual.size()) {
    auto end = actual.find('/', at);
    check += L"\\" + suite::Wide(actual.substr(
                         at, end == std::string::npos ? end : end - at));
    DWORD flags = GetFileAttributesW(check.c_str());
    if (flags != INVALID_FILE_ATTRIBUTES &&
        ((flags & FILE_ATTRIBUTE_REPARSE_POINT) || !BackupWineNoLink(check)))
      throw std::runtime_error("rollback symlink/reparse path: " + relative);
    if (end == std::string::npos)
      break;
    at = end + 1;
  }

  return path;
}
static std::string BackupRelative(const std::wstring &root,
                                  const std::wstring &path) {
  auto full = suite::FullPath(path), prefix = root + L"\\";
  if (full.size() <= prefix.size() ||
      _wcsnicmp(full.c_str(), prefix.c_str(), prefix.size()))
    throw std::runtime_error("rollback path outside installation");
  auto relative = suite::Utf8(full.substr(prefix.size()));
  std::replace(relative.begin(), relative.end(), '\\', '/');
  BackupRelativeSyntax(relative);
  return relative;
}
static suite::Json BackupState(const std::wstring &path) {
  DWORD flags = GetFileAttributesW(path.c_str());
  if (flags == INVALID_FILE_ATTRIBUTES) {
    DWORD error = GetLastError();
    if (error != ERROR_FILE_NOT_FOUND && error != ERROR_PATH_NOT_FOUND)
      throw std::runtime_error("cannot inspect rollback file");
    return {{"exists", false}};
  }
  if (flags & (FILE_ATTRIBUTE_DIRECTORY | FILE_ATTRIBUTE_REPARSE_POINT))
    throw std::runtime_error("rollback target is not a regular file");
  return {{"exists", true}, {"sha256", suite::Hash(path)}};
}
static void SaveInstallJournal(const std::wstring &folder) {
  auto root = BackupRoot(folder);
  suite::Json entries = suite::Json::array(), retained = suite::Json::array();
  for (const auto &change : g_changes) {
    auto relative = BackupRelative(root, change.path);
    // Public undo retains CURRENT user settings/saves even after configure.
    // Automatic failure rollback still has the complete in-memory changes.
    if (suite::PersonalPath(suite::Wide(relative))) {
      retained.push_back(relative);
      continue;
    }
    BackupPath(root, relative);
    suite::Json item = {{"path", relative},
                        {"existed", change.existed},
                        {"installed", BackupState(change.path)}};
    if (change.existed) {
      auto backup = BackupRelative(root, change.backup);
      if (suite::Hash(change.backup) != change.backupHash)
        throw std::runtime_error("setup backup changed before completion: " +
                                 relative);
      item["backup"] = backup;
      item["backup_sha256"] = change.backupHash;
    }
    entries.push_back(item);
  }
  suite::Json journal = {{"schema", 2},
                         {"state", "complete"},
                         {"root", suite::Utf8(root)},
                         {"entries", entries},
                         {"retained_personal", retained}};
  auto path = BackupPath(root, "coop/last-install-backup.json");
  suite::Write(path, suite::Canonical(journal) + "\n");
}
static bool OwnedBackupSuffix(const std::string &relative,
                              const std::string &backup) {
  auto prefix = relative + ".coop-backup.";
  if (backup.rfind(prefix, 0) != 0)
    return false;
  auto suffix = backup.substr(prefix.size());
  unsigned parts = 1, digits = 0;
  for (char c : suffix) {
    if (c == '.') {
      if (!digits)
        return false;
      ++parts;
      digits = 0;
    } else if (c >= '0' && c <= '9') {
      if (++digits > 10)
        return false;
    } else
      return false;
  }
  return digits && (parts == 2 || parts == 3);
}
struct PublicRestoreEntry {
  std::string relative, backup, backupHash;
  bool existed;
  suite::Json installed;
};
static std::vector<PublicRestoreEntry>
PublicRestorePlan(const std::wstring &root, const suite::Json &journal) {
  if (!journal.is_object() || !journal.contains("schema") ||
      !journal.at("schema").is_number_integer() || journal.at("schema") != 2 ||
      journal.value("state", std::string()) != "complete")
    throw std::runtime_error(
        "No guarded completed setup backup. Legacy backups require manual "
        "recovery; install or repair with the current setup first.");
  if (journal.size() != 5 || !journal.at("root").is_string() ||
      _wcsicmp(suite::Wide(journal.at("root")).c_str(), root.c_str()) ||
      !journal.at("entries").is_array() || journal.at("entries").size() > 8192)
    throw std::runtime_error("invalid rollback journal ownership");
  if (!journal.at("retained_personal").is_array())
    throw std::runtime_error("invalid retained personal paths");
  for (const auto &item : journal.at("retained_personal")) {
    if (!item.is_string() ||
        !suite::PersonalPath(suite::Wide(item.get<std::string>())))
      throw std::runtime_error("invalid retained personal entry");
    BackupRelativeSyntax(item.get<std::string>());
  }
  std::vector<PublicRestoreEntry> plan;
  std::set<std::string> seen;
  auto compare = [](const std::wstring &a, const std::wstring &b) {
    return CompareStringOrdinal(a.c_str(), -1, b.c_str(), -1, TRUE) ==
           CSTR_LESS_THAN;
  };
  std::set<std::wstring, decltype(compare)> seenTargets(compare);
  for (const auto &row : journal.at("entries")) {
    if (!row.is_object() || !row.at("path").is_string())
      throw std::runtime_error("invalid rollback entry");
    auto relative = row.at("path").get<std::string>();
    BackupRelativeSyntax(relative);
    if (!seen.insert(suite::Lower(relative)).second)
      throw std::runtime_error("duplicate rollback entry");
    // Also skip protected paths in an otherwise valid journal, before any
    // backup/current-file ownership checks, to preserve post-install edits.
    if (suite::PersonalPath(suite::Wide(relative)))
      continue;
    auto path = BackupPath(root, relative);
    if (!seenTargets.insert(path).second)
      throw std::runtime_error("duplicate rollback target");
    if (!row.at("existed").is_boolean() || !row.at("installed").is_object())
      throw std::runtime_error("invalid rollback file state");
    bool existed = row.at("existed").get<bool>();
    auto installed = row.at("installed");
    if (!installed.at("exists").is_boolean() ||
        installed.size() != (installed.at("exists").get<bool>() ? 2u : 1u) ||
        (installed.at("exists").get<bool>() &&
         (!installed.at("sha256").is_string() ||
          !suite::Hex(installed.at("sha256").get<std::string>()))))
      throw std::runtime_error("invalid applied rollback hash");
    if (row.size() != (existed ? 5u : 3u))
      throw std::runtime_error("invalid rollback entry fields");
    PublicRestoreEntry entry{relative, "", "", existed, installed};
    if (existed) {
      entry.backup = row.at("backup").get<std::string>();
      entry.backupHash = row.at("backup_sha256").get<std::string>();
      if (!suite::Hex(entry.backupHash) ||
          !OwnedBackupSuffix(relative, entry.backup))
        throw std::runtime_error("unowned rollback backup: " + relative);
      auto backup = BackupPath(root, entry.backup);
      if (BackupState(backup) !=
          suite::Json{{"exists", true}, {"sha256", entry.backupHash}})
        throw std::runtime_error(
            "backup missing or changed; preserve it and repair instead: " +
            relative);
    }
    if (BackupState(path) != installed)
      throw std::runtime_error("installed runtime changed; preserve edits and "
                               "repair before rollback: " +
                               relative);
    plan.push_back(entry);
  }
  return plan;
}
static void RestoreOwnedBackup(const std::wstring &root,
                               const PublicRestoreEntry &entry,
                               const std::wstring &path) {
  auto backup = BackupPath(root, entry.backup);
  if (suite::Hash(backup) != entry.backupHash)
    throw std::runtime_error("backup changed during rollback: " +
                             entry.relative);
  std::wstring pending;
  bool copied = false;
  for (unsigned n = 0; n < 1000; ++n) {
    pending = path + L".coop-restore-pending." +
              std::to_wstring(GetCurrentProcessId()) + L"." +
              std::to_wstring(n);
    if (CopyFileW(backup.c_str(), pending.c_str(), TRUE)) {
      copied = true;
      break;
    }
    const DWORD error = GetLastError();
    if (error != ERROR_FILE_EXISTS && error != ERROR_ALREADY_EXISTS)
      break;
  }
  if (!copied)
    throw std::runtime_error("cannot prepare rollback copy: " + entry.relative);
  try {
    if (suite::Hash(pending) != entry.backupHash ||
        suite::Hash(backup) != entry.backupHash ||
        !MoveFileExW(pending.c_str(), path.c_str(),
                     MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH))
      throw std::runtime_error("cannot restore rollback file: " +
                               entry.relative);
  } catch (...) {
    DeleteFileW(pending.c_str());
    throw;
  }
}
static bool RollbackLastInstall(const std::wstring &folder,
                                std::wstring &error) {
  try {
    auto root = BackupRoot(folder),
         journalPath = BackupPath(root, "coop/last-install-backup.json");
    auto journal = suite::Json::parse(suite::Read(journalPath));
    auto plan = PublicRestorePlan(root, journal);
    g_changes.clear();
    g_transactionActive = true;
    try {
      for (auto it = plan.rbegin(); it != plan.rend(); ++it) {
        auto path = BackupPath(root, it->relative);
        if (BackupState(path) != it->installed)
          throw std::runtime_error("runtime changed during rollback: " +
                                   it->relative);
        RememberFile(path);
        if (it->existed)
          RestoreOwnedBackup(root, *it, path);
        else if (!DeleteFileW(path.c_str()) &&
                 GetLastError() != ERROR_FILE_NOT_FOUND)
          throw std::runtime_error("cannot remove rollback file: " +
                                   it->relative);
      }
      RememberFile(journalPath);
      journal["state"] = "rolled_back";
      suite::Write(journalPath, suite::Canonical(journal) + "\n");
      g_transactionActive = false;
      g_changes.clear();
      return true;
    } catch (...) {
      RollbackFiles();
      throw;
    }
  } catch (const std::exception &failure) {
    error = L("Ruecknahme nicht ausgefuehrt. Persoenliche Einstellungen und "
              "Spielstaende bleiben erhalten.\n",
              "Rollback could not complete. Personal settings and saves are "
              "retained.\n") +
            Widen(failure.what());
    return false;
  }
}
