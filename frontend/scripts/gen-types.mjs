import { execSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const rootDir = path.resolve(__dirname, '../..');
const frontendDir = path.resolve(__dirname, '..');
const isCheck = process.argv.includes('--check');

// Find working python command
const pythonCmds = [
  'py -3.10',
  'python3',
  'python',
  'py',
  'C:\\Users\\Kavin\\AppData\\Local\\Programs\\Python\\Python310\\python.exe',
];
let exported = false;

for (const cmd of pythonCmds) {
  try {
    execSync(`${cmd} "${path.join(rootDir, 'backend', 'scripts', 'export_openapi.py')}"`, {
      stdio: 'inherit',
      cwd: rootDir,
      env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
    });
    exported = true;
    break;
  } catch (e) {
    // try next command
  }
}

if (!exported) {
  console.error('Failed to export openapi.json: no working Python interpreter found.');
  process.exit(1);
}

const checkFlag = isCheck ? '--check' : '';

try {
  execSync(`npx openapi-typescript ../openapi.json -o src/schema.d.ts ${checkFlag}`, {
    stdio: 'inherit',
    cwd: frontendDir,
  });
  console.log(`TypeScript schema types ${isCheck ? 'verified up to date' : 'generated successfully'}.`);
} catch (err) {
  console.error(`Type check/generation failed: ${err.message}`);
  process.exit(1);
}
