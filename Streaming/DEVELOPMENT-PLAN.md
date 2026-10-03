# 🚀 PFLIX — PLANO COMPLETO DE DESENVOLVIMENTO

## 1. OBJETIVO GERAL

Evoluir o Flix para uma plataforma social audiovisual completa, integrada e com experiência de produto final.

O sistema deverá contemplar:

* Feed social
* Publicações
* Stories
* Reels
* Perfis
* Seguidores
* Comunidades
* Páginas
* Mensagens privadas
* Grupos
* Chamadas de voz
* Chamadas de vídeo
* Notificações PWA inteligentes
* Verificação de usuários
* Música
* JumpFlix Music
* Salas musicais sincronizadas
* Chat em tempo real
* Catálogo musical
* Playlists
* Fila de reprodução
* Rankings
* Integração com SoundCloud
* Painel administrativo

Todos os módulos devem funcionar como partes de um único ecossistema.

---

# ⚠️ 2. REGRA PRINCIPAL DE DESENVOLVIMENTO


O objetivo é evoluir a aplicação existente sem quebrar o que já funciona.

---

# 🎨 3. PADRÃO VISUAL

Todos os novos módulos devem seguir a identidade visual já existente do JumpFlix.

Não criar interfaces genéricas, simplificadas ou com aparência de protótipo.

Os componentes devem possuir:

* Boa hierarquia visual
* Espaçamento consistente
* Tipografia consistente
* Estados de interação
* Loading states quando necessários
* Empty states quando necessários
* Feedback visual
* Animações discretas
* Responsividade
* Boa experiência em desktop e mobile

Stories, Reels, Feed, Mensagens, Music, Salas e Notificações devem possuir acabamento de produto final.

---

# 4. 🎞️ STORIES

O módulo atual de Stories precisa ser corrigido e reorganizado.

## Problemas atuais

* Informação demais na interface.
* Visual poluído.
* Fotos publicadas não aparecem corretamente.
* Vídeos publicados não aparecem corretamente.
* Fluxo de publicação pouco eficiente.

## Novo fluxo

**Adicionar mídia → Editar → Publicar**

Permitir:

* Foto
* Vídeo

Após publicar:

* Salvar corretamente.
* Aparecer imediatamente.
* Gerar thumbnail.
* Carregar corretamente.
* Reproduzir vídeo corretamente.
* Ficar disponível para outros usuários.
* Respeitar duração e expiração.

## Editor

Preparar suporte para:

* Cortar
* Dividir
* Velocidade
* Filtros
* Ajustes
* Texto
* Stickers
* Menções
* Links
* Música
* Emojis
* Desenho
* Transições
* Colagem

Para Stories, manter o editor rápido e simples.

---

# 5. 🎬 REELS

Criar/aperfeiçoar a experiência de Reels.

Editor:

* Vídeos
* Fotos
* Cortar
* Dividir
* Velocidade
* Filtros
* Ajustes
* Texto
* Stickers
* Menções
* Links
* Música
* Emojis
* Desenho
* Transições
* Colagem

Fluxo:

**Selecionar mídia → Editar → Informações → Publicar Reel**

Após publicação:

* Aparecer no perfil.
* Aparecer no feed quando aplicável.
* Thumbnail correta.
* Reprodução correta.
* Curtidas.
* Comentários.
* Compartilhamento.

---

# 6. 😀 SISTEMA DE Sticker

Corrigir definitivamente o problema de Stickers aparecendo como texto.

O Stickers deve ser preservado corretamente no ciclo:

**Editor → Banco → API → Frontend → Publicação**

Corrigir em:

* Feed
* Publicações
* Stories
* Reels
* Comentários
* Mensagens
* Grupos
* Chat de salas
* Perfil
* Legendas
* Notificações

Exemplos inválidos:

`:heart:`

`&#128525;`

Códigos Unicode exibidos como texto.

Resultado esperado:

❤️ 😍 😂 🔥 🎵

O usuário deve ver exatamente o Sticker que inseriu.

---

# 7. 🖼️ FOTO DE PERFIL E CAPA

Corrigir o fluxo de edição.

## Fluxo correto

**Selecionar imagem**

↓

**Abrir editor imediatamente**

↓

**Ajustar**

↓

**Confirmar**

↓

**Salvar**

Editor deve permitir:

* Zoom
* Arrastar
* Reposicionar
* Recortar
* Ajustar enquadramento
* Confirmar
* Cancelar

Aplicar em:

* Foto de perfil
* Foto de capa

Não salvar a imagem original como versão final antes do ajuste.

---

# 8. ☑️ VERIFICAÇÃO DE USUÁRIOS

Criar sistema de selo verificado.

## Usuário

Configurações:

**Solicitar verificação**

## Administrador

Painel:

**Verificações**

Permitir:

* Visualizar solicitações
* Analisar
* Aprovar
* Recusar
* Remover verificação

A aprovação deve ser exclusivamente administrativa.

## Exibição

Mostrar selo azul ao lado do nome.

Aplicar em:

* Perfil
* Feed
* Publicações
* Comentários
* Stories
* Reels
* Busca
* Mensagens, quando aplicável

---

# 9. 👤 SEGUIR / SEGUINDO

No Feed, próximo às informações do autor:

**+ Seguir**

Depois:

**✓ Seguindo**

Atualizar imediatamente sem reload.

Na própria publicação do usuário:

Não exibir botão para seguir a si mesmo.

---

# 10. 👤 MENU DO USUÁRIO

Na foto do usuário próxima às notificações.

Ao clicar:

* ⚙️ Configurações
* 🚪 Sair

O menu deve:

* Abrir como popover/balão.
* Fechar ao clicar fora.
* Ser responsivo.
* Possuir acabamento visual consistente.

---

# 11. 🔔 SISTEMA DE NOTIFICAÇÕES

Remover das notificações:

* Ativar notificações
* Instalar Flix

As notificações devem ser exclusivamente relacionadas a eventos relevantes.

Exemplos:

* Novo seguidor
* Curtida
* Comentário
* Menção
* Mensagem
* Grupo
* Convite
* Sala
* Verificação
* Eventos musicais relevantes

---

# 12. 📲 NOTIFICAÇÕES PWA INTELIGENTES

Implementar um sistema completo de notificações Push para o PWA.

O sistema atualmente possui notificações muito genéricas.

Isso deve ser substituído por **notificações contextuais**, identificando exatamente o evento ocorrido.

A notificação deve informar:

* Quem realizou a ação.
* Qual foi a ação.
* Tipo do conteúdo.
* Preview quando aplicável.
* Tipo de chamada quando aplicável.
* Ações disponíveis.

---

# 13. 💬 PREVIEW DE MENSAGENS NAS NOTIFICAÇÕES PWA

Quando o usuário receber uma mensagem:

A notificação deve apresentar:

* Foto do remetente
* Nome do remetente
* Preview da mensagem

Exemplo:

> João
> "Você viu o que mandei?"

Em vez de:

> Nova mensagem

O preview deve funcionar para:

* Mensagens diretas
* Mensagens de grupos
* Texto
* Emojis

Quando houver emoji, mostrar o emoji renderizado corretamente.

Exemplo:

> Maria
> "Olha isso 😂🔥"

---

# 14. 🧩 TIPOS DE NOTIFICAÇÃO

O sistema deverá identificar o tipo de evento antes de montar a notificação.

Criar uma estrutura de tipos, por exemplo:

* `message`
* `group_message`
* `call_incoming`
* `call_missed`
* `call_ended`
* `follow`
* `like`
* `comment`
* `mention`
* `story`
* `reel`
* `music`
* `music_room`
* `verification`
* `system`

Cada tipo terá seu próprio:

* Título
* Corpo
* Ícone
* Imagem
* Ações
* Destino

---

# 15. 📞 NOTIFICAÇÃO DE CHAMADA RECEBIDA

Chamadas não devem aparecer como uma notificação genérica.

Quando alguém ligar, identificar:

* Quem está ligando.
* Se é chamada de voz.
* Se é chamada de vídeo.
* ID da chamada.
* Conversa relacionada.
* Estado da chamada.

---

# 16. 📹 CHAMADA DE VÍDEO

Quando receber chamada de vídeo:

A notificação PWA deverá indicar claramente:

**📹 Chamada de vídeo**

Exemplo:

> João
> 📹 Chamada de vídeo recebida

A notificação deverá possuir:

**Atender**

**Recusar**

Ao tocar em **Atender**, abrir a interface da chamada.

Ao tocar em **Recusar**, rejeitar/encerrar a chamada.

---

# 17. 📞 CHAMADA DE VOZ

Quando receber chamada somente de áudio:

Exibir:

**📞 Chamada de voz**

Exemplo:

> Maria
> 📞 Chamada de voz recebida

Ações:

**Atender**

**Recusar**

O sistema deve diferenciar chamadas de voz e vídeo tanto na interface quanto no payload da notificação.

---

# 18. 🔔 EXPERIÊNCIA DA NOTIFICAÇÃO DE CHAMADA

A experiência deve se aproximar do padrão de aplicativos modernos de mensagens.

Exemplo:

### 📹 João

**Chamada de vídeo recebida**

**[ Atender ] [ Recusar ]**

Ou:

### 📞 João

**Chamada de voz recebida**

**[ Atender ] [ Recusar ]**

Utilizar as APIs disponíveis do navegador/PWA para ações de notificação e interação.

A interface deve se adaptar às capacidades do dispositivo e navegador.

---

# 19. 📡 PAYLOAD DE NOTIFICAÇÕES

O backend não deve enviar apenas uma mensagem genérica.

Cada Push Notification deve possuir dados estruturados.

Exemplo conceitual:

```text
type: call_incoming
callType: video
callerId: ...
callerName: ...
callerAvatar: ...
conversationId: ...
callId: ...
```

Para mensagem:

```text
type: message
messageType: text
senderId: ...
senderName: ...
senderAvatar: ...
conversationId: ...
messagePreview: ...
```

Isso permite que o Service Worker saiba exatamente qual notificação e ação apresentar.

---

# 20. ⚙️ SERVICE WORKER DO PWA

Atualizar o Service Worker responsável pelas notificações.

Ele deverá:

* Receber Push
* Identificar o tipo
* Mostrar a notificação correta
* Exibir avatar quando suportado
* Exibir preview
* Criar ações
* Processar clique
* Processar ações
* Abrir a tela correta
* Focar uma janela existente quando possível
* Criar nova janela quando necessário

Para chamadas:

* Atender
* Recusar

Para mensagens:

* Abrir conversa

Para outros eventos:

* Abrir o conteúdo correspondente.

---

# 21. 📴 ESTADOS DAS NOTIFICAÇÕES

Tratar adequadamente:

* Aplicação aberta
* Aplicação em segundo plano
* PWA instalado
* Navegador fechado
* Usuário offline
* Usuário reconectando
* Permissão negada
* Permissão concedida
* Ambientes sem suporte completo

Evitar notificações duplicadas quando o usuário já estiver visualizando a conversa ou evento correspondente, conforme a lógica atual da aplicação.

---

# 22. 📞 ESTADOS DAS CHAMADAS

A chamada deverá possuir estados claros:

* Calling
* Ringing
* Accepted
* Rejected
* Missed
* Ended
* Cancelled

Isso será utilizado para manter a notificação sincronizada com o estado real da chamada.

Exemplo:

Usuário A liga.

Usuário B recebe:

**📹 Chamada de vídeo**

Se A cancelar antes de B atender, atualizar/encerrar o estado quando tecnicamente possível.

Se B recusar, A recebe o estado correspondente.

Se B não atender, registrar chamada perdida.

---

# 23. 📲 EXPERIÊNCIA DE CHAMADA NO PWA

A experiência deve considerar:

* Aplicação aberta
* Aplicação em segundo plano
* PWA instalado

Implementar de acordo com as capacidades reais do navegador e sistema operacional.

Não assumir que todos os ambientes oferecem exatamente os mesmos recursos para chamadas em background.

---

# 24. 🌐 COMUNIDADES

Criar módulo de comunidades.

Uma comunidade possuirá:

* Nome
* @username
* Foto
* Capa
* Descrição
* Membros
* Administradores
* Moderadores
* Publicações
* Configurações

Preparar estrutura para:

* Entrada
* Saída
* Publicações
* Moderação
* Administração
* Notificações

---

# 25. 📄 PÁGINAS

Criar sistema de páginas.

Cada página poderá ter:

* Nome
* @username
* Foto
* Capa
* Descrição
* Seguidores
* Publicações
* Administradores

Administradores poderão publicar em nome da página.

---

# 26. 💬 MENSAGENS E GRUPOS

Implementar grupos no sistema de mensagens.

## Criar grupo

* Nome
* Foto
* Participantes

## Administração

Criador será administrador inicialmente.

Administradores poderão:

* Adicionar usuários
* Remover usuários
* Promover administrador
* Remover administrador
* Alterar informações

Usuários poderão:

* Enviar mensagens
* Receber
* Ver participantes
* Sair

Preparar para mensagens em tempo real.

---

# 27. 🎵 SOUNDCLOUD

Substituir o uso atual do YouTube para músicas.

Utilizar SoundCloud para a integração musical.

## Painel administrativo

Criar:

**Configurações → Música → SoundCloud**

Área para configurar as credenciais necessárias.

As credenciais não devem ficar expostas no frontend.

---

# 28. 🎵 JUMPFLIX MUSIC

Criar:

# JumpFlix Music

Uma área musical completa integrada ao JumpFlix.

## Conteúdo

* Músicas
* Artistas
* Álbuns
* Playlists
* Categorias
* Lançamentos
* Destaques
* Mais ouvidas
* Rankings

---

# 29. 🔎 BUSCA MUSICAL

Buscar:

* Música
* Artista
* Álbum

Cada resultado poderá:

* Reproduzir
* Adicionar à fila
* Salvar
* Adicionar à playlist

---

# 30. ▶️ PLAYER GLOBAL

Criar um único player global.

O player deverá manter:

* Música atual
* Artista
* Capa
* Posição
* Play/pause
* Volume
* Fila
* Repetição
* Aleatório
* Sala atual
* Estado de sincronização

O player permanece ativo durante a navegação.

---

# 31. 📋 FILA MUSICAL

Permitir:

* Adicionar
* Remover
* Reordenar
* Drag-and-drop
* Tocar agora
* Tocar depois
* Limpar fila

Exemplo:

### Tocando agora

🎵 Música A

### Próximas

☰ Música B
☰ Música C
☰ Música D

A ordem deve ser realmente aplicada ao player.

---

# 32. 🔀 ALEATÓRIO E REPETIÇÃO

Implementar:

* Reprodução normal
* Aleatório
* Repetir música
* Repetir fila

---

# 33. 📱 PLAYER MOBILE

Criar player compacto persistente.

Exemplo:

**Capa | Música | ▶️**

Ao tocar, abrir player completo.

---

# 34. 🎵 CARDS MUSICAIS NO FEED

Criar publicação musical.

Exemplo:

**🎵 Música**

Nome da música

Artista

▶️ Reproduzir

---

# 35. 🔄 CARD DINÂMICO NO FEED

Quando o JumpFlix Music estiver tocando:

O card deve mudar para:

**🎵 Tocando agora**

Com:

⏮️ ▶️ ⏭️

O card deve refletir o estado do player global.

---

# 36. ⏭️ CONTROLE PELO FEED

Permitir:

* Reproduzir
* Pausar
* Próxima
* Adicionar à fila
* Tocar depois
* Salvar

A música deve entrar na mesma fila global.

---

# 37. 👥 SALAS DE MÚSICA

Criar:

# Sala de Música

Usuário poderá:

* Criar
* Nomear
* Gerar código
* Gerar link
* Convidar usuários
* Entrar
* Sair

---

# 38. 🔄 SINCRONIZAÇÃO MUSICAL

Todos os participantes devem compartilhar o mesmo estado.

Sincronizar:

* Música
* Posição
* Play/pause
* Timestamp
* Fila
* Ordem
* Próxima música

O servidor será a referência do estado da sala.

---

# 39. 👑 HOST

Criador da sala será host.

Inicialmente poderá controlar:

* Play
* Pause
* Próxima
* Anterior
* Fila
* Ordem

Preparar arquitetura para permissões futuras.

---

# 40. 💬 CHAT DA SALA

Permitir somente texto.

Não permitir:

* Áudio
* Vídeo
* Chamadas
* Compartilhamento de tela

Chat em tempo real.

---

# 41. 👥 PARTICIPANTES

Exibir:

* Foto
* Nome
* @username
* Presença

Exemplo:

**8 pessoas na sala**

🟢 João
🟢 Maria
🟢 Pedro

---

# 42. 🎶 FILA DA SALA

Criar fila compartilhada.

Exemplo:

### Tocando agora

🎵 Música A

### Próximas

1. Música B — João
2. Música C — Maria
3. Música D — Pedro

Mostrar quem adicionou cada música.

---

# 43. 🔐 PERMISSÕES DA FILA

Inicialmente:

**Host controla reprodução e organização.**

Arquitetura preparada para:

* Sugestões
* Aprovação
* Fila colaborativa
* Limite por usuário
* Remoção

---

# 44. 🔥 RANKING MUSICAL

Criar:

* Top músicas
* Top artistas
* Top álbuns
* Mais reproduzidas
* Tendências
* Lançamentos

Utilizar dados reais.

---

# 45. 📊 PLAYS

Registrar reproduções reais.

Evitar duplicidade causada por eventos repetidos do frontend.

Os dados alimentarão:

* Rankings
* Mais ouvidas
* Tendências

---

# 46. 💾 PLAYLISTS

Permitir:

* Criar
* Nomear
* Capa
* Adicionar músicas
* Remover
* Reordenar
* Reproduzir
* Compartilhar

---

# 47. 🔗 INTEGRAÇÃO MUSIC + PLATAFORMA

Music deverá integrar com:

* Feed
* Perfil
* Stories
* Reels
* Mensagens
* Comunidades
* Páginas
* Salas
* Notificações

---

# 48. 🔔 NOTIFICAÇÕES MUSICAIS

Preparar notificações para:

* Convite para sala
* Entrada na sala
* Playlist compartilhada
* Eventos musicais relevantes

Evitar spam.

---

# 49. 🧱 ESTRUTURA DE DADOS

Adaptar ao banco existente.

Conceitos necessários:

* Users
* VerificationRequests
* Pages
* Communities
* Groups
* Stories
* Reels
* MusicTracks
* Artists
* Albums
* Playlists
* PlaylistTracks
* MusicQueues
* MusicRooms
* MusicRoomMembers
* MusicRoomQueue
* MusicRoomMessages
* MusicPlayEvents
* Notifications
* PushSubscriptions
* Calls
* CallParticipants

Não criar estruturas duplicadas se o projeto já possuir equivalentes.

---

# 50. ⚡ TEMPO REAL

Utilizar a infraestrutura realtime existente ou solução adequada.

Recursos que precisam de atualização em tempo real:

* Mensagens
* Grupos
* Presença
* Chamadas
* Salas musicais
* Player sincronizado
* Fila
* Chat

Evitar polling desnecessário.

---

# 51. 🛡️ SEGURANÇA

Nunca colocar no frontend:

* API keys privadas
* Secrets
* Tokens administrativos
* Credenciais privadas

Validar permissões no backend.

Proteger:

* Grupos
* Salas
* Chamadas
* Administração
* Verificação
* Dados de usuários

---

# 52. 📱 RESPONSIVIDADE

Todos os módulos devem funcionar em:

* Desktop
* Tablet
* Mobile
* PWA instalado

Especialmente:

* Stories
* Reels
* Feed
* Mensagens
* Chamadas
* Notificações
* Music
* Player
* Sala musical
* Grupos

---

# 53. 🚨 PRESERVAÇÃO DO SISTEMA EXISTENTE

Durante todo o desenvolvimento:

* Não apagar funcionalidades existentes.
* Não substituir componentes sem necessidade.
* Não duplicar sistemas.
* Não criar players concorrentes.
* Não duplicar sistema de usuários.
* Não duplicar sistema de mensagens.
* Não duplicar sistema de notificações.
* Não modificar APIs sem verificar dependências.

As novas funcionalidades devem aproveitar a infraestrutura existente sempre que possível.

---

# 54. 📌 ORDEM RECOMENDADA DE IMPLEMENTAÇÃO

## FASE 1 — CORREÇÕES CRÍTICAS

1. Stories
2. Emojis
3. Foto de perfil
4. Foto de capa
5. Notificações existentes

## FASE 2 — SISTEMA SOCIAL

6. Seguir / Seguindo
7. Verificação
8. Menu do usuário
9. Grupos
10. Comunidades
11. Páginas

## FASE 3 — NOTIFICAÇÕES PWA E COMUNICAÇÃO

12. Estrutura de tipos de notificação
13. Push Subscription
14. Service Worker
15. Preview de mensagens
16. Preview de mensagens de grupos
17. Identificação de chamada
18. Chamada de voz
19. Chamada de vídeo
20. Notificação de chamada recebida
21. Botão Atender
22. Botão Recusar
23. Estados da chamada
24. Chamada perdida
25. Deep linking para conversa/chamada

## FASE 4 — INFRAESTRUTURA MUSICAL

26. SoundCloud
27. Configuração administrativa
28. Catálogo
29. Busca
30. Player global
31. Fila
32. Playlists
33. Aleatório
34. Repetição

## FASE 5 — MUSIC + FEED

35. Cards musicais
36. Player no Feed
37. Reprodução pelo Feed
38. Adicionar à fila
39. Tocar depois
40. Controles
41. Plays
42. Ranking

## FASE 6 — SOCIAL MUSIC

43. Criar salas
44. Código
45. Link de convite
46. Participantes
47. Host
48. Sincronização
49. Fila da sala
50. Chat
51. Eventos em tempo real
52. Controle de reprodução

## FASE 7 — REFINAMENTO

53. Responsividade
54. Performance
55. Loading states
56. Empty states
57. Error states
58. Animações
59. Segurança
60. Polimento visual
61. Correções finais

---

# 55. 🎯 RESULTADO FINAL

O JumpFlix deverá funcionar como um ecossistema social audiovisual completo.

O usuário poderá:

**Publicar conteúdo**

↓

**Assistir Stories e Reels**

↓

**Seguir usuários**

↓

**Conversar individualmente**

↓

**Participar de grupos**

↓

**Participar de comunidades**

↓

**Interagir com páginas**

↓

**Receber notificações PWA inteligentes**

↓

**Visualizar previews das mensagens diretamente na notificação**

↓

**Receber chamadas de voz ou vídeo com identificação clara**

↓

**Atender ou recusar chamadas diretamente pela notificação quando suportado**

↓

**Ouvir músicas pelo JumpFlix Music**

↓

**Criar playlists**

↓

**Organizar filas**

↓

**Encontrar músicas no Feed**

↓

**Controlar a reprodução diretamente pelo Feed**

↓

**Criar uma sala musical**

↓

**Convidar amigos**

↓

**Ouvir a mesma música sincronizada**

↓

**Conversar por texto enquanto escutam**

↓

**Gerenciar a fila da sala conforme as permissões**

---

# 🚀 PRINCÍPIO FINAL DO PROJETO

O JumpFlix não deve parecer um conjunto de funcionalidades independentes.

A experiência deve ser:

**FEED + VÍDEO + SOCIAL + MENSAGENS + CHAMADAS + NOTIFICAÇÕES + MÚSICA + SALAS = JUMPFLIX**

Cada módulo deve conversar com os demais através de estados, APIs, componentes e sistemas compartilhados.

Antes de considerar qualquer módulo concluído, verificar conceitualmente:

**"Isso está realmente integrado ao JumpFlix ou é apenas uma funcionalidade isolada?"**

Se estiver isolado, a implementação deve ser integrada à arquitetura existente.

O resultado final deve ter aparência, comportamento e acabamento de um produto real, não de um protótipo.


CORREÇÃO:

A mensagem no chat mobile pwa está bugando quando abre o teclado ela sobre toda desaparecendo o botão de enviar e o texto que está sendo digitado