#!/usr/bin/env bash
# Re-apply the Prowlarr search panel to flood.
#
# flood here is an `npm -g` install, so `npm -g update flood` replaces dist/assets and wipes
# both changes below. Nothing breaks when that happens - the UI just reverts to stock. Rerun
# this script to put it back. No service restart is needed: flood serves these files from
# disk and sends no-cache headers, so a browser reload picks the change up.
set -euo pipefail

ASSETS=/usr/lib/node_modules/flood/dist/assets
SRC=/opt/flood-search/prowlarr-search.js
TAG='<script defer="defer" src="static/js/prowlarr-search.js"></script>'

[ -f "$SRC" ] || { echo "missing $SRC"; exit 1; }
[ -d "$ASSETS" ] || { echo "missing $ASSETS - is flood installed?"; exit 1; }

install -m 644 "$SRC" "$ASSETS/static/js/prowlarr-search.js"
echo "script installed -> $ASSETS/static/js/prowlarr-search.js"

if grep -q 'prowlarr-search.js' "$ASSETS/index.html"; then
  echo "index.html already patched"
else
  [ -f "$ASSETS/index.html.orig" ] || cp -a "$ASSETS/index.html" "$ASSETS/index.html.orig"
  TAG="$TAG" python3 -I -c '
import os, sys
p = sys.argv[1]
tag = os.environ["TAG"]
s = open(p).read()
assert "</head>" in s, "no </head> in index.html"
open(p, "w").write(s.replace("</head>", tag + "</head>", 1))
' "$ASSETS/index.html"
  echo "index.html patched (original kept as index.html.orig)"
fi

echo "done - reload flood in the browser"
