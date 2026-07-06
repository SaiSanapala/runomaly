import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const backendTarget = process.env.BACKEND_PROXY_TARGET ?? "http://backend:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": backendTarget,
      "/health": backendTarget
    }
  }
});
