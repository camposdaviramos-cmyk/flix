'use strict';
// FlixJump uses short polling for room state and WebRTC for peer audio.
Object.assign(paths, {
  chat:'M4 4h16v12H9l-5 4Z', mic:'M9 5a3 3 0 0 1 6 0v7a3 3 0 0 1-6 0ZM5 10v2a7 7 0 0 0 14 0v-2M12 19v3M8 22h8',
  micOff:'m3 3 18 18M9 5a3 3 0 0 1 6 0v6M9 9v3a3 3 0 0 0 5 2M5 10v2a7 7 0 0 0 12 5M19 10v2M12 19v3M8 22h8',
  pause:'M8 5v14M16 5v14', expand:'M8 3H3v5M16 3h5v5M3 16v5h5M21 16v5h-5', send:'m3 3 19 9-19 9 4-9ZM7 12h15',
  rewind:'m10 6-7 6 7 6V6Zm10 0-7 6 7 6V6Z', muted:'M11 5 6 9H2v6h4l5 4ZM16 9l6 6m0-6-6 6'
});
window.FlixJump = (() => {
  let active = null;
  const button = (action, label, glyph, extra='') => `<button type="button" class="fj-icon" data-jump="${action}" aria-label="${label}" title="${label}" ${extra}>${icon(glyph)}</button>`;
  const post = (path, body={}) => api(path,{method:'POST',body});
  const host = p => p.jump?.host_id===state.user?.id;
  const status = (p,message) => { if(active===p && $('.player-status')) $('.player-status').textContent=message; };
  function panel(p, title, html) {
    const el=$('.fj-panel',p.wrap);el.hidden=false;
    el.innerHTML=`<div class="fj-panel-head"><div><span class="fj-kicker">FLIXJUMP</span><h3>${title}</h3></div>${button('panel-close','Fechar painel','close')}</div>${html}`;
    $('.fj-bubbles',p.wrap).hidden=true;
    $('[data-jump="chat"]',p.wrap)?.setAttribute('aria-expanded','true');
  }
  function mount(p, room=null) {
    active=p;p.jump=room;p.disposed=false;p.peers=new Map();p.cursor=0;p.lastMessage=0;p.localStream=null;p.cameraStream=null;p.userVolume=p.video.volume;p.userMuted=p.video.muted;p.voiceMonitors=new Map();p.ducking=false;p.signalQueue=[];
    p.wrap=$('.video-wrap');p.wrap.tabIndex=0;p.wrap.setAttribute('aria-label','Player de vídeo');
    p.video.controls=false;
    p.wrap.insertAdjacentHTML('beforeend',`<div class="fj-top"><div class="fj-now"><span class="fj-kicker">${p.live?'AO VIVO':'AGORA EM EXIBIÇÃO'}</span><strong>${esc(state.items.find(i=>i.id===p.id)?.title)}</strong><span class="fj-room-label">Seu cinema, sua companhia.</span></div><span class="fj-room-badge" hidden></span></div><div class="fj-social">${button('room','FlixJump · Assistir com amigos','users')}${button('chat','Abrir chat da sala','chat','aria-expanded="false"')}${button('mic','Ativar microfone','micOff','aria-pressed="false"')}${button('camera','Ativar câmera','camera','aria-pressed="false"')}</div><div class="fj-bubbles" aria-live="polite"></div><section class="fj-panel" aria-label="FlixJump" hidden></section><aside class="fj-entry-notice" aria-live="polite" hidden></aside><div class="fj-controls"><input class="fj-timeline" aria-label="Posição do vídeo" type="range" min="0" max="100" step="0.1" value="0" ${p.live?'hidden':''}><div class="fj-control-row">${button('toggle','Reproduzir','play')}${p.live?'':button('back','Voltar 10 segundos','rewind')}<span class="fj-time">${p.live?'<i></i> AO VIVO':'00:00 / 00:00'}</span><div class="fj-volume">${button('mute','Silenciar vídeo','volume')}<input aria-label="Volume do vídeo" class="fj-volume-range" type="range" min="0" max="1" step="0.05" value="1"></div><span class="fj-sync">${p.live?'Transmissão ao vivo':'Pronto para o próximo play'}</span>${button('fullscreen','Tela cheia','expand')}</div></div><div class="fj-playback-gate" hidden><button type="button" class="btn btn-primary" data-jump="enable-playback">${icon('play')} Acompanhar sala</button><small>Ative uma vez para acompanhar o anfitrião neste dispositivo.</small></div><span class="fj-voice-priority" hidden>Voz em destaque · filme reduzido</span><div class="fj-audio"></div><div class="fj-camera-rail" aria-label="Câmeras da sala" hidden></div>`);
    $('.player-footer').insertAdjacentHTML('beforeend',`<button type="button" class="btn btn-secondary btn-small fj-room-entry" data-jump="create">${icon('users')} <span>Criar sala FlixJump</span></button>`);
    const update=()=>{
      if(active!==p)return;
      const v=p.video;
      $('[data-jump="toggle"]',p.wrap).innerHTML=icon(v.paused?'play':'pause');
      $('[data-jump="toggle"]',p.wrap).setAttribute('aria-label',p.jump&&!host(p)?'Sincronizar com a sala':v.paused?'Reproduzir':'Pausar');
      if(!p.live){$('.fj-time',p.wrap).textContent=`${timecode(v.currentTime)} / ${timecode(Number.isFinite(v.duration)?v.duration:0)}`;const seek=$('.fj-timeline',p.wrap);seek.max=Number.isFinite(v.duration)?v.duration:100;if(!p.scrubbing)seek.value=v.currentTime||0;}
      $('[data-jump="mute"]',p.wrap).innerHTML=icon(v.muted?'muted':'volume');
    };
    ['timeupdate','durationchange','play','pause','volumechange'].forEach(e=>p.video.addEventListener(e,update));
    ['play','pause','seeked','ended'].forEach(e=>p.video.addEventListener(e,()=>{if(active===p&&p.jump&&host(p)){if(['play','pause','ended'].includes(e))p.hostBuffering=false;queuePlayback(p);}}));
    p.video.addEventListener('ratechange',()=>{if(p.jump&&host(p)&&p.video.playbackRate!==1)p.video.playbackRate=1;});
    ['loadedmetadata','canplay','seeked'].forEach(event=>p.video.addEventListener(event,()=>{if(active===p&&p.jump&&!host(p))syncVideo(p,event==='loadedmetadata');}));
    p.video.addEventListener('waiting',()=>{if(p.jump&&host(p)&&!p.video.paused){p.hostBuffering=true;queuePlayback(p);}});
    p.video.addEventListener('playing',()=>{if(p.jump&&host(p)){p.hostBuffering=false;queuePlayback(p);}});
    p.video.addEventListener('volumechange',()=>{if(!p.ducking){p.userVolume=p.video.volume;p.userMuted=p.video.muted;$('.fj-volume-range',p.wrap).value=p.userVolume;}});
    p.recoverPlayback=()=>{if(!p.disposed&&p.jump){if(host(p))queuePlayback(p);else syncVideo(p,true);}};
    window.addEventListener('online',p.recoverPlayback);
    p.visibilityPlayback=()=>{if(!document.hidden)p.recoverPlayback();};document.addEventListener('visibilitychange',p.visibilityPlayback);
    p.wrap.addEventListener('pointermove',()=>{p.wrap.classList.remove('fj-idle');clearTimeout(p.hideControls);p.hideControls=setTimeout(()=>{if(!p.video.paused&&$('.fj-panel',p.wrap).hidden)p.wrap.classList.add('fj-idle');},3000);});
    p.wrap.addEventListener('keydown',e=>{if(e.target.matches('input,textarea,button'))return;if(e.code==='Space'){e.preventDefault();toggle(p);}if(e.key==='ArrowLeft'&&(!p.jump||host(p))&&!p.live)p.video.currentTime=Math.max(0,p.video.currentTime-10);if(e.key==='ArrowRight'&&(!p.jump||host(p))&&!p.live)p.video.currentTime=Math.min(p.video.duration||0,p.video.currentTime+10);});
    $('.fj-timeline',p.wrap).addEventListener('input',e=>{p.scrubbing=true;if(!p.jump||host(p))p.video.currentTime=Number(e.target.value);});
    $('.fj-timeline',p.wrap).addEventListener('change',()=>{p.scrubbing=false;});
    $('.fj-volume-range',p.wrap).addEventListener('input',e=>{p.userVolume=Number(e.target.value);p.userMuted=false;applyMovieVolume(p);});
    update();if(room)attach(p,room);
  }
  function setRoom(p,room,transit=0) {
    if(p.disposed||active!==p||p.jump&&(room.revision<p.jump.revision||(room.revision===p.jump.revision&&room.server_time<p.jump.server_time)))return;
    const becameHost=p.jump?.host_id!==state.user.id&&room.host_id===state.user.id;
    if(room!==p.jump||p.receivedAt===undefined){p.receivedAt=performance.now();p.snapshotTransit=Math.min(2,Math.max(0,transit));}
    p.jump=room;
    $('.fj-room-label',p.wrap).textContent=`${room.members.length}/8 na sala · ${host(p)?'Você é o anfitrião':'Reprodução guiada pelo anfitrião'}`;
    const badge=$('.fj-room-badge',p.wrap);badge.hidden=false;badge.textContent='FlixJump';
    $('.fj-sync',p.wrap).textContent=host(p)?'Você controla a sala':'Em sincronia';
    $('.fj-timeline',p.wrap).disabled=!host(p);
    const back=$('[data-jump="back"]',p.wrap);if(back)back.disabled=!host(p);
    const next=$('.player-footer [data-action="play"]');if(next)next.hidden=true;
    const entry=$('.fj-room-entry');if(entry){entry.dataset.jump='room';$('span',entry).textContent='Minha sala FlixJump';}
    paintRequests(p);
    $('.resume-banner')?.remove();
    const members=$('.fj-members',p.wrap);if(members)members.innerHTML=room.members.map(m=>`<div class="fj-member"><span class="fj-avatar">${esc(m.name[0].toUpperCase())}</span><span><strong>${esc(m.name)}</strong><small>@${esc(m.username)}${m.id===room.host_id?' · Anfitrião':''}</small></span>${icon(m.mic?'mic':'micOff')}</div>`).join('');
    const end=$('[data-jump="end"]',p.wrap);if(end)end.hidden=!host(p);
    const log=$('.fj-chat-log',p.wrap);
    const fresh=room.messages.filter(m=>m.id>p.lastMessage);
    if(fresh.length){p.lastMessage=room.messages.at(-1).id;if(log){log.innerHTML=room.messages.map(messageHTML).join('');log.scrollTop=log.scrollHeight;}for(const m of fresh.filter(m=>room.server_time-m.created_at<10).slice(-3))bubble(p,m);}
    if(!host(p)||becameHost)syncVideo(p,becameHost);
    scheduleVoice(p);
  }
  function messageHTML(m){return `<div class="fj-message ${m.user_id===state.user.id?'own':''}"><strong>${esc(m.name)}</strong><p>${esc(m.body)}</p><time>${new Date(m.created_at*1000).toLocaleTimeString('pt-BR',{hour:'2-digit',minute:'2-digit'})}</time></div>`;}
  function bubble(p,m){const root=$('.fj-bubbles',p.wrap);const node=document.createElement('button');node.type='button';node.className='fj-bubble';node.dataset.jump='chat';node.innerHTML=`<strong>${esc(m.name)}</strong><span>${esc(m.body)}</span>`;root.append(node);while(root.children.length>3)root.firstChild.remove();setTimeout(()=>node.remove(),8000);}
  function playbackGate(p,blocked){
    p.autoplayBlocked=blocked;
    const gate=$('.fj-playback-gate',p.wrap);if(gate)gate.hidden=!blocked;
    if(blocked)status(p,'Toque em Acompanhar sala para autorizar a reprodução neste dispositivo.');
  }
  function syncVideo(p,force=false,gesture=false) {
    if(p.disposed||!p.jump||p.video.readyState<1)return;
    const r=p.jump,v=p.video;
    const age=Math.max(0,r.server_time-r.updated_at)+(performance.now()-p.receivedAt)/1000+(p.snapshotTransit||0);
    let target=r.position+(r.paused?0:age);
    if(p.live){
      const playingDate=p.mediaSource?.hls?.playingDate;
      if(playingDate&&r.position>1000000000)target=v.currentTime+(r.position+(r.paused?0:age)-playingDate.getTime()/1000);
      else target=r.paused&&v.paused?v.currentTime:(p.mediaSource?.hls?.liveSyncPosition??(v.seekable.length?v.seekable.end(v.seekable.length-1)-3:v.currentTime));
      if(v.seekable.length)target=Math.max(v.seekable.start(0),Math.min(target,v.seekable.end(v.seekable.length-1)-.1));
    }else if(Number.isFinite(v.duration))target=Math.min(Math.max(0,target),Math.max(0,v.duration-.01));
    const delta=target-v.currentTime;
    const seek=force||p.initialSync||r.paused||v.paused||Math.abs(delta)>.6;
    if(Number.isFinite(target)&&Math.abs(delta)>(seek ? .04 : .6)&&!v.seeking&&seek){
      try{v.currentTime=target;}catch(_){return;}
    }
    // Small errors converge gently; large errors and every resume seek to the host.
    v.playbackRate=(!seek&&!p.live&&!r.paused&&Math.abs(delta)>.12)?(delta>0?1.03:.97):1;
    p.initialSync=false;
    if(r.paused){v.pause();return;}
    if((v.paused||gesture)&&(!p.playAttempt||gesture)&&(!p.autoplayBlocked||gesture)){
      const attempt=v.play();p.playAttempt=attempt;
      attempt.then(()=>{if(p.disposed||!p.jump)return;playbackGate(p,false);if(p.jump.paused)v.pause();})
        .catch(e=>{if(p.disposed||!p.jump)return;if(e.name==='NotAllowedError')playbackGate(p,true);else p.mediaSource?.handlePlayError(e);})
        .finally(()=>{if(p.playAttempt===attempt)p.playAttempt=null;});
    }
  }
  async function attach(p,room){
    p.initialSync=!host(p);setRoom(p,room);startVoicePriority(p);
    status(p,p.live?'TV ao vivo: a precisão da sincronia depende do sinal do canal.':'Sala conectada. A reprodução acompanha o anfitrião.');
    // Media synchronization must never wait for microphone negotiation or ICE servers.
    poll(p);
    p.hostTimer=setInterval(()=>{if(host(p)&&p.video.readyState>=1&&!p.video.seeking)queuePlayback(p);},1000);
    api('/jump/config').then(c=>{if(p.disposed||p.jump?.id!==room.id)return;p.iceServers=c.ice_servers;p.voiceReady=typeof RTCPeerConnection!=='undefined';scheduleVoice(p);}).catch(e=>status(p,e.message));
  }
  function scheduleVoice(p){
    if(!p.voiceReady||p.reconciling||p.disposed||!p.jump)return;
    p.reconciling=true;
    (async()=>{
      await reconcilePeers(p);
      while(p.signalQueue?.length&&!p.disposed&&p.jump){const s=p.signalQueue.shift();try{await receiveSignal(p,s);}catch(_){status(p,'Não foi possível conectar a voz de um participante.');}}
    })().catch(()=>status(p,'Reconectando a voz da sala…')).finally(()=>{p.reconciling=false;});
  }
  async function poll(p){
    if(p.disposed||!p.jump)return;
    const roomId=p.jump.id,started=performance.now();
    try{
      const r=await api(`/jump/rooms/${roomId}/poll`,{method:'POST',body:{cursor:p.cursor,mic:!!p.localStream},signal:AbortSignal.timeout(8000)});
      if(p.disposed||p.jump?.id!==roomId)return;
      p.requestRtt=performance.now()-started;setRoom(p,r.room,p.requestRtt/2000);
      p.signalQueue??=[];for(const s of r.signals){p.signalQueue.push(s);p.cursor=Math.max(p.cursor,s.id);}scheduleVoice(p);p.pollFailures=0;
    }catch(e){if(p.disposed||p.jump?.id!==roomId)return;if([401,402,403,404].includes(e.status)){status(p,e.message);leave(p);return;}p.pollFailures=(p.pollFailures||0)+1;status(p,'Reconectando à sala…');if(p.pollFailures>=3)stopMic(p);}
    if(!p.disposed&&p.jump?.id===roomId)p.pollTimer=setTimeout(()=>poll(p),p.pollFailures?1500:400);
  }
  function queuePlayback(p){
    if(p.disposed||!host(p))return;
    clearTimeout(p.publishTimer);p.publishTimer=setTimeout(()=>publish(p),25);
  }
  async function publish(p){
    if(p.disposed||!host(p)||p.video.readyState<1)return;
    if(p.publishing){p.publishAgain=true;return;}
    p.publishing=true;const rid=p.jump.id,started=performance.now();
    try{
      const paused=p.video.paused||p.video.ended||!!p.hostBuffering;
      const position=(p.live&&p.mediaSource?.hls?.playingDate?p.mediaSource.hls.playingDate.getTime()/1000:p.video.currentTime)+(paused?0:Math.min(2,(p.requestRtt||0)/2000));
      const r=await api(`/jump/rooms/${rid}/playback`,{method:'PATCH',body:{position,paused,revision:p.jump.revision},signal:AbortSignal.timeout(8000)});
      if(!p.disposed&&p.jump?.id===rid)setRoom(p,r.room,(performance.now()-started)/2000);
    }catch(e){
      if(p.disposed||p.jump?.id!==rid)return;
      if(e.status===409){
        try{const r=await post(`/jump/rooms/${rid}/poll`,{cursor:p.cursor});if(!p.disposed&&p.jump?.id===rid){setRoom(p,r.room);p.publishAgain=host(p);}}catch(_){}
      }else status(p,'Não foi possível enviar o comando. Reconectando à sala…');
    }finally{p.publishing=false;if(p.publishAgain&&!p.disposed){p.publishAgain=false;queuePlayback(p);}}
  }
  function toggle(p){
    unlockAudio(p);
    if(p.jump&&!host(p)){
      // Call play during this click, before awaiting network, for mobile autoplay policies.
      playbackGate(p,false);syncVideo(p,true,true);
      if(p.jump.paused){const attempt=p.video.play();attempt.then(()=>{if(!p.disposed&&p.jump?.paused)p.video.pause();}).catch(e=>{if(e.name==='NotAllowedError')playbackGate(p,true);});}
      return;
    }
    if(p.video.paused){p.hostBuffering=false;p.video.play().catch(e=>p.mediaSource?.handlePlayError(e));}else p.video.pause();
  }
  async function roomPanel(p){
    if(!p.jump){panel(p,'A melhor sessão é juntos.',`<div class="fj-panel-body"><p>Convide seus amigos para assistir a filmes, séries e TV em sincronia.</p><button class="btn btn-primary full-width" data-jump="create">${icon('users')} Criar uma sala</button><div class="divider-label">JÁ TEM UM CONVITE?</div><form data-jump-form="join"><label class="field">Link ou código da sala<input name="code" required maxlength="2048" autocomplete="off" placeholder="Cole o link ou código aqui"></label><button class="btn btn-secondary full-width" type="submit">Entrar na sala ${icon('arrow')}</button><p class="form-error" role="alert"></p></form><button class="fj-text" data-jump="friends">${icon('plus')} Meus amigos</button></div>`);return;}
    panel(p,'Sua sala de cinema',`<div class="fj-panel-body"><div class="fj-code"><span>Código da sala<strong>${esc(p.jump.id)}</strong></span>${button('copy','Copiar código da sala','link')}</div><label class="field fj-share-link">Link de convite<input readonly aria-label="Link de convite da sala" value="${esc(roomLink(p.jump.id))}"></label><div class="fj-room-actions"><button class="btn btn-secondary btn-small" data-jump="copy-link">${icon('link')} Copiar link</button><button class="fj-text" data-jump="share-room">Compartilhar</button></div><p><strong>${p.jump.permanent?'Sala permanente':'Sala temporária'}</strong> · ${p.jump.permanent?'O anfitrião permanece o mesmo quando sai.':'O próximo participante assume ao anfitrião sair. Vazia, a sala encerra.'}</p>${host(p)?`<button class="btn btn-secondary btn-small" data-jump="permanent">${p.jump.permanent?'Tornar temporária':'Tornar permanente'}</button>`:''}<p>Quem recebe o convite aguarda a aprovação do anfitrião. Até 8 pessoas, com plano ativo.</p><div class="fj-requests"></div><div class="fj-members"></div><div class="fj-room-actions"><button class="btn btn-secondary btn-small" data-jump="friends">${icon('plus')} Convidar amigos</button><button class="fj-text" data-jump="chat">${icon('chat')} Conversar</button></div><button class="fj-text" data-jump="leave">Sair da sala</button><button class="fj-text fj-danger" data-jump="end" ${host(p)?'':'hidden'}>Encerrar para todos</button></div>`);setRoom(p,p.jump);
  }
  function chat(p){if(!p.jump){roomPanel(p);return;}panel(p,'Conversa da sala',`<div class="fj-chat-log" role="log" aria-live="polite">${p.jump.messages.map(messageHTML).join('')}</div><form data-jump-form="chat" class="fj-chat-form"><label class="sr-only" for="fj-message">Mensagem</label><input id="fj-message" name="body" placeholder="Comente essa cena…" required maxlength="1000" autocomplete="off"><button type="submit" class="fj-icon" aria-label="Enviar mensagem">${icon('send')}</button><p class="form-error" role="alert"></p></form>`);const log=$('.fj-chat-log',p.wrap);log.scrollTop=log.scrollHeight;$('#fj-message',p.wrap).focus();}
  async function friends(p=active){
    const social=await api('/social');
    if(p&&p.disposed)return;
    const body=`<div class="fj-panel-body fj-friends"><form data-jump-form="profile" class="fj-profile"><label class="field">Seu nome de usuário<input name="username" value="${esc(state.user.username)}" pattern="[a-zA-Z0-9_]{3,24}" required maxlength="24"></label><button type="submit" class="fj-text">Salvar usuário</button><p class="form-error" role="alert"></p></form><form data-jump-form="friend"><label class="field">Adicionar pelo nome de usuário<input name="username" placeholder="@nome_do_amigo" required maxlength="25" autocomplete="off"></label><button class="btn btn-secondary full-width" type="submit">${icon('plus')} Enviar solicitação</button><p class="form-error" role="alert"></p></form>${!p?`<form data-jump-form="join" class="fj-join-form"><label class="field">Entrar em uma sala<input name="code" placeholder="Link ou código do FlixJump" required maxlength="2048"></label><button class="btn btn-secondary full-width" type="submit">Entrar na sala</button><p class="form-error" role="alert"></p></form>`:''}<h4>Convites para assistir</h4>${social.invites.length?social.invites.map(i=>`<button class="fj-invite" data-jump="join-invite" data-id="${esc(i.id)}"><strong>${esc(i.title)}</strong><small>${esc(i.host_name)} convidou você ${icon('arrow')}</small></button>`).join(''):'<p>Nenhum convite por enquanto.</p>'}<h4>Seus amigos</h4>${social.friends.length?social.friends.map(f=>`<div class="fj-friend"><span class="fj-avatar">${esc(f.name[0])}</span><span class="fj-friend-name"><strong>${esc(f.name)}</strong><small>@${esc(f.username)}${f.status==='pending'?' · Pendente':''}</small></span>${f.status==='pending'&&f.sender!==state.user.id?button('accept','Aceitar solicitação','check',`data-id="${esc(f.id)}"`):f.status==='accepted'&&p?.jump?button('invite','Convidar para a sala','plus',`data-id="${esc(f.id)}"`):''}${button('remove-friend',f.status==='accepted'?'Remover amigo':'Cancelar ou recusar solicitação','close',`data-id="${esc(f.id)}"`)}</div>`).join(''):'<p>Adicione alguém para combinar o próximo play.</p>'}<button class="fj-text" data-jump="friends">${icon('refresh')} Atualizar amigos e convites</button></div>`;
    if(p)panel(p,'Chame sua companhia',body);else showModal(`<div class="modal-body"><div class="eyebrow red">FLIXJUMP</div><h2>Juntos no próximo play.</h2>${body}</div>`,'fj-friends-modal');
  }
  const roomPath = rid => '/sala/'+encodeURIComponent(rid);
  const roomLink = rid => location.origin+roomPath(rid);
  let admission = null;
  function entryId(value){
    let rid=String(value||'').trim();
    if(!/^[A-Za-z0-9_-]{12}$/.test(rid)){
      let url;try{url=new URL(rid,location.origin);}catch(_){throw new Error('Cole o link ou o código de 12 caracteres da sala.');}
      const match=url.pathname.match(/^\/sala\/([A-Za-z0-9_-]{12})\/?$/);
      if(url.origin!==location.origin||!match)throw new Error('Use um link de sala desta plataforma ou o código de 12 caracteres.');
      rid=match[1];
    }
    return rid;
  }
  function rememberInvite(path){try{sessionStorage.setItem('flixjump-invite',path);}catch(_){}}
  function returnPath(){
    if(/^\/sala\/[A-Za-z0-9_-]{12}$/.test(location.pathname))return location.pathname;
    try{const saved=sessionStorage.getItem('flixjump-invite');return /^\/sala\/[A-Za-z0-9_-]{12}$/.test(saved||'')?saved:null;}catch(_){return null;}
  }
  function lobbyPage(rid){
    if(!/^[A-Za-z0-9_-]{12}$/.test(rid))return `${header()}<main class="page container" id="main">${empty('Convite inválido','Confira o link da sala com quem convidou você.','<a href="/catalogo" class="btn btn-primary">Explorar catálogo</a>')}</main>`;
    const signed=!!state.user,paid=state.user?.subscribed;
    return `${header()}<main class="page container fj-lobby" id="main"><section class="surface fj-lobby-card"><span class="fj-lobby-icon">${icon('users')}</span><div class="eyebrow red">FLIXJUMP · ASSISTIR JUNTOS</div><h1>Seu lugar na próxima sessão.</h1><p>O anfitrião recebe sua solicitação e decide quem entra na sala.</p><div id="fj-entry-state" role="status" aria-live="polite"><strong>${!signed?'Entre na sua conta para participar':!paid?'Você precisa de um plano ativo':'Enviando sua solicitação…'}</strong><p>${!signed?'Depois do login, voltaremos para este convite.':!paid?'Ative um plano e abra este convite novamente.':'Seu vídeo e o chat serão abertos após a aprovação.'}</p></div>${!signed?'<button class="btn btn-primary" data-action="login">Entrar e solicitar acesso</button>':!paid?'<a href="/planos" class="btn btn-primary">Escolher um plano</a>':'<button class="btn btn-secondary" data-jump="cancel-entry">Cancelar e voltar ao catálogo</button>'}<a class="fj-text" href="/catalogo">Explorar catálogo ${icon('arrow')}</a></section></main>${footer()}`;
  }
  function lobbyStatus(title,message){const el=$('#fj-entry-state');if(el)el.innerHTML=`<strong>${esc(title)}</strong><p>${esc(message)}</p>`;}
  function cancelWaiting(){
    const q=admission;admission=null;if(!q)return;
    clearTimeout(q.timer);api(`/jump/rooms/${q.rid}/join`,{method:'DELETE',body:{},keepalive:true}).catch(()=>{});
  }
  function routeChanged(path){
    const match=path.match(/^\/sala\/([A-Za-z0-9_-]{12})$/);
    if(admission?.rid!==match?.[1])cancelWaiting();
    if(!match)return;
    if(!state.user?.subscribed){rememberInvite(path);return;}
    try{sessionStorage.removeItem('flixjump-invite');}catch(_){}
    if(active?.jump?.id===match[1]||admission)return;
    const q={rid:match[1]};admission=q;awaitAdmission(q);
  }
  async function awaitAdmission(q){
    const current=()=>admission===q&&location.pathname===roomPath(q.rid);
    if(!current())return;
    try{
      const r=await post(`/jump/rooms/${q.rid}/join`);
      if(!current()){
        if(r.room)await post(`/jump/rooms/${q.rid}/leave`);
        else await api(`/jump/rooms/${q.rid}/join`,{method:'DELETE',body:{}});
        return;
      }
      if(r.room){
        admission=null;lobbyStatus('Entrada autorizada. Boa sessão!','A sala está aberta no player.');
        await play(r.room.content_id,r.room.episode_id,r.room);
        if(active?.jump?.id===q.rid)roomPanel(active);
        else {await post(`/jump/rooms/${q.rid}/leave`);lobbyStatus('Não foi possível abrir o vídeo','Atualize a página para tentar entrar novamente.');}
        return;
      }
      if(r.status==='rejected'){admission=null;lobbyStatus('Sua entrada não foi aceita','O anfitrião recusou sua solicitação para esta sala.');return;}
      lobbyStatus('Aguardando o anfitrião','Sua solicitação foi enviada. Você entrará automaticamente quando ele aceitar.');
    }catch(e){
      if(!current())return;
      if([401,402,403,404,409,429].includes(e.status)){admission=null;lobbyStatus('Não foi possível entrar',e.message);return;}
      lobbyStatus('Reconectando…','Estamos tentando consultar sua solicitação novamente.');
    }
    if(current())q.timer=setTimeout(()=>awaitAdmission(q),1500);
  }
  async function join(value){
    const rid=entryId(value);
    if(active?.jump?.id===rid){roomPanel(active);return;}
    await navigate(roomPath(rid));
  }
  function requestsHTML(requests){
    return requests.map(u=>`<div class="fj-request"><span class="fj-avatar">${esc(u.name[0])}</span><div><strong>${esc(u.name)}</strong><small>@${esc(u.username)}</small><div class="fj-request-actions"><button class="btn btn-primary btn-small" data-jump="approve-entry" data-id="${esc(u.id)}">Aceitar</button><button class="btn btn-secondary btn-small" data-jump="reject-entry" data-id="${esc(u.id)}">Recusar</button></div></div></div>`).join('');
  }
  function paintRequests(p){
    const requests=host(p)?p.jump.requests||[]:[];
    const notice=$('.fj-entry-notice',p.wrap);
    notice.hidden=!requests.length;
    const signature=JSON.stringify(requests);
    if(notice.dataset.requests!==signature){
      notice.dataset.requests=signature;
      notice.innerHTML=requests.length?`<span class="fj-kicker">${requests.length>1?requests.length+' SOLICITAÇÕES':'PEDIDO PARA ENTRAR'}</span>${requestsHTML(requests.slice(0,1))}${requests.length>1?'<button class="fj-text" data-jump="requests">Ver todas as solicitações</button>':''}`:'';
    }
    const list=$('.fj-requests',p.wrap);
    if(list&&list.dataset.requests!==signature){list.dataset.requests=signature;list.innerHTML=host(p)?`<h4>Solicitações para entrar</h4>${requests.length?requestsHTML(requests):'<p>Nenhuma solicitação pendente.</p>'}`:'';}
  }
  // Analyse voice only. Keeping the movie on its native media element avoids CORS
  // restrictions on third-party streams and preserves the viewer's volume setting.
  function voiceContext(p){
    if(p.voiceContext)return p.voiceContext;
    const Context=window.AudioContext||window.webkitAudioContext;
    if(!Context)return null;
    try{p.voiceContext=new Context();return p.voiceContext;}catch(_){return null;}
  }
  function monitorVoice(p,key,stream){
    unmonitorVoice(p,key);
    const ctx=voiceContext(p);if(!ctx)return;
    try{
      const source=ctx.createMediaStreamSource(stream),analyser=ctx.createAnalyser(),silent=ctx.createGain();
      analyser.fftSize=1024;silent.gain.value=0;source.connect(analyser);analyser.connect(silent);silent.connect(ctx.destination);
      p.voiceMonitors.set(key,{source,analyser,silent,stream,samples:new Float32Array(analyser.fftSize)});
    }catch(_){}
  }
  function unmonitorVoice(p,key){const m=p.voiceMonitors?.get(key);if(m){m.source.disconnect();m.analyser.disconnect();m.silent.disconnect();p.voiceMonitors.delete(key);}}
  function applyMovieVolume(p){
    const v=p.video,target=p.userVolume*(p.ducking ? .18 : 1);
    v.volume=target;
    // Some mobile browsers ignore volume assignments. Mute only while speech is
    // active there, then restore the user's mute preference.
    p.duckMute=p.ducking&&Math.abs(v.volume-target)>.05;
    v.muted=p.userMuted||!!p.duckMute;
  }
  function setDucking(p,on){
    if(p.ducking===on)return;
    p.ducking=on;applyMovieVolume(p);
    const label=$('.fj-voice-priority',p.wrap);if(label)label.hidden=!on;
  }
  function startVoicePriority(p){
    clearInterval(p.voiceMeter);p.voiceMonitors??=new Map();p.speechUntil=0;
    p.voiceMeter=setInterval(()=>{
      if(p.disposed||!p.jump)return;
      const now=performance.now();let speaking=false;
      if(p.voiceContext?.state==='running')for(const [id,m] of p.voiceMonitors){
        if(!m.stream.getAudioTracks().some(t=>t.readyState==='live'&&t.enabled&&!t.muted))continue;
        m.analyser.getFloatTimeDomainData(m.samples);let energy=0;for(const x of m.samples)energy+=x*x;
        const speech=Math.sqrt(energy/m.samples.length)>.018;
        speaking ||= speech;
        const peer=p.peers.get(id);if(peer)peer.audio.volume=1;
      }
      if(speaking)p.speechUntil=now+650;
      setDucking(p,now<p.speechUntil);
    },80);
  }
  function closeVoicePriority(p){
    clearInterval(p.voiceMeter);for(const key of p.voiceMonitors?.keys()||[])unmonitorVoice(p,key);
    p.voiceContext?.close().catch(()=>{});p.voiceContext=null;p.speechUntil=0;setDucking(p,false);
  }
  function clearVoice(p){stopCamera(p);stopMic(p);closeVoicePriority(p);p.peers.forEach(({pc,audio})=>{pc.close();audio.remove();});p.peers.clear();}
  function dispose(p,notify=true){
    p.disposed=true;window.removeEventListener('online',p.recoverPlayback);document.removeEventListener('visibilitychange',p.visibilityPlayback);clearTimeout(p.pollTimer);clearTimeout(p.publishTimer);clearTimeout(p.hideControls);clearInterval(p.hostTimer);clearVoice(p);
    if(notify&&p.jump)api(`/jump/rooms/${p.jump.id}/leave`,{method:'POST',body:{},keepalive:true}).catch(()=>{});
    if(active===p)active=null;
  }
  function leave(p,notify=true){
    const room=p.jump;clearTimeout(p.pollTimer);clearTimeout(p.publishTimer);clearInterval(p.hostTimer);p.jump=null;p.video.playbackRate=1;playbackGate(p,false);clearVoice(p);p.cursor=0;p.signalQueue=[];p.lastMessage=0;p.voiceReady=false;
    if(notify&&room)api(`/jump/rooms/${room.id}/leave`,{method:'POST',body:{},keepalive:true}).catch(()=>{});
    $('.fj-room-label',p.wrap).textContent='Seu cinema, sua companhia.';$('.fj-room-badge',p.wrap).hidden=true;$('.fj-sync',p.wrap).textContent='Assistindo por conta própria';$('.fj-timeline',p.wrap).disabled=false;
    const back=$('[data-jump="back"]',p.wrap);if(back)back.disabled=false;const next=$('.player-footer [data-action="play"]');if(next)next.hidden=false;$('.fj-panel',p.wrap).hidden=true;$('.fj-bubbles',p.wrap).replaceChildren();$('.fj-entry-notice',p.wrap).hidden=true;const entry=$('.fj-room-entry');if(entry){entry.dataset.jump='create';$('span',entry).textContent='Criar sala FlixJump';}
  }
  function paintCameras(p){if(!p.wrap)return;const rail=$('.fj-camera-rail',p.wrap);if(!rail)return;const visible=new Set();for(const u of (p.jump?.members||[])){const stream=u.id===state.user.id?p.cameraStream:p.peers.get(u.id)?.videoStream;if(!u.camera||!stream?.getVideoTracks().length||visible.size>=4)continue;visible.add(u.id);let tile=$(`[data-camera="${u.id}"]`,rail);if(!tile){tile=document.createElement('div');tile.dataset.camera=u.id;tile.innerHTML=`<video autoplay playsinline muted></video><span>${esc(u.id===state.user.id?'Você':u.name)}</span>`;rail.append(tile);}const video=$('video',tile);video.muted=true;if(video.srcObject!==stream){video.srcObject=stream;video.play().catch(()=>{});}}for(const tile of [...rail.children])if(!visible.has(tile.dataset.camera))tile.remove();rail.hidden=!visible.size;rail.style.setProperty('--cameras',visible.size||1);p.wrap.classList.toggle('has-cameras',!!visible.size);const b=$('[data-jump=camera]',p.wrap);if(b){b.classList.toggle('is-on',!!p.cameraStream);b.setAttribute('aria-pressed',String(!!p.cameraStream));b.setAttribute('aria-label',p.cameraStream?'Desligar câmera':'Ativar câmera');}}
  function stopCamera(p){p.cameraEpoch=(p.cameraEpoch||0)+1;p.cameraStream?.getTracks().forEach(t=>t.stop());p.cameraStream=null;p.peers.forEach(peer=>peer.videoSender?.replaceTrack(null).catch(()=>{}));const me=p.jump?.members.find(u=>u.id===state.user.id);if(me)me.camera=0;paintCameras(p);}
  async function camera(p){if(!p.jump){await roomPanel(p);return;}if(p.cameraPending)return;if(p.cameraStream){stopCamera(p);await api('/jump/rooms/'+p.jump.id+'/camera',{method:'PATCH',body:{enabled:false}});return;}if(!navigator.mediaDevices?.getUserMedia||!p.voiceReady)throw Error('A câmera precisa de HTTPS e permissão do navegador.');p.cameraPending=true;let stream;const epoch=p.cameraEpoch||0,rid=p.jump.id;try{stream=await navigator.mediaDevices.getUserMedia({video:{width:{ideal:640},height:{ideal:360}},audio:false});if(p.disposed||p.jump?.id!==rid||(p.cameraEpoch||0)!==epoch){stream.getTracks().forEach(t=>t.stop());return;}const r=await api('/jump/rooms/'+rid+'/camera',{method:'PATCH',body:{enabled:true}});if(p.disposed||p.jump?.id!==rid||(p.cameraEpoch||0)!==epoch){stream.getTracks().forEach(t=>t.stop());api('/jump/rooms/'+rid+'/camera',{method:'PATCH',body:{enabled:false}}).catch(()=>{});return;}p.jump=r.room;p.cameraStream=stream;const track=stream.getVideoTracks()[0];track.addEventListener('ended',()=>{if(p.cameraStream===stream){stopCamera(p);api('/jump/rooms/'+rid+'/camera',{method:'PATCH',body:{enabled:false}}).catch(()=>{});}});await Promise.all([...p.peers.values()].filter(peer=>peer.videoSender).map(peer=>peer.videoSender.replaceTrack(track)));paintCameras(p);scheduleVoice(p);}catch(e){stream?.getTracks().forEach(t=>t.stop());stopCamera(p);throw Error(e.name==='NotAllowedError'?'Permita o acesso à câmera no navegador.':e.message);}finally{p.cameraPending=false;}}
  function paintMic(p){const b=$('[data-jump="mic"]',p.wrap);if(!b)return;const enabled=!!p.localStream;b.innerHTML=icon(enabled?'mic':'micOff');b.classList.toggle('is-on',enabled);b.setAttribute('aria-pressed',String(enabled));b.setAttribute('aria-label',enabled?'Desativar microfone':'Ativar microfone');b.title=enabled?'Desativar microfone':'Ativar microfone';}
  function stopMic(p){unmonitorVoice(p,'self');p.micEpoch=(p.micEpoch||0)+1;p.localStream?.getTracks().forEach(t=>t.stop());p.localStream=null;p.peers.forEach(peer=>peer.sender?.replaceTrack(null).catch(()=>{}));paintMic(p);}
  async function microphone(p){
    if(!p.jump){roomPanel(p);return;}
    if(p.localStream){stopMic(p);status(p,'Microfone desligado. Você continua ouvindo a sala.');await api(`/jump/rooms/${p.jump.id}/mic`,{method:'PATCH',body:{enabled:false}});return;}
    if(!navigator.mediaDevices?.getUserMedia||!p.voiceReady)throw new Error('Para usar a voz, abra o site por HTTPS em um navegador com suporte a microfone.');
    unlockAudio(p);if(p.micPending)return;p.micPending=true;const epoch=p.micEpoch||0;
    try{
      const stream=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true,autoGainControl:true},video:false});
      if(p.disposed||!p.jump||(p.micEpoch||0)!==epoch){stream.getTracks().forEach(t=>t.stop());return;}
      p.localStream=stream;monitorVoice(p,'self',stream);stream.getAudioTracks()[0].addEventListener('ended',()=>{if(p.localStream){stopMic(p);if(p.jump)api(`/jump/rooms/${p.jump.id}/mic`,{method:'PATCH',body:{enabled:false}}).catch(()=>{});}});
      await Promise.all([...p.peers.values()].filter(peer=>peer.sender).map(peer=>peer.sender.replaceTrack(stream.getAudioTracks()[0])));
      await api(`/jump/rooms/${p.jump.id}/mic`,{method:'PATCH',body:{enabled:true}});paintMic(p);await unlockAudio(p);status(p,'Microfone ligado. Clique novamente para desligar.');
    }catch(e){stopMic(p);throw new Error(e.name==='NotAllowedError'?'Permita o microfone no navegador para falar.':e.name==='NotFoundError'?'Nenhum microfone foi encontrado neste dispositivo.':e.message);}finally{p.micPending=false;}
  }
  function unlockAudio(p){const ctx=voiceContext(p);ctx?.resume().catch(()=>{});for(const peer of p.peers.values()){if(peer.audio.srcObject)peer.audio.play().catch(()=>status(p,'Toque em reproduzir para habilitar o áudio da sala.'));}}
  async function sendSignal(p,id,payload){if(!p.disposed&&p.jump)await post(`/jump/rooms/${p.jump.id}/signals`,{recipient:id,payload});}
  async function peerFor(p,id){
    if(p.peers.has(id))return p.peers.get(id);
    if(p.disposed||!p.jump)throw new Error('Sala desconectada.');
    const pc=new RTCPeerConnection({iceServers:p.iceServers||[]});
    const audio=document.createElement('audio');audio.autoplay=true;audio.dataset.peer=id;$('.fj-audio',p.wrap).append(audio);
    // Only the offerer creates a transceiver. The answerer reuses the offered one.
    const sender=state.user.id<id?pc.addTransceiver('audio',{direction:'sendrecv'}).sender:null;
    const videoSender=state.user.id<id?pc.addTransceiver('video',{direction:'sendrecv'}).sender:null;
    const peer={pc,audio,sender,videoSender,candidates:[]};p.peers.set(id,peer);
    pc.onicecandidate=e=>{if(e.candidate)sendSignal(p,id,{type:'candidate',candidate:e.candidate.toJSON()}).catch(()=>{});};
    pc.ontrack=e=>{if(p.disposed||!p.jump||!p.peers.has(id))return;if(e.track.kind==='video'){peer.videoStream=new MediaStream([e.track]);paintCameras(p);return;}audio.srcObject=new MediaStream([e.track]);audio.volume=1;monitorVoice(p,id,audio.srcObject);audio.play().catch(()=>status(p,'Toque em reproduzir para ouvir seus amigos.'));};
    pc.onconnectionstatechange=()=>{if(pc.connectionState==='failed')status(p,'A voz não conectou a um participante. Tente reconectar o áudio.');};
    if(p.localStream&&sender)await sender.replaceTrack(p.localStream.getAudioTracks()[0]);
    if(p.cameraStream&&videoSender)await videoSender.replaceTrack(p.cameraStream.getVideoTracks()[0]);
    return peer;
  }
  async function reconcilePeers(p){
    paintCameras(p);
    const ids=p.jump.members.filter(m=>m.id!==state.user.id).map(m=>m.id);
    for(const [id,peer] of p.peers){if(!ids.includes(id)){unmonitorVoice(p,id);peer.pc.close();peer.audio.remove();p.peers.delete(id);}}
    for(const id of ids){if(p.disposed||!p.jump)return;const peer=await peerFor(p,id);const retry=peer.pc.connectionState==='failed'&&performance.now()-(peer.lastRetry||0)>10000;if(state.user.id<id&&(!peer.offered||retry)&&peer.pc.signalingState==='stable'){peer.offered=true;peer.lastRetry=performance.now();await peer.pc.setLocalDescription(await peer.pc.createOffer({iceRestart:retry}));await sendSignal(p,id,{type:'offer',sdp:peer.pc.localDescription.sdp});}}
  }
  async function receiveSignal(p,s){
    if(!p.jump?.members.some(m=>m.id===s.sender))return;
    const peer=await peerFor(p,s.sender),pc=peer.pc,d=s.payload;
    if(d.type==='candidate'){if(pc.remoteDescription)await pc.addIceCandidate(d.candidate);else peer.candidates.push(d.candidate);return;}
    if(d.type==='offer'){await pc.setRemoteDescription({type:'offer',sdp:d.sdp});const transceiver=pc.getTransceivers().find(t=>t.receiver.track.kind==='audio');transceiver.direction='sendrecv';peer.sender=transceiver.sender;if(p.localStream)await peer.sender.replaceTrack(p.localStream.getAudioTracks()[0]);const vt=pc.getTransceivers().find(t=>t.receiver.track.kind==='video');if(vt){vt.direction='sendrecv';peer.videoSender=vt.sender;if(p.cameraStream)await peer.videoSender.replaceTrack(p.cameraStream.getVideoTracks()[0]);}await pc.setLocalDescription(await pc.createAnswer());await sendSignal(p,s.sender,{type:'answer',sdp:pc.localDescription.sdp});}
    else if(d.type==='answer'&&pc.signalingState==='have-local-offer')await pc.setRemoteDescription({type:'answer',sdp:d.sdp});
    if(pc.remoteDescription)for(const c of peer.candidates.splice(0))await pc.addIceCandidate(c);
  }
  document.addEventListener('click',async e=>{
    const b=e.target.closest('[data-jump]');if(!b||b.disabled)return;const action=b.dataset.jump,p=active;
    b.disabled=true;
    try{
      if(action==='friends'){if(!state.user)authModal('login');else await friends(p);}
      else if(action==='cancel-entry'){cancelWaiting();await navigate('/catalogo');}
      else if(action==='join-invite')await join(b.dataset.id);
      else if(action==='accept'||action==='remove-friend'){await api('/social/friends/'+encodeURIComponent(b.dataset.id),{method:action==='accept'?'PATCH':'DELETE',body:{}});await friends(p);}
      else if(p){switch(action){
        case 'room':await roomPanel(p);break;
        case 'requests':panel(p,'Quem quer assistir junto',`<div class="fj-panel-body"><div class="fj-requests"></div></div>`);paintRequests(p);break;
        case 'approve-entry':case 'reject-entry':{const r=await api(`/jump/rooms/${p.jump.id}/requests/${encodeURIComponent(b.dataset.id)}`,{method:'PATCH',body:{decision:action==='approve-entry'?'approve':'reject'}});setRoom(p,r.room);status(p,action==='approve-entry'?'Entrada autorizada. A pessoa já pode se juntar à sala.':'Solicitação recusada.');break;}
        case 'copy-link':try{await navigator.clipboard.writeText(roomLink(p.jump.id));status(p,'Link copiado. Quem abrir aguardará sua aprovação.');}catch(_){status(p,'Selecione e copie o link no campo de convite.');}break;
        case 'share-room':{const url=roomLink(p.jump.id);if(navigator.share){try{await navigator.share({title:'Assista comigo no FlixJump',text:'Abra o convite para solicitar entrada na minha sala.',url});}catch(e){if(e.name!=='AbortError')throw e;}}else{try{await navigator.clipboard.writeText(url);status(p,'Link copiado para compartilhar.');}catch(_){status(p,'Selecione e copie o link no campo de convite.');}}break;}

        case 'permanent':{const r=await api('/jump/rooms/'+p.jump.id+'/settings',{method:'PATCH',body:{permanent:!p.jump.permanent}});setRoom(p,r.room);await roomPanel(p);break;}
        case 'create':{if(p.jump){await roomPanel(p);break;}const r=await post('/jump/rooms',{content_id:p.id,episode_id:p.episode,position:p.video.currentTime,paused:p.video.paused});if(p.disposed){await post(`/jump/rooms/${r.room.id}/leave`);break;}await attach(p,r.room);await roomPanel(p);break;}
        case 'chat':chat(p);break;
        case 'panel-close':$('.fj-panel',p.wrap).hidden=true;$('.fj-bubbles',p.wrap).hidden=false;$('[data-jump="chat"]',p.wrap).setAttribute('aria-expanded','false');break;
        case 'mic':await microphone(p);break;
        case 'camera':await camera(p);break;
        case 'enable-playback':case 'toggle':toggle(p);break;
        case 'back':if(!p.jump||host(p))p.video.currentTime=Math.max(0,p.video.currentTime-10);break;
        case 'mute':p.userMuted=!p.userMuted;applyMovieVolume(p);break;
        case 'fullscreen':if(document.fullscreenElement)await document.exitFullscreen();else if(p.wrap.requestFullscreen)await p.wrap.requestFullscreen();else p.wrap.classList.toggle('fj-expanded');break;
        case 'copy':try{await navigator.clipboard.writeText(p.jump.id);status(p,'Código copiado. Envie para seus amigos.');}catch(_){status(p,'Copie o código exibido no painel da sala.');}break;
        case 'invite':await post(`/jump/rooms/${p.jump.id}/invite`,{user_id:b.dataset.id});b.innerHTML=icon('check');b.dataset.sent='true';status(p,'Convite enviado. Seu amigo o verá em FlixJump.');break;
        case 'leave':leave(p);status(p,'Você saiu da sala e pode continuar assistindo.');break;
        case 'end':panel(p,'Encerrar a sessão?',`<div class="fj-panel-body"><p>Todos sairão da sala. Você poderá continuar assistindo.</p><button class="btn btn-primary" data-jump="confirm-end">Encerrar sala</button><button class="fj-text" data-jump="room">Voltar</button></div>`);break;
        case 'confirm-end':await api(`/jump/rooms/${p.jump.id}`,{method:'DELETE',body:{}});leave(p,false);status(p,'Sala encerrada. Você pode continuar assistindo.');break;
      }}
    }catch(err){if(p)status(p,err.message);else toast(err.message);}finally{if(b.isConnected&&!b.dataset.sent)b.disabled=false;}
  });
  document.addEventListener('submit',async e=>{
    const f=e.target;if(!f.dataset.jumpForm)return;e.preventDefault();e.stopImmediatePropagation();
    const b=$('[type="submit"]',f),err=$('.form-error',f);b.disabled=true;err.textContent='';const d=Object.fromEntries(new FormData(f)),p=active;
    try{switch(f.dataset.jumpForm){
      case 'join':await join(d.code);break;
      case 'chat':if(!p?.jump)throw new Error('Entre em uma sala primeiro.');await post(`/jump/rooms/${p.jump.id}/messages`,d);f.reset();$('#fj-message',p.wrap).focus();break;
      case 'friend':await post('/social/friends',d);await friends(p);break;
      case 'profile':{const r=await api('/social/profile',{method:'PATCH',body:d});state.user.username=r.username;b.textContent='Usuário salvo';break;}
    }}catch(error){if(err.isConnected)err.textContent=error.message;}finally{if(b.isConnected)b.disabled=false;}
  },true);
  window.addEventListener('pagehide',()=>{cancelWaiting();if(active)dispose(active);});
  return {mount,dispose,lobbyPage,routeChanged,returnPath};
})();
