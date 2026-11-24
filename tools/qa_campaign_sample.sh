#!/bin/bash
# Run the four-role United Fronts fixture on one campaign map and keep only evidence.
#
#   tools/qa_campaign_sample.sh <tag> <map> <port> [extra fixture args...]
#
# Disk hygiene is part of the run: refuse to start below 60 GB free, never delete
# while a game process of this run is alive, and print run/+free before and after.
set -eu

tag=${1:?usage: qa_campaign_sample.sh <tag> <map> <port> [fixture args...]}
map=${2:?missing map}
port=${3:?missing port}
shift 3

root=$(cd "$(dirname "$0")/.." && pwd)
cd "$root"
run="run/$tag"

free_gb=$(df --output=avail -BG /mnt/intern-1tb | tail -1 | tr -dc '0-9')
if [ "${free_gb:-0}" -lt 60 ]; then
    echo "refusing to start: ${free_gb} GB free (< 60 GB)" >&2
    exit 1
fi

before_free=$(df -h /mnt/intern-1tb | awk 'END{print $4}')
before_run=$(du -sh run | cut -f1)

python3 -u tools/qa_uf_fresh_roles.py --source run/campaign-host --run "$run" --runtime-dir build \
    --map "$map" --port "$port" --timeout 240 --duration 1 --checkpoint-reloads 1 \
    --experimental-gmi-loader --experimental-plan-union-media "$@" > "$run.log" 2>&1 || true

if pgrep -af CoDUOSP.exe | grep -Fq "$tag"; then
    echo "game processes for $tag are still alive; evidence kept, runtime copies NOT deleted" >&2
    exit 1
fi

mkdir -p "$run/evidence"
cp "$run"/result.json "$run"/uf-fresh-roles-proof.json "$run"/provenance.json "$run"/before.json "$run/evidence/" 2>/dev/null || true
cp "$run"/*-proof.json "$run/evidence/" 2>/dev/null || true
cp "$run.log" "$run/evidence/" 2>/dev/null || true
for d in host join1 join2 join3; do
    mkdir -p "$run/evidence/$d"
    cp "$run/$d"/codcoop*.log "$run/$d"/qa-state.json "$run/$d"/UnitedFronts/console.log "$run/evidence/$d/" 2>/dev/null || true
done
evidence=$(du -sh "$run/evidence" | cut -f1)
rm -rf "$run/host" "$run/join1" "$run/join2" "$run/join3" "$run/prefix" "$run/runtime"

after_free=$(df -h /mnt/intern-1tb | awk 'END{print $4}')
after_run=$(du -sh run | cut -f1)
printf 'run  %s -> %s (evidence %s, %s kept)\n' "$before_run" "$after_run" "$evidence" "$run"
printf 'free %s -> %s\n' "$before_free" "$after_free"
tail -2 "$run.log"
