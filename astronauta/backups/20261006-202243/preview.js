import * as THREE from './vendor/three.module.js';
import { GLTFLoader } from './vendor/GLTFLoader.js';
import { OrbitControls } from './vendor/OrbitControls.js';

const viewport=document.querySelector('#viewport');
const status=document.querySelector('#status');
const loading=document.querySelector('#loading');
let renderer,scene,camera,controls,model,mixer,helper,action,clips;
let paused=matchMedia('(prefers-reduced-motion: reduce)').matches;
let visible=!document.hidden, frame=0, previous=0;
let activeAnimation='Float';
let renderRequested=true;
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
  camera.position.set(name==='side'?distance:0,1.02,name==='side'?0:name==='back'?-distance:distance);
  camera.zoom=1;camera.updateProjectionMatrix();
  controls.update();
  renderRequested=true;
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
  renderRequested=true;
}
function tick(now){
  frame=0;if(!visible)return;
  if(previous&&now-previous<1000/30){frame=requestAnimationFrame(tick);return;}
  const delta=previous?Math.min((now-previous)/1000,.10):0;previous=now;
  if(mixer&&!paused)mixer.update(delta);
  const changed=controls.update();
  if(changed||renderRequested||(!paused&&activeAnimation!=='pose')){
    renderer.render(scene,camera);renderRequested=false;
  }
  frame=requestAnimationFrame(tick);
}
function resize(){
  const w=viewport.clientWidth,h=viewport.clientHeight;
  const halfHeight=1.5;const halfWidth=halfHeight*w/h;
  renderer.setSize(w,h);camera.left=-halfWidth;camera.right=halfWidth;camera.top=halfHeight;camera.bottom=-halfHeight;camera.updateProjectionMatrix();
  renderRequested=true;
}

async function init(){
  renderer=new THREE.WebGLRenderer({antialias:true,alpha:true});
  renderer.setPixelRatio(Math.min(devicePixelRatio,1.75));
  renderer.outputColorSpace=THREE.SRGBColorSpace;
  renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1;
  viewport.appendChild(renderer.domElement);
  scene=new THREE.Scene();camera=new THREE.OrthographicCamera(-1.5,1.5,1.5,-1.5,.05,50);
  controls=new OrbitControls(camera,renderer.domElement);
  controls.enableDamping=true;controls.enablePan=false;controls.minDistance=2.9;controls.maxDistance=7;
  controls.minZoom=.7;controls.maxZoom=2.2;
  controls.minPolarAngle=.25;controls.maxPolarAngle=Math.PI*.85;
  // Three large studio softboxes produce the broad visor reflections in the reference.
  const studio=new THREE.Scene();studio.background=new THREE.Color(0x010101);
  for(const [position,width,height,intensity] of [[[-3,2.4,4],2,3,18],[[3,2.4,4],2,3,18],[[0,5,2.2],3.4,1.2,25]]){
    const card=new THREE.Mesh(new THREE.PlaneGeometry(width,height),new THREE.MeshBasicMaterial({color:new THREE.Color(intensity,intensity,intensity),side:THREE.DoubleSide,toneMapped:false}));
    card.position.fromArray(position);card.lookAt(0,1.78,0);studio.add(card);
  }
  const pmrem=new THREE.PMREMGenerator(renderer);const environment=pmrem.fromScene(studio,.005);
  scene.environment=environment.texture;scene.environmentIntensity=.50;
  studio.traverse(o=>{if(o.isMesh){o.geometry.dispose();o.material.dispose();}});pmrem.dispose();
  scene.add(new THREE.HemisphereLight(0xffffff,0x9ca5b4,.7));
  const key=new THREE.DirectionalLight(0xffffff,2);key.position.set(-3,5,4);scene.add(key);
  const rim=new THREE.DirectionalLight(0xc9ddff,.8);rim.position.set(3,2,-3);scene.add(rim);
  const shadowCanvas=document.createElement('canvas');shadowCanvas.width=shadowCanvas.height=128;
  const shadowContext=shadowCanvas.getContext('2d');const gradient=shadowContext.createRadialGradient(64,64,5,64,64,64);
  gradient.addColorStop(0,'rgba(25,35,48,.25)');gradient.addColorStop(.45,'rgba(25,35,48,.13)');gradient.addColorStop(1,'rgba(25,35,48,0)');
  shadowContext.fillStyle=gradient;shadowContext.fillRect(0,0,128,128);
  const shadow=new THREE.Mesh(new THREE.PlaneGeometry(1.15,.72),new THREE.MeshBasicMaterial({map:new THREE.CanvasTexture(shadowCanvas),transparent:true,depthWrite:false}));
  shadow.rotation.x=-Math.PI/2;shadow.position.set(0,.012,.08);scene.add(shadow);
  resize();setView('front');
  new ResizeObserver(resize).observe(viewport);
  frame=requestAnimationFrame(tick);
  const loader=new GLTFLoader();
  // This site's CSP permits blob images, but not fetching blob URLs. Use the
  // image-element loader supported by the pinned Three.js parser for PNGs.
  loader.register(parser=>{
    parser.textureLoader=new THREE.TextureLoader(parser.options.manager);
    parser.textureLoader.setCrossOrigin(parser.options.crossOrigin);
    parser.textureLoader.setRequestHeader(parser.options.requestHeader);
    return {name:'ASTRONAUT_PNG_COMPAT'};
  });
  const gltf=await loader.loadAsync('./astronauta.glb?v=2');
  model=gltf.scene;scene.add(model);clips=gltf.animations;
  const images=new Set();
  model.traverse(object=>{
    if(object.isMesh)for(const key of ['map','normalMap','roughnessMap','metalnessMap']){
      const image=object.material[key]?.image;
      if(image?.width)images.add(image);
    }
  });
  if(images.size!==4)throw Error('As quatro texturas do astronauta não foram carregadas.');
  viewport.dataset.textures=String(images.size);
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
    renderRequested=true;
  });
  document.querySelector('#speed').addEventListener('change',event=>mixer.timeScale=Number(event.target.value));
  document.querySelector('#skeleton').addEventListener('click',event=>{
    helper.visible=!helper.visible;event.currentTarget.setAttribute('aria-pressed',String(helper.visible));
    event.currentTarget.textContent=helper.visible?'Ocultar esqueleto':'Ver esqueleto';
    renderRequested=true;
  });
  renderer.domElement.addEventListener('webglcontextlost',event=>{event.preventDefault();cancelAnimationFrame(frame);failure(new Error('WebGL context lost'));});
  document.addEventListener('visibilitychange',()=>{
    visible=!document.hidden;previous=0;
    if(visible&&!frame)frame=requestAnimationFrame(tick);
    if(!visible){cancelAnimationFrame(frame);frame=0;}
  });
  loading.hidden=true;play(activeAnimation);
  viewport.dataset.ready='true';viewport.dataset.bones=String(poses.length);
  viewport.dataset.version='2';
}
init().catch(failure);
