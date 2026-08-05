import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The content script is bundled as one IIFE with everything inlined, which is
// what Chrome requires for `content_scripts.js` entries.
export default defineConfig({
  plugins: [react()],
  // Lib mode does not substitute NODE_ENV, so React would ship its dev build.
  define: { "process.env.NODE_ENV": JSON.stringify("production") },
  build: {
    outDir: "dist",
    emptyOutDir: false,
    cssCodeSplit: false,
    lib: {
      entry: "src/content/index.tsx",
      name: "ClickbaitLens",
      formats: ["iife"],
      fileName: () => "content.js",
    },
  },
});
