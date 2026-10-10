(() => {
  'use strict';
  let registrationPromise, installPrompt, versionChecked=0;
  async function checkVersion(){
    if(document.hidden||Date.now()-versionChecked<30000)return;
    versionChecked=Date.now();
    try{
      const response=await fetch('/api/client-version',{cache:'no-store'});if(!response.ok)return;
      const value=await response.json();if(value.modules&&typeof state!=='undefined'&&state.modules&&value.modules.community!==state.modules.community){location.reload();return;}if(!value.release||value.release===window.WorkTVBoot?.release||document.querySelector('.wt-update'))return;
      const banner=document.createElement('aside');banner.className='wt-update';banner.setAttribute('role','status');
      const text=document.createElement('span');text.textContent='Uma nova versão da WorkTV está disponível.';
      const button=document.createElement('button');button.className='btn btn-primary btn-small';button.textContent='Atualizar WorkTV';
      button.onclick=()=>window.WorkTVBoot?.retry();banner.append(text,button);document.body.append(banner);
    }catch(_){}
  }
  setInterval(checkVersion,30000);
  document.addEventListener('visibilitychange',()=>{versionChecked=0;checkVersion();});
  navigator.serviceWorker?.addEventListener('controllerchange',()=>{versionChecked=0;checkVersion();});
  const standalone=()=>matchMedia('(display-mode: standalone)').matches||navigator.standalone;
  function register() {
    if(!('serviceWorker' in navigator)||!window.isSecureContext)return Promise.resolve(null);
    if(!registrationPromise)registrationPromise=navigator.serviceWorker.register('/sw.js',{scope:'/',updateViaCache:'none'}).then(reg=>{reg.update().catch(()=>{});return reg;}).catch(()=>{registrationPromise=null;return null;});
    return registrationPromise;
  }
  async function install() {
    if(installPrompt){const prompt=installPrompt;installPrompt=null;await prompt.prompt();await prompt.userChoice;return;}
    const tv=window.WorkTVPlatform?.tv;
    const copy=standalone()?'A WorkTV já está aberta como aplicativo.':tv?'Abra a WorkTV pelo navegador da sua TV e salve esta página nos favoritos. Se o navegador oferecer Instalar aplicativo, você também pode usar essa opção. A disponibilidade depende do aparelho.':'No Android ou computador, procure Instalar aplicativo no menu do navegador. No iPhone ou iPad, use Compartilhar → Adicionar à Tela de Início.';
    window.showModal?.('<div class="modal-body wt-install-help"><h2>WorkTV na sua tela</h2><p>'+copy+'</p><p>Filmes, canais e comunidade precisam de conexão com a internet.</p></div>','auth-modal');
  }
  window.WorkTVPWA={register,install};
  addEventListener('beforeinstallprompt',e=>{e.preventDefault();installPrompt=e;});
  addEventListener('appinstalled',()=>{installPrompt=null;});
  document.addEventListener('click',e=>{if(e.target.closest('[data-pwa-install]'))install().catch(()=>{});});
  document.addEventListener('DOMContentLoaded',()=>{
    register();checkVersion();
    const banner=document.createElement('div');banner.className='wt-connection';banner.setAttribute('role','status');banner.textContent='Sem conexão. Reconecte para carregar conteúdos e continuar assistindo.';document.body.append(banner);
    const update=()=>{banner.hidden=navigator.onLine;};update();addEventListener('offline',update);addEventListener('online',update);
  });
})();
