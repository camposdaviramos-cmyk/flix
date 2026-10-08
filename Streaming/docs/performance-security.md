# WorkTV: desempenho, segurança e capacidade

Atualização: 8 de outubro de 2026, UTC. Release `scale-20261008a`.

## Estado dos três objetivos

| Objetivo | Evidência disponível | O que falta para aceitar |
|---|---|---|
| 25 mil usuários simultâneos | Benchmark limitado do catálogo e ensaio misto de oito sessões, ambos com bancos descartáveis | Ambiente dedicado, dados representativos, geração distribuída de carga, teste prolongado e de picos de 25 mil sessões; dimensionamento de mídia, banco e tempo real |
| Segurança comparável à de grandes empresas | Correções de proxy, autenticação e CSRF; testes de autorização, pagamentos e SSRF; auditorias de dependências sem achados conhecidos | Revisão independente com escopo ASVS, MFA administrativo, gestão de segredos, monitoramento e resposta, limitação distribuída, restauração de backups comprovada e pentest |
| Carregamento ultrarrápido e sem travas | Menos bytes, malha simplificada, renderização WebGL suspensa em repouso e testes funcionais de efeitos/TV | Medições de campo e matriz de aparelhos reais, redes lentas, percentis de LCP/INP, frame time e rebuffering; a GPU de software ainda mostra quadros lentos |

**Nenhum desses três objetivos está certificado universalmente.** Migrar a interface para React não substitui dimensionamento de APIs, banco, mídia e infraestrutura. O servidor atual continua com um processo Waitress, oito threads e SQLite; não foi demonstrada capacidade de 25 mil usuários.

## Melhorias entregues nesta etapa

- Carteira e confirmação de compra em React, além das telas já migradas. APIs e validações de pagamentos continuam no backend. Comunidade, salas, mensagens e administração ainda possuem interfaces legadas.
- Módulos sociais/administrativos e HLS carregados conforme a rota, sessão e reprodução. O helper de campos compartilhado foi retirado da dependência do painel administrativo. Visitantes não baixam os editores da comunidade na abertura.
- Fontes hospedadas localmente com licenças OFL; remoção da dependência de Google Fonts na abertura.
- Astro: GLB de 7.324.696 para 1.337.608 bytes, triângulos de 171.152 para 53.514. Os 52 ossos e os dez materiais foram preservados. Arte original mantida; reconstrução pelo script `frontend/optimize-astro.mjs`.
- Runtime Three/GLTF/astro empacotado e minificado. DPR limitado a 1, ambiente de reflexão menor, compilação antecipada dos shaders. WebGL desenha quando há interação e deixa de executar quadros em repouso; flutuação por CSS. Aceno de seis segundos, cócegas e reação ao cursor preservados.
- Fundo continua animado, com menos partículas, resolução limitada e cadência reduzida. Preferência de movimento reduzido, aba oculta e navegação fora do início respeitadas.
- React, runtime Astro e GLB têm variantes gzip pré-geradas; Nginx usa `gzip_static`. Modelos, scripts antigos e caches não relacionados são preservados durante atualização do PWA.
- Cache **interno** do catálogo público: TTL de três segundos, máximo de 2 MB, um construtor por processo e invalidação após alterações administrativas. APIs continuam `no-store`; não há cache compartilhado de conta, carteira, sessão ou progresso. Alterações externas ao processo e contagem de espectadores podem demorar até três segundos para aparecer.
- Polling social continua em quatro segundos quando a interface está aberta e três durante chamada; passa a dez em repouso e vinte com aba oculta. Reduz tráfego ocioso, mas aumenta a latência da descoberta por polling nesse estado. Push e eventos de visibilidade continuam ativos. Ainda será necessária arquitetura de eventos para grande escala.

## Medições reproduzíveis

Navegador Chromium em localhost com banco descartável, uma abertura fria e **GPU de software**. Tamanhos abaixo são `decodedBodySize`, antes da compressão de transporte; não representam cobrança de rede ou resultado em um aparelho real. Os ensaios não usam limitação de banda. Resultados variam com o host.

| Medida | Antes | Final |
|---|---:|---:|
| Interface React visível | 743 ms | 488 ms |
| Astro pronto | 6.510 ms | 3.580 ms |
| Recursos decodificados | 14.577.025 bytes | 5.649.929 bytes |
| JavaScript decodificado | 3.708.517 bytes | 1.005.550 bytes |
| GLB | 7.324.696 bytes | 1.337.608 bytes |
| Tempo de bloqueio observado no intervalo | 9.804 ms | 6.556 ms |
| Intervalo entre quadros p95 no intervalo | 4.433,2 ms | 749,9 ms |
| Erros JavaScript | 0 | 0 |

Os dois últimos indicadores continuam ruins nesse renderizador por software. A redução é real, mas não demonstra ausência de travas. `home_ms` é o tempo até o seletor do início, **não é LCP**. O bloqueio é a soma de excessos de tarefas acima de 50 ms no intervalo observado, **não é o TBT padronizado do Lighthouse**. Evidências: `home-before.json`, `home-final.json` e respectivas capturas.

Catálogo: 300 requisições, concorrência 16, 200 séries sintéticas adicionais, oito threads, banco descartável, cache aquecido. Não é um teste de 300 usuários conectados nem de 25 mil usuários.

| Medida | Antes | Final |
|---|---:|---:|
| Requisições por segundo | 102,10 | 945,77 |
| Latência mediana | 152,68 ms | 16,04 ms |
| Latência p95 | 217,20 ms | 20,00 ms |
| Pico RSS do processo | 78,54 MiB | 78,64 MiB |
| Erros HTTP | 0 | 0 |

O cache melhorou o caminho repetido do catálogo; memória de pico ficou praticamente igual. A execução final termina antes do TTL, portanto não mede a capacidade sustentada com reconstruções contínuas. Evidências `catalog-before-final.json` e `catalog-after-final.json`.

## Segurança verificada e limites

- Nginx aceita `CF-Connecting-IP` apenas de redes Cloudflare confiáveis e sobrescreve `X-Forwarded-For` com o endereço validado. Waitress confia somente no Nginx em loopback. ProxyFix só é aplicado a um peer local. Cabeçalho enviado diretamente por cliente externo não escolhe seu IP para limitação de tentativas.
- Login faz verificação de hash também para conta inexistente; comprimento da senha é limitado. Check e incremento do rate limit são atômicos: 15 tentativas por IP+identidade e 300 por IP em 15 minutos, com `Retry-After`. A proteção por IP+identidade evita bloquear todos os usuários de um NAT após 15 tentativas, mas não resolve ataque distribuído contra uma identidade; depende de evolução da proteção na borda/MFA.
- Cookies de sessão `Secure` em HTTPS, `HttpOnly`, `SameSite=Lax`; HSTS no HTTPS. Host de produção validado. Escritas cross-site bloqueadas por Fetch Metadata, além dos controles existentes de Origin e cabeçalho de aplicação. Webhook de pagamento mantém sua exceção de origem e validação própria de assinatura.
- Suíte completa: 161 testes coletados, 160 passaram inicialmente; a única falha era expectativa antiga de nome no convite. Expectativa atualizada para a marca vigente e os 14 testes desse módulo passaram em seguida. Testes específicos de concorrência do login, cache e proxy incluídos.
- Auditoria Python de 32 pacotes encontrou avisos no pip 25.1.1; pip atualizado para 26.2.1. Nova auditoria: zero achados conhecidos. `npm audit` do lock atual: zero achados. Isso não detecta todas as falhas lógicas ou de configuração. Relatórios JSON anexos.
- Nenhuma senha real, token de teste ou cookie de usuário deve ser incluído em relatórios de carga. Os ensaios fornecidos criam sessões descartáveis e removem os arquivos ao terminar.

## Regressão de navegador

Aprovados: rotas React, carteira e confirmação de compra simulada, cadastro/cupons, recuperação de PWA antigo/falha de bundle, controle remoto de TV, resoluções 540p/720p/1080p/4K, MP4, offline/reconexão, Astro (aceno/cócegas/fundo), e roteiro móvel de salas (admissão, chat, enquetes, mudança de atividade, jogo, perfil, presente e saldo na carteira). Também aprovados: chat com áudio e figurinhas, chamada privada com voz/vídeo e consentimento, convite/entrada em live, compartilhamento de sala, troca de anfitrião e notificações. O teste social antigo usava nomes e seletores de uma versão anterior de salas; foi atualizado para os controles atuais. Os navegadores usam contas e bancos descartáveis. Nenhuma cobrança real é feita.

## Ensaios de carga e critérios de aceitação

Executar verificações pequenas no host de desenvolvimento:

```sh
python scripts/benchmark_capacity.py --requests 300 --concurrency 16 --titles 200 --output /tmp/catalog.json
python scripts/rehearse_capacity.py --k6 /caminho/para/k6 --users 8 --output /tmp/mixed.json
python scripts/profile_home.py --output /tmp/home.json
```

`rehearse_capacity.py` cria banco e sessões temporários, escuta somente em localhost, limita a 32 VUs e roda os quatro caminhos abaixo. O ensaio de validação executou oito VUs, 72 requisições e zero erros HTTP. O catálogo e as caixas de mensagens são pequenos: isso valida o roteiro, não capacidade.

`tests/load/capacity.js` aceita um ambiente isolado explícito e arquivo de fixtures com `identity` e `accounts` (`token`, `content_id`, um usuário diferente por VU). O destino deve responder ao marcador temporário `/__loadtest__/identity` com essa identidade. Esse endpoint existe apenas no runner descartável e **não é instalado na aplicação de produção**. O domínio público WorkTV é recusado, redirecionamentos são desativados e mais de 32 VUs exige `DEDICATED_LOAD_ENV=confirmed`. Para uma homologação real, provisionar fixtures e marcador exclusivamente no ambiente separado; limitar acesso aos tokens e removê-los após o ensaio.

Os quatro caminhos são distribuídos igualmente: visitante (bootstrap/catalog), conta (bootstrap/catalog/library), reprodução (autorização inicial e progresso a cada 15 s) e social (inbox/notificações a cada 4 s). O script nunca baixa a URL de vídeo retornada. Não mede entrada com senha, fan-out de mensagens, uploads, webhooks, salas, mídia ou WebRTC; esses cenários precisam de roteiros adicionais e dados representativos antes de certificar a meta completa.

SLOs propostos para APIs: erros abaixo de 0,1%, p95 abaixo de 300 ms e p99 abaixo de 1 s. Os thresholds estão no roteiro, mas passar em oito VUs não implica passar em 25 mil. Para homologação, usar rampa acordada (por exemplo 1k → 5k → 10k → 25k), patamar de pelo menos 30 minutos, pico de reconexão e ensaio prolongado. Capturar CPU, RSS, filas, conexões, locks, latência SQL, latência por endpoint e saturação do próprio gerador. Não extrapolar linearmente o benchmark curto.

Separar os testes de CDN/mídia (bitrate, origem, segmentos, tempo até primeiro quadro e rebuffering), tempo real (sinalização, TURN/SFU, perdas e reconexões), autenticação em pico, pagamentos idempotentes e operação degradada/failover. Vinte e cinco mil reproduções a 4 Mbps exigem aproximadamente 100 Gbps antes de overhead: entrega de mídia não deve depender deste processo de API.

Prioridades de infraestrutura: PostgreSQL para concorrência de escrita; pool limitado; Redis para limitação/cache/eventos distribuídos; réplicas de API sem estado local de coordenação; CDN/object storage; filas de mídia; observabilidade, alertas, backups e recuperação; TURN/SFU conforme topologia de chamadas. São mudanças ainda pendentes, com migração e validação próprias.

## Fontes técnicas

- [OWASP ASVS](https://github.com/owasp/asvs): base para revisão de controles, sem alegação de certificação.
- [Cloudflare: cabeçalhos HTTP](https://developers.cloudflare.com/fundamentals/reference/http-headers/) e [faixas IP oficiais](https://www.cloudflare.com/ips/): confiança do proxy; revisar o arquivo de redes periodicamente.
- [k6: ramping VUs](https://grafana.com/docs/k6/latest/using-k6/scenarios/executors/ramping-vus/) e [thresholds](https://grafana.com/docs/k6/latest/using-k6/thresholds/): carga e critérios automatizados.

## Publicação e conferência na origem

Publicado em https://flix.devspacey.com/ em 8 de outubro de 2026 às 04:18 UTC. Backup dos arquivos alterados em `Streaming/data/backups/scale-20261008T041825Z`, com manifesto para rollback. Nginx validado e recarregado; serviço ativo sem reinícios automáticos observados.

Checagem pública de leitura aprovada: início React, novo modelo com 52 ossos, renderização WebGL em repouso suspensa, módulos adiados para visitante, catálogo após recarga, celular sem overflow e zero erros JavaScript observados. Na origem, gzip confirmado por descompressão e comparação binária: React 83.375 bytes, runtime Astro 146.707 bytes e GLB 586.906 bytes. CSP, HSTS, `no-store` nas APIs e bloqueio 401 da biblioteca sem sessão verificados. Relatório `deployment-scale.json`. A compressão do arquivo pré-gerado usa nível 9; o tamanho gzip informativo do manifesto React usa o nível padrão e por isso difere.
