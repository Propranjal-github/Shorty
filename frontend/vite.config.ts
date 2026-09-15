import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In development the Vite dev server proxies API calls to the backend so the
// SPA can use same-origin relative URLs. In production both are served behind
// the same origin (see docker-compose).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8000",
      "/health": "http://localhost:8000",
    },
  },
});
