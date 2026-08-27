import assert from "node:assert/strict";
import { once } from "node:events";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import { spawn } from "node:child_process";
import test from "node:test";

const moduleUrl = pathToFileURL(join(import.meta.dirname, "start-dev-detached.mjs")).href;

async function waitFor(check, timeoutMs = 5_000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await check()) return;
    await new Promise((resolve) => setTimeout(resolve, 25));
  }
  throw new Error("Timed out waiting for detached process state.");
}

function processExists(pid) {
  try {
    process.kill(pid, 0);
    return true;
  } catch {
    return false;
  }
}

test("detached app survives SIGHUP when its lifecycle launcher exits", {
  skip: process.platform === "win32",
}, async (context) => {
  const directory = await mkdtemp(join(tmpdir(), "applied-ai-studio-detached-"));
  const logFile = join(directory, "child.log");
  let childPid;

  const childCode = `
    process.on("SIGHUP", () => {
      console.log("received-sighup");
      process.exit(42);
    });
    console.log("ready");
    setInterval(() => {}, 1_000);
  `;
  const launcherCode = `
    import { startDetachedProcess } from ${JSON.stringify(moduleUrl)};
    const pid = await startDetachedProcess(process.execPath, ["-e", ${JSON.stringify(childCode)}], {
      logFile: ${JSON.stringify(logFile)},
    });
    process.stdout.write(String(pid) + "\\n");
    setInterval(() => {}, 1_000);
  `;
  const launcher = spawn(process.execPath, ["--input-type=module", "-e", launcherCode], {
    detached: true,
    stdio: ["ignore", "pipe", "pipe"],
  });

  context.after(async () => {
    if (childPid && processExists(childPid)) process.kill(-childPid, "SIGKILL");
    if (processExists(launcher.pid)) process.kill(-launcher.pid, "SIGKILL");
    await rm(directory, { force: true, recursive: true });
  });

  let stdout = "";
  let stderr = "";
  launcher.stdout.setEncoding("utf8");
  launcher.stderr.setEncoding("utf8");
  launcher.stdout.on("data", (chunk) => { stdout += chunk; });
  launcher.stderr.on("data", (chunk) => { stderr += chunk; });
  await waitFor(() => stdout.includes("\n") || stderr.length > 0);
  childPid = Number.parseInt(stdout, 10);
  assert.ok(
    Number.isInteger(childPid) && childPid > 0,
    `launcher stdout: ${JSON.stringify(stdout)}\nlauncher stderr: ${JSON.stringify(stderr)}`,
  );

  await waitFor(async () => (await readFile(logFile, "utf8")).includes("ready"));
  process.kill(-launcher.pid, "SIGHUP");
  await once(launcher, "exit");
  await new Promise((resolve) => setTimeout(resolve, 100));

  assert.equal(processExists(childPid), true);
  assert.doesNotMatch(await readFile(logFile, "utf8"), /received-sighup/);
});
