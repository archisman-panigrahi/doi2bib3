#!/usr/bin/env bash
set -euo pipefail

usage() {
    echo "Usage: $0 <version> <changelog-detail>"
    echo "  version          e.g. 1.4.0"
    echo "  changelog-detail one-line description for the changelog"
    exit 1
}

[[ $# -lt 2 ]] && usage

VERSION="$1"
DETAIL="$2"
DATE="$(date -R)"
MAINTAINER="Archisman Panigrahi <apandada1@gmail.com>"

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"

# pyproject.toml
sed -i "s/^version = \".*\"/version = \"$VERSION\"/" "$REPO_ROOT/pyproject.toml"

# AUR/PKGBUILD
sed -i "s/^pkgver=.*/pkgver=$VERSION/" "$REPO_ROOT/AUR/PKGBUILD"

# debian/changelog — prepend new entry
CHANGELOG="$REPO_ROOT/debian/changelog"
NEW_ENTRY="python-doi2bib3 ($VERSION-1) unstable; urgency=medium

  * $DETAIL

 -- $MAINTAINER  $DATE

"
printf '%s' "$NEW_ENTRY" | cat - "$CHANGELOG" > "$CHANGELOG.tmp"
mv "$CHANGELOG.tmp" "$CHANGELOG"

echo "Bumped to $VERSION:"
echo "  pyproject.toml"
echo "  AUR/PKGBUILD"
echo "  debian/changelog"
