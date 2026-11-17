import legacy from "@vitejs/plugin-legacy";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The entrance TV runs this in its built-in browser, which may be several years old.
// The modern bundle targets browsers from about 2019 (ES2019: Chrome 64+, Safari 12+), with
// polyfills for what they lack. The legacy bundle (with SystemJS and core-js) covers browsers too
// old for ES modules, such as older Samsung Tizen and LG webOS TVs. Phones get the modern one.
export default defineConfig({
  plugins: [
    react(),
    legacy({
      targets: ["chrome >= 47", "safari >= 11", "firefox >= 60"],
      modernTargets: ["chrome >= 64", "safari >= 12", "firefox >= 67", "edge >= 79"],
      modernPolyfills: true,
    }),
  ],
  build: {
    cssTarget: "chrome61",
    outDir: "dist",
    sourcemap: false,
  },
  server: {
    port: 5173,
    proxy: { "/api": "http://localhost:8000" },
  },
  test: {
    environment: "node",
  },
});
