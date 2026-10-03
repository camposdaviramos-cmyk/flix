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
