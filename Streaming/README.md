# Flix — streaming e comunidade

Aplicação em português para filmes, séries e TV ao vivo, com landing page animada, catálogo, contas, planos, checkout e administração. Python 3.11+, Flask, SQLite e frontend HTML/CSS/JavaScript. O servidor usa Waitress. Salas, lives com convidados, jogos, chat com chamadas, notificações e PWA estão documentados em [COMMUNITY.md](COMMUNITY.md).

## Executar no Windows

Abra um PowerShell nesta pasta e execute:

```powershell
.\start.ps1
```

O script instala as dependências em `.packages` quando necessário. Alternativamente:

```powershell
python -m pip install --target .packages -r requirements.txt
python run.py
```

- Site: http://localhost:8000
- Administração: http://localhost:8000/admin
- Login inicial: `admin@vyra.local`
- Senha inicial aleatória: `data/initial-admin.txt`

Altere a senha em **Minha conta** depois do primeiro acesso. O arquivo de acesso inicial não é atualizado quando a senha muda. A pasta `data` e as credenciais ficam fora do controle de versão.

## Funcionalidades

- Landing page responsiva com arte original, movimento cinematográfico, animações durante a rolagem, vitrines, planos, FAQ e CTAs. Respeita a preferência por redução de movimento.
- Catálogos de filmes, séries e TV, busca, filtros, detalhes e favoritos por usuário.
- Reprodução MP4/WebM compatível com o navegador e HLS com hls.js local. Controles nativos, tela cheia, Picture-in-Picture quando suportado, próximo episódio e reinício.
- Posição fracionada por usuário, filme e episódio armazenada no servidor. Salva a cada 2,5 segundos durante a reprodução, ao pausar, buscar uma posição, fechar o player ou ocultar a página. A retomada usa a posição registrada, inclusive em outro dispositivo. Fechamento forçado do processo pode perder o intervalo desde a última gravação.
- Fila local por usuário para sincronizar progresso após falha de conexão. Atualizações antigas não sobrescrevem as mais novas.
- Cadastro vinculado a plano, login, logout, alteração de senha, sessões HttpOnly e restrição de acesso por validade. Limite de sessões de login conforme o plano; não é uma contagem de players simultâneos.
- Administração de filmes, séries, temporadas e episódios; publicação/rascunho; destaques; exclusão e edição.
- Cadastro de canais, importação de listas, edição e exclusão.
- Gestão de usuários: nome, bloqueio, permissão, plano e validade manual de acesso.
- Gestão de planos: preço, duração, qualidade anunciada, limite de acessos, benefícios, destaque e ativação/desativação.
- Dashboard com métricas reais do banco e pagamentos recentes.
- Checkout Pro do Mercado Pago, ambiente de teste/produção, credenciais criptografadas, teste de conexão, assinatura de webhook e validação do pagamento antes da liberação.

## Mercado Pago

1. Abra **Administração → Configurações**.
2. Informe a marca, e-mail de atendimento e o domínio público HTTPS, sem caminho final.
3. Selecione **Teste** e informe o Access Token da aplicação e a assinatura secreta de Webhooks. Campos secretos vazios preservam o valor salvo; o servidor não devolve os segredos ao navegador.
4. No painel de integrações do Mercado Pago, configure notificações do tipo **Pagamentos** para `https://seu-dominio/api/payments/webhook`.
5. Salve as configurações e use **Testar conexão salva**.
6. Faça uma compra com usuários/credenciais de teste compatíveis com sua aplicação. Confira a notificação e o acesso liberado antes de selecionar **Produção** e salvar as credenciais reais.

O preço e a duração vêm do banco, nunca do navegador. Cada checkout cria um pedido com valores congelados. O webhook valida a assinatura HMAC e consulta a API autenticada; confere valor, moeda, ambiente e referência do pedido. Notificações repetidas não concedem dias adicionais. O retorno do checkout também permite consultar o pagamento autenticado. Pagamentos pendentes não liberam conteúdo.

**Modelo de cobrança implementado:** compra de acesso pré-pago por período, sem renovação automática. Assinaturas recorrentes por débito automático exigem uma integração adicional com a API de Assinaturas; não são simuladas nesta versão.

A integração foi validada com testes automatizados e respostas simuladas da API. Uma transação real/sandbox completa depende das suas credenciais e de um domínio HTTPS acessível pelo Mercado Pago.

Referências: [Checkout Pro — Preferences API](https://www.mercadopago.com.br/developers/pt/reference/online-payments/checkout-pro-preferences/overview), [notificações](https://www.mercadopago.com.br/developers/pt/docs/checkout-pro-preferences/payment-notifications).

## Canais e listas IPTV

**Canal individual:** use **Canais de TV → Adicionar canal** e informe a URL do stream. HLS normalmente utiliza `.m3u8`; `.m3u`/`.m3` funcionam quando o endereço representa um manifesto HLS compatível. MP4, WebM e Ogg usam o player nativo quando suportados.

**Lista de canais:** use **Importar lista** e selecione um arquivo `.m3u`, `.m3u8`, `.m3` ou `.txt`, cole o texto ou informe uma URL pública. A extensão não define o conteúdo: uma playlist IPTV lista canais; um manifesto HLS descreve a transmissão de um canal. O importador distingue os dois.

Exemplo:

```m3u
#EXTM3U
#EXTINF:-1 tvg-logo="https://seu-cdn/logo.png" group-title="Notícias",Meu canal
https://seu-cdn/ao-vivo/master.m3u8
```

O importador preserva título, logo e grupo, resolve caminhos relativos na importação por URL, ignora URLs repetidas e rejeita protocolos fora de HTTP/HTTPS. Limites: 2 MB e 999 canais por importação. URLs importadas passam por proteção contra acesso à rede interna, inclusive em redirecionamentos. Portas remotas permitidas na importação: 80, 443, 8080 e 8443. Arquivos permitem importar fontes com outras portas.

As fontes precisam oferecer CORS e codecs compatíveis com o navegador. Em um site HTTPS, use fontes HTTPS. RTSP, RTMP, UDP, TS bruto, DRM e fontes que exigem cabeçalhos proprietários precisam de um serviço de conversão/distribuição apropriado. O projeto não transcodifica vídeos nem remove proteção das fontes.

## Conteúdo inicial

Os nomes e sinopses são fictícios para apresentar o produto. Os títulos estão identificados como demonstração nos detalhes e usam o trailer de **Sintel**, da Blender Foundation, como vídeo de amostra. A cópia local em `static/assets/sintel-trailer.mp4` garante uma prévia estável. Substitua os links e imagens no painel pelo seu catálogo. Os blocos da landing page que representam categorias de TV são ilustrativos; não há canais comerciais pré-cadastrados.

Fotografias do Unsplash foram copiadas para `static/assets`; a arte do hero foi criada especificamente para este projeto. Consulte `ASSETS.md`. O hls.js 1.6.13 está em `static/vendor/hls.min.js`, sob a licença Apache-2.0 preservada no arquivo. Referência: [hls.js](https://github.com/video-dev/hls.js).

## Persistência e publicação

- Banco: `data/vyra.sqlite3` (SQLite/WAL).
- Web Push: preserve `data/push-private.pem` e inclua `data/private-audio/` e `data/social-media/` nos backups. Instalação e notificações: [COMMUNITY.md](COMMUNITY.md#central-de-notificações-e-pwa).
- Chave de criptografia: `data/secret.key`. Faça backup junto com o banco; perder a chave impede ler os tokens de pagamento.
- Nunca publique a pasta `data` como conteúdo estático.
- Variáveis opcionais: `PORT` (padrão 8000), `HOST` (padrão 127.0.0.1), `VYRA_DATA_DIR` (diretório persistente).
- Para publicar, rode o Waitress atrás de um proxy com HTTPS e mantenha o diretório de dados persistente. Ajuste a identidade, atendimento e os textos institucionais ao serviço real.
- A qualidade anunciada nos planos depende do arquivo fornecido. Não há transcodificação, DRM, aplicativo nativo ou perfis independentes de família nesta versão.
- Para grande escala, será necessário migrar o banco e implantar a distribuição de mídia/CDN conforme a demanda.

## Verificação

### Animações e interações

O sistema local em `static/motion.js` e `static/motion.css` inclui abertura cinematográfica, entrada de texto por palavras, partículas Canvas com reação ao cursor e ao toque, parallax, capas 3D com reflexos, botões magnéticos, carrossel com inércia, palco de filmes/séries/TV controlado por rolagem e demonstração interativa de dispositivos. Há também transições de navegação, cartões de TV flutuantes, planos com bordas luminosas e entradas em sequência.

No celular, deslize horizontalmente no palco para trocar entre filmes, séries e TV; toque nas telas ou deslize na demonstração de dispositivos para mudar o foco. O catálogo mantém a rolagem horizontal nativa e as capas respondem ao pressionar. Toques no fundo da abertura criam ondas nas partículas. A rolagem vertical e o zoom por pinça continuam disponíveis.

As cenas de dispositivos são demonstrações visuais; o player real usa os dados persistidos no servidor. As animações respeitam a preferência do sistema e podem ser pausadas pelo botão **Movimento ativo**. O motor suspende o Canvas fora da abertura e interrompe a renderização quando a aba está oculta; seus observadores são removidos ao trocar de página.

Para validar mouse, toque, rolagem, teclado, pausa, navegação e capturar prévias:

```powershell
python tests/motion_check.py
```

As capturas e resultados ficam em `test-results/motion-*`.

```powershell
python tests/test_app.py
```

Testes cobrem autorização, CSRF, isolamento do progresso e frações de segundo, escrita fora de ordem, edição de episódios, importação/deduplicação, bloqueio de URLs internas, criptografia, preços do servidor, assinatura de webhook, idempotência e reembolso.

Para testar o navegador (servidor rodando e Chrome instalado no caminho padrão do Windows):

```powershell
python -m pip install --target .packages -r requirements-dev.txt
python tests/browser_check.py
```

As capturas são salvas em `test-results`. O teste usa o acesso inicial, cria/remove um filme e um canal temporários e verifica reprodução e retomada. Depois de alterar a senha inicial, ajuste a fonte das credenciais do teste antes de rodá-lo.


## FlixJump e player

O player tem controles sobre o vídeo, volume, avanço pela barra, retorno de 10 segundos,
tela cheia e um botão **FlixJump** na lateral. O vídeo mantém toda a largura disponível;
o painel e o chat são sobrepostos. A barra de espaço controla o play e as setas permitem
avançar ou voltar quando você controla a reprodução.

- O botão **Criar sala FlixJump** fica abaixo do vídeo. O ícone de pessoas na lateral
  também abre **FlixJump → Criar uma sala**. Quem cria a sala vira anfitrião.
- Dentro da sala, **Copiar link** gera um convite `/sala/CODIGO`. Também é possível
  compartilhar pelo menu nativo do dispositivo, copiar o código de 12 caracteres ou
  convidar amigos pela plataforma. Os campos de entrada aceitam link ou código.
- Ao abrir o link, a pessoa faz login, se necessário, e volta automaticamente ao convite.
  Com plano ativo, sua solicitação é enviada ao anfitrião. Ela fica na página de espera,
  sem acesso ao chat, à voz ou ao estado da sala, até ser aceita.
- O anfitrião vê o nome de usuário e os botões **Aceitar** e **Recusar** em um aviso
  sobre o vídeo. As solicitações também aparecem no painel da sala. Links, códigos e
  convites de amigos passam pela mesma aprovação. Até 8 participantes são permitidos;
  uma aprovação reserva a vaga enquanto a pessoa entra.
- A pessoa pode cancelar o pedido. Solicitações sem contato por 2 minutos expiram;
  recusas valem até a sala ser encerrada e não são anuladas ao recarregar o link.
  Quem sai e pede para entrar novamente precisa de nova aprovação. As solicitações
  pendentes acompanham o novo anfitrião em caso de transferência e são apagadas ao
  encerrar a sala. Links não expõem dados da sala e não são indexados por buscadores.
- O anfitrião controla play, pausa e posição. Play e retomada posicionam o convidado
  no tempo atual da sala; o progresso pessoal não substitui a posição do anfitrião.
  O vídeo sincroniza ao carregar, recuperar conexão e voltar para a aba. O estado é
  consultado a cada 400 ms, sem aguardar a negociação de voz. A referência considera
  o tempo do servidor, o tempo local decorrido e uma estimativa da latência.
- Diferenças superiores a 0,6 segundo são corrigidas pela posição; desvios menores
  convergem com velocidade temporária de 0,97x ou 1,03x. Pausas e retomadas usam a
  posição do anfitrião diretamente. Buffering do anfitrião pausa a referência da sala.
  Latência, buffering e suspensão de abas ainda podem causar diferenças: não há
  garantia de reprodução exatamente no mesmo frame entre dispositivos.
- Se o navegador impedir reprodução automática com som, aparece **Acompanhar sala**.
  O participante precisa tocar uma vez nesse dispositivo para autorizar a reprodução;
  esse toque aplica a posição atual antes de dar play. As próximas ações seguem o
  anfitrião automaticamente enquanto o navegador mantiver a autorização.
- Na TV, streams HLS com `EXT-X-PROGRAM-DATE-TIME` usam o relógio do programa;
  outras fontes acompanham a borda ao vivo. A precisão depende da fonte, e não é
  possível garantir sincronia exata para canais sem relógio compartilhado.
- O chat abre em uma janela flutuante. Mensagens recentes aparecem em balões por
  oito segundos. As mensagens são texto, com limite de 1.000 caracteres. São retidas
  até 200 por sala, com as últimas 60 no painel. Ao encerrar a sala elas são excluídas.
- A voz usa WebRTC entre os participantes. O microfone começa desligado, liga após
  o clique e a permissão do navegador, e é liberado ao desligar, sair ou fechar o player.
  Participantes podem ouvir sem ativar o próprio microfone.
- A fala é detectada no áudio recebido e no microfone local, sem gravar o áudio no
  servidor. Durante a fala, o filme usa 18% do volume escolhido e a voz mantém volume
  integral; após 650 ms de silêncio, o filme recupera o volume anterior. O controle de
  volume continua representando a preferência do usuário. O mute é preservado. Em
  navegadores que ignoram volume programático, o filme fica mudo durante a fala e
  recupera o estado anterior ao final. A análise de voz depende de Web Audio e pode
  precisar do primeiro toque em reproduzir ou no microfone para ser autorizada.
- Em **FlixJump e amigos**, no cabeçalho, é possível escolher seu nome de usuário,
  enviar, aceitar, recusar ou cancelar solicitações e consultar convites. Atualize essa
  área para buscar novos convites. Uma amizade exige aceite do destinatário.
- A presença expira após 45 segundos sem contato. Se o anfitrião sai, o participante
  mais antigo assume; sem participantes, a sala e seus dados são removidos na próxima
  operação de sala/social. Feche a sala antes de trocar de filme ou episódio.
- Cada conta representa um participante; use uma única aba por conta na mesma sala.

As tabelas novas e os nomes de usuário das contas existentes são migrados automaticamente
na inicialização. O banco usa SQLite; estado e sinalização funcionam entre processos da
mesma aplicação que compartilhem o arquivo do banco. Não é necessário WebSocket.

### Voz em produção

Sirva a aplicação por **HTTPS** (localhost também permite testes). O navegador recebe
`Permissions-Policy: microphone=(self)`; a câmera continua bloqueada. Por padrão há
um servidor STUN público para descoberta de conexão. Configure `FLIXJUMP_ICE_SERVERS`
com um array JSON de servidores ICE para usar um serviço TURN nas redes que bloqueiam
conexões diretas. Exemplo de estrutura, substituindo as credenciais e o domínio:

```json
[
  {"urls": "stun:seu-servidor.example:3478"},
  {"urls": ["turn:seu-servidor.example:3478", "turns:seu-servidor.example:5349"],
   "username": "usuario-do-relay", "credential": "credencial-do-relay"}
]
```

Essas são credenciais de cliente do relay, entregues somente a assinantes autenticados;
não use chaves administrativas do provedor. O projeto não provisiona um serviço TURN.
O teste de navegador valida áudio com dois navegadores locais e microfone simulado;
redes externas e navegadores móveis reais devem ser validados na implantação.

### Cadastro administrativo

Em **Admin → Usuários → Cadastrar usuário**, informe nome, usuário único, e-mail,
senha inicial e plano. O plano libera acesso imediatamente por sua duração, sem cobrança.
Uma validade personalizada é opcional. O cadastro também pode ficar sem plano.
A sessão do administrador é preservada. A edição existente permite trocar plano,
validade, status e permissões.

### Validação

```bash
python -m unittest discover -s tests -p 'test_*.py'
python tests/jump_browser_check.py
python tests/jump_invite_browser_check.py
```

O segundo comando cria banco temporário e servidor isolado na porta 8127. Requer
Playwright/Chromium; ajuste o caminho do executável para seu ambiente. Ele verifica
cadastro administrativo, amigos, convite, chat, reprodução em duas sessões, áudio WebRTC,
tela cheia, layout móvel, transferência de anfitrião e encerramento. As capturas ficam
em `test-results/flixjump-*.png`.

O teste `jump_invite_browser_check.py` usa a porta 8128 e valida o link copiado, o retorno
após login, a espera sem acesso à sala, os avisos em desktop e celular, a aprovação,
o cancelamento, a recusa após recarregar e o convite de uma sala já encerrada.


## Cupons de teste grátis

Em **Admin → Cupons → Criar cupom**, defina o código, a duração em horas ou dias,
o plano permitido (ou todos os planos ativos), a validade e o limite total de usos.
Validade e limite são opcionais. É possível editar, ativar e desativar os códigos;
essas mudanças não alteram acessos que já foram liberados.

No cadastro público há um campo **Tem um cupom?** e um botão **Aplicar** para consultar
o benefício. O cadastro revalida o cupom no servidor, mesmo que ele já tenha sido
consultado. Com um código válido de teste grátis, a conta recebe imediatamente o
plano selecionado e o período de acesso, sem criar pedido ou chamar o Mercado Pago.
Sem cupom, permanece a confirmação de assinatura pelo checkout. Um cupom inválido,
expirado, desativado, esgotado ou incompatível com o plano impede o cadastro e mostra
o motivo; a pessoa pode corrigir ou remover o código.

A duração começa no cadastro e não há cobrança automática ao terminar. A reserva de
uso, a criação da conta e a liberação do acesso são feitas na mesma transação SQLite,
para que duas pessoas não consumam a última utilização simultaneamente. Tentativas
de cadastro que falham não consomem usos. Os resgates mantêm um registro do benefício
concedido. Os cupons são para contas novas; não há resgate na conta existente.

As tabelas são criadas automaticamente na inicialização. Nenhum cupom é ativado por
padrão; o administrador define os códigos e os benefícios pela interface.

A correção de formulários invisíveis garante que diálogos continuem visíveis quando
as animações estão pausadas, com movimento reduzido ou ao alternar abas.

Validação adicional (banco temporário e servidor isolado na porta 8130):

```bash
python -m unittest discover -s tests -p 'test_*.py'
python tests/coupons_browser_check.py
```

O teste de navegador verifica o cadastro administrativo com animações pausadas,
gestão de cupons, cadastro móvel, liberação sem checkout e o fluxo normal sem cupom.
Capturas ficam em `test-results/admin-create-user-fixed.png`,
`test-results/admin-coupons.png` e `test-results/signup-free-trial-mobile.png`.


### Regressão de sincronia e prioridade de voz

`python tests/jump_sync_browser_check.py` usa banco temporário e porta 8131. Exercita
um episódio local em dois navegadores, progresso anterior diferente, negociação de voz
bloqueada, pausa/seek/play do anfitrião, conflito de revisão e entrada durante a reprodução.
O bloqueio de autoplay é simulado com `NotAllowedError` até um clique real, porque
avaliações do Playwright podem conceder ativação ao navegador. O vídeo e o áudio são
reais: um sinal de teste via WebRTC alterna fala/silêncio para verificar redução do filme,
restauração, alteração do volume, preservação de mute e limpeza ao sair. Navegadores
móveis físicos e redes externas precisam de validação na implantação.
