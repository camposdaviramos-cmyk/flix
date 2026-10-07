# Astronauta — versão 3 para Web

Modelo de referência refinado em GLB, pose T, com 52 ossos, dez materiais e três animações: `Float`, `Wave` e `WalkInPlace`. Tamanho: cerca de 7,3 MB; 171.152 triângulos. Frente +Z, eixo vertical Y, altura aproximada de 2,2 unidades.

A versão 3 corrige o tronco cilíndrico: o perfil frontal agora varia de cerca de 0,22 no alto do peito a 0,34 na barriga e volta a 0,22 no baixo ventre. Cinto, costuras e decalque seguem a mesma superfície e seus pesos. O visor segue a curvatura do casco, com uma faixa contínua fechando sua junção; a folga máxima de sua borda para o casco caiu para cerca de 0,021 unidade. A prévia inclui vista 3/4 e desmarca a vista fixa ao girar manualmente.

Esta versão substitui os volumes arredondados isolados do traje por mangas e pernas contínuas com dobras mais suaves. Inclui costuras em relevo, cinto com fivela, joelheiras com canais, botas com biqueira e detalhes na sola, mochila arredondada e anéis azuis polidos. O visor preto tem acabamento com clearcoat. Quatro PNGs estão embutidos no GLB: cor do tecido, microtrama normal, rugosidade e impressão WORK com transparência. Sem arquivos de textura externos.

O esqueleto mantém raiz, quadril, coluna, peito, pescoço, cabeça, clavículas, braços, antebraços, mãos, três falanges por dedo, coxas, canelas, pés e pontas dos pés. Os pesos do traje fazem transições nos cotovelos, joelhos e torso. Sem rig facial sob o visor opaco. O GLB contém ossos de deformação, sem controles de IK do Blender.

## Apresentação publicada

https://flix.devspacey.com/static/previews/astronauta-494d1355b7451e28724368dd/index.html?v=3

A página usa fundo claro, câmera ortográfica e ambiente com três softboxes para comparar melhor com as vistas da referência. Seus controles permitem girar e aproximar, selecionar vistas, trocar animações, usar pose T, pausar, mudar a velocidade, mostrar o esqueleto e baixar o GLB. Renderiza até 30 vezes por segundo; em pausa ou pose T só redesenha quando necessário. Suspende a renderização com a aba oculta.

A pasta estática é exclusiva desta apresentação. A publicação não altera templates, rotas, banco ou configuração do servidor e não reinicia o aplicativo. O endereço tem um identificador aleatório e a página declara `noindex`; qualquer pessoa com o link pode acessar. Sem autenticação adicional. Three.js 0.180.0 é servido localmente com sua licença MIT.

O carregador usa `TextureLoader` para as imagens PNG embutidas, respeitando a política existente do site que permite imagens `blob:` e bloqueia fetch de URLs `blob:`. A apresentação só declara o modelo pronto depois de confirmar que as quatro imagens foram carregadas.

`update_preview.py` salva a versão pública anterior em `backups/` e substitui atomicamente os quatro arquivos da apresentação. O endereço registrado em `preview.json` permanece igual. URLs com `?v=3` evitam reutilizar o script e o modelo anteriores em cache.

## Uso em Three.js

```js
import { AnimationMixer } from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

const gltf = await new GLTFLoader().loadAsync('/assets/astronauta.glb');
scene.add(gltf.scene);
const mixer = new AnimationMixer(gltf.scene);
mixer.clipAction(gltf.animations.find(clip => clip.name === 'Float')).play();
// No loop existente: mixer.update(deltaEmSegundos);
```

O visor precisa de um ambiente com painéis claros para reproduzir os reflexos da apresentação. Os reflexos não são pintados sobre a textura: mudam com o ponto de vista. As extensões usadas são `KHR_materials_clearcoat` e `KHR_materials_unlit` (impressão WORK).

## Regeneração e verificação

O gerador usa a biblioteca padrão do Python e Pillow para as texturas. Neste ambiente, Pillow foi instalado isoladamente em `/tmp/astronauta-tools`, sem alterar o ambiente do site. `geometry_v2.py` contém as superfícies e os materiais; `create_astronaut.py` cria o esqueleto, as animações e o GLB.

```sh
python3 create_astronaut.py
python3 validate.py
```

`validate.py` verifica chunks binários, limites de buffer, índices, normais unitárias, UVs, PNGs embutidos, pesos, matrizes de bind e animações. `inspect_v2.py` captura as vistas locais para revisão visual. `check_preview.py` usa o Playwright já disponível para testar a versão pública em desktop e mobile e conferir que a página inicial do site segue retornando HTTP 200.

## Limitações

O modelo é uma aproximação procedural da referência. Existem superfícies sobrepostas na união entre torso, luvas, capacete e acessórios. A caminhada é uma demonstração sem deslocamento da raiz e sem IK de contato com o chão. Refinamentos artísticos de topologia, silhueta, poses extremas e desempenho nos dispositivos de destino continuam possíveis.
