import { execFileSync } from "node:child_process";
import { existsSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { resolve } from "node:path";

const stateFile = resolve(tmpdir(), "agentguard-qwb-app-playwright-runtime.json");

interface RuntimeState {
  processIds: number[];
  databaseDir: string;
}

export default async function globalTeardown() {
  if (!existsSync(stateFile)) return;
  try {
    const state = JSON.parse(readFileSync(stateFile, "utf8")) as RuntimeState;
    for (const processId of state.processIds) {
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
        // A service may already have exited after a startup or test failure.
      }
    }
    rmSync(state.databaseDir, { recursive: true, force: true });
  } finally {
    rmSync(stateFile, { force: true });
  }
}
