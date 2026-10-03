/* Service Worker notification routing without changing production permissions. */
const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const handlers={},shown=[],opened=[],messages=[],requests=[];let focused=0,closed=0,tabs=[];
const context={URL,Date,JSON,Promise,console,fetch:async(url,options)=>{requests.push({url,options});return {ok:true,status:200};},self:{location:{origin:'https://flix.test'},Notification:{maxActions:2},addEventListener:(n,fn)=>handlers[n]=fn,registration:{showNotification:async(title,options)=>shown.push({title,options}),getNotifications:async()=>[{close:()=>closed++}]},clients:{matchAll:async()=>tabs,openWindow:async u=>opened.push(u)},navigator:{setAppBadge:async()=>{}}}};
vm.runInNewContext(fs.readFileSync('static/sw.js','utf8'),context);
async function event(type,args){let work;handlers[type]({...args,waitUntil:p=>work=p});await work;}
(async()=>{
 const cid='abcdefghijklmno',call={type:'call_incoming',callId:cid,callType:'video',title:'Luna',body:'📹 Chamada de vídeo recebida',url:'/comunidade?call='+cid,expires:Date.now()/1000+40,tag:'flix-call-'+cid};
 await event('push',{data:{json:()=>call}});assert.equal(shown.at(-1).title,'Luna');assert.equal(shown.at(-1).options.actions.length,2);assert.equal(shown.at(-1).options.data.callType,'video');
 await event('notificationclick',{action:'decline',notification:{data:shown.at(-1).options.data,close:()=>closed++}});assert.equal(requests[0].url,'/api/hub/calls/'+cid);assert.equal(JSON.parse(requests[0].options.body).action,'decline');assert.equal(opened.length,0);
 await event('push',{data:{json:()=>({...call,expires:1})}});assert.equal(shown.at(-1).title,'Chamada perdida');assert.equal(shown.at(-1).options.actions[0].action,'open');
 tabs=[{url:'https://flix.test/comunidade',focus:async()=>focused++,postMessage:m=>messages.push(m)}];
 await event('notificationclick',{action:'answer',notification:{data:{callId:cid,url:call.url},close:()=>closed++}});assert.equal(focused,1);assert.equal(messages.at(-1).url,'/comunidade?call='+cid+'&call_action=answer');
 await event('notificationclick',{action:'open',notification:{data:{url:'https://evil.example/steal'},close:()=>closed++}});assert.equal(messages.at(-1).url,'/comunidade');
 await event('push',{data:{json:()=>({type:'group_message',title:'Luna · Cinema',body:'Oi 😂',url:'/comunidade?tab=friends&group=abc',conversationId:'group:abc',silent:true})}});assert.equal(shown.at(-1).options.body,'Oi 😂');assert.equal(shown.at(-1).options.vibrate,undefined);assert.equal(shown.at(-1).options.data.conversationId,'group:abc');
 context.self.Notification.maxActions=0;await event('push',{data:{json:()=>call}});assert.equal(shown.at(-1).options.actions.length,0);
 await event('message',{data:{type:'flix-close-call',callId:cid}});assert.ok(closed>=4);
 console.log(JSON.stringify({contextual_messages:true,call_actions:true,expired_calls:true,existing_window_focus:true,safe_deep_links:true,unsupported_actions_fallback:true,ended_call_cleanup:true}));
})().catch(e=>{console.error(e);process.exitCode=1;});
