import React,{useEffect,useRef,useState} from 'react';
import {useApp,Action} from './shared.jsx';
let decoderPromise;
function loadDecoder(){
 if(window.jsQR)return Promise.resolve(window.jsQR);
 if(!decoderPromise)decoderPromise=new Promise((resolve,reject)=>{
  const script=document.createElement('script');script.src='/static/vendor/jsqr-1.4.0.min.js';script.async=true;
  script.onload=()=>window.jsQR?resolve(window.jsQR):reject(new Error('Leitor indisponível.'));
  script.onerror=()=>{script.remove();decoderPromise=null;reject(new Error('Não foi possível carregar o leitor. Tente novamente.'));};document.head.append(script);
 });return decoderPromise;
}
export function activationPath(value){
 try{const url=new URL(value);if(url.origin===location.origin&&url.pathname==='/ativar'&&/^[A-Za-z0-9_-]{43}$/.test(url.hash.slice(1)))return url.pathname+url.hash;}catch(_){}
 return null;
}
export function Scanner(){
 const {s,actions}=useApp();const video=useRef(null),stream=useRef(null),timer=useRef(null),generation=useRef(0),alive=useRef(true);
 const [active,setActive]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState('');
 function stop(){generation.current++;clearTimeout(timer.current);stream.current?.getTracks().forEach(t=>t.stop());stream.current=null;if(video.current)video.current.srcObject=null;if(alive.current){setActive(false);setBusy(false);}}
 useEffect(()=>{alive.current=true;const hide=()=>{if(document.hidden)stop();};document.addEventListener('visibilitychange',hide);return()=>{alive.current=false;stop();document.removeEventListener('visibilitychange',hide);};},[]);
 async function accept(value){const path=activationPath(value);if(!path){setError('Este não é um QR Code de entrada da WorkTV. Aponte para o código da TV ou do computador.');return false;}stop();await actions.navigate(path);return true;}
 async function start(){
  stop();setBusy(true);setError('');const run=generation.current;
  try{
   if(!navigator.mediaDevices?.getUserMedia)throw new Error('Este navegador não disponibilizou a câmera. Use a opção de escolher uma imagem abaixo.');
   // Request permission only after an explicit tap, before awaiting the decoder.
   const camera=await navigator.mediaDevices.getUserMedia({audio:false,video:{facingMode:{ideal:'environment'},width:{ideal:640},height:{ideal:480}}});
   if(!alive.current||run!==generation.current){camera.getTracks().forEach(t=>t.stop());return;}
   stream.current=camera;video.current.srcObject=camera;await video.current.play();setActive(true);const decode=await loadDecoder();
   if(!alive.current||run!==generation.current)return;setBusy(false);
   const canvas=document.createElement('canvas'),context=canvas.getContext('2d',{willReadFrequently:true});
   async function scan(){
    if(!alive.current||run!==generation.current)return;
    if(video.current?.readyState>=2&&video.current.videoWidth>0){
     const scale=Math.min(1,640/video.current.videoWidth);canvas.width=Math.round(video.current.videoWidth*scale);canvas.height=Math.round(video.current.videoHeight*scale);
     context.drawImage(video.current,0,0,canvas.width,canvas.height);const frame=context.getImageData(0,0,canvas.width,canvas.height);const qr=decode(frame.data,frame.width,frame.height,{inversionAttempts:'dontInvert'});
     if(qr&&await accept(qr.data))return;
    }
    if(run===generation.current)timer.current=setTimeout(scan,250);
   }await scan();
  }catch(e){if(!alive.current||run!==generation.current)return;stop();setError(e.name==='NotAllowedError'?'A câmera não foi autorizada. Permita o acesso nas configurações do navegador ou escolha uma imagem do QR Code.':e.name==='NotFoundError'?'Não encontramos uma câmera. Escolha uma imagem do QR Code.':e.message);}
 }
 async function readImage(event){
  const file=event.target.files?.[0];event.target.value='';if(!file)return;stop();setError('');setBusy(true);const run=generation.current;let url;
  try{
   if(file.size>12*1024*1024)throw new Error('Escolha uma imagem de até 12 MB.');
   const decode=await loadDecoder();url=URL.createObjectURL(file);const image=new Image();await new Promise((resolve,reject)=>{image.onload=resolve;image.onerror=()=>reject(new Error('Não conseguimos abrir essa imagem.'));image.src=url;});
   if(!alive.current||run!==generation.current)return;
   const scale=Math.min(1,1600/Math.max(image.width,image.height)),canvas=document.createElement('canvas');canvas.width=Math.round(image.width*scale);canvas.height=Math.round(image.height*scale);const context=canvas.getContext('2d');context.drawImage(image,0,0,canvas.width,canvas.height);const frame=context.getImageData(0,0,canvas.width,canvas.height),qr=decode(frame.data,frame.width,frame.height);
   if(!qr)throw new Error('Não encontramos um QR Code legível nessa imagem.');await accept(qr.data);
  }catch(e){if(alive.current&&run===generation.current)setError(e.message);}finally{if(url)URL.revokeObjectURL(url);if(alive.current)setBusy(false);}
 }
 return <main id="main" className="page container access-page" data-react-page="scanner"><h1>Escanear QR Code</h1>{!s.user?<><p>Entre neste celular para autorizar sua TV ou computador.</p><Action action="login">Entrar na minha conta</Action></>:<section className="surface qr-scanner"><p>Na outra tela, abra Entrar. Depois, aponte a câmera para o QR Code. Você poderá conferir o aparelho antes de autorizar.</p><video ref={video} autoPlay muted playsInline className={active?'scanner-video active':'scanner-video'} aria-label="Câmera para ler QR Code"/><div className="access-actions">{!active?<button className="btn btn-primary" onClick={start} disabled={busy}>{busy?'Preparando câmera…':'Abrir câmera'}</button>:<button className="btn btn-secondary" onClick={stop}>Parar câmera</button>}{busy&&!active&&<button className="text-button" onClick={stop}>Cancelar</button>}<label className="btn btn-secondary scanner-image">Escolher imagem do QR Code<input type="file" accept="image/*" aria-label="Escolher imagem do QR Code" disabled={busy} onChange={readImage}/></label></div><p className="muted">A imagem é lida neste aparelho e não é enviada ao servidor.</p>{error&&<p className="form-error" role="alert">{error}</p>}</section>}</main>;
}
