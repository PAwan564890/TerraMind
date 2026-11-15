import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const proxy = {
    "/api": {
      target: env.TERRAMIND_PROXY_TARGET || "http://127.0.0.1:8000",
      changeOrigin: true,
      rewrite: (path: string) => path.replace(/^\/api/, ""),
    },
  };
  return {
    plugins: [react()],
    build: {
      rollupOptions: { output: { manualChunks: (id: string) => id.includes("/node_modules/") && /recharts|d3-|victory|internmap|redux|immer|reselect/.test(id) ? "charts" : undefined } },
    },
    server: { port: 5173, strictPort: true, proxy },
    preview: { host: "127.0.0.1", port: 4173, strictPort: true, proxy },
  };
});
