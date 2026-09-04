import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

const proxyTarget = process.env.VITE_PROXY_TARGET || "http://localhost:8000";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: true,
    port: 5173,
    // sandbox preview proxies (e.g. 5173-<id>.e2b.app); dev server only
    allowedHosts: ['.e2b.app', 'localhost'],
    proxy: {
      "/health": { target: proxyTarget, changeOrigin: true },
      "/api": { target: proxyTarget, changeOrigin: true },
    },
  },
});
