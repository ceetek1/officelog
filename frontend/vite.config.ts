import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The entrance TV runs this in its built-in browser, which may be several years old.
// Keep the output conservative (decision D8): ES2019 syntax, older CSS.
export default defineConfig({
  plugins: [react()],
  build: {
    target: "es2019",
    cssTarget: "chrome61",
    outDir: "dist",
    sourcemap: false,
  },
  server: {
    port: 5173,
    proxy: { "/api": "http://localhost:8000" },
  },
});
