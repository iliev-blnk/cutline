import { resolve } from "node:path";
import { defineConfig } from "vite";

export default defineConfig({
  base: "/cutline/",
  build: {
    rollupOptions: {
      input: {
        index: resolve(__dirname, "index.html"),
        record: resolve(__dirname, "record.html"),
        method: resolve(__dirname, "method.html"),
      },
    },
  },
  worker: { format: "es" },
});
