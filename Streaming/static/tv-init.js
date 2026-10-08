/* Small ES5 bootstrap: detection also runs when an older TV cannot parse the app. */
(function () {
  'use strict';
  // Small runtime gaps in otherwise compatible TV engines (e.g. Chromium 87).
  if (!Array.prototype.at) Object.defineProperty(Array.prototype, 'at', {configurable:true,writable:true,value:function(index){var n=Math.trunc(Number(index)||0);return this[n<0?this.length+n:n];}});
  if (!String.prototype.at) Object.defineProperty(String.prototype, 'at', {configurable:true,writable:true,value:function(index){var n=Math.trunc(Number(index)||0);return this[n<0?this.length+n:n];}});
  if (!Object.hasOwn) Object.defineProperty(Object, 'hasOwn', {configurable:true,writable:true,value:function(object,key){return Object.prototype.hasOwnProperty.call(object,key);}});
  var ua = navigator.userAgent || '';
  var device = /SmartTV|Smart-TV|Tizen|Web0S|WebOS|NetCast|HbbTV|Viera|BRAVIA|GoogleTV|Android TV|AFT[A-Z0-9]|TV Safari/i.test(ua);
  var query = /(?:\?|&)tv=([01])(?:&|$)/.exec(location.search), saved = null;
  try { saved = localStorage.getItem('worktv-tv'); if (query) { saved = query[1]; localStorage.setItem('worktv-tv', saved); } } catch (_) {}
  var enabled = query ? query[1] === '1' : saved === null ? device : saved === '1';
  window.WorkTVPlatform = { tv: enabled, television: device };
  if (enabled) document.documentElement.classList.add('wt-tv');
  // Keep unsupported engines out of an endless spinner, without eval or weakening CSP.
  window.addEventListener('load', function () {
    if (typeof window.navigate === 'function') return;
    if (window.WorkTVBoot) { window.WorkTVBoot.fail(); return; }
    var app = document.getElementById('app');
    if (!app) return;
    app.innerHTML = '<main style="padding:8%;color:white;background:#070e1c;font:24px sans-serif"><h1>WorkTV</h1><p>O navegador deste aparelho precisa ser atualizado para abrir a WorkTV.</p><p>Atualize o sistema da TV ou use um navegador atualizado em um dispositivo conectado por HDMI.</p><a style="color:#62d6ff" href="/?tv=0">Tentar novamente</a></main>';
    app.querySelector('a').focus();
  });
}());
