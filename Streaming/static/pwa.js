(() => {
  'use strict';
  let registrationPromise, installPrompt;
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
    register();
    const banner=document.createElement('div');banner.className='wt-connection';banner.setAttribute('role','status');banner.textContent='Sem conexão. Reconecte para carregar conteúdos e continuar assistindo.';document.body.append(banner);
    const update=()=>{banner.hidden=navigator.onLine;};update();addEventListener('offline',update);addEventListener('online',update);
  });
})();
