import { existsSync } from "node:fs";
import { spawnSync } from "node:child_process";

const python = process.platform === "win32"
  ? ".venv\\Scripts\\python.exe"
  : ".venv/bin/python";

if (!existsSync(python)) {
  console.error(`Python virtual environment not found at ${python}.`);
  console.error("Create it first with Python 3.11: python -m venv .venv");
  process.exit(1);
}

const result = spawnSync(python, process.argv.slice(2), {
  stdio: "inherit",
  env: process.env,
});

if (result.error) {
  console.error(result.error.message);
  process.exit(1);
}

process.exit(result.status ?? 1);