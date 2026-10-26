import { execFileSync, spawn, type ChildProcess } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const frontendDir = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const backendDir = resolve(frontendDir, "../backend");
const pythonVenv = resolve(
  backendDir,
  process.platform === "win32" ? ".venv/Scripts/python.exe" : ".venv/bin/python",
);
const python = process.env.E2E_PYTHON ?? (existsSync(pythonVenv) ? pythonVenv : "python");
const stateFile = resolve(tmpdir(), "agentguard-qwb-app-playwright-runtime.json");

interface RuntimeState {
  processIds: number[];
  databaseDir: string;
}

function stopProcessTree(processId: number) {
  try {
    if (process.platform === "win32") {
      const taskkill = resolve(process.env.SystemRoot ?? "C:/Windows", "System32/taskkill.exe");
      execFileSync(taskkill, ["/PID", String(processId), "/T", "/F"], {
        stdio: "ignore",
        windowsHide: true,
      });
    } else {
      process.kill(-processId, "SIGTERM");
    }
  } catch {
    // The process may already have exited during a failed startup or test run.
  }
}

async function assertPortAvailable(port: number) {
  await new Promise<void>((resolvePort, rejectPort) => {
    const server = createServer();
    server.once("error", rejectPort);
    server.listen(port, "127.0.0.1", () => server.close((error) => {
      if (error) rejectPort(error);
      else resolvePort();
    }));
  });
}

function cleanRuntimeState() {
  if (!existsSync(stateFile)) return;
  try {
    const state = JSON.parse(readFileSync(stateFile, "utf8")) as RuntimeState;
    for (const processId of state.processIds) stopProcessTree(processId);
    rmSync(state.databaseDir, { recursive: true, force: true });
  } catch {
    // A partial runtime-state file must not prevent a fresh isolated run.
  }
  rmSync(stateFile, { force: true });
}

function startProcess(command: string, args: string[], cwd: string, env: NodeJS.ProcessEnv): ChildProcess {
  const child = spawn(command, args, {
    cwd,
    env,
    detached: process.platform !== "win32",
    stdio: "ignore",
    windowsHide: true,
  });
  return child;
}

async function waitForUrl(child: ChildProcess, url: string, label: string) {
  const deadline = Date.now() + 120_000;
  let launchError: Error | undefined;
  child.once("error", (error) => { launchError = error; });
  while (Date.now() < deadline) {
    if (launchError) throw launchError;
    if (child.exitCode !== null) throw new Error(`${label} exited during startup (${child.exitCode})`);
    try {
      const response = await fetch(url);
      if (response.ok) return;
    } catch {
      // The server is still starting.
    }
    await new Promise((resolveDelay) => setTimeout(resolveDelay, 250));
  }
  throw new Error(`${label} did not become ready within 120 seconds`);
}

export default async function globalSetup() {
  cleanRuntimeState();
  await assertPortAvailable(8101);
  await assertPortAvailable(8102);
  await assertPortAvailable(5173);
  const databaseDir = resolve(tmpdir(), `agentguard-qwb-e2e-${process.pid}`);
  mkdirSync(databaseDir, { recursive: true });
  const backend = startProcess(
    python,
    ["tests/e2e_server.py"],
    backendDir,
    {
      ...process.env,
      E2E_BFF_PORT: "8101",
      E2E_STUB_PORT: "8102",
      E2E_DATABASE_DIR: databaseDir,
    },
  );
  const frontend = startProcess(
    process.execPath,
    [resolve(frontendDir, "node_modules/vite/bin/vite.js"), "--host", "127.0.0.1", "--port", "5173"],
    frontendDir,
    { ...process.env, VITE_PROXY_TARGET: "http://127.0.0.1:8101" },
  );

  const state: RuntimeState = {
    processIds: [backend.pid, frontend.pid].filter((pid): pid is number => pid !== undefined),
    databaseDir,
  };
  writeFileSync(stateFile, JSON.stringify(state), "utf8");

  try {
    await waitForUrl(backend, "http://127.0.0.1:8101/api/health", "isolated BFF and Stub");
    await waitForUrl(frontend, "http://127.0.0.1:5173", "Vite frontend");
  } catch (error) {
    cleanRuntimeState();
    throw error;
  }
}
