# WorkTV e Astro

A identidade azul está em `static/worktv.css`. APIs, cookies e nomes internos existentes continuam compatíveis.

O Astro é um personagem interativo na página inicial. A abertura pública usa a paisagem aeroespacial gerada em `static/assets/worktv-world-v1.webp`, com planetas e terreno alienígena. O cenário não contém outro personagem. O sistema original de partículas, órbita e paralaxe foi reativado, acompanhado por névoa e meteoros animados em CSS. O usuário interage diretamente com o personagem: ele acompanha o cursor, acena durante seis segundos, faz um gesto com a cabeça e reage flutuando aos toques sucessivos. Ao passar o cursor na barriga, faz uma reação de cócegas, recolhendo os braços e balançando ombros e cabeça. A região sensível é projetada a partir do esqueleto, acompanha a rotação e funciona também com toque. Ao sair da região, a reação termina suavemente. Arrastar horizontalmente gira o corpo. As falas são curtas e desaparecem automaticamente. Não há painel, sugestões de catálogo, atalhos ou botão flutuante.

`static/worktv-guide.js` conserva o nome do arquivo/API interno para compatibilidade, mas recebe apenas a rota. Não acessa catálogo, dados do usuário ou ações de navegação. Na página de assinantes, o Astro tem um espaço separado abaixo do destaque, sem cobrir a imagem do filme.

`static/worktv/astro.js` reutiliza o GLB aprovado (`astro-v3.glb`, 52 ossos e quatro texturas embutidas) e Three.js 0.180.0. As reações usam curvas suaves e tempo real entre quadros, com início na primeira renderização da reação. Isso evita perder o gesto ou prolongá-lo indevidamente em dispositivos lentos. O canvas é reutilizado nas transições da aplicação; a renderização para fora da tela, fora da página inicial, em aba oculta e durante modais. A preferência de movimento reduzido do sistema também pausa o personagem. Não há botão de movimento na interface. Nesse caso, o toque continua mostrando uma resposta textual.

O carregamento é adiado até o personagem ficar visível. Em economia de dados, espera pelo toque. Em falha de WebGL/rede, mantém a imagem do modelo e a resposta ao toque. As texturas usam `TextureLoader`, respeitando a CSP atual. A licença do Three.js está em `static/worktv/vendor/LICENSE`.

Verificação em banco temporário:

```sh
/opt/flix/venv/bin/python tests/worktv_browser_check.py
```

O prompt final e a origem do cenário estão em `docs/worktv-world-image.md`. A preferência de movimento reduzido também se aplica aos efeitos do ambiente.
