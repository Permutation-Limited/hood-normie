/**
 * Guards the contract between the Vite build and the Python server: the server
 * serves whatever is in dist/, so an empty or index-less bundle must fail here
 * rather than as a blank page in the browser.
 */
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

// Resolved from this file so the check does not depend on the test's cwd.
const dist = fileURLToPath(new URL("../dist", import.meta.url));

const index = readFileSync(join(dist, "index.html"), "utf8");
if (!index.includes('<div id="root">')) {
  throw new Error("dist/index.html is missing the #root container");
}
if (!/<script[^>]+src="[^"]+\.js"/.test(index)) {
  throw new Error("dist/index.html does not reference a bundled script");
}

const assets = readdirSync(join(dist, "assets"));
if (!assets.some((name) => name.endsWith(".js"))) {
  throw new Error("dist/assets contains no JavaScript bundle");
}

console.log(`dist looks servable: index.html + ${assets.length} asset(s)`);
