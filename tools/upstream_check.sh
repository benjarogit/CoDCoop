#!/bin/sh
# Upstream-Abgleich, nur lesend: welche Commits hat TheTiranix/CoDCoop, die dieser Branch nicht hat?
#
# Kein Automatismus und kein Hintergrunddienst: Orqen hat fuer dieses Projekt keinen Adapter und
# beobachtet keinen Upstream. Der Abgleich ist ein expliziter Schritt vor einem Release oder nach
# einer Pause; das Ergebnis gehoert als Eintrag in docs/HANDOFF-0.6.md (Abschnitt U1).
#
#   tools/upstream_check.sh
#   tools/upstream_check.sh --log      zusaetzlich den Betreff jedes Commits
set -eu

REMOTE=${REMOTE:-https://github.com/TheTiranix/CoDCoop}
BRANCH=${BRANCH:-master}
HERE=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$HERE"

git fetch --quiet "$REMOTE" "$BRANCH:refs/remotes/upstream/$BRANCH"

UPSTREAM="upstream/$BRANCH"
echo "HEAD            $(git rev-parse --short HEAD) $(git rev-parse --abbrev-ref HEAD)"
echo "upstream/$BRANCH $(git rev-parse --short "$UPSTREAM")"
echo "Basis           $(git merge-base HEAD "$UPSTREAM" | cut -c1-12)"
echo "nur upstream    $(git rev-list --count "HEAD..$UPSTREAM")"
echo "nur hier        $(git rev-list --count "$UPSTREAM..HEAD")"
echo

if [ -z "$(git rev-list "HEAD..$UPSTREAM")" ]; then
    echo "Keine neuen Upstream-Commits."
    exit 0
fi

git log --format='%h %ad %s' --date=short "HEAD..$UPSTREAM"
echo
git diff --stat "HEAD...$UPSTREAM" | tail -25

if [ "${1:-}" = "--log" ]; then
    echo
    for c in $(git rev-list "HEAD..$UPSTREAM"); do
        echo "== $(git log -1 --format='%h %s' "$c")"
        git log -1 --format='%b' "$c" | sed -n '1,12p'
        echo
    done
fi
