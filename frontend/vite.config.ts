import path from "node:path";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

const apiTarget = process.env.API_PROXY_TARGET ?? "http://localhost:8000";
const fixturesDir = path.resolve(import.meta.dirname, "../backend/tests/fixtures");

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": path.resolve(import.meta.dirname, "src") } },
  optimizeDeps: {
    include: ["shiki/core", "shiki/engine/javascript", "shiki/langs", "shiki/themes"],
  },
  server: {
    host: "0.0.0.0",
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": { target: apiTarget, changeOrigin: true },
      "/healthz": { target: apiTarget, changeOrigin: true },
    },
    watch: { ignored: ["**/playwright-report/**", "**/test-results/**"] },
    fs: process.env.VITEST ? { allow: [".", fixturesDir] } : undefined,
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    coverage: {
      provider: "v8",
      include: ["src/features/analyze/**"],
      exclude: ["src/**/*.test.{ts,tsx}", "src/**/testData.ts"],
      thresholds: { lines: 80, branches: 80, functions: 80, statements: 80 },
    },
  },
});
