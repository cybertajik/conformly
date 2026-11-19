import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vitest/config";
import { loadEnv } from "vite";

export default defineConfig(({ mode }) => ({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: loadEnv(mode, ".", "").CONFORMLY_DEV_API_TARGET ? {
      "/api": {
        target: loadEnv(mode, ".", "").CONFORMLY_DEV_API_TARGET,
        changeOrigin: true,
        rewrite: (path: string) => path.replace(/^\/api/, ""),
      },
    } : undefined,
  },
  test: {
    environment: "jsdom",
  },
}));
