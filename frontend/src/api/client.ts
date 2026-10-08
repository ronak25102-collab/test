import type { Company, Report, RunSummary } from './generated'

export const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}/api/v1${path}`, init)
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.message || 'Request failed')
  }
  return response.json()
}

export const api = {
  companies: (q: string) => request<{ items: Company[] }>(`/companies?q=${encodeURIComponent(q)}`),
  createRun: (company_id: string, as_of: string, mode: string) => request<{ run_id: string }>('/runs', { method: 'POST', headers: { 'Content-Type': 'application/json', 'Idempotency-Key': crypto.randomUUID() }, body: JSON.stringify({ company_id, as_of, mode }) }),
  run: (id: string) => request<RunSummary>(`/runs/${id}`),
  events: (id: string, after = 0) => request<{ items: { sequence: number; stage: string; public_summary: string }[]; next_cursor: number }>(`/runs/${id}/events?after=${after}`),
  report: (id: string) => request<Report>(`/runs/${id}/report`),
  cancel: (id: string) => request(`/runs/${id}/cancel`, { method: 'POST' }),
}
