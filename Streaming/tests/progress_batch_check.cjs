const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(require('node:path').join(__dirname,'../static/app.js'),'utf8');
const body=source.slice(source.indexOf('function saveProgress('),source.indexOf('async function syncPending('));
let now=1000000;const requests=[],cache=new Map();
const player={video:{duration:300,currentTime:1},id:'test-title',episode:'',uid:'test-user',ready:true,live:false,lastSaved:0,lastClock:0};
const context={player,state:{progress:[]},Date:{now:()=>now},Math,Number,JSON,localStorage:{setItem:(k,v)=>cache.set(k,v),getItem:k=>cache.get(k),removeItem:k=>cache.delete(k)},pendingKey:(u,c,e)=>`${u}:${c}:${e}`,api:(url,options)=>{requests.push({url,options});return Promise.resolve();},$:()=>null};
vm.createContext(context);vm.runInContext(body,context);
(async()=>{
 for(let n=0;n<=24;n++){player.video.currentTime=n*2.5+1;context.saveProgress(false,true);await Promise.resolve();now+=2500;}
 assert.equal(requests.length,5,'25 timer ticks must produce only five routine requests');
 assert.equal(context.state.progress[0].position,61);
 player.video.currentTime=62;context.saveProgress();await Promise.resolve();assert.equal(requests.length,6,'Pause/seek save immediately');
 now+=1;context.saveProgress(true);await Promise.resolve();assert.equal(requests.length,7);assert.equal(requests.at(-1).options.keepalive,true);
 for(let n=1;n<requests.length;n++)assert.ok(requests[n].options.body.client_time>requests[n-1].options.body.client_time);
 assert.equal(cache.size,0,'Only an acknowledged matching checkpoint is removed');
 console.log('PASS: periodic writes batched; local checkpoints; immediate pause/exit; monotonic timestamps and acknowledgements.');
})().catch(e=>{console.error(e);process.exitCode=1;});
