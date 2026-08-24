import app from "./app";
import { logger } from "./lib/logger";
import { spawn } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const rawPort = process.env["PORT"];

if (!rawPort) {
  throw new Error(
    "PORT environment variable is required but was not provided.",
  );
}

const port = Number(rawPort);

if (Number.isNaN(port) || port <= 0) {
  throw new Error(`Invalid PORT value: "${rawPort}"`);
}

function startLegacyDiscordBot() {
  const artifactDir = path.dirname(fileURLToPath(import.meta.url));
  const projectRoot = path.resolve(artifactDir, "../../..");
  const python = path.join(projectRoot, ".pythonlibs", "bin", "python");
  const bot = spawn(python, [path.join(projectRoot, "main.py")], {
    cwd: projectRoot,
    env: process.env,
    stdio: "inherit",
  });

  bot.on("error", (error) => logger.error({ error }, "Nigerian Legacy bot process failed to start"));
  bot.on("exit", (code, signal) => {
    if (code !== 0) logger.error({ code, signal }, "Nigerian Legacy bot process exited");
  });
}

app.listen(port, (err) => {
  if (err) {
    logger.error({ err }, "Error listening on port");
    process.exit(1);
  }

  logger.info({ port }, "Server listening");
  startLegacyDiscordBot();
});
