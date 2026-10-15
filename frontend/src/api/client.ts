import type { Company, Report, RunSummary } from './generated'

export const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'

export class RequestError extends Error {
  constructor(message: string, public readonly status: number) { super(message) }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}/api/v1${path}`, init)
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new RequestError(body.message || 'Request failed', response.status)
  }
  return response.json()
}

export const api = {
  configuration: () => request<{ ready: boolean; issues: string[]; demo_time_warning: boolean }>('/health/configuration'),
  companies: (q: string) => request<{ items: Company[] }>(`/companies?q=${encodeURIComponent(q)}`),
  resolve: (query: string) => request<{ resolved: Company }>('/companies/resolve', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ query }) }),
  createRun: (company_id: string, as_of: string, mode: string, idempotencyKey: string = crypto.randomUUID()) => request<{ run_id: string }>('/runs', { method: 'POST', headers: { 'Content-Type': 'application/json', 'Idempotency-Key': idempotencyKey }, body: JSON.stringify({ company_id, as_of, mode }) }),
  run: (id: string) => request<RunSummary>(`/runs/${id}`),
  events: (id: string, after = 0) => request<{ items: { sequence: number; stage: string; public_summary: string }[]; next_cursor: number }>(`/runs/${id}/events?after=${after}`),
  report: (id: string) => request<Report>(`/runs/${id}/report`),
  cancel: (id: string) => request(`/runs/${id}/cancel`, { method: 'POST' }),
  queue: () => request<{ queued_count: number }>('/runs/queue'),
  clearQueue: () => request<{ cancelled_count: number; run_ids: string[] }>('/runs/queue/clear', { method: 'POST' }),
  resume: (id: string) => request(`/runs/${id}/resume`, { method: 'POST' }),
}
