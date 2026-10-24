import react from "@vitejs/plugin-react";
import { configDefaults, defineConfig } from "vitest/config";

// The dev server proxies /api to the BFF so the browser only ever talks to the
// application backend; AgentGuard is never reachable from the browser directly.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: process.env.VITE_PROXY_TARGET ?? "http://127.0.0.1:8001",
        changeOrigin: false,
      },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    globals: true,
    css: false,
    exclude: [...configDefaults.exclude, "e2e/**"],
  },
});
