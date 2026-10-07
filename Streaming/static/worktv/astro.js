import * as THREE from './vendor/three.module.js';
import {GLTFLoader} from './vendor/GLTFLoader.js';

export async function createAstro(host) {
  const renderer=new THREE.WebGLRenderer({alpha:true,antialias:true});
  renderer.setPixelRatio(Math.min(devicePixelRatio,1.25));
  renderer.outputColorSpace=THREE.SRGBColorSpace;
  renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=.9;
  renderer.domElement.setAttribute('aria-hidden','true');host.append(renderer.domElement);
  const scene=new THREE.Scene(),camera=new THREE.OrthographicCamera(-1.4,1.4,1.4,-1.4,.05,30);
  camera.position.set(0,1.2,5);camera.lookAt(0,1.2,0);
  const studio=new THREE.Scene();studio.background=new THREE.Color(0x010101);
  for(const [pos,w,h,power] of [[[-3,2.4,4],2,3,18],[[3,2.4,4],2,3,18],[[0,5,2.2],3.4,1.2,25]]){
    const card=new THREE.Mesh(new THREE.PlaneGeometry(w,h),new THREE.MeshBasicMaterial({color:new THREE.Color(power,power,power),side:THREE.DoubleSide,toneMapped:false}));
    card.position.fromArray(pos);card.lookAt(0,1.78,0);studio.add(card);
  }
  const pmrem=new THREE.PMREMGenerator(renderer),environment=pmrem.fromScene(studio,.005);
  scene.environment=environment.texture;scene.environmentIntensity=.5;
  studio.traverse(o=>{if(o.isMesh){o.geometry.dispose();o.material.dispose();}});pmrem.dispose();
  scene.add(new THREE.HemisphereLight(0xeaf4ff,0x7891b5,.8));
  const key=new THREE.DirectionalLight(0xffffff,2);key.position.set(-3,5,4);scene.add(key);
  const rim=new THREE.DirectionalLight(0x7bc8ff,1.3);rim.position.set(3,2,-3);scene.add(rim);
  const loader=new GLTFLoader();
  loader.register(parser=>{
    parser.textureLoader=new THREE.TextureLoader(parser.options.manager);
    parser.textureLoader.setCrossOrigin(parser.options.crossOrigin);
    parser.textureLoader.setRequestHeader(parser.options.requestHeader);
    return {name:'WORKTV_PNG_COMPAT'};
  });
  let model;
  try{model=(await loader.loadAsync(new URL('./astro-v3.glb',import.meta.url).href)).scene;}
  catch(error){environment.dispose();renderer.dispose();renderer.domElement.remove();throw error;}
  scene.add(model);
  const bones={},images=new Set();
  model.traverse(o=>{
    if(o.isBone)bones[o.name.replace(/\./g,'')]=o;
    if(o.isMesh)for(const name of ['map','normalMap','roughnessMap','metalnessMap']){
      const image=o.material[name]?.image;if(image?.width)images.add(image);
    }
  });
  host.dataset.textures=String(images.size);host.dataset.bones=String(Object.keys(bones).length);
  let active=false,motion=true,lost=false,frame=0,last=0,elapsed=0;
  let action=null,actionTime=0,targetX=0,targetY=0,lookX=0,lookY=0,turnTarget=0,turn=0;
  let tickled=false,tickleRelease=0;
  const bellyCenter=new THREE.Vector3(),bellyEdge=new THREE.Vector3(),bellyTop=new THREE.Vector3();
  const belly={x:.5,y:.54,rx:.08,ry:.065};
  const clamp=THREE.MathUtils.clamp;
  const ease=t=>{t=clamp(t,0,1);return t*t*(3-2*t);};
  function pose(dt){
    const smooth=1-Math.exp(-dt*9);
    lookX+=(targetX-lookX)*smooth;lookY+=(targetY-lookY)*smooth;turn+=(turnTarget-turn)*smooth;
    if(action&&actionTime===null)actionTime=elapsed;
    if(action==='tickle'&&!tickled&&tickleRelease===null)tickleRelease=Math.max(elapsed,actionTime+1.4);
    const t=elapsed-(actionTime??elapsed),duration=action==='wave'?6:1.65;
    const laughing=action==='tickle';
    const envelope=action?ease(t/.3)*(laughing?(tickled?1:ease((tickleRelease+.65-elapsed)/.65)):ease((duration-t)/.4)):0;
    if(action&&(laughing?!tickled&&elapsed>tickleRelease+.65:t>=duration))action=null;
    const tickle=action==='tickle'?envelope:0;
    const wave=action==='wave'?envelope:0,nod=action==='nod'?envelope:0,bounce=action==='bounce'?envelope:0;
    bones.UpperArmL.rotation.x=-tickle*.7;
    bones.UpperArmR.rotation.x=-tickle*.7;
    bones.UpperArmL.rotation.z=-1.18+wave*1.14+bounce*.25+tickle*(.26+Math.sin(t*18)*.04);
    bones.UpperArmR.rotation.z=1.18-bounce*.25-tickle*(.26+Math.cos(t*18)*.04);
    bones.ForearmL.rotation.z=.12+wave*(1.25+Math.sin(t*10)*.24)-tickle*1.4;
    bones.ForearmR.rotation.z=-.12+tickle*1.4;bones.HandL.rotation.z=wave*Math.sin(t*13)*.2;
    bones.Head.rotation.set(lookY*.22+nod*Math.sin(t*9)*.16-tickle*.13,lookX*.4+tickle*Math.sin(t*16)*.09,-wave*.07+tickle*Math.sin(t*17)*.055);
    bones.Chest.rotation.set(tickle*.065,lookX*.055+tickle*Math.sin(t*15)*.04,tickle*Math.sin(t*18)*.035);
    bones.ClavicleL.rotation.z=tickle*Math.sin(t*18)*.055;
    bones.ClavicleR.rotation.z=-tickle*Math.cos(t*18)*.055;
    bones.ThighL.rotation.x=bounce*.15;bones.ThighR.rotation.x=-bounce*.1;
    model.position.y=(motion?Math.sin(elapsed*1.7)*.035:0)+bounce*Math.sin(t/duration*Math.PI)*.14+tickle*Math.abs(Math.sin(t*11))*.025;
    model.rotation.set(0,.12+turn+lookX*.12,(motion?Math.sin(elapsed*.8)*.015:0)+bounce*Math.sin(t*7)*.04+tickle*Math.sin(t*18)*.022);
    host.dataset.reaction=action||'idle';
  }
  function draw(dt=0){
    pose(dt);renderer.render(scene,camera);
    // Project the belly from the skeleton so the hit area follows rotation and layout.
    bones.Spine.localToWorld(bellyCenter.set(0,-.025,.28)).project(camera);
    bones.Spine.localToWorld(bellyEdge.set(.21,-.025,.28)).project(camera);
    bones.Spine.localToWorld(bellyTop.set(0,.145,.28)).project(camera);
    belly.x=(bellyCenter.x+1)/2;belly.y=(1-bellyCenter.y)/2;
    belly.rx=Math.max(.02,Math.abs(bellyEdge.x-bellyCenter.x)/2);
    belly.ry=Math.max(.02,Math.abs(bellyTop.y-bellyCenter.y)/2);
  }
  function tick(now){
    frame=0;if(!active)return;
    if(last&&now-last<1000/24){frame=requestAnimationFrame(tick);return;}
    // Wall time keeps a slow device from stretching a greeting into minutes.
    const dt=last?(now-last)/1000:0;last=now;elapsed+=dt;draw(dt);
    if(motion)frame=requestAnimationFrame(tick);
  }
  function resize(){
    if(!host.clientWidth||!host.clientHeight)return;
    const height=1.32,width=height*host.clientWidth/host.clientHeight;
    camera.left=-width;camera.right=width;camera.top=height;camera.bottom=-height;camera.updateProjectionMatrix();
    renderer.setSize(host.clientWidth,host.clientHeight);draw();
  }
  function setActive(value){
    value=value&&!lost;if(active===value)return;active=value;last=0;host.dataset.running=String(active&&motion);
    if(!active){tickled=false;if(action==='tickle')action=null;cancelAnimationFrame(frame);frame=0;}
    else if(!frame)frame=requestAnimationFrame(tick);
  }
  function setMotion(value){
    if(motion===value)return;motion=value;host.dataset.running=String(active&&motion);
    if(!motion){tickled=false;action=null;lookX=lookY=targetX=targetY=turnTarget=turn=0;cancelAnimationFrame(frame);frame=0;draw();}
    else if(active&&!frame){last=0;frame=requestAnimationFrame(tick);}
  }
  function react(name){if(motion){tickled=false;action=name;actionTime=null;}}
  function isBelly(x,y){return !lost&&Math.abs(turn)<.9&&((x-belly.x)/belly.rx)**2+((y-belly.y)/belly.ry)**2<1;}
  function setTickled(value){
    if(!motion||tickled===value)return false;
    tickled=value;
    if(value){action='tickle';actionTime=null;}
    else if(action==='tickle')tickleRelease=null;
    return value;
  }
  function look(x,y){targetX=clamp(x,-1,1);targetY=clamp(y,-1,1);}
  function rotate(value){turnTarget=clamp(value,-1.2,1.2);}
  const observer=new ResizeObserver(resize);observer.observe(host);
  renderer.domElement.addEventListener('webglcontextlost',event=>{event.preventDefault();lost=true;setActive(false);host.dataset.ready='fallback';});
  resize();host.dataset.ready='true';
  return {setActive,setMotion,react,look,turn:rotate,resize,isBelly,setTickled};
}
