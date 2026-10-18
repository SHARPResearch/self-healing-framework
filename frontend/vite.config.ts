import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "path";

const ML_BACKEND = process.env.ML_BACKEND_URL ?? "http://localhost:8002";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    // services/ml-backend (uvicorn on :8002; the decision engine keeps :8000 and is called directly
    // by lib/api.ts). The app falls back to mock data when ml-backend isn't up.
    proxy: {
      "/api": ML_BACKEND,
      "/ws": { target: ML_BACKEND.replace(/^http/, "ws"), ws: true },
    },
  },
});
