import assert from 'node:assert/strict';
import http from 'node:http';
import { test } from 'node:test';
import { backendIsRunning } from './dev.mjs';

for (const status of ['ready', 'initializing', 'error']) {
  test(`health check handles ${status}`, async () => {
    const server = http.createServer((_request, response) => {
      response.writeHead(status === 'ready' ? 200 : 503, { 'Content-Type': 'application/json' });
      response.end(JSON.stringify({ service: 'semantic-product-search', status, message: 'Model missing' }));
    });
    await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
    try {
      const port = server.address().port;
      if (status === 'error') {
        await assert.rejects(backendIsRunning(port), /Model missing.*Stop it/);
      } else {
        assert.equal(await backendIsRunning(port), true);
      }
    } finally {
      await new Promise((resolve) => server.close(resolve));
    }
  });
}
