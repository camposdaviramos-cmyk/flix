# PostgreSQL, QR Code e perfis — WorkTV

Publicado em **8 de outubro de 2026, às 16h21 (Brasília)**, release `access-20261008a`.
A API continua em Python/Flask; as novas telas são React. O banco de produção agora é PostgreSQL 18.6. SQLite permanece apenas como alternativa de desenvolvimento e origem do backup da migração.

## Uso

- **QR Code:** abra Entrar → Entrar com QR Code no computador/TV. Escaneie com o celular, entre na conta se necessário e confirme o código e o aparelho. A outra tela conclui o login automaticamente. O código expira em cinco minutos.
- **Perfis:** menu da conta → Trocar perfil, ou `/perfis`. Cada conta possui de um a três perfis; cada perfil tem lista, histórico e progresso próprios. A assinatura, carteira e identidade da comunidade pertencem à conta. O limite de sessões do plano continua valendo independentemente dos três perfis.
- **Administradores:** entre em `/conta`, ative Verificação em duas etapas com um aplicativo autenticador e guarde os dez códigos de recuperação. Enquanto isso, APIs com privilégios administrativos ficam bloqueadas, inclusive caminhos da comunidade. Não existe segundo fator compartilhado ou ativado em nome do usuário.

## Controles ativos

- Conta PostgreSQL `worktv_app` sem superusuário, criação de banco ou criação de objetos; privilégios de dados separados da conta de migração. Banco e Redis escutam apenas em loopback. Pool de 1–12 conexões por processo, fila limitada e timeouts de consulta, bloqueio e transação ociosa.
- Redis autenticado, ACL limitada às chaves `worktv:*` e aos comandos necessários, AOF, memória máxima de 128 MB e política sem descarte de contadores. Limites atômicos compartilhados: 300 tentativas/IP e 15/IP+conta a cada 15 minutos; 60 por e-mail entre IPs. Configuração MFA usa a identidade autenticada. Redis indisponível impede novas tentativas de autenticação, sem liberar uma rota sem limite.
- Catálogo público com cache local e Redis, TTL de três segundos por camada (até aproximadamente seis segundos de defasagem entre processos); respostas pessoais nunca entram nesse cache. APIs continuam com `no-store`.
- MFA TOTP com segredo criptografado pela chave existente, proteção contra reutilização de códigos e dez códigos de recuperação armazenados como hashes e consumidos uma vez. Ativação/troca exige senha atual; troca/remoção exige também o fator anterior. Ativação revoga outras sessões. Administradores não podem desativar o fator pela API.
- QR com dois segredos distintos: autorização no fragmento da URL e segredo de resgate em cookie HttpOnly/Secure/SameSite. O banco guarda hashes. Aprovação autenticada e explícita, validade de cinco minutos, código de conferência, consumo único e vínculo à sessão autorizadora. Encerrar essa sessão revoga aprovações ainda não consumidas. Consulta limitada a 30/minuto por segredo do aparelho; interface consulta a cada quatro segundos.
- Limite de três perfis protegido pela transação e pelo banco (`slot` entre 1 e 3, exclusivo por conta). Verificação de titularidade em todas as operações; progresso atrasado de outro perfil é rejeitado.
- CSRF, validação de origem, CSP, HSTS, cookies protegidos e validação de autorização existentes preservados. Serviço com `ProtectSystem=strict`, escrita limitada à pasta de dados, proteção de diretórios pessoais, sem capabilities e sem novos privilégios. Chaves e arquivo de ambiente com permissão 0600.

## Migração e operação

`deployment-access.json` registra a troca. Foram comparados contagens e SHA-256 das linhas de **113 tabelas**, incluindo binários; **573 registros** e **40 triggers** foram migrados. A tabela de versão PostgreSQL acrescenta uma 114ª tabela. A origem passou nas verificações de integridade e de chaves estrangeiras. A manutenção durou 2,93 segundos. As sessões existentes e os segredos de integração foram preservados; o histórico anterior foi transferido ao perfil principal de cada conta.

- Driver: `postgres_backend.py`; conversão offline: `scripts/migrate_postgres.py`. O conversor abre a origem somente para leitura e recusa destino não vazio. Não colocar credenciais na linha de comando; usar `WORKTV_MIGRATION_DATABASE_URL` em ambiente protegido.
- Índices operacionais adicionais: `scripts/postgres_indexes.sql`, aplicados online na produção. Reaplicar depois de uma futura importação integral do SQLite.
- Ambiente do serviço: `data/runtime.env`, lido pelo drop-in `deploy/flix-postgres.conf`. **Não imprimir nem versionar esse arquivo.** A aplicação não recebe a senha de migração.
- O SQLite anterior permanece congelado no backup de corte. **Não voltar a apontar a aplicação para ele depois da reabertura do tráfego:** isso descartaria as operações recebidas no PostgreSQL. Depois da reabertura, corrigir adiante ou fazer uma migração reversa explícita dos dados mais recentes.
- `worktv-backup.timer` gera backup local diariamente por volta de **03h15 em Brasília**, com até cinco minutos de variação e retenção de 14 dias. Inclui dump PostgreSQL e cópia privada das chaves de criptografia/push. Uma cópia foi restaurada em banco isolado, com 114 tabelas, 40 triggers e nenhuma restrição inválida (`backup-restore-check.json`). Replicação criptografada para outro host ainda precisa ser configurada para proteção contra perda deste servidor.

## Validação reproduzível

```sh
python -m unittest discover -s tests -p 'test_*.py'
# WORKTV_TEST_DATABASE_URL deve apontar para um banco descartável, com permissão de criar schemas.
python tests/run_postgres_suite.py
python tests/account_access_browser_check.py
# WORKTV_TEST_REDIS_URL deve apontar para um Redis de testes.
python tests/security_store_check.py
```

Resultado final: **171/171 testes aprovados em SQLite; 168 aprovados e três exclusivos de SQLite ignorados em PostgreSQL**, sem falhas. O teste de 80 tentativas concorrentes no Redis aceitou exatamente 15; indisponibilidade simulada retornou 503 no login e manteve o catálogo público via PostgreSQL. Evidências em `access-validation.json`.

A suíte PostgreSQL usa um schema isolado por teste e o remove ao terminar. Três testes exclusivos de migração/trace SQLite são executados no backend SQLite. Os demais exercitam SQL, transações e triggers reais do PostgreSQL. O teste no Chromium usa contextos separados para celular e TV e cobre autorização QR, MFA, recuperação, criação dos três perfis e troca. A verificação pública em 720p/celular passou sem erros JavaScript, sem overflow e com respostas privadas protegidas.

## Limites que continuam relevantes

Esta entrega **não certifica 25 mil usuários simultâneos**, invulnerabilidade ou ausência de lag em todo dispositivo. Há somente um host de aplicação/banco, e operações compostas antigas ainda usam um advisory lock global para preservar sua atomicidade. Cache e limites são compartilháveis entre processos, mas arquivos de áudio/mídia privados ainda estão no disco local. Alta disponibilidade, armazenamento externo, observabilidade/alertas, auditoria de segurança independente e carga representativa com 25 mil usuários continuam necessários. Os testes descritos comprovam os fluxos e a integridade da migração, não aquela capacidade.


## Atualização: scanner e logo — qr-20261008b

O QR agora é gerado automaticamente ao abrir Entrar, ao lado da senha no computador/TV. No celular conectado, **Minha conta → Escanear QR Code** ou **Menu da conta → Escanear QR Code** abre `/escanear`. A câmera só é solicitada depois de tocar em Abrir câmera. O leitor também aceita uma imagem escolhida no próprio aparelho, sem enviar a imagem ao servidor. Só links de ativação da mesma origem são aceitos; a leitura conduz à conferência do aparelho e nunca aprova um acesso automaticamente.

O decoder jsQR 1.4.0 é servido localmente e carregado apenas ao usar o scanner. A câmera para após a leitura, ao ocultar a página ou ao sair dela. O teste usou os pixels de um QR real em um fluxo de câmera simulado no Chromium e concluiu o login em outro contexto; cobriu também permissão negada, leitura de imagem e encerramento das tracks. Não substitui testes físicos em todos os modelos de celular.

A logo PNG fornecida foi aplicada sem alterar seus bytes, no cabeçalho, rodapé, login, carregamento e tela offline. O favicon usa a mesma imagem; o manifesto PWA usa uma moldura SVG contendo a imagem original. Aplicativos já instalados dependem da atualização de ícones do sistema operacional.

HTML e APIs enviam `no-store` também para CDN. O service worker tem uma nova versão, não usa cache HTTP para navegações e remove os caches antigos da interface. Arquivos React/startup incompatíveis acionam recuperação visível. Nas próximas versões, uma aba aberta mostra um aviso para atualizar sem interromper automaticamente formulários ou vídeos. Para sair de uma aba antiga agora, abrir `/?_wt_reload=qr-20261008b`.

Evidências: `qr-scanner-release.json`. API: 15 testes aprovados; navegador: QR automático, senha visível, logo original, scanner, aprovação, câmera negada e imagem; recuperação de PWA antigo aprovada; site público verificado sem erros JavaScript observados.
