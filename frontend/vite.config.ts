import { defineConfig } from "vite";

export default defineConfig({
  cacheDir: ".vite-cache",
  server: {
    host: "0.0.0.0",
    port: 5173,
  },
  build: {
    outDir: "dist",
  },
});
