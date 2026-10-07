'use strict';
// Safari's native HLS path avoids unnecessary MSE/CORS dependencies on Apple devices.
window.VyraMedia = (() => {
  function nativeHls(video) {
    const apple = /Apple/.test(navigator.vendor || '') || /iPad|iPhone|iPod/.test(navigator.userAgent || '') || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
    const tv = !!window.WorkTVPlatform?.television || /SmartTV|Smart-TV|Tizen|Web0S|WebOS|Android TV|AFT[A-Z0-9]/i.test(navigator.userAgent || '');
    return (apple || tv) && !!video.canPlayType('application/vnd.apple.mpegurl');
  }
  function failure(data, nativeError) {
    const code=Number(data?.response?.code || data?.networkDetails?.status || 0);
    if(code===404||code===410)return 'A fonte não disponibilizou o vídeo para esta conexão (HTTP '+code+').';
    if(code===401||code===403)return 'A fonte recusou o acesso ao vídeo. O link pode ter expirado ou exigir autorização.';
    if(data&&data.type===window.Hls?.ErrorTypes?.NETWORK_ERROR)return 'Não foi possível baixar a transmissão nesta conexão. A fonte pode estar bloqueando o acesso ou não permitir a reprodução neste site.';
    if(nativeError?.code===3)return 'O navegador não conseguiu decodificar este vídeo. A fonte precisa de um formato compatível. (Vídeo 3)';
    if(nativeError?.code===4)return 'O navegador não conseguiu abrir esta fonte de vídeo. O formato ou a resposta do servidor não é compatível. (Vídeo 4)';
    return 'Não foi possível carregar o vídeo. A fonte pode estar indisponível, expirada ou incompatível com este navegador.';
  }
  function attach(video,url,{hls=false,onError=()=>{},onReady=()=>{},diagnostic=null}={}) {
    let disposed=false,instance=null,recoveries=0,mode='native',fallbackUsed=false,started=false,terminalError='';
    const trace=window.VyraDiagnostics?.create(video,diagnostic,()=>mode);
    const originalRemotePlayback=video.disableRemotePlayback;
    video.playsInline=true;video.setAttribute('playsinline','');video.preload='metadata';video.removeAttribute('crossorigin');
    const report=message=>{if(!disposed){terminalError=message;onError(message);}};
    // The native HLS stack can reject a playlist that hls.js can transmux.
    // Try the alternate engine once, only during startup, without changing the URL.
    function fallback(){
      if(disposed||started||fallbackUsed||mode!=='native-hls'||!window.Hls?.isSupported())return false;
      fallbackUsed=true;
      trace?.record('fallback');
      onError('Preparando um modo de reprodução compatível…');
      video.removeAttribute('src');video.load();
      startHls();
      return true;
    }
    const failed=()=>{if(disposed)return;trace?.record('native-error');if(!fallback())report(terminalError||failure(null,video.error));};
    const ready=()=>{if(!disposed){started=true;terminalError='';onReady();}};
    video.addEventListener('error',failed);video.addEventListener('playing',ready);
    const native= hls && (nativeHls(video)||(!window.Hls?.isSupported()&&!!video.canPlayType('application/vnd.apple.mpegurl')));
    function startHls(){
      mode='hlsjs';
      // iPhone MMS will not start without an AirPlay alternative or this flag.
      if(window.ManagedMediaSource)video.disableRemotePlayback=true;
      instance=new Hls({maxBufferLength:30});
      if(trace){
        instance.on(Hls.Events.MANIFEST_PARSED,(_,d)=>trace.record('manifest',{videoCodec:d.levels?.[0]?.videoCodec,audioCodec:d.levels?.[0]?.audioCodec}));
        instance.on(Hls.Events.LEVEL_LOADED,()=>trace.record('level'));
        instance.once(Hls.Events.FRAG_LOADED,()=>trace.record('fragment'));
        instance.on(Hls.Events.BUFFER_CODECS,(_,tracks)=>{
          for(const [kind,track] of Object.entries(tracks)){
            const Media=window.ManagedMediaSource||window.MediaSource;
            trace.record('codecs',{[kind==='audio'?'audioCodec':'videoCodec']:track.codec,mime:track.container,
              supported:!!Media?.isTypeSupported(`${track.container};codecs="${track.codec}"`)});
          }
        });
      }
      instance.on(Hls.Events.ERROR,(_,data)=>{
        if(!disposed)trace?.record('hls-error',{fatal:!!data.fatal,detail:data.details,errorType:data.type,
          httpStatus:Number(data.response?.code||data.networkDetails?.status||0),
          mime:data.networkDetails?.getResponseHeader?.('Content-Type')?.split(';')[0]});
        if(disposed||!data.fatal)return;
        if(data.details==='manifestLoadError'&&!Number(data.response?.code||data.networkDetails?.status||0))trace?.probeSource(url);
        if(data.type===Hls.ErrorTypes.MEDIA_ERROR&&recoveries++<1){instance.recoverMediaError();return;}
        report(failure(data));
      });
      instance.attachMedia(video);instance.loadSource(url);
    }
    if(hls&&!native&&window.Hls?.isSupported())startHls();
    else if(hls&&!native){report('Este navegador não oferece suporte a esta transmissão HLS.');}
    else {mode=native?'native-hls':'native';video.src=url;video.load();}
    trace?.record('source');
    return {
      get hls(){return instance;},get mode(){return mode;},
      handlePlayError(error){
        if(disposed||error.name==='AbortError')return;
        trace?.record('play-error',{errorName:error.name});
        if(error.name==='NotAllowedError'){onError('Toque em Reproduzir para iniciar o vídeo neste dispositivo.');return;}
        if(error.name==='NotSupportedError'){
          if(fallback())return;
          // A rejected native play() can arrive after switching to hls.js.
          if(fallbackUsed&&!terminalError&&!video.error)return;
          report(terminalError||failure(null,video.error||{code:4}));return;
        }
        report(terminalError||failure(null,video.error));
      },
      destroy(){if(disposed)return;trace?.close();disposed=true;video.removeEventListener('error',failed);video.removeEventListener('playing',ready);instance?.destroy();video.disableRemotePlayback=originalRemotePlayback;}
    };
  }
  return {attach,nativeHls,failure};
})();
