const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync('static/media-player.js','utf8');
function setup(nav,{native=true,supported=true,mms=false}={}){
  const listeners=new Map();const events={};let loads=0,recoveries=0,destroyed=0,created=0;
  class Hls{static isSupported(){return supported}static Events={ERROR:'error'};static ErrorTypes={MEDIA_ERROR:'media',NETWORK_ERROR:'network'};constructor(){created++}on(e,fn){events[e]=fn}attachMedia(v){this.video=v;if(mms)assert.equal(v.disableRemotePlayback,true,'MMS must disable remote playback before attach');}loadSource(url){this.url=url}recoverMediaError(){recoveries++}destroy(){destroyed++}}
  const video={canPlayType:()=>native?'maybe':'',setAttribute(){},removeAttribute(){},addEventListener(e,f){listeners.set(e,f)},removeEventListener(e){listeners.delete(e)},load(){loads++;this.error=null}};
  const context={window:{Hls,ManagedMediaSource:mms?class MMS{}:undefined},navigator:nav,Hls};vm.createContext(context);vm.runInContext(source,context);
  return {api:context.window.VyraMedia,video,events,stats:()=>({loads,recoveries,destroyed,created}),listeners};
}
const appleDevices=[{vendor:'Apple Computer, Inc.',userAgent:'Safari',platform:'MacIntel',maxTouchPoints:0},{vendor:'Apple Computer, Inc.',userAgent:'iPhone',platform:'iPhone',maxTouchPoints:5},{vendor:'',userAgent:'Desktop',platform:'MacIntel',maxTouchPoints:5}];
for(const nav of appleDevices){const s=setup(nav);const p=s.api.attach(s.video,'https://media.test/index.m3u8',{hls:true});assert.equal(p.mode,'native-hls');assert.equal(s.video.src,'https://media.test/index.m3u8');assert.equal(s.stats().created,0);assert.equal(s.stats().loads,1);assert.equal(s.video.playsInline,true);p.destroy();assert.equal(s.listeners.size,0);}
const s=setup({vendor:'Google Inc.',platform:'Linux',userAgent:'Chrome'});let messages=[];const p=s.api.attach(s.video,'https://media.test/index.m3u8',{hls:true,onError:m=>messages.push(m)});assert.equal(p.mode,'hlsjs');assert.equal(s.stats().created,1);
s.events.error(null,{fatal:false,response:{code:404}});assert.equal(messages.length,0);
s.events.error(null,{fatal:true,response:{code:404}});assert.match(messages.pop(),/404/);
s.events.error(null,{fatal:true,response:{code:403}});assert.match(messages.pop(),/recusou/);
s.events.error(null,{fatal:true,type:'media'});s.events.error(null,{fatal:true,type:'media'});assert.equal(s.stats().recoveries,1);assert.equal(messages.length,1);p.destroy();p.destroy();assert.equal(s.stats().destroyed,1);s.events.error(null,{fatal:true,response:{code:404}});assert.equal(messages.length,1);
const mp4=setup(appleDevices[0]);assert.equal(mp4.api.attach(mp4.video,'https://media.test/movie.mp4').mode,'native');assert.equal(mp4.stats().created,0);
const fallback=setup({vendor:'',platform:'',userAgent:''},{supported:false});assert.equal(fallback.api.attach(fallback.video,'https://media.test/a.m3u8',{hls:true}).mode,'native-hls');
console.log('PASS: native HLS on iPhone/iPad/Mac; hls.js on Chrome; native MP4; bounded recovery; errors and cleanup.');

// Native startup failure on iPhone must recover once through MMS, then retain
// the useful HTTP failure if play() rejects later with a generic DOMException.
const ios=setup(appleDevices[1],{mms:true}),notSupported={name:'NotSupportedError'};
let iosMessages=[];const iosPlayer=ios.api.attach(ios.video,'https://media.test/signed.m3u8?t=unchanged',{hls:true,onError:m=>iosMessages.push(m)});
ios.video.error={code:4};ios.listeners.get('error')();
assert.equal(iosPlayer.mode,'hlsjs');assert.equal(iosPlayer.hls.url,'https://media.test/signed.m3u8?t=unchanged');assert.equal(ios.stats().created,1);
const pendingCount=iosMessages.length;iosPlayer.handlePlayError(notSupported);assert.equal(iosMessages.length,pendingCount);
ios.events.error(null,{fatal:true,type:'network',response:{code:403}});iosPlayer.handlePlayError(notSupported);assert.match(iosMessages.at(-1),/recusou/);assert.equal(ios.stats().created,1);
iosPlayer.destroy();assert.equal(ios.video.disableRemotePlayback,undefined);assert.equal(ios.stats().destroyed,1);assert.equal(ios.listeners.size,0);
const early=setup(appleDevices[1],{mms:true});const ep=early.api.attach(early.video,'/a.m3u8',{hls:true});ep.handlePlayError(notSupported);assert.equal(ep.mode,'hlsjs');ep.destroy();
const old=setup(appleDevices[1],{supported:false});let oldMessage='';const op=old.api.attach(old.video,'/a.m3u8',{hls:true,onError:m=>oldMessage=m});op.handlePlayError(notSupported);assert.match(oldMessage,/Vídeo 4/);assert.equal(op.mode,'native-hls');
const blocked=setup(appleDevices[1]);let blockedMessage='';const bp=blocked.api.attach(blocked.video,'/a.m3u8',{hls:true,onError:m=>blockedMessage=m});bp.handlePlayError({name:'NotAllowedError'});assert.match(blockedMessage,/Toque/);assert.equal(bp.mode,'native-hls');bp.handlePlayError({name:'AbortError'});assert.equal(blocked.stats().created,0);
blocked.listeners.get('playing')();blocked.video.error={code:3};blocked.listeners.get('error')();assert.equal(bp.mode,'native-hls');assert.match(blockedMessage,/decodificar/);
console.log('PASS: iPhone native-to-MMS fallback; signed URL unchanged; late promise errors; no fallback loops; autoplay block; legacy iOS; cleanup.');

for (const userAgent of ['SMART-TV Tizen 7.0', 'Web0S Linux SmartTV', 'Android TV', 'Android AFTMM']) {
 const tv=setup({vendor:'',platform:'Linux',userAgent});
 const engine=tv.api.attach(tv.video,'https://media.test/tv.m3u8',{hls:true});
 assert.equal(engine.mode,'native-hls');
 tv.video.error={code:4};tv.listeners.get('error')();
 assert.equal(engine.mode,'hlsjs');assert.equal(tv.stats().created,1);engine.destroy();
 const noNative=setup({userAgent},{native:false});assert.equal(noNative.api.attach(noNative.video,'/tv.m3u8',{hls:true}).mode,'hlsjs');
}
console.log('PASS: TV native HLS preference, native startup fallback and capability fallback.');
