(() => {
  'use strict';
  let root,scene,actor,loading,visible=false,observer,gesture,count=0,bubbleTimer,greeted=false,failed=false;
  const reduced=matchMedia('(prefers-reduced-motion: reduce)');
  const paused=()=>reduced.matches||(!window.WorkTVPlatform?.tv&&document.documentElement.classList.contains('vx-paused'));
  function bellyAt(event){
    if(!actor)return false;
    const box=scene.getBoundingClientRect();
    return actor.isBelly((event.clientX-box.left)/box.width,(event.clientY-box.top)/box.height);
  }
  function tickle(){
    if(!actor||paused())return;
    actor.setTickled(true);actor.setTickled(false);say('Hahaha! Faz cócegas! 😆');
  }
  function say(text){
    const bubble=root.querySelector('.wt-astro-bubble');bubble.textContent=text;bubble.hidden=false;
    clearTimeout(bubbleTimer);bubbleTimer=setTimeout(()=>{bubble.hidden=true;},2600);
  }
  function respond(){
    if(!root?.isConnected)return;
    visible=true;sync();
    const reaction=['wave','nod','bounce'][count++%3];
    if(!actor&&!failed)load(true);
    if(actor&&!paused())actor.react(reaction);
    say(['Oi! 👋','Estou de olho em você. 👀','Gravidade? Que gravidade? ✨'][(count-1)%3]);
    if(!actor&&!paused()){
      scene.getAnimations().forEach(animation=>animation.cancel());
      scene.animate([{transform:'translateY(0) rotate(0)'},{transform:'translateY(-10px) rotate(-5deg)'},{transform:'translateY(0) rotate(0)'}],{duration:650,easing:'ease-in-out'});
    }
  }
  function sync(){
    if(!actor)return;
    actor.setMotion(!paused());
    actor.setActive(visible&&root.isConnected&&!document.hidden&&!document.querySelector('dialog[open]'));
  }
  async function load(explicit=false){
    if(window.WorkTVPlatform?.tv){scene.dataset.ready='fallback';return;}
    if(actor||loading||failed||navigator.connection?.saveData&&!explicit)return;
    loading=import('/static/worktv/astro.js?v=20261007c').then(module=>module.createAstro(scene)).then(value=>{
      actor=value;sync();
      if(visible&&!paused()&&!greeted){greeted=true;actor.react('wave');}
    }).catch(()=>{failed=true;scene.dataset.ready='fallback';}).finally(()=>{loading=null;});
  }
  function init(){
    if(root)return;
    root=document.createElement('div');root.className='wt-astro';
    root.innerHTML='<p class="wt-astro-bubble" role="status" aria-live="polite" hidden></p><button class="wt-astro-touch" type="button" aria-label="Interagir com Astro" aria-describedby="wt-astro-hint"><span class="wt-scene" data-ready="poster"><img class="wt-poster" src="/static/worktv/astro-poster.png" alt="" aria-hidden="true"></span></button><p id="wt-astro-hint">Passe o cursor na barriga. Ele sente cócegas.</p>';
    scene=root.querySelector('.wt-scene');
    if(window.WorkTVPlatform?.tv)root.querySelector('#wt-astro-hint').textContent='Pressione OK para cumprimentar o Astro.';
    const touch=root.querySelector('button');
    touch.addEventListener('click',event=>{const dragged=gesture?.dragged;gesture=null;if(dragged)return;if(event.detail&&bellyAt(event)&&!paused())tickle();else respond();});
    touch.addEventListener('pointermove',event=>{
      if(event.pointerType==='touch'||event.buttons||paused())return;
      if(actor?.setTickled(bellyAt(event)))say('Hahaha! Faz cócegas! 😆');
    },{passive:true});
    touch.addEventListener('pointerleave',()=>actor?.setTickled(false));
    touch.addEventListener('pointerdown',event=>{gesture={x:event.clientX,y:event.clientY,id:event.pointerId,dragged:false};});
    touch.addEventListener('pointermove',event=>{
      if(!gesture||!event.buttons||gesture.id!==event.pointerId||paused())return;
      const dx=event.clientX-gesture.x,dy=event.clientY-gesture.y;
      if(Math.abs(dx)>10&&Math.abs(dx)>Math.abs(dy)){
        if(!gesture.dragged){gesture.dragged=true;touch.setPointerCapture(event.pointerId);}
        actor?.turn(dx*.008);
      }
    });
    touch.addEventListener('pointerup',()=>{if(gesture?.dragged)actor?.turn(0);});
    touch.addEventListener('pointercancel',()=>{gesture=null;actor?.turn(0);});
    touch.addEventListener('lostpointercapture',()=>actor?.turn(0));
    observer=new IntersectionObserver(entries=>{
      visible=entries[0]?.isIntersecting??false;if(visible)load();sync();
    },{threshold:.15});observer.observe(root);
    document.addEventListener('visibilitychange',sync);
    reduced.addEventListener('change',sync);
    new MutationObserver(sync).observe(document.documentElement,{attributes:true,attributeFilter:['class']});
    new MutationObserver(sync).observe(document.querySelector('#modal'),{attributes:true,attributeFilter:['open']});
    document.addEventListener('pointermove',event=>{
      if(!visible||paused()||event.pointerType==='touch'||gesture?.dragged)return;
      const r=scene.getBoundingClientRect();actor?.look((event.clientX-r.left-r.width/2)/(innerWidth*.4),(event.clientY-r.top-r.height*.35)/(innerHeight*.5));
    },{passive:true});
    document.documentElement.addEventListener('pointerleave',()=>actor?.look(0,0));
  }
  window.WorkTVGuide={
    beforeRoute(){
      visible=false;actor?.setTickled(false);actor?.setActive(false);root?.remove();gesture=null;clearTimeout(bubbleTimer);
      if(root)root.querySelector('.wt-astro-bubble').hidden=true;
    },
    mount({path}){
      if(path!=='/')return;
      init();const hero=document.querySelector('.hero');
      if(hero){hero.classList.add('wt-hero');hero.append(root);if(!hero.querySelector('.wt-space-effects')){const effects=document.createElement('div');effects.className='wt-space-effects';effects.setAttribute('aria-hidden','true');effects.innerHTML='<i class="wt-space-haze"></i><i class="wt-meteor"></i><i class="wt-meteor wt-meteor-two"></i>';hero.append(effects);}}
      else {
        const host=document.createElement('section');host.className='wt-astro-member container';host.setAttribute('aria-label','Astro');
        host.append(root);document.querySelector('.member-hero')?.after(host);
      }
      actor?.resize();observer.unobserve(root);observer.observe(root);sync();
    }
  };
})();
