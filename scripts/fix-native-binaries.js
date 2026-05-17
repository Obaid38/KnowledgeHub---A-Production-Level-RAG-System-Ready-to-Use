// scripts/fix-native-binaries.js
//
// npm workspaces hoists optional native binary packages to the root
// node_modules/, but Turbopack (running from client/) can't reach them there.
// This script copies each .node file into the package directory that loads it
// so the local fallback `require('../foo.node')` path succeeds.
//
// Run automatically via the root `postinstall` script after every `npm install`.

const fs   = require("fs");
const path = require("path");

const root   = path.resolve(__dirname, "..");
const client = path.join(root, "client", "node_modules");

const copies = [
  // lightningcss — used by @tailwindcss/postcss
  {
    src:  path.join(root, "node_modules", "lightningcss-linux-x64-gnu", "lightningcss.linux-x64-gnu.node"),
    dest: path.join(client, "lightningcss", "lightningcss.linux-x64-gnu.node"),
  },
  // @tailwindcss/oxide — used by @tailwindcss/postcss
  {
    src:  path.join(root, "node_modules", "@tailwindcss", "oxide-linux-x64-gnu", "tailwindcss-oxide.linux-x64-gnu.node"),
    dest: path.join(client, "@tailwindcss", "oxide", "tailwindcss-oxide.linux-x64-gnu.node"),
  },
];

let anyError = false;
for (const { src, dest } of copies) {
  try {
    if (!fs.existsSync(src)) {
      console.warn(`[fix-native] SKIP (src missing): ${src}`);
      continue;
    }
    const destDir = path.dirname(dest);
    if (!fs.existsSync(destDir)) {
      console.warn(`[fix-native] SKIP (dest dir missing): ${destDir}`);
      continue;
    }
    fs.copyFileSync(src, dest);
    console.log(`[fix-native] OK  ${path.relative(root, dest)}`);
  } catch (err) {
    console.warn(`[fix-native] WARN: ${err.message}`);
    anyError = true;
  }
}

if (anyError) {
  console.warn("[fix-native] Some binaries could not be copied — CSS compilation may fail.");
}
