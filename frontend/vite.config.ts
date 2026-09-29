import { copyFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath, URL } from "node:url";
import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";

const modules = fileURLToPath(new URL("./node_modules", import.meta.url));

/** Files copied into the build: the API docs UI (served by the backend at /api/docs instead of
 * a CDN) and the licences of bundled third-party assets. */
const STATIC_COPIES: Array<[string, string]> = [
  ["swagger-ui-dist/swagger-ui-bundle.js", "swagger/swagger-ui-bundle.js"],
  ["swagger-ui-dist/swagger-ui.css", "swagger/swagger-ui.css"],
  ["swagger-ui-dist/LICENSE", "swagger/LICENSE"],
  ["swagger-ui-dist/NOTICE", "swagger/NOTICE"],
  ["@fontsource/ibm-plex-sans/LICENSE", "licenses/ibm-plex-sans-OFL.txt"],
  ["@fontsource/ibm-plex-mono/LICENSE", "licenses/ibm-plex-mono-OFL.txt"],
  ["@fontsource-variable/source-serif-4/LICENSE", "licenses/source-serif-4-OFL.txt"],
];

function staticCopies(): Plugin {
  return {
    name: "ecce-static-copies",
    apply: "build",
    writeBundle(options) {
      const out = options.dir ?? "dist";
      for (const [from, to] of STATIC_COPIES) {
        mkdirSync(join(out, to, ".."), { recursive: true });
        copyFileSync(join(modules, from), join(out, to));
      }
    },
  };
}

// API requests are relative ("/api/..."); in development they are proxied to the backend.
export default defineConfig({
  plugins: [react(), staticCopies()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: process.env.VITE_API_PROXY ?? "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: false,
    chunkSizeWarningLimit: 900,
  },
});
