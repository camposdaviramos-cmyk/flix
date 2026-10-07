/* Remote navigation is opt-in/detected, and leaves desktop/mobile input untouched. */
(() => {
  'use strict';
  const enabled = !!window.WorkTVPlatform?.tv;
  const selector = 'a[href],button,input:not([type=hidden]),select,textarea,summary,video[controls],[tabindex]';
  const positions = new Map();
  let routing = true, opener = null, lastFocus = null, timer = 0, repairTimer = 0, remoteStamp = 0, playerVideo = null;
  const visible = el => !!(el?.isConnected && el.getClientRects().length && !el.disabled && el.getAttribute('aria-disabled') !== 'true' && !el.closest('[hidden],[inert],[aria-hidden=true]') && getComputedStyle(el).visibility !== 'hidden');
  const scope = () => {
    const dialog=[...document.querySelectorAll('dialog[open],[role=dialog][aria-modal=true]')].filter(visible).pop();
    if(dialog)return [...dialog.querySelectorAll('.fj-panel:not([hidden])')].filter(visible).pop()||dialog;
    return [...document.querySelectorAll('#fh-messenger:not(.inline):not([hidden]),#fh-notifications:not([hidden]),.fs-user-menu[open]')].filter(visible).pop()||document;
  };
  const candidates = (root = scope()) => [...root.querySelectorAll(selector)].filter(el => visible(el) && el.tabIndex >= 0 && !el.matches('.skip-link'));
  function announce(message) { const el=document.getElementById('wt-tv-status'); if(el)el.textContent=message; }
  function focus(el, scroll = true) {
    if (!visible(el)) return;
    try { el.focus({preventScroll:true}); } catch (_) { el.focus(); }
    if (scroll) el.scrollIntoView({block:'nearest',inline:'nearest',behavior:'auto'});
    lastFocus=el;
  }
  function identity(el) {
    if (!el || el === document.body) return null;
    return {id:el.id,action:el.getAttribute('data-action'),item:el.getAttribute('data-id'),href:el.getAttribute('href'),label:el.getAttribute('aria-label'),text:el.textContent};
  }
  function matching(record) {
    if(!record)return null;
    return candidates().find(el => {
      const key=identity(el);
      if(record.id)return key.id===record.id;
      return ['action','item','href','label','text'].every(k=>key[k]===record[k]);
    });
  }
  function remember() {
    if(!enabled)return;
    positions.set(location.pathname+location.search,{focus:identity(document.activeElement),x:scrollX,y:scrollY});
    if(positions.size>30)positions.delete(positions.keys().next().value);
  }
  function routeChanged() {
    if(!enabled)return;
    routing=true;
    clearTimeout(timer);
    timer=setTimeout(()=>{
      routing=false;
      if(scope()!==document){focus(candidates()[0]);return;}
      const saved=positions.get(location.pathname+location.search);
      const target=matching(saved?.focus);
      if(target){window.scrollTo(saved.x,saved.y);focus(target);}
      else focus(document.querySelector('.header nav a.active') || candidates()[0]);
      enhancePlayer();
      const header=document.querySelector('.header');
      if(header)document.documentElement.style.setProperty('--wt-tv-header',header.getBoundingClientRect().height+'px');
    },120);
  }
  function move(direction) {
    const all=candidates(), current=document.activeElement;
    if(!all.includes(current)){focus(all[0]);return;}
    const a=current.getBoundingClientRect(), horizontal=direction==='left'||direction==='right', sign=direction==='left'||direction==='up'?-1:1;
    const ac=horizontal?(a.left+a.right)/2:(a.top+a.bottom)/2;
    const ap=horizontal?(a.top+a.bottom)/2:(a.left+a.right)/2;
    let best=null,score=Infinity;
    all.forEach(el=>{
      if(el===current)return;
      const b=el.getBoundingClientRect(), bc=horizontal?(b.left+b.right)/2:(b.top+b.bottom)/2;
      const primary=(bc-ac)*sign;
      if(primary<2)return;
      const bp=horizontal?(b.top+b.bottom)/2:(b.left+b.right)/2;
      const overlap=horizontal?Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top):Math.min(a.right,b.right)-Math.max(a.left,b.left);
      const cost=primary+Math.abs(bp-ap)*2+(overlap>4?0:2500);
      if(cost<score){score=cost;best=el;}
    });
    if(best)focus(best);
  }
  function back() {
    if(document.fullscreenElement){document.exitFullscreen().catch(()=>{});return true;}
    const dialog=scope();
    if(dialog!==document){
      const close=dialog.querySelector('[data-action=close],.modal-close,[data-jump=panel-close],[data-hub=hide],[data-hub=notices-close],[aria-label=Fechar]');
      if(close){const panel=dialog.tagName!=='DIALOG';close.click();if(panel)setTimeout(()=>focus(document.querySelector('#modal[open] [data-jump=room]')||document.querySelector('[data-hub=chat]')||candidates()[0]),50);}else if(dialog.matches('.fs-user-menu')){dialog.open=false;focus(dialog.querySelector('summary'));}else if(dialog.tagName==='DIALOG')dialog.dispatchEvent(new Event('cancel',{cancelable:true}));
      return true;
    }
    const menu=document.querySelector('#main-nav.open');
    if(menu){document.querySelector('[data-action=menu]')?.click();return true;}
    if((history.state?.worktvDepth||0)>0){history.back();return true;}
    if(location.pathname!=='/'){window.navigate('/');return true;}
    return false; // Let the TV/browser handle exit at the root.
  }
  function playPause(action) {
    const v=document.querySelector('#video-player');if(!visible(v))return false;
    if(window.FlixJump?.canControlPlayback?.()===false){
      if(action==='play'||action==='toggle')document.querySelector('[data-jump=toggle]')?.click();
      else announce('A reprodução desta sala é controlada pelo anfitrião.');
      return true;
    }
    if(action==='pause'||action==='stop'){v.pause();return true;}
    if(action==='toggle'&&!v.paused)v.pause();
    else v.play().catch(()=>announce('Selecione Reproduzir para iniciar o vídeo.'));
    return true;
  }
  function seek(delta) {
    const v=document.querySelector('#video-player');if(!visible(v))return false;
    if(window.FlixJump?.canSeekPlayback?.()===false){announce('Não é possível avançar nesta transmissão ou sala.');return true;}
    if(!v.seekable.length)return false;
    const end=v.seekable.end(v.seekable.length-1),start=v.seekable.start(0);
    v.currentTime=Math.max(start,Math.min(end-.1,v.currentTime+delta));return true;
  }
  function enhancePlayer() {
    const v=document.querySelector('#video-player');
    if(!enabled||!v||v===playerVideo)return;
    playerVideo=v;
    const bar=document.createElement('div');bar.className='wt-tv-player-controls';bar.setAttribute('role','group');bar.setAttribute('aria-label','Controles de reprodução');
    bar.innerHTML='<button type="button" data-tv-play="back">Voltar 10 s</button><button type="button" data-tv-play="toggle">Reproduzir</button><button type="button" data-tv-play="forward">Avançar 10 s</button><button type="button" data-tv-play="fullscreen">Tela cheia</button><span class="wt-tv-time"></span>';
    v.parentElement.insertAdjacentElement('afterend',bar);
    const toggle=bar.querySelector('[data-tv-play=toggle]'),clock=bar.querySelector('.wt-tv-time');
    const format=n=>Number.isFinite(n)?Math.floor(n/60)+':'+String(Math.floor(n%60)).padStart(2,'0'):'Ao vivo';
    const update=()=>{
      toggle.textContent=v.paused?'Reproduzir':'Pausar';clock.textContent=format(v.currentTime)+' / '+format(v.duration);
      bar.querySelectorAll('[data-tv-play=back],[data-tv-play=forward]').forEach(b=>{b.disabled=!v.seekable.length||window.FlixJump?.canSeekPlayback?.()===false;});
    };
    ['play','pause','loadedmetadata','timeupdate','progress','durationchange'].forEach(name=>v.addEventListener(name,update));update();
    // The Fullscreen API forbids requesting a <dialog> itself. Use a child stage.
    const modal=document.querySelector('.player-modal');
    let stage=modal.querySelector('.wt-tv-player-stage');
    if(!stage){stage=document.createElement('div');stage.className='wt-tv-player-stage';while(modal.firstChild)stage.append(modal.firstChild);modal.append(stage);}
    const full=bar.querySelector('[data-tv-play=fullscreen]');full.hidden=!document.fullscreenEnabled;
    bar.addEventListener('click',e=>{
      const action=e.target.getAttribute('data-tv-play');
      if(action==='toggle')playPause('toggle');else if(action==='back')seek(-10);else if(action==='forward')seek(10);
      else if(action==='fullscreen')stage.requestFullscreen().catch(()=>announce('Tela cheia indisponível neste aparelho.'));
    });
  }
  window.WorkTVTV={enabled,remember,routeChanged,
    beforeNavigate(){if(!enabled)return;remember();routing=true;},
    historyState(){return enabled?{worktvDepth:(history.state?.worktvDepth||0)+1}:{};},
    modalOpening(){if(enabled&&!document.querySelector('dialog[open]'))opener=document.activeElement;},
    modalOpened(){if(enabled){enhancePlayer();focus(document.querySelector('#modal input:not([type=hidden]),#modal .btn-primary,#modal [data-tv-play=toggle]')||candidates()[0]);}},
    modalClosed(){if(enabled&&visible(opener)){focus(opener);opener=null;}}
  };
  document.addEventListener('click',e=>{
    const toggle=e.target.closest('[data-tv-mode]');if(!toggle)return;
    e.preventDefault();const url=new URL(location.href);url.searchParams.set('tv',enabled?'0':'1');location.assign(url.href);
  });
  if(!enabled)return;
  history.replaceState({...history.state,worktvDepth:history.state?.worktvDepth||0},'',location.href);
  addEventListener('popstate',()=>{routing=true;});
  document.addEventListener('keydown',e=>{
    if(e.altKey||e.ctrlKey||e.metaKey||e.isComposing)return;
    const codes={37:'ArrowLeft',38:'ArrowUp',39:'ArrowRight',40:'ArrowDown',13:'Enter',10009:'BrowserBack',461:'BrowserBack',4:'BrowserBack',10252:'MediaPlayPause',179:'MediaPlayPause',415:'MediaPlay',19:'MediaPause',413:'MediaStop',417:'MediaFastForward',412:'MediaRewind'};
    const key=codes[e.keyCode]||e.key,editable=e.target.matches('input,textarea,select,[contenteditable=true]');
    let handled=false;
    if(['BrowserBack','GoBack','Escape'].includes(key)||key==='Backspace'&&!editable)handled=back();
    else if(['MediaPlayPause','MediaPlay','MediaPause','MediaStop','MediaFastForward','MediaRewind'].includes(key))handled=key==='MediaFastForward'?seek(10):key==='MediaRewind'?seek(-10):playPause(key==='MediaPause'?'pause':key==='MediaStop'?'stop':key==='MediaPlay'?'play':'toggle');
    else if(key==='Tab'){
      const all=candidates(),index=all.indexOf(document.activeElement);focus(all[(index+(e.shiftKey?-1:1)+all.length)%all.length]);handled=true;
    } else if(key.startsWith('Arrow')){
      // Horizontal editing and native select/textarea keys belong to the TV keyboard.
      if(editable&&(e.target.matches('textarea,select,[contenteditable=true],input[type=range]')||['ArrowLeft','ArrowRight'].includes(key)))return;
      if(e.repeat&&performance.now()-remoteStamp<90){handled=true;}else{remoteStamp=performance.now();move(key.slice(5).toLowerCase());handled=true;}
    } else if(key==='Enter'&&!editable){
      if(!e.repeat){const el=document.activeElement;if(el?.matches('video,.video-wrap'))playPause('toggle');else if(visible(el)&&el!==document.body)el.click();else focus(candidates()[0]);}handled=true;
    }
    if(handled){e.preventDefault();e.stopImmediatePropagation();}
  },true);
  document.addEventListener('focusin',e=>{if(visible(e.target))lastFocus=e.target;});
  document.addEventListener('DOMContentLoaded',()=>{
    const status=document.createElement('p');status.id='wt-tv-status';status.className='wt-tv-hint';status.setAttribute('role','status');status.textContent='Use as setas para navegar · OK para selecionar · Voltar para retornar';document.body.append(status);
    new MutationObserver(()=>{
      clearTimeout(repairTimer);repairTimer=setTimeout(()=>{
        enhancePlayer();
        if(routing)return;
        const currentScope=scope();
        if(currentScope!==document&&!currentScope.contains(document.activeElement))focus(candidates()[0]);
        else if(lastFocus&&(!lastFocus.isConnected||!visible(lastFocus))){focus(candidates().find(el=>el.matches('.poster-button,.channel-card'))||candidates()[0]);}
      },80);
    }).observe(document.body,{childList:true,subtree:true,attributes:true,attributeFilter:['hidden','open']});
    // Registration is only available inside a packaged Samsung app; browsers use ordinary keys.
    try{const input=window.tizen?.tvinputdevice;['MediaPlay','MediaPause','MediaPlayPause','MediaStop','MediaFastForward','MediaRewind'].forEach(key=>{try{input?.registerKey(key);}catch(_){}});}catch(_){}
  });
})();
