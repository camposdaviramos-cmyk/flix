/* Startup recovery is independent of React, effects and the application bundle. */
(function () {
  'use strict';
  var release = 'account-20261009a', ready = false, panel = null, timer, observer;
  function removePanel() {
    if (panel && panel.parentNode) panel.parentNode.removeChild(panel);
    panel = null;
  }
  function retry() {
    var button = panel && panel.querySelector('button');
    if (button) { button.disabled = true; button.textContent = 'Atualizando…'; }
    // Only public UI caches: cookies, sessions, downloads and playback checkpoints stay intact.
    var cleanup = Promise.resolve();
    if (window.caches) cleanup = caches.keys().then(function (keys) {
      return Promise.all(keys.filter(function (key) { return key.indexOf('flix-shell-') === 0; }).map(function (key) { return caches.delete(key); }));
    }).catch(function () {});
    if (navigator.serviceWorker) navigator.serviceWorker.getRegistration().then(function (reg) { if (reg) return reg.update(); }).catch(function () {});
    var reload = function () {
      var url = new URL(location.href);
      url.searchParams.set('_wt_reload', release + '-' + Date.now());
      location.replace(url.href);
    };
    Promise.race([cleanup, new Promise(function (resolve) { setTimeout(resolve, 2000); })]).then(reload, reload);
  }
  function fail() {
    if (panel || !document.body) return;
    panel = document.createElement('section');
    panel.id = 'worktv-recovery'; panel.setAttribute('role', 'alert');
    panel.style.cssText = 'position:fixed;inset:0;z-index:2147483647;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:18px;padding:28px;background:#070e1c;color:#f4f8ff;font:18px/1.5 Arial,sans-serif;text-align:center;overflow:auto';
    var brand = document.createElement('strong'); brand.textContent = 'WorkTV'; brand.style.cssText = 'font-size:38px;color:#62c4ff';
    var title = document.createElement('h1'); title.textContent = 'Vamos recuperar sua conexão com a WorkTV.'; title.style.cssText = 'font-size:25px;max-width:680px;margin:0';
    var copy = document.createElement('p'); copy.textContent = 'A página não terminou de carregar. Tente abrir novamente com os arquivos atualizados.'; copy.style.cssText = 'max-width:560px;margin:0';
    var button = document.createElement('button'); button.type = 'button'; button.textContent = 'Atualizar e tentar novamente'; button.style.cssText = 'font:700 17px Arial;padding:16px 24px;border:0;border-radius:10px;background:#2582ef;color:white;cursor:pointer'; button.addEventListener('click', retry);
    panel.appendChild(brand); panel.appendChild(title); panel.appendChild(copy); panel.appendChild(button); document.body.appendChild(panel); button.focus();
  }
  function rendered() {
    var app = document.getElementById('app');
    if (!app || !app.firstElementChild || app.querySelector('[data-worktv-render-failed]')) return;
    if (!window.WorkTVUI || window.WorkTVUI.release !== release) { fail(); return; }
    ready = true; clearTimeout(timer); removePanel();
    var url = new URL(location.href);
    if (url.searchParams.has('_wt_reload')) { url.searchParams.delete('_wt_reload'); history.replaceState(history.state, '', url.href); }
  }
  function inspect() {
    var app = document.getElementById('app');
    if (ready && app && !app.firstElementChild) fail();
  }
  window.WorkTVBoot = { fail: fail, rendered: rendered, retry: retry, release: release };
  // Start before deferred scripts so a stalled dependency cannot postpone the timeout indefinitely.
  timer = setTimeout(function () { if (!ready) fail(); }, 20000);
  document.addEventListener('DOMContentLoaded', function () {
    var app = document.getElementById('app');
    if (app && window.MutationObserver) {
      observer = new MutationObserver(function () { setTimeout(inspect, 0); });
      observer.observe(app, { childList: true });
    }
  });
}());
