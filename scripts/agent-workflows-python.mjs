// The agent workflow service has its own virtual environment so its Agent Framework
// dependencies never collide with the model services in the shared .venv.
import { existsSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { join } from "node:path";

const service = join("services", "agent-workflow-api");
const venv = join(service, ".venv");
const python = process.platform === "win32" ? join(venv, "Scripts", "python.exe") : join(venv, "bin", "python");

function run(command, args, options = {}) {
  const result = spawnSync(command, args, { stdio: "inherit", env: process.env, ...options });
  if (result.error) {
    console.error(result.error.message);
    process.exit(1);
  }
  if (result.status !== 0) process.exit(result.status ?? 1);
}

if (process.argv[2] === "--setup") {
  if (!existsSync(python)) {
    const base = process.env.PYTHON ?? (process.platform === "win32" ? "python" : "python3");
    run(base, ["-m", "venv", venv]);
  }
  run(python, ["-m", "pip", "install", "--upgrade", "pip"]);
  run(python, ["-m", "pip", "install", "-e", `${service}[dev]`]);
  console.log(`\nAgent workflow service ready. Copy ${service}/settings.example.json to settings.local.json to enable live runs.`);
  process.exit(0);
}

if (!existsSync(python)) {
  console.error(`Agent workflow environment not found at ${python}.`);
  console.error("Create it first: npm run setup:agent-workflows");
  process.exit(1);
}

const result = spawnSync(python, process.argv.slice(2), { stdio: "inherit", env: process.env });
if (result.error) {
  console.error(result.error.message);
  process.exit(1);
}
process.exit(result.status ?? 1);
