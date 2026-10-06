import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// /api is proxied at dev/preview time. Default target: the mock server
// (frontend/mock/server.mjs, fixtures-driven). Point it at the real backend
// with VITE_PROXY_TARGET=http://localhost:8000 (S2 switch).
const target = process.env.VITE_PROXY_TARGET || "http://127.0.0.1:5175";
const proxy = { "/api": { target, changeOrigin: true } };

export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy },
  preview: { port: 4173, proxy },
  build: { outDir: "dist", chunkSizeWarningLimit: 1200 },
});
