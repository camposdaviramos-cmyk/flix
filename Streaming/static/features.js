/* Route-dependent bundles: classic script order is preserved without blocking the guest homepage. */
(() => {
  'use strict';
  const version='scale-20261008a',files=new Map(),groups=new Map();
  function file(name,css=false) {
    const url='/static/'+name+(name.includes('?')?'':'?v='+version);
    if(files.has(url))return files.get(url);
    const promise=new Promise((resolve,reject)=>{
      const el=document.createElement(css?'link':'script');
      if(css){el.rel='stylesheet';el.href=url;}else{el.src=url;el.async=false;}
      el.onload=resolve;el.onerror=()=>{files.delete(url);el.remove();reject(Error('Não foi possível carregar esta função. Verifique sua conexão e tente novamente.'));};
      document.head.append(el);
    });files.set(url,promise);return promise;
  }
  function group(name,scripts,styles=[]) {
    if(!groups.has(name))groups.set(name,Promise.all([...styles.map(n=>file(n+'.css',true)),...scripts.map(n=>file(n+'.js'))]).catch(e=>{groups.delete(name);throw e;}));
    return groups.get(name);
  }
  const social=()=>group('social',["jump", "community", "community-social", "community-studio", "community-games", "community-room", "social-hub", "story-studio", "reel-studio", "community-create", "community-feed", "social-spaces", "flix-music", "room-mobile", "flix-wallet", "jump-mobile"],["jump", "community", "community-social", "community-studio", "social-hub", "community-create", "story-studio", "reel-studio", "social-spaces", "flix-music", "room-mobile", "flix-wallet"]);
  const player=()=>group('player',['vendor/hls.min']);
  window.WorkTVFeatures={player,async ensure(path,user){
    if(user||/^\/(?:comunidade|sala|carteira|admin)(?:\/|$)/.test(path))await social();
    if(/^\/(?:comunidade|sala|admin)(?:\/|$)/.test(path))await player();
    if(path.startsWith('/admin'))await group('admin',['admin']);
  }};
})();
