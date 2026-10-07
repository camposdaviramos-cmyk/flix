# WorkTV em TVs e PWA

Acesso: `https://flix.devspacey.com/?tv=1`. O modo fica salvo neste navegador. Para sair, use o rodapé **Sair do modo TV** ou `?tv=0`. A detecção usa identificadores conhecidos de TVs; tamanho de tela sozinho não ativa o modo.

## Uso

- Setas movem o foco entre elementos na direção escolhida, inclusive nas fileiras horizontais. OK abre o item. Tab e Shift+Tab também funcionam.
- Voltar fecha primeiro um painel, sai de tela cheia, fecha o player ou retorna à página anterior, conforme o contexto. No início, sem histórico interno, a saída fica a cargo do navegador/sistema.
- O retorno ao catálogo recupera o cartão e a posição de rolagem. Foco permanece dentro de janelas e painéis de conversa abertos.
- Campos mantêm edição de texto pelas setas horizontais; selects e áreas de texto preservam o comportamento nativo.
- Play/Pause, Play, Pause, Stop (pausa), avanço e retrocesso de dez segundos funcionam no player do catálogo. Também há botões visíveis. A navegação de reprodução respeita o anfitrião de WorkTV Juntos; transmissões ao vivo não recebem seek por estes controles.
- Códigos de retorno Samsung `10009` e LG `461` são reconhecidos, assim como eventos `BrowserBack`, `GoBack` e Escape. Dentro de um pacote Tizen, o registro opcional das teclas multimídia é feito apenas se a API estiver disponível.
- O modo TV usa tipografia maior, margem nas bordas, foco de alto contraste e layout verificado entre 960×540 e 3840×2160. Computador e celular mantêm seus layouts.
- Para reduzir uso de CPU/GPU, a coreografia de fundo fica estática no modo TV; Astro usa sua imagem e reage ao OK sem carregar Three.js/GLB. A experiência 3D e as animações normais continuam fora do modo TV.

## PWA e rede

O service worker é registrado também para visitantes, em contexto seguro e quando suportado. O manifesto inicia na página inicial e oferece atalhos para filmes, TV ao vivo, modo TV e comunidade. O botão **Instalar WorkTV** usa o convite nativo quando disponível; caso contrário, apresenta instruções adequadas à tela.

O cache contém a página offline, ícones e até 90 recursos públicos JS/CSS versionados. Não armazena APIs, páginas autenticadas, vídeos, requisições Range ou fontes externas. Cache privado/no-store é respeitado. A navegação usa rede, com fallback offline em falha, erro do servidor ou espera superior a dez segundos. A página offline mantém o endereço solicitado, recebe OK do controle e tenta retornar quando a conexão volta. Não existe download offline de filmes.

Atualizações do worker não recarregam automaticamente a página nem interrompem um vídeo em andamento. Os arquivos de interface usam URLs versionadas; mudanças futuras nesses arquivos precisam incrementar suas versões no HTML. Registro e notificações da comunidade compartilham o worker existente. Push e ações de chamadas foram preservados.

## Compatibilidade e limites de validação

PWA em navegador e aplicativo de loja para TV são distribuições diferentes. Esta entrega é a versão web/PWA; não inclui APK, IPK, WGT, assinatura nem publicação nas lojas. Algumas TVs permitem apenas salvar um favorito. Câmera, microfone, teclado virtual, DRM, codecs, HLS e eventos físicos do controle dependem do aparelho e do navegador. Recursos de criação por desenho/gestos continuam dependendo de um ponteiro/toque; embeds de terceiros mantêm seus próprios controles.

A interface existente usa JavaScript moderno; TVs com engines anteriores ao suporte a optional chaining e logical assignment podem não executar o site. O bootstrap ES5 apresenta uma orientação em vez de deixar o carregamento infinito quando o script principal não executa. Pequenas lacunas de runtime (`Array.at`, `String.at`, `Object.hasOwn`) têm fallback. Isso não transpila a aplicação para TVs antigas.

Os testes automatizados usam Chromium atual com teclado, resoluções e identificação de dispositivos simuladas. **Não equivalem a executar em hardware Samsung/LG/Android TV nem nos emuladores oficiais.** A reprodução real de MP4 local foi verificada. A seleção HLS nativa em TVs e a recuperação por hls.js têm testes unitários; cada fonte de transmissão precisa de validação no hardware alvo. Ainda não há certificação universal de modelos/anos.

Referências oficiais consultadas:

- [Samsung: controle remoto](https://developer.samsung.com/smarttv/develop/guides/user-interaction/remote-control.html).
- [LG: Magic Remote](https://webostv.developer.lge.com/develop/guides/magic-remote) e [botão Voltar](https://webostv.developer.lge.com/develop/guides/back-button).
- [LG: engines por versão](https://webostv.developer.lge.com/develop/specifications/web-api-and-web-engine) e [Samsung: especificações do engine](https://developer.samsung.com/smarttv/develop/specifications/web-engine-specifications.html). Os fabricantes documentam diferenças entre gerações; a matriz automatizada deste projeto não substitui esses runtimes.

## Verificação reproduzível

`/opt/flix/venv/bin/python Streaming/tests/tv_browser_check.py` inicia Waitress em 8023 com banco temporário e conta de teste exclusiva desse banco. Testa controle remoto, restauração de foco, login, painéis, fullscreen, reprodução MP4 real, política de seek, quatro resoluções, mobile/desktop, detecção e saída do modo TV, cache e recuperação offline de visitantes. Saída em `Streaming/test-results/tv/`.

No diretório `Streaming`, execute os scripts Node `tests/media_player_check.cjs` e `tests/service_worker_check.cjs` para seleção de engine, recuperação de mídia e notificações. Para validar aparelhos: abrir o link de TV, entrar, buscar um título, assistir/pausar/retomar, alternar canais, testar Voltar, suspender/retomar o app e reconectar a rede; registrar modelo, ano, versão do sistema, navegador e fonte de vídeo.
