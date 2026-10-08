'use strict';
// Cache only public, same-origin UI resources. Never API data, documents or streams.
const CACHE='flix-shell-worktv-scale-v4',OFFLINE='/static/offline.html';
const SHELL=[OFFLINE,'/static/offline.js','/static/assets/worktv-icon-192.png','/static/assets/worktv-icon-512.png'];
self.addEventListener('install',e=>{e.waitUntil(caches.open(CACHE).then(c=>c.addAll(SHELL)).then(()=>self.skipWaiting()));});
self.addEventListener('activate',e=>{e.waitUntil(Promise.all([caches.keys().then(keys=>Promise.all(keys.filter(k=>k.startsWith('flix-shell-')&&k!==CACHE).map(k=>caches.delete(k)))),self.clients.claim()]));});
self.addEventListener('fetch',e=>{
 const u=new URL(e.request.url);
 if(e.request.method!=='GET'||u.origin!==self.location.origin||u.pathname.startsWith('/api/')||e.request.headers.has('range'))return;
 if(e.request.mode==='navigate'){
   e.respondWith((async()=>{
     let timer;
     try{
       const response=await Promise.race([fetch(e.request),new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error('timeout')),10000);})]);
       if(response.status>=500)throw Error('unavailable');
       return response;
     }catch(_){return await caches.match(OFFLINE)||Response.error();}
     finally{clearTimeout(timer);}
   })());return;
 }
 // Versioned local scripts/styles only; media and third-party URLs bypass the worker.
 const cacheable=SHELL.includes(u.pathname)||(/^\/static\/[^/]+\.(js|css)$/.test(u.pathname)&&u.searchParams.has('v'));
 if(!cacheable)return;
 e.respondWith((async()=>{
   const cache=await caches.open(CACHE),cached=await cache.match(e.request);
   if(cached)return cached;
   const response=await fetch(e.request);
   if(response.ok&&response.type==='basic'&&!/no-store|private/i.test(response.headers.get('cache-control')||'')){
     await cache.put(e.request,response.clone());
     const keys=await cache.keys();
     const optional=keys.filter(k=>!SHELL.includes(new URL(k.url).pathname));
     await Promise.all(optional.slice(0,Math.max(0,optional.length-90)).map(k=>cache.delete(k)));
   }
   return response;
 })());
});

function localURL(value){try{const u=new URL(value,self.location.origin);if(u.origin===self.location.origin)return u.pathname+u.search+u.hash;}catch(_){}return '/comunidade';}
self.addEventListener('push',e=>{e.waitUntil((async()=>{
 let d={};try{d=e.data?.json()||{};}catch(_){}
 const expired=d.type==='call_incoming'&&d.expires&&d.expires<Date.now()/1000,incoming=d.type==='call_incoming'&&!expired;
 const data={url:localURL(d.url),id:d.id,type:d.type,callId:d.callId,callType:d.callType,callState:d.callState,expires:d.expires,conversationId:d.conversationId};
 const actions=(incoming?[{action:'answer',title:'Atender'},{action:'decline',title:'Recusar'}]:[{action:'open',title:d.type?.includes('message')?'Abrir conversa':'Abrir WorkTV'}]).slice(0,self.Notification?.maxActions??2);
 let avatar='/static/assets/worktv-icon-192.png';try{const url=new URL(d.icon,self.location.origin);if(url.protocol==='https:'||url.origin===self.location.origin)avatar=url.href;}catch(_){}
 const options={body:expired?'A chamada não foi atendida. Abra a conversa para retornar.':d.body||'Confira suas novidades.',icon:avatar,badge:'/static/assets/worktv-badge.png',tag:d.tag||'flix',data,actions,silent:!!d.silent,requireInteraction:incoming,renotify:incoming};
 if(!options.silent)options.vibrate=incoming?[250,100,250,100,250]:[100,60,100];
 await self.registration.showNotification(expired?'Chamada perdida':d.title||'WorkTV',options);
 if(self.navigator?.setAppBadge&&d.badge)await self.navigator.setAppBadge(d.badge);
 const tabs=await self.clients.matchAll({type:'window',includeUncontrolled:true});for(const tab of tabs)tab.postMessage({type:'flix-notification',notification:data});
})());});
async function openFlix(url){const target=localURL(url),tabs=await self.clients.matchAll({type:'window',includeUncontrolled:true});const tab=tabs.find(t=>new URL(t.url).origin===self.location.origin);if(tab){await tab.focus();tab.postMessage({type:'flix-open',url:target});}else await self.clients.openWindow(self.location.origin+target);}
self.addEventListener('notificationclick',e=>{e.notification.close();e.waitUntil((async()=>{
 const d=e.notification.data||{},callId=/^[A-Za-z0-9_-]{12,32}$/.test(d.callId||'')?d.callId:null;
 if(e.action==='decline'&&callId){try{const r=await fetch('/api/hub/calls/'+callId,{method:'PATCH',credentials:'include',headers:{'Content-Type':'application/json','X-Requested-With':'Flix'},body:JSON.stringify({action:'decline'})});if(r.ok||r.status===409||r.status===404)return;}catch(_){}await openFlix('/comunidade?call='+callId+'&call_action=decline');return;}
 if(e.action==='answer'&&callId){await openFlix('/comunidade?call='+callId+'&call_action=answer');return;}
 await openFlix(d.url);
})());});
self.addEventListener('message',e=>{if(e.data?.type==='flix-close-call'&&typeof e.data.callId==='string')e.waitUntil(self.registration.getNotifications({tag:'flix-call-'+e.data.callId}).then(ns=>ns.forEach(n=>n.close())));});
