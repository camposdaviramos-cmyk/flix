import {build} from 'esbuild';
import {gzipSync} from 'node:zlib';
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
const result=await build({entryPoints:['../static/worktv/astro.js'],bundle:true,minify:true,write:false,format:'esm',target:['chrome87','safari15'],legalComments:'eof'});
const bytes=result.outputFiles[0].contents,hash=createHash('sha256').update(bytes).digest('hex').slice(0,16),name=`astro-runtime-${hash}.js`;
await writeFile('../static/worktv/'+name,bytes);
let guide=await readFile('../static/worktv-guide.js','utf8');
guide=guide.replace(/import\('\/static\/worktv\/astro[^']*'\)/,`import('/static/worktv/${name}')`);await writeFile('../static/worktv-guide.js',guide);
console.log({file:name,bytes:bytes.length});

await writeFile('../static/worktv/'+name+'.gz',gzipSync(bytes,{level:9}));
const model=await readFile('../static/worktv/astro-web-v4.glb');
await writeFile('../static/worktv/astro-web-v4.glb.gz',gzipSync(model,{level:9}));
