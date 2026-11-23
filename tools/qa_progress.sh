#!/bin/sh
# Fortschritt eines QA-Laufs anzeigen, ohne ihn anzuhalten oder zu pollenden Loop zu starten.
#
#   tools/qa_progress.sh qa-foy-m8-heapbody1
#
# Zeigt je Instanz die letzte Logzeile mit Zeitstempel, die Dateizahl der Kopie, native Fehler,
# laufende Spielprozesse, ein Ergebnis falls schon da, und den Plattenstand.
set -eu
TAG=${1:-}
[ -n "$TAG" ] || { echo "Aufruf: tools/qa_progress.sh <run-tag>" >&2; exit 2; }
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
R=$ROOT/run/$TAG
[ -d "$R" ] || { echo "kein Lauf: run/$TAG" >&2; exit 1; }

state=bereit
[ -f "$R/.codcoop-qa-owned" ] && state="laeuft (Marker gesetzt)"
[ -f "$R/result.json" ] && state="fertig ($(python3 -c 'import json,sys;print(json.load(open(sys.argv[1])).get("status"))' "$R/result.json" 2>/dev/null || echo '?'))"

echo "Lauf    $TAG"
echo "Status  $state"
echo "Platte  $(df -h /mnt/intern-1tb 2>/dev/null | tail -1 | awk '{print $4" frei ("$5" belegt)"}')"
echo

for d in host join1 join2 join3; do
    [ -d "$R/$d" ] || { printf '%-6s %s\n' "$d" "noch nicht kopiert"; continue; }
    files=$(find "$R/$d" -maxdepth 1 -type f 2>/dev/null | wc -l)
    log=""
    for candidate in "$R/$d/codcoop_join.log" "$R/$d/codcoop.log"; do
        [ -s "$candidate" ] && log=$candidate && break
    done
    if [ -n "$log" ]; then
        printf '%-6s %s  %s\n' "$d" "$(date -r "$log" +%H:%M:%S)" "$(tail -1 "$log" | cut -c1-118)"
    else
        printf '%-6s %s\n' "$d" "$files Dateien, noch kein Log (kopiert/ladet)"
    fi
done

echo
console_errors=0
for f in "$R"/join*/UnitedFronts/console.log "$R"/host/UnitedFronts/console.log; do
    [ -f "$f" ] && console_errors=$((console_errors + $(grep -c 'failed allocation\|ERROR:' "$f" 2>/dev/null || true)))
done
echo "Native Fehler in den Konsolen: $console_errors"
echo "Spielprozesse: $(pgrep -f 'CoDUOSP.exe' | wc -l) (nur Wine, ohne fremde Spiele)"
[ -f "$R/result.json" ] && python3 - "$R/result.json" <<'EOF'
import json, sys
d = json.load(open(sys.argv[1]))
print("Ergebnis:", d.get("status"), "-", d.get("error"))
EOF
exit 0
