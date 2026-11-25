/* Shared top bar for every page. Include right after <body>: <script src="nav.js"></script>
   Pages (same order as the cards on index.html): Tech Tree / Designer / Models / Missions / Story / Bosses / World Map / Rewards / Flags / Credits. The current page is highlighted (helper pages count as their parent). */
(function () {
  var PAGES = [['tree.html', 'Tech Tree'], ['designer.html', 'Designer'], ['models.html', 'Models'], ['drydock.html', 'Dry Dock'], ['bosses.html', 'Bosses'], ['boss_anim.html', 'Boss Animations'], ['water.html', 'Water'], ['flags.html', 'Flags']];      // same order as the cards on index.html
  var PARENT = { 'designer3d.html': 'designer.html', 'designer_models.html': 'designer.html' };      // helper page -> the tab it counts as (none at the moment)
  var file = (location.pathname.split('/').pop() || 'index.html').toLowerCase();      // the site root is the index page: no tab is highlighted there
  var cur = PARENT[file] || file;
  var css = document.createElement('style');
  css.textContent =
    ':root{--sn-h:44px;--sn-bg:#0a101c;--sn-line:#2a3a55;--sn-text:#dbe6f5;--sn-muted:#8aa0bd;--sn-accent:#5cc8ff}' +
    '@media (prefers-color-scheme:light){:root{--sn-bg:#fff;--sn-line:#c9d3e0;--sn-text:#16202e;--sn-muted:#5a6b82;--sn-accent:#0a6fb5}}' +
    '.sitenav{position:sticky;top:0;z-index:100;flex:none;height:var(--sn-h);box-sizing:border-box;display:flex;align-items:center;gap:4px;padding:0 12px;background:var(--sn-bg);border-bottom:1px solid var(--sn-line);font:14px/1 "Segoe UI",Roboto,"Helvetica Neue",Arial,"Noto Sans",sans-serif;overflow-x:auto;white-space:nowrap}' +
    '.sitenav .brand{font-weight:700;color:var(--sn-text);margin-right:10px;text-decoration:none}' +
    '.sitenav a.tab{color:var(--sn-muted);text-decoration:none;padding:8px 12px;border-radius:6px;border:1px solid transparent}' +
    '.sitenav a.tab:hover{color:var(--sn-text);border-color:var(--sn-line)}' +
    '.sitenav a.tab[aria-current=page]{color:var(--sn-accent);border-color:var(--sn-accent)}' +
    '@media (max-width:520px){.sitenav .brand{display:none}}';
  document.head.appendChild(css);
  var nav = document.createElement('div'); nav.className = 'sitenav'; nav.setAttribute('role', 'navigation'); nav.setAttribute('aria-label', 'Site');
  var b = document.createElement('a'); b.className = 'brand'; b.href = 'index.html'; b.textContent = 'Warship Gunner 2 Compendium'; nav.appendChild(b);
  PAGES.forEach(function (p) {
    var a = document.createElement('a'); a.className = 'tab'; a.href = p[0]; a.textContent = p[1];
    if (p[0] === cur) a.setAttribute('aria-current', 'page');
    nav.appendChild(a);
  });
  document.body.insertBefore(nav, document.body.firstChild);
  // pages whose <body> has padding (campaign, rewards, maps, weapons): pull the bar out to the window edges so it spans the full width and sticks to the top
  var bs = getComputedStyle(document.body), pt = parseFloat(bs.paddingTop) || 0, pr = parseFloat(bs.paddingRight) || 0, pl = parseFloat(bs.paddingLeft) || 0;
  if (pt || pr || pl) nav.style.margin = (-pt) + 'px ' + (-pr) + 'px ' + pt + 'px ' + (-pl) + 'px';
})();

/* Scaffold notice: this repository ships the pages without game data. When a page fails to load its data, say why instead of failing silently. */
(function () {
  var shown = false;
  function notice() {
    if (shown || !document.body) return; shown = true;
    var d = document.createElement('div');
    d.setAttribute('role', 'status');
    d.style.cssText = 'margin:12px;padding:12px 16px;border:1px solid #c9a227;border-radius:8px;background:#fff8dc;color:#3a2f00;font:14px/1.4 sans-serif';
    d.textContent = 'No game data found. This is the code-only scaffold: the JSON files are empty stubs and the model, texture and music files are not included. Generate them from your own copy of the game with the scripts in tools/ (see the README).';
    document.body.insertBefore(d, document.body.children[1] || null);
  }
  window.addEventListener('unhandledrejection', notice);
  window.addEventListener('error', notice);
})();
