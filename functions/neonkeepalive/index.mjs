// Neon Function Trigger -> Render liveness endpoint. No Postgres queries or secrets.
const HEALTH_URL = 'https://beyond-gtg4.onrender.com/api/v1/health/live'

export default {
  async fetch(request) {
    if (request.method !== 'POST') {
      return new Response('Method not allowed', { status: 405, headers: { Allow: 'POST' } })
    }
    // Neon strips client-supplied X-Neon-* headers at its public gateway.
    if (!request.headers.get('x-neon-trigger-invocation-id')) {
      return Response.json({ error: 'Scheduled trigger required' }, { status: 403 })
    }
    const payload = await request.json().catch(() => null)
    const scheduledAt = payload?.data?.scheduled_at
    if (typeof scheduledAt !== 'string' || Number.isNaN(Date.parse(scheduledAt))) {
      return Response.json({ error: 'Valid data.scheduled_at required' }, { status: 400 })
    }
    const started = performance.now()
    try {
      const response = await fetch(HEALTH_URL, {
        signal: AbortSignal.timeout(90_000), redirect: 'error',
      })
      const body = await response.json().catch(() => null)
      const ok = response.ok && body?.status === 'ok'
      const result = {
        ok, scheduled_at: scheduledAt, status: response.status,
        latency_ms: Math.round(performance.now() - started),
      }
      console.log(JSON.stringify(result))
      return Response.json(result, { status: ok ? 200 : 502 })
    } catch {
      const result = {
        ok: false, scheduled_at: scheduledAt, error: 'Website health check failed',
        latency_ms: Math.round(performance.now() - started),
      }
      console.warn(JSON.stringify(result))
      return Response.json(result, { status: 502 })
    }
  },
}
