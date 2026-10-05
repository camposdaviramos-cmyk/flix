# Evolução integrada do Flix — 03/10/2026

Plano autorizado: [DEVELOPMENT-PLAN.md](DEVELOPMENT-PLAN.md). Aplicação publicada em https://flix.devspacey.com, preservando os sistemas existentes de usuários, mensagens, notificações, catálogo e salas.

## Implementado e publicado

- [x] Chat mobile/PWA ajustado à VisualViewport, com campo e envio visíveis ao abrir o teclado; botão flutuante restrito ao desktop.
- [x] Stories/reels em etapas, mídia real, thumbnails de colagens, divisão/corte, velocidade, filtros/ajustes, texto, links, figurinhas, menções, desenho, transições e música.
- [x] Normalização de emojis; recorte de avatar/capa com confirmação; seguir junto do autor; menu da conta.
- [x] Solicitação de verificação e aprovação/recusa/remoção exclusivamente administrativas, com selo azul.
- [x] Comunidades e páginas com identidade, cargos, membros, publicações e moderação; páginas publicam com sua identidade.
- [x] Grupos integrados ao chat existente, incluindo áudio, emojis, figurinhas, compartilhamentos, cargos, contadores e controle de acesso.
- [x] Push contextual, remetente/avatar/preview, ações e estados de chamadas, links internos e tratamento de conteúdo inacessível.
- [x] SoundCloud com configuração segura no admin, busca por música/artista/álbum e reprodução pelo widget oficial.
- [x] Catálogo musical, destaques, gêneros, player global persistente, fila, playlists, arraste, modos de reprodução e ranking de plays registrados.
- [x] Integrações de música com feed, perfil, editor, mensagens e salas sincronizadas com chat de texto.
- [x] Administração de comunidades/páginas e metadados/destaques musicais, além das áreas anteriores.
- [x] Compatibilidade com salas musicais anteriores, migração idempotente, backup, documentação e publicação.

## Evidências de validação

- **115 testes Python aprovados**: `/tmp/flix-release-unittest.log`.
- Navegador: publicação de filmes/séries, reels/colagens, stories, recortes, privacidade e comentários: `/tmp/flix-experience-plan2.log`.
- Reprodução real de vídeo cortado e trilha enviada: `/tmp/flix-media-plan.log`.
- Mensagens, áudio, chamadas WebRTC, lives, quatro participantes, ciclo de salas e PWA offline: `/tmp/flix-hub-plan.log`.
- Integração social/musical, admin, grupos, thumbnail, desenho, menções, link direto de story, fila global, perfil e sala com dois navegadores: `/tmp/flix-final-story-link.log`. Diferença de áudio observada nessa execução: aproximadamente **0,12 segundo**.
- Service Worker: `tests/service_worker_check.cjs`, com ações Atender/Recusar, chamada vencida, janela existente, links seguros, recursos não suportados e encerramento de alertas.
- Migração executada duas vezes sobre cópia do banco real: registros preservados, integridade `ok`, nenhuma violação de chave estrangeira. Banco publicado também conferido.
- Produção autenticada, sem criar conteúdo de teste: `/tmp/flix-production-evolution.log`, sem erros de JavaScript ou respostas 500 nas rotas verificadas.
- Assets: `evolution-20261003b`; Service Worker: `flix-shell-v3`; serviço `flix.service` ativo.

## Configuração e validação externas

- [ ] Preencher Client ID e Client Secret do SoundCloud em **Admin → Configurações** para habilitar a busca global. Integração de API testada com respostas simuladas; não há credenciais reais configuradas.
- [ ] Validar teclado real, entrega de Web Push e chamadas em iPhone físico/PWA. O teste automatizado de teclado simula altura e deslocamento da VisualViewport.
- [ ] Validar chamadas entre redes móveis distintas e a infraestrutura TURN configurada para esse ambiente.

Esses itens dependem de credenciais ou dispositivos externos. Navegadores podem exigir gesto para liberar áudio e permissão para notificações. PWA não garante câmera/microfone executando após fechar o aplicativo. Edições de stories/reels são composições reproduzidas no Flix, sem exportação de MP4 renderizado. Consulte [COMMUNITY.md](COMMUNITY.md) para limites, operação e arquitetura.

Backup inicial de código: `/tmp/flix-plan-backup-20261003-181634`.
Backup consistente do banco anterior à publicação: `data/backups/before-social-music-20261003-200515.sqlite3` (0600).

## Salas mobile/PWA — rooms-20261004a

Layout baseado nas quatro telas de referência, mantendo a paleta Flix. A tela inicial é sempre Chat: conteúdo ativo no topo, participantes, conversa e abas Chat/Mídia/Mais. Participantes, ferramentas e menu são telas secundárias. A revisão inicial ocultava o palco sem mídia; corrigido na versão rooms-20261004b para manter palco e participantes visíveis desde a entrada; com plugin sem mídia, o plugin ocupa o palco. Salas de música e JumpFlix do catálogo adotam a mesma estrutura mobile. Navegador desktop mantém sua composição; PWA instalado usa a nova interface.

Adicionadas privacidade pública/privada/senha, pedidos flutuantes, mudança de atividade pelo anfitrião, fila de vídeos, trilha musical independente, enquetes, widgets oficiais, plugins externos cadastrados pelo admin, carteira, presentes, bônus de boas-vindas e entrada paga opcional em jogos. Perfil mostra presentes e a música recente com reprodução e reação. Detalhes operacionais em [ROOM-PLUGINS.md](ROOM-PLUGINS.md).

Validação em banco isolado: 126 testes Python; navegadores mobile e desktop com mensagens, aprovação, privacidade, mudança de modo, jogos, presentes, carteira, plugins pagos, transmissão WebRTC, quatro câmeras no JumpFlix e música simultânea. Teste específico cobre abertura, recarga e histórico de nove atividades no mobile e PWA standalone, sempre em Chat e sem abrir o teclado. Capturas em `test-results/rooms-redesign-*` e `test-results/experience-jump-four-cameras-mobile.png`. Dispositivos móveis foram simulados em Chromium; não equivale a teste físico no iPhone. Pagamentos e plugins externos foram validados com fixtures, sem cobrança real.

Service Worker atualizado para `flix-shell-v4` e todos os arquivos da página versionados em `rooms-20261004a`. Nenhum pacote de moedas ou bônus financeiro é ativado automaticamente.

Publicada em 2026-10-04 UTC. Serviço `flix.service` ativo; verificação HTTPS de produção aprovou APIs de sala/carteira/admin, arquivos novos, ausência de erros JavaScript/HTTP 5xx, responsividade das páginas e worker v4. Backup: `data/backups/before-mobile-rooms-20261004-003106.sqlite3` (0600); migração aplicada duas vezes numa cópia com integridade e contagens preservadas.

## Correção do estado inicial e links compartilhados — rooms-20261004b

O print da sala Teste correspondeu ao estado sem mídia (`kind=video`, URL vazia). O layout ocultava palco e participantes. Agora todas as salas mobile/PWA mantêm o palco inicial, faixa de participantes e chat; o palco oferece Adicionar vídeo/Adicionar música/Iniciar live conforme a atividade. A interface continua mobile na orientação horizontal de aparelhos com tela de toque.

O endereço exato `https://youtu.be/ROYmf8KSXdE?si=KW6tOaHIWgt9V5nZ` foi aceito e normalizado para `https://www.youtube.com/watch?v=ROYmf8KSXdE`. O formulário começa pelo link, título opcional. O primeiro conteúdo pode ser aberto diretamente com Exibir agora/Tocar agora; o servidor aplica a seleção e inserção numa transação e exige anfitrião para iniciar. Os demais participantes continuam podendo adicionar itens à fila sem assumir o controle.

Erros e bloqueios do player aparecem na tela mobile, com nova tentativa e acesso ao YouTube. O player usa identificação de origem, reprodução inline e referrer policy. Na prova externa real, o YouTube retornou 150 e o texto “Sign in to confirm you’re not a bot” para o ambiente de testes; portanto a execução local não comprova disponibilidade do vídeo no iPhone do usuário. A integração e navegação foram testadas separadamente com fixture da API oficial. WebKit está instalado mas não executa neste servidor por falta de bibliotecas; testes mobile usam Chromium com dispositivo iPhone simulado.

Novas verificações: `tests/test_room_youtube.py`, `tests/room_youtube_browser_check.py`; testes existentes de abertura das salas, aprovação, música, jogos e plugins ajustados à estrutura inicial sempre visível. Captura: `test-results/rooms-empty-fixed-mobile.png`. Nenhuma alteração nos conteúdos ou links da sala real foi feita para estes testes.

Validação final da correção: 129 testes Python aprovados; testes de sala inicial vazia, link exato, título opcional, fila, retry, erro visível, orientação horizontal e nove atividades/PWA aprovados; música simultânea, jogos, plugins e live preservados. Backup pré-publicação: `data/backups/before-room-youtube-20261004-010527.sqlite3`. Serviço reiniciado com `rooms-20261004b`, worker `flix-shell-v5`.

## Player inicial, palco e filas automáticas — rooms-20261004c

Mobile/PWA abre com player em espera e oito assentos visíveis, incluindo vagas vazias; lives mantêm quatro. Controles junto ao campo de mensagem permitem ativar áudio, ligar/desligar microfone/câmera e pedir/cancelar entrada no palco ou descer. O anfitrião recebe o pedido flutuante com Aceitar no palco/Recusar. A aprovação não liga dispositivos sem ação da pessoa. As permissões continuam respeitadas: microfone exige assento e liberação, vídeo/live exigem palco; watch tem até quatro câmeras; salas musicais usam chat de texto.

O término de vídeo/áudio nativo, YouTube ou SoundCloud solicita o próximo item ao servidor como anfitrião. `media_epoch` identifica a reprodução independentemente dos heartbeats, impedindo que respostas e eventos repetidos pulem itens, inclusive URLs consecutivas iguais. Próxima mídia começa na posição zero, em reprodução, e os participantes recebem o novo estado. Fila esgotada pausa. Playlist musical respeita repetição/aleatório; trilha independente avança sem substituir vídeo, live ou jogo e valida o ID atual antes da troca.

Corrigida corrida de inicialização em que o heartbeat de buffering fazia o próprio anfitrião pausar na resolução de `play()`. O vídeo e o áudio nativos reutilizam seus elementos entre itens; listeners anteriores são removidos. A estratégia preserva a autorização por elemento conforme [documentação da Apple sobre playlists](https://developer.apple.com/library/archive/documentation/AudioVideo/Conceptual/Using_HTML5_Audio_Video/ControllingMediaWithJavaScript/ControllingMediaWithJavaScript.html). WebKit físico/iPhone não disponível neste ambiente: verificações mobile usam Chromium emulado.

Validação: 136 testes Python; migração executada duas vezes em cópia isolada do banco real, preservando contagens e integridade. Teste com duas sessões valida player inicial, oito lugares, pedido/aceite, câmera recebida pelo anfitrião, desligamento, bloqueio de microfone, término real de MP4 e WAV, sequência sincronizada, proteção contra evento repetido, mesmo player reutilizado e fila esgotada. Fixture YouTube cobre avanço único no evento de término. Nove atividades e PWA abrem na tela Chat; regressões de quatro câmeras JumpFlix, câmeras entre plateia, widgets e chat dos jogos passaram.

Capturas: `test-results/rooms-stage-empty-mobile.png`, `test-results/rooms-stage-request-mobile.png`, `test-results/rooms-stage-playing-mobile.png`. Testes novos: `tests/test_room_stage_queue.py`, `tests/room_stage_queue_browser_check.py`.

Backup pré-publicação: `data/backups/before-room-stage-queue-20261004-042425.sqlite3`. Assets `rooms-20261004c`, worker `flix-shell-v6`.

## Editor de Story conforme o esboço — stories-20261004a

Criar Story abre um editor próprio: Câmera/Galeria na seleção inicial; depois, uma única foto ou vídeo cobre a tela. Cabeçalho mínimo, seis ferramentas circulares Light Glass à direita (Texto, Figurinhas, Música, Link, Desenhar, Ajustar) e rodapé Seu story/Amigos próximos/Enviar para. Menções ficam dentro de Figurinhas. Sem cenas, carrossel ou timeline no story; o editor de reels mantém seu fluxo. Editor inicializa junto com a tela, sem depender da resposta de SEO. Safe areas e visualViewport acomodam teclado e tamanho útil da tela.

Arrastar, pinça, rotação, duplo toque para editar e lixeira funcionam com Pointer Events. Enquadramento mantém a mídia cobrindo o canvas. Texto oferece fontes, cores, alinhamento, fundo e animação; desenho oferece lápis, marcador, neon, borracha e desfazer. Figurinhas incluem emoji, GIF enviado do dispositivo, localização, enquete, pergunta, horário, menção e hashtag; links abrem o destino. Enquetes registram um voto por pessoa e permitem alterar a escolha; respostas de perguntas são visíveis ao autor. A reprodução pausa durante a resposta e retoma ao fechar.

Vídeos acima de 30 segundos abrem o recorte antes da publicação; o trecho escolhido reproduz em loop durante a edição. A câmera tira foto ou grava vídeo com contador e parada automática em 30 segundos, liberando os dispositivos ao sair. Ajustes incluem brilho, contraste, saturação, filtros, velocidade, som original e duração da foto. Música permite busca via integração já configurável no admin, trecho, volume e prévia, além de arquivo de áudio próprio. YouTube e SoundCloud usam players oficiais; não há extração de áudio do YouTube. A busca depende da configuração do provedor; arquivo de áudio funciona sem chave externa.

Servidor valida uma mídia, duração máxima e formato; composição guarda o trecho, transformações e camadas, sem gerar uma nova codificação do vídeo. O limite de upload continua 25 MB. Amigos próximos e destinatários selecionados têm acesso aplicado ao feed, detalhe, arquivos, visualizações, reações e figurinhas. Enviar para cria o compartilhamento no chat dos amigos escolhidos. GIFs próprios e capas seguem as mesmas restrições de acesso. Stories existentes permanecem legíveis e a migração é aditiva.

Evidências: `tests/test_story_studio.py`, `tests/story_studio_browser_check.py`, `tests/story_studio_gestures_check.py`; captura `test-results/story-studio-reference-mobile.png`. Testes de navegador usam Chromium com viewport/toque mobile e câmera/microfone de teste, com arquivos, gravação e publicação reais em banco isolado. Não representam teste físico em Safari/iPhone. Regressão de corte, áudio e reprodução de reels aprovada. Migração executada duas vezes em cópia do banco de produção, preservando contagens e integridade.

Validação final: 142 testes Python aprovados. Navegadores cobriram gestos reais de toque, pinça/rotação, lixeira, duplo toque, recorte, pausa/resposta de enquete, foto da câmera, gravação de 30 segundos com parada automática, trilha própria e os dois fluxos privados de publicação. Backup pré-publicação: `data/backups/before-story-studio-20261004-072858.sqlite3`. Assets `stories-20261004a`, worker `flix-shell-v7`.

Publicada em 2026-10-04 UTC. Verificação HTTPS de produção aprovada: editor mobile acessível, APIs de stories e seleção de público respondendo, arquivos `stories-20261004a` e worker v7 disponíveis, sem erro JavaScript ou HTTP 5xx. Serviço `flix.service` ativo. A verificação de produção não criou stories nem enviou mensagens para usuários reais.


## Editor de Reels conforme o esboço — reels-20261004a

O fluxo próprio de Reels substitui o formulário anterior: seleção com dois cards, câmera, editor vertical com cinco ferramentas laterais Light Glass, timeline de quadros reais, seleção de capa, publicação e Mais opções. A paleta preta/rosa Flix permanece. Recorte e capa têm telas dedicadas, controles avançados aparecem sob demanda, safe areas e visualViewport acompanham o teclado. O rodapé permanece visível de 320 a 1440 pixels.

A instrução mais recente do usuário amplia o limite do plano para **60 segundos**, em um único vídeo. Gravação tem contador, parada automática, timer, velocidades e troca de câmera; flash depende do aparelho. Vídeos maiores abrem o recorte automaticamente. A timeline do editor e a capa mostram o trecho selecionado; a timeline de recorte mostra o arquivo inteiro. Stories continuam limitados a 30 segundos.

Texto e figurinhas reutilizam gestos de arrastar, pinça, rotação, duplo toque e lixeira. Filtros incluem intensidade, Cinema e Vintage; ajustes incluem brilho, contraste, saturação, temperatura, exposição e nitidez. Capa aceita quadro do vídeo ou foto com recorte/zoom. Música oferece catálogo, pesquisa, favoritas locais, prévia, trecho e volumes independentes; áudio próprio funciona sem provedor. YouTube/SoundCloud continuam com players oficiais, sem extração de áudio. A busca externa depende das credenciais configuradas no admin.

Publicação guarda descrição de até 2.200 caracteres, pessoas, localização, temas, público, comentários, reutilização no feed, rótulo de IA, marca, qualidade, playlist, descrição acessível e permissões de remix/download/dublagem. Estas três permissões têm endpoint de autorização; não criam editores adicionais de remix/dublagem. Marcações notificam apenas destinatários que podem ver o Reel. Público e comentários são aplicados no servidor, inclusive em arquivos e compartilhamentos. Ações do menu do post mantêm essas opções consistentes. Publicar usa chave de idempotência para evitar duplicação em uma repetição do envio.

Rascunho em IndexedDB preserva o arquivo de vídeo, áudio próprio, capa, composição e opções no aparelho. Ao retornar, aparece Continuar Reel. Envio mostra progresso real e mantém o editor em caso de falha. Alta qualidade mantém o arquivo original; Padrão regrava o trecho com resolução de até 1280 pixels e bitrate reduzido onde Canvas/MediaRecorder são suportados. A reprodução aplica as camadas e efeitos da composição no Flix; não há renderização de um MP4 final com todos os efeitos incorporados. O limite existente de 25 MB por arquivo permanece.

Testes: `tests/test_reel_studio.py`, `tests/reel_studio_browser_check.py`, `tests/reel_studio_camera_check.py` e regressões de reprodução no feed e de Stories. Câmera testada com MediaRecorder real e dispositivos de teste do Chromium: parada em 60 segundos, publicação, limpeza de dispositivos, gestos, responsividade e conversão Padrão reproduzível. Arquivo MP4 com mais de 60 segundos valida a abertura automática do recorte. Rascunho foi recuperado após recarregar a página e publicado com música/capa/texto. Não representa validação física em Safari/iPhone. Migração aplicada duas vezes numa cópia do banco de produção, preservando integridade e contagens existentes.

Validação final: 149 testes Python aprovados; testes de editor mobile, câmera/gestos, reprodução de áudio/feed e Stories aprovados. Backup pré-publicação: `data/backups/before-reel-studio-20261004-231530.sqlite3` (0600). Assets `reels-20261004a`, worker `flix-shell-v8`. Serviço reiniciado em 2026-10-04 UTC.

Verificação HTTPS de produção aprovada: tela Criar Reels anuncia 60 segundos, seleção de vídeo único, APIs de playlists e comunidade respondendo, assets novos e worker v8 carregados, sem erros JavaScript/HTTP 5xx e sem overflow mobile. O teste não criou publicações nem enviou mensagens para usuários reais. Captura: `test-results/reel-studio-production-mobile.png`.
