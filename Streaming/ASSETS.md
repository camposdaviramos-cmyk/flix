# Recursos visuais

## Hero original

Arquivo: `static/assets/hero.png`.

Criado com a ferramenta integrada de geração de imagens, usando a skill `imagegen` (sem CLI/API externa).

Prompt final:

> Create a premium cinematic film still for a black and red streaming service website hero. Very wide landscape 16:9. A lone astronaut in worn charcoal and ivory spacesuit stands on a rugged red desert ridge in the RIGHT THIRD foreground, gazing at a colossal dark eclipsed planet with a glowing crimson and warm orange atmospheric halo in the upper right. Dramatic epic science fiction, photorealistic IMAX cinematography, fine film grain, atmospheric dust, realistic terrain, deep black sky and subtle stars. LEFT HALF is very dark near-black empty atmospheric negative space to place website headline over it. Subject and planet are on the right half. Moody chiaroscuro, rich blacks, vermilion accents, muted sandy brown, visually sophisticated, beautiful highly detailed professional movie key art, no text, no logos, no typography, no watermark.

## Fotografias de demonstração

As URLs originais e IDs do Unsplash estão em `seed.py`. Os arquivos são armazenados localmente em `static/assets/{id}.jpg`, via `setup_assets.py`. Títulos e tipografia são renderizados em HTML/CSS, não fazem parte das fotos.

## Vídeo de demonstração

[Sintel — Blender Foundation](https://www.sintel.org/), trailer disponibilizado pelo W3C em `https://media.w3.org/2010/05/sintel/trailer.mp4`. Cópia local: `static/assets/sintel-trailer.mp4`. O player informa a origem e os detalhes dos títulos sinalizam a reprodução de amostra. Filme disponibilizado sob Creative Commons Attribution 3.0; autoria Blender Foundation / Sintel, sem alterações no vídeo.

© copyright Blender Foundation | www.sintel.org. [Condições de compartilhamento e atribuição](https://durian.blender.org/sharing/) · [Creative Commons Attribution 3.0](https://creativecommons.org/licenses/by/3.0/).

## Ícones e marca

Ícones SVG e identidade Flix criados em código no projeto. Fontes Outfit e DM Sans carregadas pelo Google Fonts, com fallback local sans-serif.

## Cenários dos jogos da comunidade — 03/10/2026

Criados com a ferramenta integrada de geração de imagens, seguindo a skill `imagegen`. São ilustrações originais, sem marcas de jogos de terceiros, sem texto embutido e com o centro livre para os controles reais.

- `static/assets/community/cinema-lounge.png`: lounge de cinema noturno, mesa oval de feltro verde-petróleo, madeira escura, latão, sofás bordô e luz quente. Usado no jogo de cartas **Cores**.
- `static/assets/community/artists-loft.png`: ateliê noturno com vista da cidade, luz índigo, bancada e moldura de madeira, pincéis e materiais artísticos nas bordas. Usado no jogo de desenho **Traço**.

Originais em PNG, 1536 × 1024. Versões WebP de mesmo nome, qualidade 84, produzidas por conversão de formato com FFmpeg e usadas no site (aproximadamente 180 KB cada). O baralho, a lousa, os controles, as animações e a tipografia são elementos reais de HTML/CSS/canvas, separados da imagem.


## Identidade Flix e aplicativo instalável

O monograma **F**, o favicon SVG e os ícones `flix-icon-192.png`, `flix-icon-512.png`, `flix-maskable.png` e `flix-badge.png` foram desenhados em código para esta atualização. São formas geométricas originais, sem imagens de terceiros; o ícone adaptável mantém o símbolo na área segura. Usados no PWA, na Tela de Início e em notificações.

## Editores de criação

As prévias, colagens, textos, figurinhas de link, recortes e a faixa de câmeras são construídos em HTML/CSS/canvas, sem novos bitmaps gerados. O editor utiliza as mídias enviadas pelo usuário. Capas retornadas na busca de música vêm do YouTube e identificam vídeos reproduzidos pelo player oficial.
