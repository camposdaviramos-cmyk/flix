(function () {
  'use strict';
  var link = document.getElementById('retry');
  // A navigation fallback keeps the originally requested URL, including TV mode.
  link.href = location.pathname === '/static/offline.html' ? '/' : location.href;
  link.focus();
  document.addEventListener('keydown', function (e) {
    if ([13,37,38,39,40].indexOf(e.keyCode) !== -1) {
      e.preventDefault();link.focus();if(e.keyCode === 13) location.replace(link.href);
    }
  });
  var attempts = 0;
  function reconnect() {
    if (!navigator.onLine || attempts >= 5) return;
    attempts += 1;
    if (!window.fetch) { location.replace(link.href); return; }
    // Some TVs emit online before their connection is usable. Confirm the server first.
    fetch('/manifest.webmanifest?connection-check=' + Date.now(), {cache:'no-store'}).then(function (response) {
      if (!response.ok) throw Error('offline');
      location.replace(link.href);
    }).catch(function () { setTimeout(reconnect, 1500); });
  }
  window.addEventListener('online', function () { attempts = 0; reconnect(); });
}());
