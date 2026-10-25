import assert from 'node:assert/strict'
import { afterEach, mock, test } from 'node:test'
import handler from './index.mjs'

const request = (options = {}) => new Request('https://function.example/', {
  method: 'POST', headers: { 'x-neon-trigger-invocation-id': 'test-invocation' },
  body: JSON.stringify({ data: { scheduled_at: '2026-10-25T09:00:00Z' } }), ...options,
})
afterEach(() => mock.restoreAll())

test('rejects public requests without calling the website', async () => {
  const upstream = mock.method(globalThis, 'fetch', () => assert.fail('Unexpected HTTP call'))
  assert.equal((await handler.fetch(request({ headers: {} }))).status, 403)
  assert.equal((await handler.fetch(new Request('https://function.example/'))).status, 405)
  assert.equal((await handler.fetch(request({ body: '{}' }))).status, 400)
  assert.equal(upstream.mock.callCount(), 0)
})

test('a scheduled invocation checks only the database-free liveness endpoint', async () => {
  const upstream = mock.method(globalThis, 'fetch', async (url, options) => {
    assert.equal(url, 'https://beyond-gtg4.onrender.com/api/v1/health/live')
    assert.ok(options.signal instanceof AbortSignal)
    return Response.json({ status: 'ok' })
  })
  const response = await handler.fetch(request())
  assert.equal(response.status, 200)
  const { latency_ms, ...result } = await response.json()
  assert.deepEqual(result, {
    ok: true, scheduled_at: '2026-10-25T09:00:00Z', status: 200,
  })
  assert.ok(Number.isInteger(latency_ms) && latency_ms >= 0)
  assert.equal(upstream.mock.callCount(), 1)
})

test('HTML gateway errors and network failures are reported as failed checks', async () => {
  const upstream = mock.method(globalThis, 'fetch', async () =>
    new Response('<html>Bad Gateway</html>', { status: 502 }))
  assert.equal((await handler.fetch(request())).status, 502)
  upstream.mock.mockImplementation(async () => { throw new Error('Network unavailable') })
  const response = await handler.fetch(request())
  assert.equal(response.status, 502)
  assert.equal((await response.json()).error, 'Website health check failed')
})
