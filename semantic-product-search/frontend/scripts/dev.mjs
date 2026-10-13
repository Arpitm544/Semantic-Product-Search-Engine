import { spawn } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const scriptsDir = path.dirname(fileURLToPath(import.meta.url));
const frontendDir = path.resolve(scriptsDir, '..');
const projectDir = path.resolve(frontendDir, '..');
const python = process.env.PYTHON || (process.platform === 'win32' ? 'python' : 'python3');
const backend = spawn(python, ['backend/main.py'], { cwd: projectDir, stdio: 'inherit' });
const frontend = spawn(process.execPath, ['node_modules/next/dist/bin/next', 'dev', '-p', '3001'], {
  cwd: frontendDir,
  stdio: 'inherit',
});

let stopping = false;
function stop() {
  if (stopping) return;
  stopping = true;
  backend.kill('SIGTERM');
  frontend.kill('SIGTERM');
}

process.on('SIGINT', stop);
process.on('SIGTERM', stop);
backend.on('error', (error) => console.error(`Could not start backend (${python}): ${error.message}`));
backend.on('exit', (code) => {
  if (!stopping && code !== 0) {
    console.error(`Backend exited (${code ?? 'unknown status'}). Product search needs the API on port 8000.`);
  }
});
frontend.on('error', (error) => {
  console.error(`Could not start the frontend: ${error.message}`);
  stop();
});
frontend.on('exit', stop);
