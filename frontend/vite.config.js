import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// base "./" and relative api/ paths keep the app working if Launchpad serves it under a sub-path.
export default defineConfig({
  plugins: [react()],
  base: "./",
  server: { proxy: { "/api": "http://127.0.0.1:7777" } },
});
