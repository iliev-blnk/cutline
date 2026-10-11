import { resolve } from "node:path";
import { defineConfig } from "vite";

export default defineConfig({
  base: "/cutline/",
  build: {
    rollupOptions: {
      input: { index: resolve(__dirname, "index.html") },
    },
  },
  worker: { format: "es" },
});
