# Comunidade Flix

Entrada: `/comunidade`. Funciona com uma conta ativa, sem exigir assinatura para conteúdo externo. O catálogo pago e as salas FlixJump do catálogo conservam as regras de assinatura existentes.

## O que está implementado

- Feed paginado com filmes, séries, notícias, conversas e música; busca de publicações e pessoas; filtro de contas seguidas.
- Publicações com links HTTPS, capa, edição, remoção, curtidas únicas por conta e comentários.
- Perfil com foto enviada pelo dispositivo (convertida para PNG 256 px no navegador), capa por URL ou envio do dispositivo, biografia, gêneros, cidade e site; nome de usuário único; seguidores; emblemas concedidos e revogados pelo administrador.
- Pedidos de amizade e mensagens privadas entre amizades aceitas. A remoção da amizade interrompe o acesso à conversa pela API.
- Ranking: 5 pontos por curtida recebida, 2 por espectador único de outra conta, 1 por seguidor. Visualizações são registradas pelo player depois de 10 segundos e deduplicadas por conta/publicação. Esses contadores não são métricas antifraude ou de faturamento.
- Salas persistentes com página e link próprios, aprovação opcional (ativada inicialmente), assentos, presença, chat com balões e painel sobre o player, remoção de participantes e encerramento.
- JumpFlix externo com YouTube, MP4, WebM e M3U8; música com YouTube e arquivos MP3/OGG/M4A/WAV; fila de reprodução controlada pelo anfitrião.
- Salas de voz, vídeo e lives com câmera ou compartilhamento de tela (quando suportado pelo navegador). Todas as salas têm 8 assentos em destaque, incluindo o anfitrião, e uma plateia sem limite fixo. Somente participantes promovidos podem transmitir voz; câmera/tela também exigem assento em salas de vídeo/live. Câmera e microfone começam desligados.
- Sincronização por estado autoritativo do anfitrião, revisões, relógio do servidor, compensação de latência e correção de posição. Ao bloquear reprodução automática, o navegador pede o toque em “Ativar áudio”.
- Detecção local de voz por Web Audio reduz a mídia a 18% do volume escolhido durante a fala e restaura após o silêncio; áudio das pessoas permanece em volume integral.
- Admin: publicações, destaques, salas, denúncias, comentários e chat público, emblemas e concessões, histórico de moderação. Gestão de contas, planos, cupons e catálogo continua nas seções existentes. Mensagens privadas não são listadas no painel.

## Operação e limites reais

O banco é migrado automaticamente por `create_app()`. Os dados ficam em tabelas `community_*` no SQLite existente; fotos ficam em BLOB e são servidas como PNG com `nosniff`. Não há importação, download ou retransmissão dos links pelo servidor: o navegador acessa a fonte. Fontes precisam permitir incorporação/reprodução e, para HLS, CORS. A API oficial do YouTube é carregada apenas ao abrir mídia do YouTube; o CSP autoriza seus domínios específicos.

Cada sala tem oito assentos de voz/vídeo e plateia sem limite fixo de participantes na aplicação. Isso **não significa capacidade infinita de transmissão**: voz/vídeo usam WebRTC direto entre participantes que transmitem, sinalizado por polling HTTP. Cada transmissão cria conexões com ouvintes; CPU, upload dos emissores, banco e servidor limitam a escala. Não foi realizado teste de carga para grandes audiências. Para centenas/milhares de pessoas simultâneas em voz/vídeo/lives, é necessária uma arquitetura SFU e/ou distribuição HLS/CDN; isso não está incluído nesta implantação.

STUN padrão: Google. Para conectividade em redes móveis/corporativas/NAT restritivo, configurar `FLIXJUMP_ICE_SERVERS` com servidores TURN reais (JSON no formato `RTCIceServer`). Nenhum serviço TURN pago foi contratado ou credencial inventada. A configuração é compartilhada com o FlixJump existente. HTTPS é necessário para dispositivos de mídia fora de localhost. O acesso depende da permissão do navegador. Compartilhamento de tela depende do suporte do dispositivo.

Polling de salas: aproximadamente 650 ms, heartbeat de reprodução: 1 s. Presença expira após 45 s sem heartbeat. Salas não desaparecem por ficarem vazias; seu anfitrião ou admin pode encerrá-las. Histórico de chat por sala retém 200 mensagens; snapshot mostra 60. Fila retém até 100 itens. Pedidos de entrada só aparecem enquanto o solicitante aguarda. Admin/host podem remover participantes, e a recusa não pode ser anulada pela chamada de saída.

Mídia ao vivo HLS com Program Date Time usa horário absoluto. Sem essa informação, os clientes seguem a borda ao vivo local, com precisão dependente da origem. YouTube pode impor restrições regionais, anúncios, incorporação e reprodução automática. Não há promessa de precisão por quadro.

A contagem de visualizações é deduplicada, mas um cliente modificado pode chamar a API diretamente; rankings são sociais. A API limita ritmo de publicação, chat, sinalização e denúncias. Não há notificações push nem gravação de chamadas. Uploads de vídeos da comunidade são servidos pelo servidor da aplicação, com autenticação e suporte a HTTP Range.

## Rede social e jogos

A estrutura de `/comunidade` usa navegação lateral, feed contínuo no centro e descobertas na lateral direita. No celular, usa navegação inferior com área segura e atalhos para catálogo, notícias, jogos e ranking. Os campos têm fonte mínima de 16 px em telas pequenas/dispositivos de toque para evitar o zoom de foco do Safari, mantendo o gesto de ampliar a página.

- Stories de texto, foto ou vídeo expiram em 24 horas; contam visualizações únicas e aceitam reações, denúncia e remoção pelo autor/admin.
- Reels aceitam upload MP4/WebM ou YouTube. Vídeos enviados usam player vertical com controles; vídeos fora da tela são pausados. O YouTube abre no player incorporado existente.
- Seis reações, substituíveis por conta, em publicações, stories e mensagens de sala. Figurinhas locais e emojis funcionam em mensagens e comentários; não dependem de fornecedor externo.
- Conversas privadas entre amigos mostram presença, mensagens não lidas e indicador de digitação. “Chamar” cria uma sala de voz com aprovação e envia o link na conversa mediante clique do usuário. Presença online: heartbeat de 20 s, validade de 60 s. Chat aberto consulta novidades a cada 2 s; digitação expira em 5 s.
- Fotos são convertidas no navegador para PNG de até 1600 px; API aceita PNG até 4 MB/4096 px. Vídeos MP4/WebM e áudio MP3/M4A/WAV/OGG até 25 MB. Limites por conta: 250 MB, 300 arquivos ativos, 30 uploads/hora. “Gerenciar meus envios” no editor permite excluir arquivos. A exclusão remove o arquivo dos lugares onde é usado.
- Arquivos ficam em `data/social-media/` e são servidos somente a contas ativas em `/api/community/assets/<id>`, com `nosniff`, `no-store` e HTTP Range. Arquivos usados exclusivamente em stories expiram; são removidos fisicamente no próximo upload ou abertura da biblioteca do autor. Arquivos referenciados por publicações, perfis ou salas são preservados.
- O Nginx aceita 26 MB de corpo multipart somente na rota exata `/api/community/assets`; o limite das outras rotas permanece em 3 MB. A aplicação conserva seu limite padrão e amplia somente o POST de upload.

### Partidas nas salas

Todas as salas têm uma seção de jogos. O anfitrião escolhe **Cores** (cartas) ou **Traço** (desenho e adivinhação), aguarda a entrada dos jogadores e inicia. São jogos próprios inspirados nessas modalidades, sem integração com contas/servidores oficiais de UNO ou Gartic. Cada partida aceita de 2 a 8 jogadores; os demais membros acompanham como espectadores. Chat e voz continuam na sala.

O servidor valida entrada, vez, carta, cor, prazo, permissões da lousa e palpites em transações SQLite. A resposta de Cores só contém a mão do solicitante e contagens dos demais; a palavra do Traço só é enviada a quem desenha, até a revelação. A interface consulta o jogo a cada segundo. Revisões e identificação de partida rejeitam comandos antigos. Pedidos de atualização iniciados antes de uma jogada local são descartados pela interface.

Cores: comece com 7 cartas. Ao comprar uma carta válida, pode jogar essa carta ou passar; carta inválida passa a vez. +2/+4 fazem comprar e pular, sem empilhar; +4 é bloqueado quando a mão contém a cor atual. Inversão com dois jogadores pula o adversário. O botão UNO! prepara o anúncio com duas cartas na própria vez, ou anuncia imediatamente após ficar com uma. Outro jogador pode cobrar 2 cartas antes da próxima jogada. Penalidades são aplicadas mesmo na última carta. Prazo de 60 s: compra uma carta e passa, ou somente passa caso já tenha comprado. Traço: uma rodada de 75 s por jogador, com 5 s de revelação; pontuação de acerto depende do tempo restante e o desenhista também pontua. Timeouts avançam quando algum membro consulta ou atua na sala; não há processo de simulação rodando para salas abandonadas. Após 30 min, a partida expira sem pontos.

Resultados são registrados uma vez por partida/conta: 5 pontos de participação, 25 extras por vitória e até 50 do placar do Traço. Limite de 200 pontos de jogos por conta nas últimas 24 horas. Partidas canceladas não pontuam. Os pontos entram no ranking junto de curtidas, visualizações, seguidores e 2 pontos por reação recebida de outra conta. Os emblemas automáticos são **Primeira vitória** (uma vitória), **Mesa amiga** (cinco partidas concluídas) e **Mestre do traço** (três vitórias em Traço). Esses limites não equivalem a um sistema antifraude competitivo.

O perfil mostra pontos de jogos, vitórias, capa, avatar, presença e emblemas. O painel **Stories e jogos** permite inspecionar/remover stories e arquivos e encerrar partidas em andamento; não expõe mãos ou palavras secretas. Publicações e reels continuam na moderação de publicações. As ações ficam no histórico administrativo. Mensagens privadas permanecem fora do painel.

Testes adicionais: `tests/test_community_social.py`, `tests/social_browser_check.py` e `tests/community_ui_check.py`. O teste de navegador utiliza contas/banco descartáveis, dois contextos isolados, uploads reais, reprodução do vídeo de demonstração, entrada por convite, jogadas de cartas e desenho compartilhado. Capturas em `test-results/social-*.png`. A validação de zoom verifica CSS/viewport em emulação móvel Chromium; não substitui um teste em iPhone físico.

## Flix Studio e nova apresentação dos jogos

O editor de publicações tem blocos de texto, subtítulo, citação, lista, divisor, imagem, vídeo e áudio/música; formatação em negrito/itálico e links; capa, prévia e marcações de pessoas e títulos. O conteúdo é armazenado como documento estruturado e renderizado com texto escapado, sem aceitar HTML arbitrário. Limites: 32 blocos, 8 anexos, 20 mil caracteres e 10 pessoas/10 títulos. Marcar um título premium não inclui sua URL de reprodução nem altera a exigência de assinatura.

Rascunhos privados têm salvamento automático, revisão para conflitos entre abas e recuperação local por usuário. Até 20 por conta. A API verifica propriedade; publicar remove o rascunho correspondente. Referências preservam os anexos, inclusive quando usados apenas em blocos ou rascunhos. Uploads da comunidade continuam acessíveis a contas ativas que conheçam o link; o conteúdo textual do rascunho e a listagem dos rascunhos são privados.

A criação de salas oferece seleção visual de cinema, voz, vídeo, live, música e jogos, capa, aprovação de entrada e convite opcional pelo feed. Criar uma sala de jogos inicializa seu lobby na mesma transação. Lives são transmitidas diretamente no site: o formulário não solicita link nem arquivo de vídeo. Após **Criar live**, o anfitrião usa **Iniciar transmissão** para autorizar câmera e microfone juntos no navegador. **Parar transmissão** desliga os dois dispositivos sem encerrar a sala; câmera, microfone e compartilhamento de tela também têm controles individuais. Câmera/microfone não são ativados ao criar a sala ou entrar como espectador. Um convite em pop-up aparece a quem ainda não entrou na partida; pode ser recusado e volta a aparecer para uma nova partida. O pop-up fica acima do conteúdo da página, inclusive quando a pessoa está vendo os assentos.

**Cores / Lounge Cinema** e **Traço / Ateliê Noturno** usam cenários originais (origem em `ASSETS.md`). Cartas foram desenhadas em CSS, com animações de distribuição, compra, descarte, UNO, ações especiais e vitória. Movimentos são confirmados pelo servidor, que envia somente eventos públicos. O modo de movimentos reduzidos preserva a visibilidade de cartas, convites e mensagens.

Chat, emojis e figurinhas ficam em uma janela compacta dentro do jogo; mensagens novas aparecem em balões por 7 segundos. O microfone usa a mesma chamada WebRTC e as mesmas permissões de assento da sala. Balões de voz mostram o nome de quem está falando, detectado pelo nível do áudio, sem transcrição. A negociação aceita ofertas autenticadas de participantes com assento mesmo quando chegam antes do heartbeat que anuncia o microfone. A conexão inicial ganha uma janela curta de 2,5 segundos para esse anúncio, sem ignorar bloqueios ou retirada de assento. O anfitrião continua podendo silenciar e retirar pessoas dos assentos. Um convidado nunca tem seu microfone ligado ao aceitar o jogo.

O feed central mostra um ranking específico de jogos, inclusive no celular. A página Jogos permite filtrar Cores/Traço e mostra pontos, vitórias e a posição do usuário. Resultados e emblemas continuam usando o registro único por partida existente.

APIs adicionadas: `GET /api/community/publishing/search`, `GET /api/community/games/ranking`, `GET/POST /api/community/drafts`, `GET/PUT/DELETE /api/community/drafts/<id>`. As rotas existentes de publicações recebem `document`, `people`, `titles` e `draft_id`; salas recebem `cover`, `game_kind` e `publish_to_feed`. Ações de cartas: `uno`, `catch`, `pass`, além das anteriores. As migrações são aditivas e publicações antigas continuam legíveis.

Verificações específicas: `tests/test_community_studio.py` e `tests/studio_browser_check.py`. O teste de navegador usa banco descartável, duas sessões, CSP habilitada, áudio de teste transmitido por WebRTC, celular Chromium, uploads de áudio/vídeo, rascunhos, marcações, UNO, animação, convites entre partidas, chat/voz, moderação, desenho e ranking. O teste força anúncio de microfone atrasado e permite testar as duas ordens de negociação com `STUDIO_OFFERER=guest` (padrão) ou `STUDIO_OFFERER=host`. Capturas em `test-results/studio-*.png`. Emulação móvel não substitui validação em iPhone físico. A infraestrutura de voz continua WebRTC em malha, conforme os limites de implantação descritos acima.

## Verificação

```bash
/opt/flix/venv/bin/python -m unittest discover -s tests -p 'test_*.py' -q
/opt/flix/venv/bin/python tests/community_browser_check.py
```

Os testes usam bancos temporários e contas de teste. A verificação de navegador usa mídia MP4 local interceptada sob URL HTTPS de teste, dois contextos isolados, câmera sintética e áudio WebRTC. Screenshots em `test-results/community-*.png`. Não fazem validação de capacidade de audiência, TURN entre redes físicas nem da disponibilidade de vídeos específicos do YouTube.

Referências: [YouTube IFrame API](https://developers.google.com/youtube/iframe_api_reference), [WebRTC](https://www.w3.org/TR/webrtc/).

## Assentos e catálogos gratuitos

O anfitrião ocupa o assento 1 e pode promover até sete convidados, devolver participantes à plateia, silenciar e liberar microfones. “Silenciar” mantém o bloqueio até o anfitrião usar “Permitir microfone”; liberar ou promover nunca abre o dispositivo automaticamente. A interface encerra as trilhas locais revogadas e os receptores silenciam áudio sem permissão. As permissões são confirmadas pelo servidor a cada polling, inclusive se um cliente envia `mic=true` após ser silenciado. Assentos são reservados em transações serializadas e protegidos por índice único; convidados desconectados liberam o assento após 45 segundos. A plateia continua assistindo e conversando no chat.

`/comunidade?tab=catalog&kind=movie|series|channel|news` contém somente publicações da comunidade. Cada cartão mostra autor, seguir e avaliações de 1–5 estrelas (uma por conta/publicação, editável e removível, sem autoavaliação). O perfil mostra a média das avaliações das suas publicações. O botão “Assistir grátis” abre um player individual sem criar sala. As salas continuam disponíveis em “Assistir juntos”.

O cadastro `account_type=community` cria conta com `plan_id=NULL`, validade zero e sem checkout. Dados de plano/validade enviados nesse cadastro não concedem assinatura. O catálogo do administrador continua protegido por `auth(paid=True)` na reprodução e no FlixJump do catálogo. A comunidade exige apenas conta ativa.

Verificação adicional: `tests/community_stage_browser_check.py` cobre cadastro gratuito, bloqueio do catálogo premium, TV da comunidade, avaliações/seguir, os 8 assentos e interrupção real da trilha de microfone ao silenciar/rebaixar.

## Reprodução no Safari

`static/media-player.js` centraliza a escolha da reprodução nos players do catálogo, comunidade e salas. Dispositivos Apple com suporte nativo a HLS recebem a URL diretamente no elemento `video`; outros navegadores continuam usando hls.js quando suportado. `playsinline` é preservado, a mídia nativa não força `crossorigin`, e falhas de autoplay orientam o usuário a tocar em reproduzir. Recuperação de erro de mídia hls.js é limitada a uma tentativa para evitar ciclos infinitos.

Referência da seleção nativa: [documentação do hls.js](https://github.com/video-dev/hls.js#compatibility). Teste da seleção por ambiente, mensagens HTTP e descarte de recursos: `tests/media_player_check.cjs` (Node). Testes Chromium continuam cobrindo reprodução real, sincronização, autoplay bloqueado e áudio nas salas. Não houve teste em um iPhone físico nesta alteração.


Quando o HLS nativo falha antes de começar a tocar, o carregador agora tenta hls.js uma única vez, se suportado, sem alterar a URL assinada. No iPhone com ManagedMediaSource, o modo alternativo define `disableRemotePlayback` antes de anexar a mídia, conforme a [documentação do WebKit](https://webkit.org/blog/14735/webkit-features-in-safari-17-1/). Isso desativa AirPlay apenas durante esse modo alternativo; a configuração é restaurada ao fechar. A detecção de suporte continua permitindo o modo nativo em iPhones antigos. Não há transcodificação nem contorno de restrições de acesso da fonte.

Erros de `play()` são tratados em português; uma rejeição genérica tardia não substitui uma falha HTTP já identificada. A referência ao hls.js nas salas é dinâmica para acompanhar a troca de modo. O teste `tests/media_fallback_browser_check.py` gera HLS real a partir da amostra Sintel local, força uma falha na primeira resposta e verifica reprodução pela mesma URL, pausa/play, encerramento e preservação de erro 403. Requer `ffmpeg` no PATH ou `FFMPEG_BINARY`. Ele roda no Chromium e não substitui validação no iPhone. O WebKit baixado neste servidor não pôde ser executado por falta das bibliotecas nativas exigidas.


### Diagnóstico no aparelho

Acrescente `?player_debug=1` à página `/titulo/<id>` e abra um episódio. O player registra automaticamente a seleção de motor, erros nativos/hls.js, status HTTP acessível ao navegador, codecs e etapas de carregamento/reprodução. A coleta só é ativada por esse parâmetro e aparece um aviso no player. Não captura URLs, parâmetros assinados, corpo de respostas, cookies, IP ou o user-agent completo. A API exige conta com acesso ao catálogo e proteção CSRF; a consulta `/api/admin/player-diagnostics` é restrita ao administrador. Relatórios expiram na limpeza após sete dias, com limite global de 300, 12 novos relatórios/hora por conta e 32 revisões por relatório. O hash da URL salvo no servidor permite comparar as fontes sem expor o link.

`tests/test_playback_diagnostics.py` cobre autorização, acesso a conteúdo, CSRF, propriedade, limites e descarte de dados não permitidos. `tests/media_fallback_browser_check.py` também verifica o envio e a recuperação do diagnóstico após uma falha nativa seguida de reprodução HLS real. Uma falha de envio do diagnóstico não interrompe a reprodução.


Para investigar um título sem depender de parâmetros na URL, a configuração interna `player_diagnostic_window` aceita `{"content_id":"...","until":<timestamp>}`. Durante essa janela, `/api/play/<id>` ativa o diagnóstico somente para administradores autenticados e somente para esse título. A coleta para automaticamente no vencimento. O aviso fica no cabeçalho do player, e erros de envio aparecem com o status HTTP. Contas de clientes continuam sem coleta automática; o link explícito `?player_debug=1` permanece disponível. O teste de navegador agora verifica o caminho normal `/titulo/neon`, sem parâmetro, com reprodução HLS real e recebimento do relatório.


A versão `diagnostic3` inclui o botão administrativo **Abrir fonte diretamente** no cabeçalho. Ele abre a mesma URL em outra aba, sem modificar o catálogo. Em falha fatal `manifestLoadError` com status HTTP inacessível (zero), o diagnóstico executa no máximo duas sondagens da própria playlist no aparelho: uma leitura CORS e uma requisição `no-cors`. Não envia conteúdo/URL para o relatório e cancela a resposta sem baixá-la integralmente. Resposta opaca confirma somente acesso a alguma resposta HTTP; não confirma status 200, validade do HLS ou codec. Ambas as sondagens são canceladas ao fechar o player. O teste de navegador usa uma fonte HTTP local em outra origem, com resposta 404 sem CORS, e verifica essa distinção e o limite de duas sondagens.
