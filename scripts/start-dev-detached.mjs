import { closeSync, openSync } from "node:fs";
import { spawn } from "node:child_process";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";

export function startDetachedProcess(command, args, options) {
  const output = openSync(options.logFile, "a");

  return new Promise((resolvePid, reject) => {
    let child;
    try {
      child = spawn(command, args, {
        cwd: options.cwd ?? process.cwd(),
        env: options.env ?? process.env,
        detached: true,
        stdio: ["ignore", output, output],
      });
    } catch (error) {
      closeSync(output);
      reject(error);
      return;
    }

    closeSync(output);
    child.once("error", reject);
    child.once("spawn", () => {
      child.unref();
      resolvePid(child.pid);
    });
  });
}

const invokedPath = process.argv[1] ? pathToFileURL(resolve(process.argv[1])).href : "";

if (import.meta.url === invokedPath) {
  const logFile = process.argv[2];
  if (!logFile) {
    console.error("Usage: node scripts/start-dev-detached.mjs <log-file>");
    process.exitCode = 1;
  } else {
    const npmCommand = process.platform === "win32" ? "npm.cmd" : "npm";
    try {
      const pid = await startDetachedProcess(npmCommand, ["run", "dev"], { logFile });
      process.stdout.write(`${pid}\n`);
    } catch (error) {
      console.error(error instanceof Error ? error.message : String(error));
      process.exitCode = 1;
    }
  }
}
