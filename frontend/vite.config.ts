import path from "node:path";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Em dev, /api vai para a API local: mesmo host, como em produção (proxy reverso).
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": path.resolve(import.meta.dirname, "./src") } },
  server: {
    proxy: { "/api": { target: process.env.VITE_API_PROXY_TARGET ?? "http://localhost:8000" } },
  },
});
