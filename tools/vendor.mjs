// Copies the exact files the browser needs from node_modules into static/vendor.
// Run: npm ci && npm run vendor   (the result is committed, so running the app needs no Node)
import { cpSync, mkdirSync, readFileSync, rmSync } from 'node:fs';
const out = 'static/vendor';
rmSync(out, { recursive: true, force: true });
mkdirSync(`${out}/three/build`, { recursive: true });
mkdirSync(`${out}/three/addons/loaders`, { recursive: true });
mkdirSync(`${out}/three/addons/utils`, { recursive: true });
mkdirSync(`${out}/bootstrap`, { recursive: true });
const t = 'node_modules/three';
for (const f of ['three.module.js', 'three.core.js']) cpSync(`${t}/build/${f}`, `${out}/three/build/${f}`);
cpSync(`${t}/examples/jsm/loaders/GLTFLoader.js`, `${out}/three/addons/loaders/GLTFLoader.js`);
cpSync(`${t}/examples/jsm/utils/BufferGeometryUtils.js`, `${out}/three/addons/utils/BufferGeometryUtils.js`);
cpSync(`${t}/examples/jsm/utils/SkeletonUtils.js`, `${out}/three/addons/utils/SkeletonUtils.js`);
cpSync(`${t}/LICENSE`, `${out}/three/LICENSE`);
cpSync('node_modules/bootstrap/dist/css/bootstrap.min.css', `${out}/bootstrap/bootstrap.min.css`);
cpSync('node_modules/bootstrap/LICENSE', `${out}/bootstrap/LICENSE`);
console.log('vendored three', JSON.parse(readFileSync(`${t}/package.json`, 'utf8')).version);
