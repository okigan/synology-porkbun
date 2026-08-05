import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Popup + background service worker. The content script is built separately
// (see vite.content.config.ts) because MV3 content scripts must be a single
// self-contained IIFE, not an ES module graph.
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "dist",
    emptyOutDir: true,
    rollupOptions: {
      input: {
        popup: "popup.html",
        background: "src/background/index.ts",
      },
      output: {
        entryFileNames: "[name].js",
        chunkFileNames: "assets/[name]-[hash].js",
        assetFileNames: "assets/[name][extname]",
      },
    },
  },
});
