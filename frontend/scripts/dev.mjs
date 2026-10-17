import { spawn } from 'node:child_process';
import path from 'node:path';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const scriptsDir = path.dirname(fileURLToPath(import.meta.url));
const frontendDir = path.resolve(scriptsDir, '..');
const projectDir = path.resolve(frontendDir, '..');
const backendDir = path.join(projectDir, 'backend');
const localPython = path.join(backendDir, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
const python = process.env.PYTHON || (existsSync(localPython) ? localPython : (process.platform === 'win32' ? 'python' : 'python3'));
const backend = spawn(python, ['api/main.py'], {
  cwd: backendDir,
  stdio: 'inherit',
  env: { ...process.env, TOKENIZERS_PARALLELISM: 'false', OMP_NUM_THREADS: '1', VECLIB_MAXIMUM_THREADS: '1' },
});
const frontend = spawn(process.execPath, ['node_modules/next/dist/bin/next', 'dev', '-p', '3001'], {
  cwd: frontendDir,
  stdio: 'inherit',
});

let stopping = false;
function stop(exitCode) {
  if (stopping) return;
  stopping = true;
  if (exitCode != null) process.exitCode = exitCode;
  backend.kill('SIGTERM');
  frontend.kill('SIGTERM');
}

process.on('SIGINT', stop);
process.on('SIGTERM', stop);
backend.on('error', (error) => {
  console.error(`Could not start backend (${python}): ${error.message}`);
  stop(1);
});
backend.on('exit', (code) => {
  if (stopping) return;
  if (code !== 0) console.error(`Backend exited (${code ?? 'unknown status'}). Product search needs the API on port 8000.`);
  else console.error('Backend exited unexpectedly. Product search needs the API on port 8000.');
  stop(1);
});
frontend.on('error', (error) => {
  console.error(`Could not start the frontend: ${error.message}`);
  stop(1);
});
frontend.on('exit', (code, signal) => {
  if (stopping) return;
  if (code !== 0) process.exitCode = code ?? 1;
  stop();
});
