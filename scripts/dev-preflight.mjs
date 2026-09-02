import { createConnection } from "node:net";

const services = [
  { name: "web app", port: Number(process.env.WEB_PORT ?? 5173) },
  { name: "catalog API", port: 4310 },
  { name: "agent API", port: 4320 },
  { name: "order API", port: 4330 },
  { name: "fraud API", port: 4340 },
  { name: "pneumonia API", port: 4350 },
];

function isListening(port) {
  return new Promise((resolve) => {
    const socket = createConnection({ host: "127.0.0.1", port });
    const finish = (listening) => {
      socket.destroy();
      resolve(listening);
    };

    socket.setTimeout(400);
    socket.once("connect", () => finish(true));
    socket.once("error", () => finish(false));
    socket.once("timeout", () => finish(false));
  });
}

const states = await Promise.all(
  services.map(async (service) => ({
    ...service,
    listening: await isListening(service.port),
  })),
);
const occupied = states.filter((service) => service.listening);

if (occupied.length > 0) {
  const ports = occupied
    .map((service) => `  - ${service.port}: ${service.name}`)
    .join("\n");
  const recovery = process.env.CODESPACES === "true"
    ? `Applied AI Studio starts automatically in Codespaces. Do not run npm run dev.
If the app is healthy, open port 5173 from the Ports tab. If it is not healthy,
stop and restart the codespace at https://github.com/codespaces, wait for it to
reconnect, and then open port 5173.`
    : `If the app is healthy, open http://127.0.0.1:5173. If it is not healthy:
  1. Return to the terminal running npm run dev and press Ctrl+C once.
  2. Wait for that command to return to the prompt.
  3. Run npm run dev once.`;

  console.error(`
Applied AI Studio did not start because another copy, or part of one, is still running.

Occupied ports:
${ports}

Do not start a second copy. Vite would otherwise create a different URL while the
APIs still belong to the first copy.

${recovery}
`);
  process.exitCode = 1;
}
