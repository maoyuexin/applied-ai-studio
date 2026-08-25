import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// GitHub Codespaces serves this dev server through a forwarded HTTPS domain
// (https://<codespace>-5173.app.github.dev) rather than localhost. Two things have to
// change for that to work, and neither is visible until you actually open a codespace:
//
//  1. Vite must listen on every interface, not only loopback. Locally we keep the
//     loopback-only bind that docs/architecture.md requires; inside a codespace the
//     container is already isolated per student and forwarded ports are private by
//     default, so binding broadly adds no exposure.
//  2. Vite refuses requests whose Host header it does not recognise, so the forwarded
//     domain has to be allow-listed or students just see "Blocked request".
//
// HMR also has to be told the browser reaches it on 443, because the forwarded URL is
// HTTPS even though the server inside the container is plain HTTP.
const inCodespaces = process.env.CODESPACES === "true";
const forwardingDomain = process.env.GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN ?? "app.github.dev";

export default defineConfig({
  plugins: [react()],
  server: {
    host: inCodespaces ? true : "127.0.0.1",
    allowedHosts: inCodespaces ? [`.${forwardingDomain}`] : undefined,
    hmr: inCodespaces ? { clientPort: 443, protocol: "wss" } : undefined,
    port: Number(process.env.WEB_PORT ?? 5173),
    strictPort: true,
    proxy: {
      "/api/fraud": process.env["services__fraud__http__0"] ?? "http://127.0.0.1:4340",
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
