import react from "@vitejs/plugin-react";
import { execFileSync } from "node:child_process";
import { createReadStream, statSync } from "node:fs";
import type { IncomingMessage, ServerResponse } from "node:http";
import path from "node:path";
import { defineConfig, type Plugin } from "vite";

const ROOT = path.resolve(import.meta.dirname, "../..");

/** data/processed/web/, asked to the package's config.py: paths live there only. */
function webDir(): string {
  const code = "from segmentation_cartes_etat_major import config; print(config.WEB)";
  return execFileSync("uv", ["run", "--quiet", "python", "-c", code], {
    cwd: ROOT,
    encoding: "utf8",
  }).trim();
}

const TYPES: Record<string, string> = {
  ".png": "image/png",
  ".webp": "image/webp",
  ".json": "application/json",
  ".geojson": "application/geo+json",
};

/** Serves the web dir under /data/. A missing tile is a 204, not a 404: tiles with no
 * data are never written, so most edge requests miss and the console stays quiet. */
function serveWeb(dir: string): Plugin {
  const handler = (req: IncomingMessage, res: ServerResponse, next: () => void) => {
    const { pathname } = new URL(req.url ?? "/", "http://localhost");
    if (!pathname.startsWith("/data/")) return next();
    const rel = decodeURIComponent(pathname.slice("/data/".length));
    const file = path.join(dir, rel);
    const isTile = rel.startsWith("tiles/");
    if (!file.startsWith(dir + path.sep)) {
      res.statusCode = 403;
      return res.end();
    }
    let size: number;
    try {
      const stat = statSync(file);
      if (!stat.isFile()) throw new Error("not a file");
      size = stat.size;
    } catch {
      res.statusCode = isTile ? 204 : 404;
      return res.end();
    }
    res.setHeader("Content-Type", TYPES[path.extname(file)] ?? "application/octet-stream");
    res.setHeader("Content-Length", size);
    // tile URLs carry the layer's build version (?v=), so they can be cached for good
    res.setHeader("Cache-Control", isTile ? "public, max-age=31536000, immutable" : "no-cache");
    createReadStream(file).pipe(res);
  };
  return {
    name: "serve-processed-web",
    configureServer: (server) => void server.middlewares.use(handler),
    configurePreviewServer: (server) => void server.middlewares.use(handler),
  };
}

export default defineConfig({
  plugins: [react(), serveWeb(webDir())],
});
