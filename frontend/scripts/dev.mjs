import { spawn } from 'node:child_process';
import http from 'node:http';
import path from 'node:path';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const scriptsDir = path.dirname(fileURLToPath(import.meta.url));
const frontendDir = path.resolve(scriptsDir, '..');
const backendDir = path.resolve(frontendDir, '../backend');

export function backendIsRunning(port) {
  return new Promise((resolve, reject) => {
    const request = http.get({ host: '127.0.0.1', port, path: '/api/health', agent: false }, (response) => {
      let body = '';
      response.setEncoding('utf8');
      response.on('data', (chunk) => {
        body += chunk;
        if (body.length > 65536) request.destroy(new Error('Unexpected health response.'));
      });
      response.on('error', reject);
      response.on('end', () => {
        try {
          const health = JSON.parse(body);
          // A 503 response also identifies our backend while models are loading.
          if (health.service === 'semantic-product-search') {
            resolve(true);
            return;
          }
        } catch {}
        reject(new Error(`Port ${port} is occupied by another service. Stop it before starting the backend.`));
      });
    });
    request.setTimeout(3000, () => {
      request.destroy(new Error(`Port ${port} did not answer the health check. Check the process using that port.`));
    });
    request.on('error', (error) => {
      if (error.code === 'ECONNREFUSED') resolve(false);
      else reject(error);
    });
  });
}

async function main() {
  const port = Number(process.env.PORT || 8000);
  const reuseBackend = await backendIsRunning(port);
  let backend;
  if (reuseBackend) {
    console.log(`Using the existing backend at http://127.0.0.1:${port}.`);
  } else {
    const localPython = path.join(backendDir, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
    const python = process.env.PYTHON || (existsSync(localPython) ? localPython : (process.platform === 'win32' ? 'python' : 'python3'));
    backend = spawn(python, ['api/main.py'], {
      cwd: backendDir,
      stdio: 'inherit',
      env: { ...process.env, PORT: String(port), TOKENIZERS_PARALLELISM: 'false', OMP_NUM_THREADS: '1', VECLIB_MAXIMUM_THREADS: '1' },
    });
  }

  const frontend = spawn(process.execPath, ['node_modules/next/dist/bin/next', 'dev', '-p', '3001'], {
    cwd: frontendDir,
    stdio: 'inherit',
  });

  let stopping = false;
  function stop(exitCode = 0) {
    if (stopping) return;
    stopping = true;
    process.exitCode = exitCode;
    // Only stop processes started by this launcher.
    backend?.kill('SIGTERM');
    frontend.kill('SIGTERM');
  }

  process.on('SIGINT', () => stop());
  process.on('SIGTERM', () => stop());
  backend?.on('error', (error) => {
    console.error(`Could not start backend: ${error.message}`);
    stop(1);
  });
  backend?.on('exit', (code) => {
    if (stopping) return;
    console.error(`Backend exited (${code ?? 'unknown status'}). Product search needs the API on port ${port}.`);
    stop(1);
  });
  frontend.on('error', (error) => {
    console.error(`Could not start the frontend: ${error.message}`);
    stop(1);
  });
  frontend.on('exit', (code) => {
    if (!stopping) stop(code ?? 1);
  });
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch((error) => {
    console.error(error.message);
    process.exitCode = 1;
  });
}
