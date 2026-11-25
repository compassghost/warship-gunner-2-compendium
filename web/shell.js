// Loaded by every page. Inside the player shell (player.html): tell the shell which page / hash this is, so its address bar follows. On its own: offer the music player.
(function () {
  var here = function () { return location.pathname.split('/').pop() + location.search + location.hash; };
  if (window.top !== window) {
    var post = function () { try { parent.postMessage({ wg2nav: true, url: here(), title: document.title }, location.origin); } catch (e) {} };
    ['pushState', 'replaceState'].forEach(function (k) { var o = history[k]; history[k] = function () { var r = o.apply(this, arguments); post(); return r; }; });   // pages update their hash with replaceState
    addEventListener('hashchange', post); addEventListener('load', post); post();
    return;
  }
  if (/[?&]noshell\b/.test(location.search) || location.protocol === 'file:') return;
  addEventListener('DOMContentLoaded', function () {
    var a = document.createElement('a'); a.href = 'player.html#/' + here(); a.textContent = '♪ Music player';
    a.setAttribute('style', 'position:fixed;right:12px;bottom:12px;z-index:50;padding:5px 12px;border-radius:999px;background:#141f33;color:#e8eef9;border:1px solid #3b4d6b;font:13px system-ui,sans-serif;text-decoration:none;opacity:.85');
    a.title = 'Open this page inside the player, so music keeps playing while you browse'; document.body.appendChild(a);
  });
})();
