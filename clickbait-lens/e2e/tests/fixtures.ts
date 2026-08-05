import { existsSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { type BrowserContext, type Worker, test as base, chromium } from "@playwright/test";

const EXTENSION_PATH = fileURLToPath(new URL("../../extension/dist", import.meta.url));
const API_BASE = "http://127.0.0.1:8901";

/**
 * Resolve a full Chromium build.
 *
 * Extensions do not load in the headless shell Playwright downloads by default,
 * and some environments pre-install browsers under PLAYWRIGHT_BROWSERS_PATH
 * with a different revision than the installed Playwright expects. Honour
 * `CHROMIUM_PATH` first, then look for a pre-installed full build, then fall
 * back to Playwright's own resolution.
 */
function chromiumExecutable(): string | undefined {
  if (process.env.CHROMIUM_PATH) return process.env.CHROMIUM_PATH;

  const root = process.env.PLAYWRIGHT_BROWSERS_PATH ?? "/opt/pw-browsers";
  if (!existsSync(root)) return undefined;
  const candidates = readdirSync(root)
    .filter((name) => name.startsWith("chromium-"))
    .map((name) => join(root, name, "chrome-linux", "chrome"))
    .filter((path) => existsSync(path));
  return candidates[0];
}

/**
 * Playwright fixtures that load the unpacked MV3 extension.
 *
 * Chrome only loads extensions from a persistent profile, so each test gets a
 * fresh persistent context with the built `dist/` directory loaded.
 */
export const test = base.extend<{
  context: BrowserContext;
  extensionId: string;
}>({
  // eslint-disable-next-line no-empty-pattern
  context: async ({}, use) => {
    const context = await chromium.launchPersistentContext("", {
      headless: true,
      executablePath: chromiumExecutable(),
      args: [
        `--disable-extensions-except=${EXTENSION_PATH}`,
        `--load-extension=${EXTENSION_PATH}`,
        "--no-first-run",
        "--no-default-browser-check",
      ],
    });

    // Point the extension at the test backend before any page loads.
    const worker = await extensionWorker(context);
    await worker.evaluate(async (apiBase) => {
      await chrome.storage.local.set({ apiBase, enabled: true, autoHighlight: true });
    }, API_BASE);

    await use(context);
    await context.close();
  },

  extensionId: async ({ context }, use) => {
    const worker = await extensionWorker(context);
    await use(new URL(worker.url()).host);
  },
});

/**
 * The extension's service worker, once its `chrome` APIs are actually usable.
 *
 * `serviceWorkers()` can hand back a worker whose global scope is still being
 * set up, so evaluating against it immediately intermittently fails with
 * `chrome.storage` undefined.
 */
async function extensionWorker(context: BrowserContext): Promise<Worker> {
  const deadline = Date.now() + 15_000;
  while (Date.now() < deadline) {
    const worker =
      context.serviceWorkers().find((candidate) => candidate.url().startsWith("chrome-extension://")) ??
      (await context.waitForEvent("serviceworker", { timeout: 5_000 }).catch(() => null));
    if (worker) {
      const ready = await worker
        .evaluate(() => typeof chrome !== "undefined" && Boolean(chrome.storage?.local))
        .catch(() => false);
      if (ready) return worker;
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error("The extension service worker never became ready");
}

export const expect = test.expect;
export { API_BASE };
