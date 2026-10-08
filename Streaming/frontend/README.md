# WorkTV React

Componentes reais em JSX para as rotas principais, autenticação, player e elementos compartilhados. Consulte [escopo, testes e capacidade](../docs/react-migration.md).

```sh
npm ci
npm run check
```

Node 22+ somente para build. O resultado está em `../static/worktv-react-<hash>.js`; `build.mjs` atualiza a referência em `../static/index.html`. Publicar também o JavaScript de integração `../static/app.js`. Nunca editar o bundle manualmente ou incluir `node_modules` na publicação.

`window.WorkTVUI` é a ponte temporária para os serviços existentes. `unmount`/`unmountModal` devem ser chamados antes de remover os respectivos contêineres. Os controladores de mídia e do astronauta mantêm seu próprio ciclo de limpeza. Novas telas devem ser escritas em React; módulos ainda legados estão identificados na documentação.

O build também empacota o runtime do astronauta e gera `.gz` dos bundles e do GLB otimizado. `npm run optimize:astro` reconstrói a malha web a partir do original, preservando os nomes dos ossos. Consulte [resultados e limitações](../docs/performance-security.md). A carteira e sua confirmação de compra já usam React; as APIs continuam Python.
