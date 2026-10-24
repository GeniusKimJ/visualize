// 웹 UI를 번들해 안드로이드 앱 assets/www 로 복사
import { build } from 'esbuild';
import { copyFileSync, mkdirSync } from 'node:fs';

var out = '../android/app/src/main/assets/www';
mkdirSync(out, { recursive: true });

await build({
  entryPoints: ['src/main.js'],
  bundle: true,
  format: 'iife',
  target: ['chrome100'],
  minify: true,
  loader: { '.html': 'text' },
  outfile: out + '/app.js',
});
copyFileSync('index.html', out + '/index.html');
copyFileSync('style.css', out + '/style.css');
console.log('built →', out);
