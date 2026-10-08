import { build } from "esbuild";
import { createHash } from "node:crypto";
import { readFile, writeFile, mkdir } from "node:fs/promises";
import { gzipSync } from "node:zlib";
import { fileURLToPath } from "node:url";
const root = fileURLToPath(new URL("../", import.meta.url));
const result = await build({
  absWorkingDir: fileURLToPath(new URL(".", import.meta.url)),
  entryPoints: ["src/index.jsx"],
  bundle: true,
  write: false,
  minify: true,
  legalComments: "eof",
  format: "iife",
  target: ["chrome87", "safari15"],
  define: { "process.env.NODE_ENV": '"production"' },
  metafile: true,
});
const bytes = result.outputFiles[0].contents,
  hash = createHash("sha256").update(bytes).digest("hex").slice(0, 16),
  name = `worktv-react-${hash}.js`;
await mkdir(root + "static", { recursive: true });
await writeFile(root + "static/" + name, bytes);
const tag = `<script data-worktv-react src="/static/${name}?v=${hash}" defer></script>`;
const path = root + "static/index.html";
let html = await readFile(path, "utf8");
html = html.includes("data-worktv-react")
  ? html.replace(/<script data-worktv-react[^>]*><\/script>/, tag)
  : html.replace(
      '  <script src="/static/app.js',
      `  ${tag}\n  <script src="/static/app.js`,
    );
await writeFile(path, html);
const manifest = {
  file: name,
  sha256: createHash("sha256").update(bytes).digest("hex"),
  bytes: bytes.length,
  gzipBytes: gzipSync(bytes).length,
};
await writeFile(
  root + "frontend/build-manifest.json",
  JSON.stringify(manifest, null, 2) + "\n",
);
console.log(manifest);

// Precompressed immutable assets reduce origin CPU and transfer size.
await writeFile(root + "static/" + name + ".gz", gzipSync(bytes, {level:9}));
