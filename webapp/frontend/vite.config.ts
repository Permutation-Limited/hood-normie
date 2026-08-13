import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Matches the Python server's default port; only `pnpm dev` reads this.
const API_PORT = 8765;

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "dist",
    emptyOutDir: true,
    // Bazel gives every build a clean sandbox, so a content hash is enough for
    // cache-busting and the manifest is unnecessary.
    sourcemap: false,
  },
  server: {
    // Only used by `pnpm dev`; the Bazel-built app is served by the Python server.
    proxy: { "/api": `http://127.0.0.1:${API_PORT}` },
  },
});
