# WorkTV: migração para React e capacidade

Atualizado em 8 de outubro de 2026 (UTC).

A etapa atual está documentada em [desempenho, segurança e critérios de capacidade](performance-security.md), incluindo resultados finais e limitações. Os benchmarks de 120 requisições abaixo são históricos da primeira migração.

## O que já foi convertido

A interface principal usa React 19, JSX e um build de produção local com esbuild. Componentes renderizam os elementos diretamente; não são contêineres com `dangerouslySetInnerHTML`. Novas telas e alterações estruturais do frontend devem ser implementadas em React. O CSS, a identidade azul, os endereços e os contratos das APIs foram preservados.

| Interface | Implementação |
|---|---|
| Início público e início do assinante | `frontend/src/home.jsx` |
| Catálogo, filmes, séries, TV e favoritos | `frontend/src/catalog.jsx` |
| Continuar e histórico | `frontend/src/catalog.jsx` |
| Detalhes do título, episódios e planos | `frontend/src/details.jsx` |
| Carteira e confirmação de compra | `frontend/src/wallet.jsx` |
| Conta, termos e privacidade | `frontend/src/account.jsx` |
| Login e cadastro geral | `frontend/src/auth.jsx` |
| Estrutura visual do player | `frontend/src/details.jsx` |
| Cabeçalho, menu, rodapé e cartões | `frontend/src/shared.jsx` |
| Montagem, transições e limpeza das raízes | `frontend/src/index.jsx` |

São 13 rotas fixas e a família `/titulo/:id`, além dos modais e cabeçalho/rodapé compartilhados nas rotas antigas. Busca, filtros e favoritos já têm estado local React. A integração transitória `window.WorkTVUI` permite migrar os módulos restantes sem interromper o produto.

Ainda existem módulos de interface legados: interiores da comunidade, mensagens, salas, jogos, criação de conteúdo e administração. Os controladores compartilhados de navegação, formulários, reprodução, sincronização e efeitos também continuam em JavaScript existente. O cadastro específico da comunidade permanece nesse módulo. O próximo ciclo deve extrair esses controladores para serviços e migrar cada módulo, com testes de permissões, uploads, pagamento, WebRTC e restauração de foco.

O backend continua Python/Flask: autenticação, autorização, pagamentos, banco de dados, APIs e validações não são substituídos por React. React executa a interface no navegador. Não é correto transferir segredos ou regras de acesso para o cliente para reduzir Python.

## Correção da abertura

O servidor inseria o catálogo textual para SEO dentro de `#app`; esse texto ficava visível até a resposta das APIs. Agora a abertura mantém a tela de carregamento e o catálogo textual fica em `<noscript>`, disponível quando JavaScript está desativado. Metadados e dados estruturados continuam no HTML inicial.

A primeira abertura também deixou de buscar novamente o documento HTML para atualizar SEO. As navegações seguintes usam `/api/seo?path=...`.

## Reduções de carga entregues

- O catálogo usa uma consulta conjunta de episódios, eliminando uma consulta adicional para cada título. As fontes privadas dos vídeos continuam fora da resposta pública.
- Progresso permanece salvo localmente a cada 2,5 segundos; a gravação periódica no servidor passou para 15 segundos. Pausa, busca e saída continuam com gravação imediata. O teste verifica os identificadores monotônicos e confirmações dos checkpoints.
- Nginx entrega JS, CSS, fontes, imagens, GLB e vídeos locais de `/static/`, com gzip e suporte a Range. Arquivos HTML estáticos continuam no Flask para preservar a CSP dinâmica. APIs e respostas de sessão permanecem fora de cache compartilhado.
- Bundle React com dependências: 281.101 bytes, 83.639 bytes com gzip no build. Arquivo com hash e query de versão, compatível com o cache do PWA. Não depende de CDN de scripts nem de processo Node em produção.

Teste local isolado: 120 requisições, concorrência 8, Waitress com 8 threads, banco descartável com 200 séries adicionais. É uma amostra do endpoint `/api/catalog`, não um teste de usuários simultâneos.

| Medida | Antes | Depois |
|---|---:|---:|
| Requisições/s | 69,03 | 101,22 |
| Latência mediana | 114,12 ms | 74,06 ms |
| Latência p95 | 183,88 ms | 129,07 ms |
| Pico RSS do processo em `/proc/self/status` | 78,52 MiB | 78,46 MiB |
| Erros HTTP | 0 | 0 |

O consumo medido ficou praticamente igual. Não há evidência de redução relevante de memória por usar React. Resultados variam com concorrência, cache e carga do host. `ru_maxrss` apresentou divergência com o processo de lançamento; o relatório usa VmRSS/VmHWM do próprio processo Linux. Relatórios completos: `docs/capacity-baseline-before.json` e `docs/capacity-baseline-after.json`.

## Meta de 25 mil usuários: todos os cenários

A configuração atual (SQLite e um processo Waitress com 8 threads) **não está certificada para 25 mil usuários simultâneos**. Antes de dimensionar produção, medir usuários conectados, usuários ativos, reproduções, bitrate e requisições por segundo separadamente.

| Cenário | Carga a considerar | Próxima etapa necessária |
|---|---|---|
| Abertura e navegação | Picos de login, catálogo, busca, imagens, SEO | CDN de assets; cache público versionado; paginação; índices e profiling; réplicas stateless com balanceamento |
| Filmes, séries e TV ao vivo | Segmentos, bitrate, origem e conexões longas | Object storage/CDN para mídia própria, HLS/DASH e ABR; validar origens externas; não transportar o vídeo inteiro pelo servidor de APIs |
| Progresso, favoritos e conta | Escritas concorrentes e múltiplos dispositivos | PostgreSQL, pool limitado, filas e operações idempotentes; manter autorização por usuário |
| Comunidade e mensagens | Feeds, notificações, presença, fan-out e uploads | Reduzir polling, eventos por WebSocket/SSE, Redis/pubsub, limites por conexão, filas para mídia e feeds paginados |
| Salas sincronizadas e chamadas | Estado por sala, sinalização, conexões e tráfego de áudio/vídeo | Serviço de tempo real, TURN e SFU conforme tamanho das chamadas; evitar malha entre muitos participantes |
| Pagamentos e administração | Webhooks repetidos, transações, consistência | Idempotência, filas de processamento, auditoria e testes de recuperação |
| PWA, Smart TV e emuladores | Memória/GPU do cliente, codecs, reconexão, teclas | Matriz de aparelhos reais, builds conforme navegadores suportados, player nativo quando disponível e degradação de efeitos |

Exemplos de orçamento, não medições de produção:

- 25.000 vídeos a 4 Mbps representam aproximadamente **100 Gbps** se todos forem entregues pela mesma origem, antes de overhead. CDN é determinante.
- Gravação periódica de progresso: 25.000 / 2,5 = 10.000 requisições/s antes; 25.000 / 15 ≈ 1.667 depois, além de ações imediatas. Ainda exige dimensionamento de escrita.
- Duas consultas sociais a cada 4 segundos, para 25.000 usuários ativos, representam cerca de 12.500 requisições/s. Há também presença e sincronização de chamadas/salas. Migrar apenas a renderização dessas telas para React não elimina esse tráfego.

Plano de validação: ambiente dedicado equivalente à produção; dados representativos; cenários separados e mistos; rampa gradual até 25 mil sessões; picos de entrada/reconexão e ensaio prolongado; coleta de p95/p99, erros, filas, CPU/RSS, conexões, locks, latência SQL, tempo até reprodução e rebuffering. Definir SLOs antes do teste. Não executar essa carga no site público ou em emissoras de terceiros sem autorização e limites acordados.

## Build e manutenção

Requer Node 22+ e npm apenas na máquina de build:

```sh
cd Streaming/frontend
npm ci
npm run check
```

O build atualiza `static/index.html`, gera `static/worktv-react-<hash>.js` e `frontend/build-manifest.json`. Publicar o bundle antes do HTML que o referencia. Não publicar `node_modules`. Manter bundles anteriores durante a transição dos clientes PWA.

Alvos de sintaxe atuais: Chrome 87 e Safari 15. Isso não comprova compatibilidade com todos os modelos de TV; navegadores anteriores precisam de estratégia específica e testes físicos. As verificações de controle remoto, foco, reprodução, offline e resoluções são feitas no Chromium automatizado.

Testes, a partir de `Streaming` com o ambiente Python do projeto:

```sh
python -m unittest discover -s tests -p 'test_react_migration.py'
python -m unittest discover -s tests -p 'test_seo.py'
python tests/react_browser_check.py
python tests/tv_browser_check.py
python tests/worktv_browser_check.py
python scripts/benchmark_capacity.py --requests 120 --concurrency 8 --titles 200
```

Executar os testes de navegador sequencialmente para não disputar a GPU de software. Eles usam bancos descartáveis, não as contas reais.

Configuração estática: `deploy/nginx-static.conf`, incluída no bloco do domínio; validar com `nginx -t` antes de recarregar. Mudanças em `app.py` exigem reiniciar `flix`; mudanças somente no bundle não exigem Node no servidor.

Referências: [adoção incremental oficial do React](https://react.dev/learn/add-react-to-an-existing-project) e [deploy de produção do Flask](https://flask.palletsprojects.com/en/stable/deploying/).

## Verificação da publicação

Publicado em https://flix.devspacey.com/ em 7 de outubro de 2026 (America/Sao_Paulo). Serviço Flask ativo e configuração Nginx validada antes do reload.

Validação pública: início, catálogo e detalhes em React; abertura com bootstrap atrasado sem exibir o catálogo textual; navegação TV por setas/OK; celular sem overflow; nenhum erro JavaScript observado. Na origem Nginx: bundle com gzip (96.823 bytes com o nível de compressão configurado), vídeo com Range/206, API com `no-store` e CSP mantida no HTML estático. A camada Cloudflare tem regras próprias de cache; o tamanho gzip do build usa um nível diferente do Nginx.

Regressões locais aprovadas: login, cadastro com e sem cupom, favoritos, reprodução MP4, conta, histórico, transições para comunidade/admin, botões disponíveis mesmo com SEO atrasado, fallback sem JavaScript, PWA offline/reconexão, controles TV e efeitos/interações do astronauta. Esses testes não representam uma certificação de 25 mil usuários ou de todos os modelos físicos de TV.

## Correção de recuperação da abertura (7 de outubro, 21h BRT)

Após relato de tela preta antes do login, foram verificadas abertura, recarga com PWA e catálogo no endereço público; não foi reproduzida a tela idêntica ao print. Não foi confirmada uma causa exclusiva no navegador do usuário.

A versão `recovery-20261007c` renova as URLs dos scripts e estilos e atualiza o cache público do PWA para `flix-shell-worktv-react-v3`. Inclui proteção de renderização do React e um script de recuperação independente: erro de renderização, arquivo principal interrompido ou inicialização sem conclusão exibem uma ação de recuperação. Uma resposta atrasada que termina com sucesso remove o aviso automaticamente. A recuperação limpa apenas caches públicos `flix-shell-*`, mantendo cookies e checkpoints locais, e não desregistra o service worker de notificações.

Teste isolado `tests/startup_recovery_check.py`: migração de cache antigo adulterado, exceção de componente, bundle interrompido, recuperação sem loop, checkpoint preservado e resposta atrasada aprovados. Regressão React de autenticação, player, rotas e celular aprovada.
