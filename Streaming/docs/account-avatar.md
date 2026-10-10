# Avatar e menu da conta

A foto pode ser alterada em `/conta`, seção Foto da conta, com a comunidade ativada ou desativada. O seletor aceita JPG, PNG e WebP de até 8 MB; o navegador oferece prévia recortada ao centro e envia PNG de 256 x 256 após confirmação.

`GET/PUT/DELETE /api/account/avatar` exige autenticação e sempre utiliza o usuário da sessão. Escritas usam a proteção CSRF existente. O servidor valida formato, dimensões, CRC e descompressão limitada do PNG, restringe o armazenamento a 300 KB e remove metadados opcionais. Respostas não são armazenadas em cache.

O armazenamento existente é mantido, preservando fotos antigas e campos do perfil. A conta usa uma rota independente da comunidade para ler a própria foto. Remover a foto restaura a inicial do nome. Fotos indisponíveis também exibem a inicial.

O menu da conta tem estilos no CSS principal e fechamento por clique externo/Escape implementado em React. Não depende de bundles sociais. Mantém a classe reconhecida pela navegação de TV.

Validação: testes SQLite e PostgreSQL isolado, regressão de acesso e módulo comunidade, teste Chromium de desktop/celular com comunidade ligada e desligada, foto anterior, upload, persistência e remoção.
