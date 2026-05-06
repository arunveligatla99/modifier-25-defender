import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In dev (incl. ngrok tunnels), the UI fetches /healthz and /analyze
// as relative paths. Vite proxies them to the FastAPI backend on
// localhost:8000 so the browser sees same-origin requests and is not
// blocked by mixed-content (https UI -> http backend) or CORS.
const BACKEND_TARGET = "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    allowedHosts: ["hardening-library-barometer.ngrok-free.dev"],
    port: 5173,
    host: true,
    proxy: {
      "/healthz": { target: BACKEND_TARGET, changeOrigin: true },
      "/analyze": { target: BACKEND_TARGET, changeOrigin: true },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./tests/setup.ts"],
  },
});
