import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

// Local-only dev server. Proxies /api -> FastAPI backend on :8000
export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": path.resolve(__dirname, "src") } },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api/, ""),
      },
    },
  },
});
