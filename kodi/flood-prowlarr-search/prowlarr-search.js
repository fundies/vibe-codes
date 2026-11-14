/* Prowlarr search panel for flood.
 *
 * flood 4.11 has no plugin API and no tracker search - verified against the installed
 * bundle - so this is injected by a <script> tag added to flood's index.html.
 *
 * It works because two things line up:
 *   - Prowlarr answers with Access-Control-Allow-Origin: * and allows x-api-key, so the
 *     page can call it cross-origin without a proxy.
 *   - flood already exposes POST /api/torrents/add-urls, which its own feed browser uses.
 *
 * Canonical copy lives at /opt/flood-search/prowlarr-search.js. An `npm -g update flood`
 * overwrites flood's assets dir and index.html; rerun /opt/flood-search/install.sh to
 * put both back.
 */
(function () {
  'use strict';

  var CFG = {
    prowlarr: 'http://PROWLARR_HOST:9696',   // your Prowlarr base URL
    apiKey: 'YOUR_PROWLARR_API_KEY',         // Prowlarr -> Settings -> General -> API Key
    library: '/media/share',
    destination: '/media/torrents',   // fallback when the category is unknown
    tag: 'prowlarr',
    limit: 80,
  };

  // cat-* tag -> library subfolder, matching /opt/media-sort's CATEGORY_TAGS exactly.
  var FOLDERS = {
    'cat-anime': 'Anime',
    'cat-movies': 'Movies',
    'cat-music': 'Music',
    'cat-games': 'Games',
    'cat-tv': 'TV',
  };

  if (window.__prowlarrSearchLoaded) return;
  window.__prowlarrSearchLoaded = true;

  // ---------- helpers ----------

  function el(tag, props, kids) {
    var n = document.createElement(tag);
    if (props) Object.keys(props).forEach(function (k) {
      if (k === 'style') Object.assign(n.style, props[k]);
      else if (k.slice(0, 2) === 'on') n.addEventListener(k.slice(2), props[k]);
      else if (k === 'text') n.textContent = props[k];
      else n.setAttribute(k, props[k]);
    });
    (kids || []).forEach(function (c) { if (c) n.appendChild(c); });
    return n;
  }

  function size(b) {
    if (!b && b !== 0) return '-';
    var u = ['B', 'KiB', 'MiB', 'GiB', 'TiB'], i = 0;
    while (b >= 1024 && i < u.length - 1) { b /= 1024; i++; }
    return b.toFixed(b >= 100 || i === 0 ? 0 : 1) + ' ' + u[i];
  }

  function slug(s) {
    return (s || '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
  }

  /* Turn the tracker's own category into a cat-* tag that /opt/media-sort acts on.
   * Prowlarr normalises every indexer to Torznab ids, so TorrentLeech's "Movies/UHD" and
   * "TV/HD" arrive as 2045 and 5040 regardless of the tracker's own naming. Sorting
   * descending checks the specific id before its parent, so 5070 (TV/Anime) wins over 5000.
   * Books (7000s) and anything unmapped deliberately return null: there is no folder for
   * them, and the sorter leaves unclassified torrents alone rather than guessing.
   */
  function categoryTag(r) {
    var ids = (r.categories || [])
      .map(function (c) { return c && c.id; })
      .filter(function (n) { return typeof n === 'number' && n < 10000; })
      .sort(function (a, b) { return b - a; });

    for (var i = 0; i < ids.length; i++) {
      var id = ids[i];
      if (id === 5070) return 'cat-anime';
      if (id >= 2000 && id < 3000) return 'cat-movies';
      if (id >= 3000 && id < 4000) return 'cat-music';
      if (id >= 5000 && id < 6000) return 'cat-tv';
      if ((id >= 1000 && id < 2000) || (id >= 4000 && id < 5000)) return 'cat-games';
    }
    return null;
  }

  function age(iso) {
    if (!iso) return '';
    var d = Math.floor((Date.now() - new Date(iso).getTime()) / 86400000);
    if (isNaN(d)) return '';
    if (d <= 0) return 'today';
    if (d === 1) return '1 day';
    if (d < 30) return d + ' days';
    if (d < 365) return Math.floor(d / 30) + ' mo';
    return Math.floor(d / 365) + ' yr';
  }

  // ---------- styles ----------

  var css = document.createElement('style');
  css.textContent = [
    '#pws-btn{position:fixed;right:18px;bottom:18px;z-index:2147483000;background:#2c5fa8;',
    'color:#fff;border:0;border-radius:4px;padding:9px 14px;font:600 12px/1 system-ui,sans-serif;',
    'cursor:pointer;box-shadow:0 2px 10px rgba(0,0,0,.45)}',
    '#pws-btn:hover{background:#3a74c4}',
    '#pws-ov{position:fixed;inset:0;z-index:2147483100;background:rgba(0,0,0,.55);display:flex;',
    'align-items:flex-start;justify-content:center;padding:6vh 16px}',
    '#pws{background:#1f2328;color:#dfe3e8;width:min(980px,100%);max-height:84vh;display:flex;',
    'flex-direction:column;border-radius:6px;box-shadow:0 10px 40px rgba(0,0,0,.6);',
    'font:13px/1.45 system-ui,sans-serif;overflow:hidden}',
    '#pws header{display:flex;gap:8px;padding:12px;border-bottom:1px solid #333a42;align-items:center}',
    '#pws input{flex:1;background:#15181c;border:1px solid #39414a;color:#dfe3e8;padding:8px 10px;',
    'border-radius:4px;font-size:13px;outline:none}',
    '#pws input:focus{border-color:#2c5fa8}',
    '#pws select{background:#15181c;border:1px solid #39414a;color:#dfe3e8;padding:8px;border-radius:4px}',
    '#pws .go{background:#2c5fa8;color:#fff;border:0;border-radius:4px;padding:8px 14px;cursor:pointer;font-weight:600}',
    '#pws .x{background:transparent;color:#8b949e;border:0;font-size:20px;cursor:pointer;padding:0 6px}',
    '#pws .body{overflow:auto}',
    '#pws table{width:100%;border-collapse:collapse}',
    '#pws th{position:sticky;top:0;background:#262b31;text-align:left;font-size:11px;',
    'text-transform:uppercase;letter-spacing:.04em;color:#8b949e;padding:7px 10px;font-weight:600}',
    '#pws td{padding:7px 10px;border-top:1px solid #2a3037;vertical-align:top}',
    '#pws tr:hover td{background:#252b31}',
    '#pws .t{word-break:break-word}',
    '#pws .meta{color:#8b949e;font-size:11px}',
    '#pws .s{color:#4caf72;font-weight:600;text-align:right;white-space:nowrap}',
    '#pws .l{color:#8b949e;text-align:right;white-space:nowrap}',
    '#pws .sz{white-space:nowrap;text-align:right}',
    '#pws .add{background:#30363d;color:#dfe3e8;border:1px solid #434b54;border-radius:4px;',
    'padding:4px 10px;cursor:pointer;white-space:nowrap;font-size:12px}',
    '#pws .add:hover{background:#3a434c}',
    '#pws .add[disabled]{opacity:.55;cursor:default}',
    '#pws .ok{color:#4caf72;border-color:#2f5d41;background:#1d2a22}',
    '#pws .err{color:#ff7b72;border-color:#5d2f2f;background:#2a1d1d}',
    '#pws .note{padding:18px;color:#8b949e;text-align:center}',
  ].join('');
  document.head.appendChild(css);

  // ---------- panel ----------

  var input, sortSel, tbody, note, overlay;

  function open() {
    if (overlay) { overlay.style.display = 'flex'; input.focus(); input.select(); return; }

    input = el('input', { type: 'text', placeholder: 'Search TorrentLeech and Nyaa.si…', onkeydown: function (e) {
      if (e.key === 'Enter') run();
      if (e.key === 'Escape') close();
    }});
    sortSel = el('select', { onchange: render });
    [['seeders', 'Most seeders'], ['publishDate', 'Newest'], ['size', 'Largest']].forEach(function (o) {
      sortSel.appendChild(el('option', { value: o[0], text: o[1] }));
    });

    tbody = el('tbody');
    note = el('div', { class: 'note', text: 'Type a search and press Enter.' });

    var table = el('table', null, [
      el('thead', null, [el('tr', null, [
        el('th', { text: 'Release' }),
        el('th', { text: 'Size', style: { textAlign: 'right' } }),
        el('th', { text: 'S', style: { textAlign: 'right' } }),
        el('th', { text: 'L', style: { textAlign: 'right' } }),
        el('th', { text: '' }),
      ])]),
      tbody,
    ]);
    table.style.display = 'none';

    var body = el('div', { class: 'body' }, [note, table]);
    var panel = el('div', { id: 'pws' }, [
      el('header', null, [
        input,
        sortSel,
        el('button', { class: 'go', text: 'Search', onclick: run }),
        el('button', { class: 'x', text: '×', onclick: close }),
      ]),
      body,
    ]);
    panel.__table = table;

    overlay = el('div', { id: 'pws-ov', onclick: function (e) { if (e.target === overlay) close(); } }, [panel]);
    document.body.appendChild(overlay);
    input.focus();
  }

  function close() { if (overlay) overlay.style.display = 'none'; }

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && overlay && overlay.style.display !== 'none') close();
  });

  // ---------- search ----------

  var results = [];

  /* Two ways to authenticate to Prowlarr, tried in order:
   *   1. X-Api-Key header - tidier, but a custom header makes this a non-simple CORS
   *      request, so the browser sends an OPTIONS preflight first.
   *   2. ?apikey= query parameter - a plain GET with no custom headers, so no preflight
   *      at all. Fewer moving parts; the key does end up in Prowlarr's request log.
   * Prowlarr answers both with Access-Control-Allow-Origin: *. The fallback exists because
   * anything sitting between the browser and Prowlarr is far more likely to interfere with
   * a preflight than with an ordinary GET.
   */
  function search(q) {
    var base = CFG.prowlarr + '/api/v1/search?type=search&query=' + encodeURIComponent(q);

    function viaQueryParam() {
      return fetch(base + '&apikey=' + encodeURIComponent(CFG.apiKey)).then(function (r) {
        if (!r.ok) throw new Error('Prowlarr returned ' + r.status);
        return r.json();
      });
    }

    return fetch(base, { headers: { 'X-Api-Key': CFG.apiKey } })
      .then(function (r) {
        if (!r.ok) throw new Error('Prowlarr returned ' + r.status);
        return r.json();
      })
      .catch(viaQueryParam);
  }

  function run() {
    var q = input.value.trim();
    if (!q) return;
    results = [];
    render();
    note.textContent = 'Searching…';
    note.style.display = '';
    document.querySelector('#pws').__table.style.display = 'none';

    search(q)
      .then(function (d) {
        results = (d || []).filter(function (x) { return x.downloadUrl || x.magnetUrl; });
        render();
      })
      .catch(function (e) {
        note.textContent = 'Search failed: ' + e.message;
        note.style.display = '';
      });
  }

  function render() {
    if (!tbody) return;
    var table = document.querySelector('#pws').__table;
    tbody.textContent = '';

    if (!results.length) {
      note.textContent = note.textContent === 'Searching…' ? 'Searching…' : 'No results.';
      note.style.display = '';
      table.style.display = 'none';
      return;
    }

    var key = sortSel.value;
    var rows = results.slice().sort(function (a, b) {
      if (key === 'publishDate') return new Date(b.publishDate || 0) - new Date(a.publishDate || 0);
      return (b[key] || 0) - (a[key] || 0);
    }).slice(0, CFG.limit);

    note.style.display = 'none';
    table.style.display = '';

    rows.forEach(function (r) {
      var btn = el('button', { class: 'add', text: 'Add' });
      btn.addEventListener('click', function () { add(r, btn); });
      tbody.appendChild(el('tr', null, [
        el('td', { class: 't' }, [
          el('div', { text: r.title || '(untitled)' }),
          el('div', { class: 'meta', text: [r.indexer, age(r.publishDate)].filter(Boolean).join(' · ') }),
        ]),
        el('td', { class: 'sz', text: size(r.size) }),
        el('td', { class: 's', text: r.seeders == null ? '-' : String(r.seeders) }),
        el('td', { class: 'l', text: r.leechers == null ? '-' : String(r.leechers) }),
        el('td', null, [btn]),
      ]));
    });
  }

  // ---------- add to flood ----------

  /* Where this release should download to. The category is known now, at add time, so a grab
   * can land directly in its library folder instead of going to staging and being moved by
   * media-sort afterwards. Precedence mirrors the sorter's exactly:
   *   Nyaa -> Anime (Greg's rule), else the tracker category, else staging.
   * Anything that resolves to staging is still filed later by media-sort's name heuristics,
   * so nothing regresses - this only shortcuts the cases we can already place confidently.
   */
  function destFor(r) {
    if (/nyaa/i.test(r.indexer || '')) return CFG.library + '/Anime';
    var c = categoryTag(r);
    if (c && FOLDERS[c]) return CFG.library + '/' + FOLDERS[c];
    return CFG.destination;
  }

  function add(r, btn) {
    btn.disabled = true;
    btn.textContent = 'Adding…';
    btn.className = 'add';

    fetch('api/torrents/add-urls', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        urls: [r.downloadUrl || r.magnetUrl],
        destination: destFor(r),
        // the tracker name and its category are tagged too: the destination above already
        // routes the confident cases, and these let media-sort file the rest (and the
        // watch-dir / Feeds additions, which carry no destination) by category not filename
        tags: [CFG.tag, slug(r.indexer), categoryTag(r)].filter(Boolean),
        isBasePath: false,
        isCompleted: false,
        isSequential: false,
        isInitialSeeding: false,
        start: true,
      }),
    })
      .then(function (res) {
        if (!res.ok) return res.text().then(function (t) { throw new Error(res.status + ' ' + t.slice(0, 120)); });
        btn.textContent = 'Added';
        btn.className = 'add ok';
      })
      .catch(function (e) {
        btn.textContent = 'Failed';
        btn.className = 'add err';
        btn.title = e.message;
        btn.disabled = false;
      });
  }

  // ---------- mount ----------

  function mount() {
    if (document.getElementById('pws-btn')) return;
    document.body.appendChild(
      el('button', { id: 'pws-btn', text: 'Search trackers', onclick: open })
    );
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', mount);
  } else {
    mount();
  }
})();
