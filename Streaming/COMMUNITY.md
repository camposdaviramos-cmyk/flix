# Comunidade Flix

Entrada: `/comunidade`. Funciona com uma conta ativa, sem exigir assinatura para conteúdo externo. O catálogo pago e as salas FlixJump do catálogo conservam as regras de assinatura existentes.

## O que está implementado

- Feed paginado com filmes, séries, notícias, conversas e música; busca de publicações e pessoas; filtro de contas seguidas.
- Publicações com links HTTPS, capa, edição, remoção, curtidas únicas por conta e comentários.
- Perfil com foto enviada pelo dispositivo (convertida para PNG 256 px no navegador), capa por URL ou envio do dispositivo, biografia, gêneros, cidade e site; nome de usuário único; seguidores; emblemas concedidos e revogados pelo administrador.
- Pedidos de amizade e mensagens privadas entre amizades aceitas. A remoção da amizade interrompe o acesso à conversa pela API.
- Ranking: 5 pontos por curtida recebida, 2 por espectador único de outra conta, 1 por seguidor. Visualizações são registradas pelo player depois de 10 segundos e deduplicadas por conta/publicação. Esses contadores não são métricas antifraude ou de faturamento.
- Salas temporárias por padrão, com opção permanente, página e link próprios, aprovação opcional (ativada inicialmente), assentos, presença, chat com balões e painel sobre o player, remoção de participantes e encerramento.
- JumpFlix externo com YouTube, MP4, WebM e M3U8; música com YouTube e arquivos MP3/OGG/M4A/WAV; fila de reprodução controlada pelo anfitrião.
- Salas de voz, vídeo e lives com câmera ou compartilhamento de tela (quando suportado pelo navegador). Lives têm 4 assentos no total (anfitrião + 3 convidados); as demais salas têm 8 assentos em destaque e uma plateia sem limite fixo. Somente participantes promovidos podem transmitir voz; câmera/tela também exigem assento em salas de vídeo/live. Câmera e microfone começam desligados.
- Sincronização por estado autoritativo do anfitrião, revisões, relógio do servidor, compensação de latência e correção de posição. Ao bloquear reprodução automática, o navegador pede o toque em “Ativar áudio”.
- Detecção local de voz por Web Audio reduz a mídia a 18% do volume escolhido durante a fala e restaura após o silêncio; áudio das pessoas permanece em volume integral.
- Admin: publicações, destaques, salas, denúncias, comentários e chat público, emblemas e concessões, histórico de moderação. Gestão de contas, planos, cupons e catálogo continua nas seções existentes. Mensagens privadas não são listadas no painel.

## Operação e limites reais

O banco é migrado automaticamente por `create_app()`. Os dados ficam em tabelas `community_*` e `hub_*` no SQLite existente; fotos ficam em BLOB e são servidas como PNG com `nosniff`. Não há importação, download ou retransmissão dos links pelo servidor: o navegador acessa a fonte. Fontes precisam permitir incorporação/reprodução e, para HLS, CORS. A API oficial do YouTube é carregada apenas ao abrir mídia do YouTube; o CSP autoriza seus domínios específicos.

Lives têm quatro assentos de transmissão; as demais salas têm oito assentos de voz/vídeo. A plateia não tem limite fixo de participantes na aplicação. Isso **não significa capacidade infinita de transmissão**: voz/vídeo usam WebRTC direto entre participantes que transmitem, sinalizado por polling HTTP. Cada transmissão cria conexões com ouvintes; CPU, upload dos emissores, banco e servidor limitam a escala. Não foi realizado teste de carga para grandes audiências. Para centenas/milhares de pessoas simultâneas em voz/vídeo/lives, é necessária uma arquitetura SFU e/ou distribuição HLS/CDN; isso não está incluído nesta implantação.

STUN padrão: Google. Para conectividade em redes móveis/corporativas/NAT restritivo, configurar `FLIXJUMP_ICE_SERVERS` com servidores TURN reais (JSON no formato `RTCIceServer`). Nenhum serviço TURN pago foi contratado ou credencial inventada. A configuração é compartilhada com o FlixJump existente. HTTPS é necessário para dispositivos de mídia fora de localhost. O acesso depende da permissão do navegador. Compartilhamento de tela depende do suporte do dispositivo.

Polling de salas: aproximadamente 650 ms, heartbeat de reprodução: 1 s. Presença expira após 45 s sem heartbeat. Na sala temporária, a saída do anfitrião transfere o controle para o membro conectado que entrou primeiro; se ninguém estiver conectado, encerra a sala. A saída explícita é imediata; perda de conexão tem tolerância de 45 s e manutenção a cada 15 s. Na sala permanente, o anfitrião e a sala são preservados mesmo sem participantes. O anfitrião ou admin pode encerrá-la. Histórico de chat por sala retém 200 mensagens; snapshot mostra 60. Fila retém até 100 itens. Pedidos de entrada só aparecem enquanto o solicitante aguarda. Admin/host podem remover participantes, e a recusa não pode ser anulada pela chamada de saída.

Mídia ao vivo HLS com Program Date Time usa horário absoluto. Sem essa informação, os clientes seguem a borda ao vivo local, com precisão dependente da origem. YouTube pode impor restrições regionais, anúncios, incorporação e reprodução automática. Não há promessa de precisão por quadro.

A contagem de visualizações é deduplicada, mas um cliente modificado pode chamar a API diretamente; rankings são sociais. A API limita ritmo de publicação, chat, sinalização e denúncias. Há notificações Web Push descritas abaixo; chamadas não são gravadas pelo servidor. Uploads de vídeos da comunidade são servidos pelo servidor da aplicação, com autenticação e suporte a HTTP Range.

## Rede social e jogos

A estrutura de `/comunidade` usa navegação lateral, feed contínuo no centro e descobertas na lateral direita. No celular, usa navegação inferior com área segura e atalhos para catálogo, notícias, jogos e ranking. Os campos têm fonte mínima de 16 px em telas pequenas/dispositivos de toque para evitar o zoom de foco do Safari, mantendo o gesto de ampliar a página.

- Stories de texto, foto ou vídeo expiram em 24 horas; contam visualizações únicas e aceitam reações, denúncia e remoção pelo autor/admin.
- Reels aceitam upload MP4/WebM ou YouTube. Vídeos enviados usam player vertical com controles; vídeos fora da tela são pausados. O YouTube abre no player incorporado existente.
- Seis reações, substituíveis por conta, em publicações, stories e mensagens de sala. Figurinhas locais e emojis funcionam em mensagens e comentários; não dependem de fornecedor externo.
- Conversas privadas entre amigos mostram presença, mensagens não lidas, indicador de digitação, áudios e compartilhamentos. Os botões de telefone e câmera iniciam chamadas privadas diretamente no site, com aceitação pelo destinatário. Presença online: heartbeat de 20 s, validade de 60 s; aparecer offline também oculta a digitação. Chat e notificações consultam novidades a cada 4 s; chamadas ativas a cada 1 s. Digitação expira em 5 s.
- Fotos são convertidas no navegador para PNG de até 1600 px; API aceita PNG até 4 MB/4096 px. Vídeos MP4/WebM e áudio MP3/M4A/WAV/OGG até 25 MB. Limites por conta: 250 MB, 300 arquivos ativos, 30 uploads/hora. “Gerenciar meus envios” no editor permite excluir arquivos. A exclusão remove o arquivo dos lugares onde é usado.
- Arquivos ficam em `data/social-media/` e são servidos somente a contas ativas em `/api/community/assets/<id>`, com `nosniff`, `no-store` e HTTP Range. Arquivos usados exclusivamente em stories expiram; são removidos fisicamente no próximo upload ou abertura da biblioteca do autor. Arquivos referenciados por publicações, perfis ou salas são preservados.
- O Nginx aceita 26 MB de corpo multipart na rota exata `/api/community/assets` e 9 MB em `/api/hub/audio`; o limite das outras rotas permanece em 3 MB. A aplicação conserva seu limite padrão e amplia somente o POST de upload.

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

O anfitrião ocupa o assento 1 e pode promover até sete convidados nas salas comuns ou três convidados nas lives, devolver participantes à plateia, silenciar e liberar microfones. “Silenciar” mantém o bloqueio até o anfitrião usar “Permitir microfone”; liberar ou promover nunca abre o dispositivo automaticamente. A interface encerra as trilhas locais revogadas e os receptores silenciam áudio sem permissão. As permissões são confirmadas pelo servidor a cada polling, inclusive se um cliente envia `mic=true` após ser silenciado. Assentos são reservados em transações serializadas e protegidos por índice único; convidados desconectados liberam o assento após 45 segundos. A plateia continua assistindo e conversando no chat.

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


## Salas, presença e Flix Messenger

A opção **Sala permanente** fica na criação e nos ajustes da sala, e também na edição administrativa. O padrão é temporário. A eleição usa a ordem de entrada dos membros conectados, preserva o controle no servidor e pausa a mídia no momento da transferência. O novo anfitrião recebe os controles e uma notificação; microfone e câmera não são ativados automaticamente. O mesmo comportamento temporário/permanente existe no FlixJump do catálogo, cujas permissões de assinatura continuam vigentes.

Na live, o espectador pode **Pedir para participar**. O anfitrião aceita ou recusa; também pode convidar alguém da plateia. Um convite só ocupa assento depois de **Aceitar convite** pelo convidado. Há quatro pessoas no palco no total, incluindo o anfitrião. Todos continuam precisando ativar seus dispositivos por conta própria; o anfitrião pode silenciar ou retirar do palco. Sair do palco desliga câmera e microfone locais.

O Flix Messenger fica na área de amigos e em uma janela flutuante nas demais páginas. No celular, a conversa ocupa a tela, considera a área segura e acompanha a altura do teclado virtual. Navegar para uma sala compartilhada recolhe o chat móvel. Uma chamada recebida continua acessível mesmo com um modal de player aberto.

- Texto, emojis, figurinhas e mensagens de áudio gravadas no navegador. Gravações têm prévia, descarte e envio explícito; até 2 minutos e 8 MB por arquivo, 30 envios/hora e 200 MB por conta. A captura escolhe um formato que o navegador suporta (incluindo M4A no Safari quando disponível).
- Áudios ficam em `data/private-audio/`, fora da área estática, e só são servidos com autenticação ao autor ou ao destinatário de uma mensagem que os contém, com HTTP Range e `no-store`.
- Chamadas privadas de voz/vídeo entre amigos usam WebRTC, com toque, aceitar/recusar, silenciar, câmera, minimizar e encerrar. O destinatário só autoriza câmera/microfone ao atender. Chamadas não atendidas expiram após 45 s; uma conexão sem heartbeat expira após 60 s. Voz e vídeo usam a mesma configuração STUN/TURN das salas.
- Salas, jogos, publicações e reels são enviados como cartões com título, imagem e link. Conteúdo removido aparece como indisponível. Compartilhar não dispensa amizade, aprovação da sala nem assinatura do catálogo.
- O foguinho começa com dois dias consecutivos em que **as duas pessoas** enviaram mensagens. O dia usa `America/Sao_Paulo` (UTC−3). Texto, áudio e compartilhamentos contam; curtidas isoladas ou mensagens de apenas um lado não. Há tolerância até terminar o dia atual; um dia completo sem troca dos dois lados quebra a sequência.
- O perfil mostra status personalizado, online/ocupado/offline, assistindo agora e até 12 títulos recentes. Mostrar atividade publicamente é opcional e começa desativado. O próprio usuário pode consultar seu histórico; aparecer offline oculta a atividade ao vivo. O perfil publica apenas metadados, nunca os links protegidos dos vídeos.

## Central de notificações e PWA

O sino está no cabeçalho de todo o site. Notifica mensagens, amizades, seguidores, publicações de contas seguidas, marcações, comentários, curtidas/reações, emblemas, resultados/convites de jogos, pedidos e decisões de salas/lives, troca de anfitrião, chamadas, alterações de plano/pagamento e eventos administrativos. As notificações são criadas na mesma transação da ação original. Usuários só podem listar/marcar suas próprias notificações. As preferências controlam chamadas, sons e cada grupo de alertas; o histórico permanece no sino por até 90 dias.

O aplicativo instalável tem manifesto, ícones, tela offline e um service worker em `/sw.js`. O cache contém apenas a tela offline e ícones; mensagens, contas, APIs e vídeos não são armazenados em cache offline. Notificações Web Push chegam pelo serviço do navegador mesmo sem uma aba aberta, quando as permissões e o sistema operacional permitem. Não há processo JavaScript permanentemente aberto nem garantia de manter uma ligação depois de fechar o aplicativo.

Ativação: **sino → Preferências → Ativar notificações neste dispositivo**. A permissão só é solicitada após essa ação. No iPhone/iPad, requer iOS/iPadOS 16.4 ou posterior, instalação pela **Tela de Início** e abertura pelo ícone. Som, modo Foco/silencioso, bateria e entrega continuam sob controle do sistema. A ação **Enviar notificação de teste** permite verificar o aparelho; apenas o próprio usuário recebe esse teste. Para desligar, use **Desativar neste dispositivo**. Logout cancela a inscrição push do navegador.

### Operação do push

- Dependência `pywebpush==2.5.0` em `requirements.txt`. Na primeira inicialização, gera `data/push-private.pem` com permissão 0600; incluir em backup e não servir pela web. Manter essa chave para preservar as inscrições existentes.
- Inscrições são privadas, até 10 dispositivos por conta, e aceitam endpoints HTTPS dos serviços de Chrome, Firefox, Apple e Windows. Se um navegador compartilhado trocar de conta, as entregas pendentes da conta anterior são removidas dessa inscrição.
- Um worker no processo WSGI envia a fila transacional com carga criptografada, tentativas limitadas e recuo exponencial. Inscrições revogadas (404/410) são removidas. Alertas lidos, desativados, antigos e chamadas já encerradas são descartados antes do envio. A prévia de mensagens mostra texto limitado a 180 caracteres quando habilitada nas preferências; desativá-la substitui o texto por um aviso genérico. Arquivos de áudio não são enviados no push.
- O serviço requer acesso HTTPS de saída aos provedores de push. Clique no alerta abre a rota correspondente; se o app já estiver aberto, navega sem recarregar a chamada em andamento.
- Backup: banco SQLite, `secret.key`, `push-private.pem`, `private-audio/`, `social-media/` e demais arquivos persistentes. A marca pública mudou para **Flix**; nomes internos de banco, variáveis e cookies foram preservados por compatibilidade.

Validação: `tests/test_social_hub.py`, `tests/hub_browser_check.py`, `tests/test_jump.py`. Os testes usam banco isolado, dois navegadores, captura de mídia sintética, transmissão efetiva de pacotes/quadros WebRTC, gravação e reprodução de áudio, privacidade, troca de anfitrião, palco com quatro pessoas, compartilhamentos, perfil, responsividade e fallback offline. O teste de push criptografa com a biblioteca real e decifra a carga com chaves do destinatário, usando transporte HTTP simulado. **A entrega por push em aparelho físico e a conectividade TURN entre redes móveis ainda precisam ser validadas nesses ambientes.**

Referências: [Web Push no iOS/iPadOS](https://webkit.org/blog/13878/web-push-for-web-apps-on-ios-and-ipados/), [Service Worker API](https://developer.mozilla.org/en-US/docs/Web/API/Service_Worker_API).

## Criação, privacidade e personalização — 03/10/2026

`/comunidade/criar` reúne os caminhos dedicados `/post`, `/movie`, `/series`, `/reel` e `/story`. Filmes pedem título, gênero, sinopse, foto e link MP4. Séries permitem adicionar, ordenar por temporada/número e editar até 200 episódios, preservando seus identificadores. As publicações entram no catálogo gratuito da comunidade; não alteram as permissões do catálogo administrativo.

O editor de reels/stories permite combinar até oito fotos ou vídeos em sequência, grade ou faixas, com duração final de até três minutos. Inclui corte temporal, ordem de cenas, enquadramento, zoom, filtros, volume, texto, emojis e links posicionáveis, cor, tamanho, rotação e intervalo de exibição. Há prévia e desfazer. O conteúdo é salvo como composição não destrutiva e reproduzido no Flix; não é exportado como MP4 renderizado. Uploads mantêm os limites existentes de 25 MB por arquivo e 250 MB por conta. O recorte de avatar/capa usa canvas e permite arrastar e ajustar zoom antes de salvar, inclusive em imagens já escolhidas.

A busca musical desta versão foi substituída pelo SoundCloud na evolução descrita abaixo. Composições antigas com YouTube continuam usando o player oficial; a chave antiga não alimenta mais a busca de músicas.

Cada post possui menu para excluir, privar, arquivar, ocultar curtidas/comentários e desativar comentários. Posts privados/arquivados ficam em **Meu perfil → Minhas publicações**. A API revalida visibilidade no feed, detalhes e compartilhamentos; arquivos locais exclusivos desses posts são protegidos. Links externos continuam sob controle de sua origem. Imagens reutilizadas em um perfil, story ativo ou publicação pública permanecem acessíveis nesses lugares. Moderação administrativa não pode ser desfeita pelo autor.

O comentário mais recente aparece no feed. O autor pode editar/excluir seu comentário; o dono do post pode ocultar/excluir comentários. Menções `@usuario` sugerem amigos e geram notificação para amizades aceitas, com deduplicação. Comentários ocultos são exibidos apenas para seu autor e o dono do post.

O feed “Para você” combina recência, engajamento limitado logaritmicamente, gêneros favoritos, histórico, interações, autores seguidos e conteúdos ainda não vistos. Variação diária e diversidade de autores reduzem repetição. “Não tenho interesse” exclui aquela publicação das recomendações do usuário. A ordem é preservada por 15 minutos para paginação estável; acesso e visibilidade são sempre checados de novo. A seleção considera as 600 publicações públicas mais recentes e não é um modelo de aprendizado de máquina.

`/historico` mostra os últimos 100 títulos do catálogo acessados, incluindo filmes/séries finalizados e canais, com filtros. A página inicial ganhou “Assistidos recentemente”; o perfil combina esse histórico com o da comunidade e conserva a escolha de privacidade do usuário.

## Câmeras, chat e instalação nesta atualização

FlixJump do catálogo e salas de cinema da comunidade aceitam até quatro câmeras simultâneas. A faixa lateral só existe com câmeras ativas e divide a altura total do player pelo número de participantes. Na comunidade, a câmera não exige assento de microfone; a voz continua respeitando os assentos e bloqueios do anfitrião. A reserva da câmera é atômica e independente de heartbeats atrasados. Ao sair, as trilhas são encerradas.

Em partidas, participantes, assentos, solicitações e ações de anfitrião ficam no menu **Turma**, dentro do jogo. Novos pedidos de entrada abrem o menu para aprovação. Chat, emojis e indicadores de voz continuam no próprio tabuleiro. Chamadas privadas atendidas ocupam a tela inteira, com opção de minimizar.

O botão flutuante de conversas aparece apenas acima de 700 px; no celular, o acesso é pela aba Mensagens. As mensagens não lidas também são contadas no ícone dessa aba. O PWA inicia em `/comunidade?app=1` e apresenta um convite de ativação de notificações quando aberto instalado. A autorização do sistema acontece após tocar no botão. A inscrição push é restaurada quando a permissão já foi concedida e não há inscrição ativa. Prévia textual de mensagens vem ativada nas preferências e pode ser desativada.

No iPhone, Web Push exige um web app adicionado à Tela de Início e iOS/iPadOS compatível (16.4+). Não existe permissão web para manter JavaScript e chamadas rodando indefinidamente com o app fechado: o service worker recebe push, e som/entrega seguem o sistema operacional. Câmera/microfone são pedidos ao usá-los. Referência: [WebKit — Web Push for Web Apps](https://webkit.org/blog/13878/web-push-for-web-apps-on-ios-and-ipados/).

Testes adicionais: `test_community_experience.py`, `experience_browser_check.py`, `experience_rooms_browser_check.py` e `creator_media_browser_check.py`. Usam bancos descartáveis, CSP habilitada, quatro contextos reais de navegador com câmeras sintéticas/WebRTC, recortes, composição, episódios, privacidade, menções, badges e instalação simulada. O teste de mídia verifica corte e reprodução de vídeo real com áudio próprio no editor e após publicar, incluindo encerramento do áudio ao sair. A integração de busca usa resposta simulada da API oficial nos testes; uma chave real ainda precisa ser configurada. Emulação Chromium não certifica entrega push ou reprodução em iPhone físico.


## Evolução integrada — outubro de 2026

O plano em `DEVELOPMENT-PLAN.md` foi aplicado sobre os sistemas existentes. Novos conceitos vivem em `social_spaces.py` (espaços, grupos e verificação), `flix_music.py` (catálogo, playlists e filas) e `notification_payload.py` (representação compartilhada de notificações). Mensagens de grupos usam `community_dm`, com `group_id` e destinatário privado nulo; notificações usam a fila e o worker existentes. Salas musicais usam `community_rooms`, `community_members`, `community_queue` e `community_messages`.

### Stories, reels e identidade

Criação em etapas: mídia, edição e prévia/informações. Uploads aparecem na prévia antes de avançar. A capa é gerada em canvas com as cenas da colagem, enquadramento, filtros, textos, figurinhas e desenho. Stories expiram em 24 horas, avançam ao terminar e mantêm o acesso às mídias durante sua validade. Reels continuam no feed e no perfil com os controles sociais existentes.

O editor ganhou divisão de cenas, velocidade (0,25× a 3×), brilho, contraste, transições, seleção de figurinhas, menções a usuários e desenho por toque/mouse, além das ferramentas anteriores. A composição conserva os originais: não exporta um MP4 renderizado. Até 8 mídias, 20 elementos, 40 traços/5.000 pontos e 180 segundos. Imagens externas sem CORS podem impedir a captura da capa; uploads locais são o caminho mais previsível. Avatar e capa só são aplicados após confirmar o recorte; cancelar mantém a imagem anterior.

A normalização de emojis é compartilhada entre entrada, banco, API e apresentação. Shortcodes conhecidos, entidades numéricas e sequências Unicode literais viram caracteres; marcação HTML continua escapada. Seguir/Seguindo fica junto do autor e atualiza sem recarregar. O avatar abre perfil, configurações, preferências e sair, fechando com Escape ou clique fora.

### Comunidades, páginas, grupos e verificação

`/comunidade?tab=communities` e `?tab=pages` abrem os diretórios. Cada espaço tem nome, endereço, foto, capa, descrição, membros e cargos. Comunidades podem ser públicas ou por convite; páginas públicas permitem publicação com identidade da página por seus administradores. Criador concede cargos, administradores gerenciam membros, moderadores ocultam publicações. O painel **Comunidades e páginas** pode ocultar/reativar espaços com registro de auditoria. Visibilidade é revalidada no feed, detalhes, busca, arquivos, menções e compartilhamentos.

Conversas permitem criar grupos com nome, foto e amigos. Até 100 participantes por grupo; administradores adicionam/removem membros, promovem responsáveis e editam o grupo. Ao sair o último administrador, o primeiro participante recebe a função. Mensagens, áudios, figurinhas e compartilhamentos usam o mesmo chat, contadores e deduplicação das conversas privadas. A entrada em um grupo delimita o histórico acessível; remover alguém também impede acesso aos áudios do grupo e a prévias pendentes de suas mensagens.

**Conta → Solicitar verificação** envia motivo e links para **Admin → Verificações**. Apenas administradores podem aprovar, recusar ou remover o selo. A decisão gera notificação e auditoria. Pedidos recusados/removidos podem ser reenviados após sete dias. O selo aparece em perfis, autores, comentários, mensagens e identidades nos espaços sociais.

### JumpFlix Music

`/comunidade?tab=music` reúne músicas, busca de faixas/artistas/álbuns, gêneros, novidades, destaques administrativos, salvos, playlists e rankings. Configure **Admin → Configurações → Música / SoundCloud** com Client ID e Client Secret. As credenciais e tokens OAuth são criptografados no servidor, nunca retornados ao frontend. Busca usa a API oficial, cache de 15 minutos e limite de 30 consultas/importações não atendidas por cache por usuário/hora. Sem credenciais, links públicos incorporáveis do SoundCloud e áudios próprios continuam disponíveis; a busca global depende de configurar a aplicação SoundCloud. Referências: [API](https://developers.soundcloud.com/docs/api/guide), [Widget oficial](https://developers.soundcloud.com/docs/api/html5-widget).

SoundCloud toca no widget oficial visível, mantendo a origem e atribuição, sem extração ou armazenamento de seu áudio. A disponibilidade, os limites e eventuais restrições de cada faixa são definidos pelo SoundCloud. O módulo aceita áudio próprio pelo sistema de uploads existente. Não há catálogo nem números de popularidade fictícios.

O player global permanece fora da árvore substituída pela navegação e mantém faixa, posição, volume e fila. No celular há modo compacto e expandido. A fila permite tocar agora/depois, remover, limpar, reordenar por arraste ou botões, aleatório e repetição de faixa/fila. O servidor persiste a fila com revisão para detectar alterações simultâneas. Cards do feed controlam esse mesmo player; músicas e playlists podem ser compartilhadas no chat, playlists públicas aparecem no perfil, e trilhas SoundCloud entram nos editores.

Playlists têm nome, capa, privacidade e até 200 faixas, com ordem efetiva e compartilhamento. Rankings contam sessões após tempo de reprodução observado: até 30 segundos ou metade da duração de faixas curtas, com mínimo de 10 segundos. Saltos/repetições de eventos não somam tempo arbitrário; a mesma pessoa/faixa conta no máximo uma vez a cada 10 minutos. Isso reduz duplicação e abuso simples, sem prometer comprovação física de que alguém ouviu o áudio.

### Salas musicais

O anfitrião cria uma sala com código/link, aprovação opcional e duração temporária ou permanente. Convites a amigos usam as notificações existentes. O player global toca a fila compartilhada, apresenta quem adicionou cada faixa e mostra os participantes presentes. Apenas o anfitrião altera reprodução, posição e ordem; cada dispositivo controla seu volume e pode precisar de um toque para liberar áudio por exigência do navegador.

Servidor é a referência de faixa, posição, pausa, timestamp e revisão. O cliente compensa o tempo da requisição, corrige diferenças maiores que 1,2 segundo e rejeita estados atrasados. Comandos concorrentes são serializados e retomados após atualização da revisão. É sincronização aproximada entre dispositivos, sujeita à rede, ao buffering e ao provedor; não áudio sincronizado em nível de amostra.

Salas musicais têm apenas chat de texto e emojis; sinalização de áudio/vídeo é recusada na API. Salas temporárias transferem o anfitrião ao primeiro participante ou encerram vazias; permanentes preservam o responsável. Áudios e filas compatíveis anteriores são incorporados sem substituir seus links. Salas antigas com vídeo/YouTube conservam o player anterior por compatibilidade.

### Mobile e notificações

O chat ajusta altura e posição pela `VisualViewport`, mantém cabeçalho e composição visíveis, reserva espaço para a área segura e oculta a navegação quando o teclado reduz o espaço. O botão flutuante continua restrito ao desktop. O PWA abre na comunidade.

Notificações exibem remetente/avatar, preview, grupo, tipo de conteúdo e chamada de voz/vídeo. O mesmo construtor alimenta a lista do site e Web Push. A lista contém eventos; instalação e ativação ficam nas preferências. O Service Worker usa tags por chamada, ações Atender/Recusar quando suportadas, foco da janela existente, links internos validados e descarte de ações vencidas. Cancelamento, recusa, perda e encerramento respeitam o estado atual da chamada. Mensagens lidas e conteúdos inacessíveis são ignorados na entrega; notificações não conferem acesso ao conteúdo.

Permissões exigem uma ação do usuário. No iOS, Web Push requer a aplicação adicionada à Tela de Início em versão compatível. PWA não garante processo de vídeo/voz permanente com o aplicativo fechado; ações, som, câmera e execução em segundo plano dependem do navegador/sistema. Ainda é necessária validação física no iPhone para teclado, notificações e chamadas entre redes reais.

### Verificação e operação

Testes adicionais: `test_social_evolution.py`, `evolution_browser_check.py` e `service_worker_check.cjs`, além das regressões existentes. São verificados permissões, isolamento de grupos/comunidades, emoji, selo administrativo, fila/revisão, playlists, plays, migração idempotente, contexto e criptografia do push, edição/publicação real, chat mobile e áudio sincronizado em dois contextos de navegador. O teste de teclado reduz e desloca a VisualViewport; não substitui teste no teclado real do iOS. As chamadas à API SoundCloud são simuladas por falta de credenciais reais.

As migrações são aditivas e idempotentes. Antes de publicar, copie o banco via SQLite backup e preserve `secret.key`, `push-private.pem` e diretórios de mídia. Não substitua o banco pelos bancos temporários dos testes. As alterações de frontend usam nova versão de assets e o Service Worker `flix-shell-v3`.

Validação desta entrega: **115 testes Python aprovados**, testes de navegador citados acima e verificação autenticada no domínio de produção, sem erros JavaScript nem respostas 500 nas rotas exercitadas. Migração validada duas vezes em cópia do banco, seguida de conferência de integridade em produção. Estado detalhado e pendências externas em `IMPLEMENTATION-STATUS.md`.
