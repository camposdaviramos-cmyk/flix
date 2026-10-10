# Módulo Comunidade

Controle em `/admin?tab=settings`, seção Comunidade. Padrão: ativado, preservando a instalação existente.
Persistência na tabela `settings`, chave `community_enabled` (`true`/`false`).
`GET/PUT /api/admin/modules/community` exige administrador, proteção CSRF e a política MFA administrativa já aplicada em produção. PUT aceita somente booleano JSON em `enabled`.

Quando desativado:
- Servidor retorna HTTP 503 com `code=community_disabled` para APIs community, social, jump, hub, music, wallet e suas áreas administrativas.
- Páginas `/comunidade`, `/sala` e `/carteira`, incluindo subcaminhos, exibem indisponibilidade e não são armazenadas em cache.
- Cadastro exclusivo da comunidade e novos checkouts de moedas ficam bloqueados. Webhooks de pagamentos existentes continuam funcionando.
- Entrega de notificações sociais fica pausada; registros armazenados são preservados.
- Navegação, botões e carregamento de bundles sociais ficam ocultos/desativados. Configurações permanece acessível para reativação.
- Abas ativas verificam alterações a cada 30 segundos e ao retornar ao primeiro plano. Uma mudança recarrega o documento para encerrar timers, mídia e conexões WebRTC existentes. Navegadores podem limitar temporizadores em segundo plano; as APIs já ficam bloqueadas no servidor. Requisições que já estavam em execução não são canceladas retroativamente.

Catálogo, reprodução individual, contas, até três perfis de streaming, QR login e assinaturas são independentes do módulo. Desativar não exclui publicações, usuários, salas ou saldos. Reativar restaura os acessos.

Validação: `tests/test_community_module.py` em SQLite e PostgreSQL temporário, `tests/community_module_browser_check.py` em Chromium (admin, celular, aba aberta, URLs diretas, reativação), além dos testes de PWA e recuperação de inicialização.

O menu administrativo também oculta todas as áreas sociais quando desativadas. O endereço antigo `?tab=modules` abre Configurações por compatibilidade.
