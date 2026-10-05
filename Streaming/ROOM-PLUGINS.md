# Plugins de sala Flix

O administrador cadastra jogos e widgets em `/admin?tab=economy`. Use uma URL HTTPS incorporável em um domínio diferente do Flix. O host ativa o item em Mídia → Jogos ou Plugins / Widgets. Widgets são gratuitos; jogos podem ter entrada em moedas confirmada por cada participante. O valor fica fixo durante a sessão.

## Integração multiplayer

O iframe recebe periodicamente `postMessage` com origem exata do Flix:

```js
{
  type: 'flix:room', version: 1,
  session_id: 'identificador-da-sessao', revision: 1,
  room: {id: 'sala', title: 'Nome', host_id: 'usuario'},
  user: {id: 'usuario', name: 'Nome'},
  players: [], state: {}, events: []
}
```

Valide `event.origin` contra a origem autorizada do Flix e `event.source === parent`. Renderize o estado recebido sem executar HTML arbitrário. Participantes enviam ações assim:

```js
parent.postMessage({
  type: 'flix:event', session_id: session.session_id,
  payload: {action: 'move', card: 'blue-3'}
}, FLIX_ORIGIN);
```

Somente o anfitrião pode publicar o estado compartilhado, usando a revisão recebida:

```js
parent.postMessage({
  type: 'flix:state', session_id: session.session_id,
  revision: session.revision, state: nextState
}, FLIX_ORIGIN);
```

Revisões antigas são recusadas. Estado limitado a 32 KB; evento a 4 KB e 15 eventos/s por participante. A resposta inclui os 50 eventos recentes; mantenha o último ID processado e persista o resultado no estado compartilhado. O servidor retém até 200 eventos por sessão. Reentrada usa o estado mais recente. Um plugin deve tratar reconexão e troca de anfitrião; o Flix fornece transporte, não implementa as regras do jogo externo.

A origem, janela e sessão do iframe são verificadas pelo cliente e a participação pelo servidor. O iframe não recebe credenciais, saldo ou acesso ao banco. Plugins não concedem pontos, emblemas ou moedas por declarações do cliente. Resultados dos jogos integrados Cores e Traço permanecem validados pelo servidor. O iframe é isolado e precisa permitir incorporação; novos domínios cadastrados podem exigir recarregar a página para atualizar a política CSP.

## Mídia e provedores

Vídeos da fila principal e músicas da trilha independente têm transportes distintos; a trilha pode tocar durante jogos e lives. YouTube usa o player oficial visível, sem extração de áudio. Spotify e Twitch usam incorporações oficiais e respeitam as opções do provedor; não oferecem a sincronização dos transportes nativos da sala. Restrições de reprodução automática podem exigir tocar em Ouvir/Ativar áudio.

Referências: [Spotify Embeds](https://developer.spotify.com/documentation/embeds/tutorials/creating-an-embed), [Twitch Embed](https://dev.twitch.tv/docs/embed/video-and-clips/).

## Moedas e configuração

O bônus de boas-vindas começa desativado (0) e vale para novas contas após o administrador salvar. Pacotes de compra precisam ser criados e ativados; o checkout reutiliza a integração Mercado Pago existente. O crédito depende da confirmação validada do pagamento e é idempotente. Estornos revertem o crédito, podendo deixar saldo devedor se as moedas já tiverem sido gastas. A compra de moedas não altera a assinatura.

Presentes debitam quem envia e aparecem na coleção do destinatário; não representam saldo sacável. Jogos integrados cancelados antes do início devolvem entradas. Sessões de plugins externos representam acesso ao plugin, sem prêmio financeiro. Não foram feitos pagamentos reais na validação desta versão.
