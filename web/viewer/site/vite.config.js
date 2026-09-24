import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  base: "/rainier-seismic-atlas/",
  plugins: [react()],
  server: { host: "127.0.0.1", port: 5176 },
  preview: { host: "127.0.0.1", port: 4176 },
  test: {
    environment: "jsdom",
    setupFiles: ["src/test/setup.js"],
    include: ["src/**/*.test.{js,jsx}"],
  },
});
