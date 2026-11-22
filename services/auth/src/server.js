/**
 * SHARP web server: one origin for the browser.
 *
 *   /api/auth/*   Better Auth (sign up, sign in, organizations, invitations, /jwks, /token)
 *   /api/*, /ws/* proxied to ml-backend (it verifies the JWT itself; this is transport only)
 *   everything else  the built dashboard (frontend/dist), with index.html for client routes
 *
 * One origin keeps the session cookie first-party: on Render the dashboard and the auth service
 * would otherwise sit on two *.onrender.com hosts, which browsers treat as different sites.
 * In local development Vite serves the dashboard and proxies /api/auth here instead (STATIC_DIR
 * unset).
 */
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import express from "express";
import { createProxyMiddleware } from "http-proxy-middleware";
import { toNodeHandler } from "better-auth/node";
import { getMigrations } from "better-auth/db/migration";
import { auth, pool } from "./auth.js";

const PORT = Number(process.env.PORT ?? 8010);
const ML_BACKEND_URL = process.env.ML_BACKEND_URL ?? "http://localhost:8002";
const here = path.dirname(fileURLToPath(import.meta.url));
const STATIC_DIR = process.env.STATIC_DIR ? path.resolve(here, "..", process.env.STATIC_DIR) : null;

async function migrate() {
  const { toBeCreated, toBeAdded, runMigrations } = await getMigrations(auth.options);
  if (toBeCreated.length || toBeAdded.length) {
    console.log(`auth: migrating (${toBeCreated.map((t) => t.table).join(", ") || "new columns"})`);
    await runMigrations();
  }
}

const app = express();
app.disable("x-powered-by");
app.set("trust proxy", 1);                       // Render terminates TLS in front of us

app.get("/healthz", async (_req, res) => {
  try {
    await pool.query("SELECT 1");
    res.json({ status: "ok" });
  } catch (err) {
    res.status(503).json({ status: "db unavailable", error: String(err.message ?? err) });
  }
});

// Better Auth reads the raw body itself: no body parser before it.
app.all("/api/auth/{*rest}", toNodeHandler(auth));

const toBackend = createProxyMiddleware({
  target: ML_BACKEND_URL,
  changeOrigin: true,
  ws: true,
  pathFilter: ["/api/**", "/ws/**"],
  logger: console,
});
app.use(toBackend);

if (STATIC_DIR && existsSync(STATIC_DIR)) {
  app.use(express.static(STATIC_DIR, { index: false, maxAge: "1h" }));
  app.get("/{*rest}", (_req, res) => res.sendFile(path.join(STATIC_DIR, "index.html")));
  console.log(`serving the dashboard from ${STATIC_DIR}`);
}

await migrate();
const server = app.listen(PORT, () => console.log(`SHARP web on :${PORT}, ml-backend at ${ML_BACKEND_URL}`));
server.on("upgrade", toBackend.upgrade);        // the dashboard's WebSocket
