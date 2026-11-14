# Flood + Prowlarr search panel

Flood 4.11 has no plugin API and no built-in tracker search. This adds a "Search trackers"
button to the Flood web UI that queries **Prowlarr** and adds results straight to Flood, routed
to the right library folder by category.

It's a single script injected into Flood's `index.html` — no fork, no rebuild. It works because
Prowlarr sends `Access-Control-Allow-Origin: *` (so the browser can call it directly) and Flood
already exposes `POST /api/torrents/add-urls`.

## Configure

Edit the `CFG` block at the top of `prowlarr-search.js`:

```js
var CFG = {
  prowlarr: 'http://PROWLARR_HOST:9696',   // your Prowlarr base URL
  apiKey:   'YOUR_PROWLARR_API_KEY',       // Prowlarr -> Settings -> General -> API Key
  library:  '/media/share',                // base path grabs download into
  destination: '/media/torrents',          // fallback when category is unknown
  tag: 'prowlarr',
  limit: 80,
};
```

The `apiKey` is sent from the browser, so treat it as visible to anyone who can open your Flood
instance — keep Flood on your LAN / behind auth.

## Install

Flood here is a global npm install, so `npm -g update flood` wipes the injected script and the
`index.html` edit. Nothing breaks (the UI just reverts to stock); rerun the installer to put it
back.

```bash
# copies prowlarr-search.js into Flood's assets and adds the <script> tag to index.html
./install.sh
```

`install.sh` assumes Flood's assets at `/usr/lib/node_modules/flood/dist/assets`; adjust if your
install differs. It keeps a backup of the original `index.html` as `index.html.orig`. Reload
Flood in the browser afterward — no service restart needed.

## Category routing

Nyaa results go to `library/Anime`; otherwise the Torznab category id maps to
Anime / Movies / Music / TV / Games, falling back to `destination` (then a separate media-sorter
can file it). Adjust `FOLDERS` and `categoryTag()` to taste.
