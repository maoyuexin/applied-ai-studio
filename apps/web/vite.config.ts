import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: Number(process.env.WEB_PORT ?? 5173),
    proxy: {
      "/api/orders": {
        target: process.env["services__orders__http__0"] ?? "http://127.0.0.1:4330",
        configure: (proxy) => {
          proxy.on("proxyRes", (proxyResponse) => {
            proxyResponse.headers["x-accel-buffering"] = "no";
            proxyResponse.headers["cache-control"] = "no-cache";
          });
        },
      },
      "/api/catalog": process.env["services__catalog__http__0"] ?? "http://127.0.0.1:4310",
      "/api/agent": {
        target: process.env["services__agent__http__0"] ?? "http://127.0.0.1:4320",
        configure: (proxy) => {
          proxy.on("proxyRes", (proxyResponse) => {
            proxyResponse.headers["x-accel-buffering"] = "no";
            proxyResponse.headers["cache-control"] = "no-cache";
          });
        },
      },
    },
  },
});
