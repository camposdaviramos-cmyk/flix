import * as THREE from './vendor/three.module.js';
import { GLTFLoader } from './vendor/GLTFLoader.js';
import { OrbitControls } from './vendor/OrbitControls.js';
import { RoomEnvironment } from './vendor/RoomEnvironment.js';

const viewport=document.querySelector('#viewport');
const status=document.querySelector('#status');
const loading=document.querySelector('#loading');
let renderer,scene,camera,controls,model,mixer,helper,action,clips;
let paused=matchMedia('(prefers-reduced-motion: reduce)').matches;
let visible=!document.hidden, frame=0, previous=0;
let activeAnimation='Float';
const poses=[];

function failure(error){
  console.error('Falha no visualizador:',error);
  document.querySelector('.spinner').hidden=true;
  document.querySelector('#load-message').textContent='Não foi possível abrir o 3D. Atualize a página ou tente um navegador com WebGL.';
  status.textContent='Visualização indisponível';
  loading.hidden=false;
  viewport.dataset.ready='error';
}

function setView(name){
  controls.target.set(0,1.02,0);
  const mobile=viewport.clientWidth<600;
  const distance=mobile?5.3:4.8;
  camera.position.set(name==='side'?distance:0,1.45,name==='side'?0:name==='back'?-distance:distance);
  controls.update();
  document.querySelectorAll('[data-view]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.view===name)));
}
function restorePose(){
  for(const {bone,position,quaternion,scale} of poses){bone.position.copy(position);bone.quaternion.copy(quaternion);bone.scale.copy(scale);}
}
function play(name){
  mixer.stopAllAction();restorePose();
  activeAnimation=name;
  action=null;
  if(name!=='pose'){
    const clip=THREE.AnimationClip.findByName(clips,name);
    action=mixer.clipAction(clip);action.reset().play();action.paused=paused;
  }
  document.querySelectorAll('[data-animation]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.animation===name)));
  status.textContent=name==='pose'?'Pose T · pronto para animar':({Float:'Flutuando',Wave:'Acenando',WalkInPlace:'Caminhando'})[name];
  viewport.dataset.animation=name;
  document.querySelector('#pause').disabled=name==='pose';
  document.querySelector('#speed').disabled=name==='pose';
  model.updateMatrixWorld(true);
}
function tick(now){
  frame=0;if(!visible)return;
  const delta=previous?Math.min((now-previous)/1000,.05):0;previous=now;
  if(mixer&&!paused)mixer.update(delta);
  controls.update();renderer.render(scene,camera);
  frame=requestAnimationFrame(tick);
}
function resize(){
  const w=viewport.clientWidth,h=viewport.clientHeight;
  renderer.setSize(w,h);camera.aspect=w/h;camera.updateProjectionMatrix();
}

async function init(){
  renderer=new THREE.WebGLRenderer({antialias:true,alpha:true});
  renderer.setPixelRatio(Math.min(devicePixelRatio,1.75));
  renderer.outputColorSpace=THREE.SRGBColorSpace;
  renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.15;
  viewport.appendChild(renderer.domElement);
  scene=new THREE.Scene();camera=new THREE.PerspectiveCamera(38,1,.05,50);
  controls=new OrbitControls(camera,renderer.domElement);
  controls.enableDamping=true;controls.enablePan=false;controls.minDistance=2.9;controls.maxDistance=7;
  controls.minPolarAngle=.25;controls.maxPolarAngle=Math.PI*.85;
  const environment=new RoomEnvironment();const pmrem=new THREE.PMREMGenerator(renderer);
  const target=pmrem.fromScene(environment,.04);scene.environment=target.texture;
  environment.dispose();pmrem.dispose();
  scene.add(new THREE.HemisphereLight(0xe5f2ff,0x415371,2));
  const key=new THREE.DirectionalLight(0xffffff,3);key.position.set(3,5,5);scene.add(key);
  const rim=new THREE.DirectionalLight(0x4bafff,2);rim.position.set(-3,2,-3);scene.add(rim);
  const base=new THREE.Mesh(new THREE.CylinderGeometry(1.28,1.28,.035,96),new THREE.MeshStandardMaterial({color:0x13233b,metalness:.4,roughness:.55}));
  base.position.y=-.035;scene.add(base);
  const ring=new THREE.Mesh(new THREE.TorusGeometry(1.15,.004,8,96),new THREE.MeshBasicMaterial({color:0x3687bf}));
  ring.rotation.x=-Math.PI/2;ring.position.y=-.014;scene.add(ring);
  resize();setView('front');
  new ResizeObserver(resize).observe(viewport);
  frame=requestAnimationFrame(tick);
  const gltf=await new GLTFLoader().loadAsync('./astronauta.glb');
  model=gltf.scene;scene.add(model);clips=gltf.animations;
  model.traverse(object=>{if(object.isBone)poses.push({bone:object,position:object.position.clone(),quaternion:object.quaternion.clone(),scale:object.scale.clone()});});
  mixer=new THREE.AnimationMixer(model);
  helper=new THREE.SkeletonHelper(model);helper.visible=false;
  helper.material.depthTest=false;helper.material.transparent=true;helper.material.opacity=.95;helper.renderOrder=10;
  scene.add(helper);
  document.querySelectorAll('.panel button,.panel select').forEach(b=>b.disabled=false);
  document.querySelector('#pause').textContent=paused?'Continuar':'Pausar';
  document.querySelector('#pause').setAttribute('aria-pressed',String(paused));
  document.querySelectorAll('[data-animation]').forEach(button=>button.addEventListener('click',()=>play(button.dataset.animation)));
  document.querySelectorAll('[data-view]').forEach(button=>button.addEventListener('click',()=>setView(button.dataset.view)));
  document.querySelector('#reset').addEventListener('click',()=>setView('front'));
  document.querySelector('#pause').addEventListener('click',event=>{
    paused=!paused;if(action)action.paused=paused;
    event.currentTarget.textContent=paused?'Continuar':'Pausar';event.currentTarget.setAttribute('aria-pressed',String(paused));
  });
  document.querySelector('#speed').addEventListener('change',event=>mixer.timeScale=Number(event.target.value));
  document.querySelector('#skeleton').addEventListener('click',event=>{
    helper.visible=!helper.visible;event.currentTarget.setAttribute('aria-pressed',String(helper.visible));
    event.currentTarget.textContent=helper.visible?'Ocultar esqueleto':'Ver esqueleto';
  });
  renderer.domElement.addEventListener('webglcontextlost',event=>{event.preventDefault();cancelAnimationFrame(frame);failure(new Error('WebGL context lost'));});
  document.addEventListener('visibilitychange',()=>{
    visible=!document.hidden;previous=0;
    if(visible&&!frame)frame=requestAnimationFrame(tick);
    if(!visible){cancelAnimationFrame(frame);frame=0;}
  });
  loading.hidden=true;play(activeAnimation);
  viewport.dataset.ready='true';viewport.dataset.bones=String(poses.length);
}
init().catch(failure);
