'use strict';
// Enabled by an explicit link or a temporary server investigation of one title.
// Never records source URLs or bodies. Failures must not stop the player.
window.VyraDiagnostics = (() => {
  function enabled(context) {
    return !!context && (context.enabled === true || new URLSearchParams(location.search).get('player_debug') === '1');
  }
  function create(video, context, getMode) {
    if (!enabled(context)) return null;
    const indicator=document.querySelector('#player-diagnostic-status');
    let id;
    try {
      const bytes=new Uint8Array(16);crypto.getRandomValues(bytes);
      id=Array.from(bytes,b=>b.toString(16).padStart(2,'0')).join('');
    } catch (_) {
      if(indicator)indicator.textContent='Não foi possível iniciar o diagnóstico neste navegador.';
      return null;
    }
    const started=performance.now(), events=[], listeners=[];
    let timer=null,closed=false,sends=0,progress=false,probed=false;
    const probes=new Set();
    const capabilities={nativeHls:!!video.canPlayType('application/vnd.apple.mpegurl'),mse:!!window.MediaSource,mms:!!window.ManagedMediaSource,hlsSupported:!!window.Hls?.isSupported(),secureContext:window.isSecureContext};
    function flush(){
      clearTimeout(timer);timer=null;if(sends++>=30)return;
      fetch('/api/player/diagnostics',{method:'POST',credentials:'same-origin',keepalive:true,
        headers:{'Content-Type':'application/json','X-Requested-With':'VYRA'},
        body:JSON.stringify({id,content_id:context.contentId,episode_id:context.episodeId||'',trace:{build:'diagnostic3',capabilities,events}})
      }).then(r=>{if(indicator?.isConnected)indicator.textContent=r.ok?'Diagnóstico registrado: '+id.slice(0,8):'Não foi possível registrar o diagnóstico (HTTP '+r.status+').';}).catch(()=>{if(indicator?.isConnected)indicator.textContent='Falha de conexão ao enviar o diagnóstico.';});
    }
    function record(event,details={}){
      if(closed)return;
      events.push({event,at:Math.round(performance.now()-started),mode:getMode(),readyState:video.readyState,
        networkState:video.networkState,mediaCode:video.error?.code||0,position:video.currentTime||0,
        paused:video.paused,remotePlaybackDisabled:!!video.disableRemotePlayback,...details});
      if(events.length>40)events.shift();
      if(!timer)timer=setTimeout(flush,700);
    }
    for(const event of ['loadedmetadata','canplay','playing','waiting','stalled','pause']){
      const fn=()=>record(event);video.addEventListener(event,fn);listeners.push([event,fn]);
    }
    const tick=()=>{if(!progress&&video.currentTime>0&&!video.paused){progress=true;record('progress');}};
    video.addEventListener('timeupdate',tick);listeners.push(['timeupdate',tick]);
    const timeout=setTimeout(()=>{if(!progress)record('timeout');},15000);
    const sourceLink=document.querySelector('#player-diagnostic-source');
    const direct=()=>{record('direct-open');flush();};
    sourceLink?.addEventListener('click',direct);
    async function probeSource(url){
      if(closed||probed)return;probed=true;
      // Only after an unreadable manifest failure. Opaque success means the
      // browser reached an HTTP response, NOT that it received playable HLS.
      await Promise.all(['cors','no-cors'].map(async mode=>{
        const controller=new AbortController();probes.add(controller);
        const deadline=setTimeout(()=>controller.abort(),8000);
        try{
          const response=await fetch(url,{mode,credentials:'omit',cache:'no-store',signal:controller.signal});
          record('source-probe',{probeMode:mode,responseType:response.type,httpStatus:response.status,
            reachable:true,mime:response.headers.get('Content-Type')?.split(';')[0]});
          await response.body?.cancel();
        }catch(error){record('source-probe',{probeMode:mode,reachable:false,errorName:error.name});}
        finally{clearTimeout(deadline);probes.delete(controller);}
      }));
    }
    return {record,probeSource,close(){record('closed');closed=true;clearTimeout(timeout);for(const controller of probes)controller.abort();sourceLink?.removeEventListener('click',direct);for(const [e,fn] of listeners)video.removeEventListener(e,fn);flush();}};
  }
  return {create,enabled};
})();
