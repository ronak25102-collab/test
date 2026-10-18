export function displayNumber(value?: string) {
  if (value == null) return 'Unavailable'
  const number = Number(value)
  return Number.isFinite(number) ? number.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : value
}

export function displayUnit(value?: string) {
  return value?.replaceAll('_', ' ') || ''
}

export function displayMetric(value: string) {
  const known: Record<string, string> = { nim: 'NIM', nii: 'Net interest income', casa: 'CASA', ape: 'APE', vnb: 'VNB', gnpa: 'GNPA', nnpa: 'NNPA', segment_profit: 'Reported segment result', segment_profit_total: 'Total reported segment results', segment_revenue_total: 'Gross segment revenue total' }
  return known[value] || value.replaceAll('_', ' ').replace(/^./, letter => letter.toUpperCase())
}

// Research gaps are diagnostic prose; exact quoted evidence is never rewritten.
export function displayResearchGap(value: string) {
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
  const text = value.replace(/\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b/g, key => displayMetric(key).toLowerCase())
    .replace(/\b(\d{4})-(\d{2})-(\d{2})\b/g, (original, year, month, day) =>
      months[Number(month) - 1] ? `${Number(day)} ${months[Number(month) - 1]} ${year}` : original)
  return text.replace(/^./, letter => letter.toUpperCase())
}

export const calculationFormulas: Record<string, string> = {
  segment_revenue_share: 'named segment revenue / gross segment revenue total × 100; all components reconcile',
  segment_profit_share: 'named segment result / reported segment result total × 100; all components reconcile',
  segment_dependency_gap: 'segment result contribution − segment revenue contribution (percentage points); same reporting window',
  deposit_borrowing_mix: 'deposits / (deposits + borrowings) × 100; excludes other liabilities',
  deposit_borrowing_mix_change: 'current deposit share − prior deposit share (percentage points)',
  yoy_growth: '(current / prior − 1) × 100', change_pp: 'current − prior', change_bps: '(current − prior) × 100',
  growth_gap: 'growth of A − growth of B', ldr_change: 'current advances / deposits × 100 − prior advances / deposits × 100',
  funding_share: 'borrowing component / total borrowings × 100', profit_margin: 'net profit / revenue × 100', transaction_revenue_share: 'transaction revenue / total revenue × 100',
  vnb_to_ape: 'VNB / APE × 100', fee_yield: 'fee revenue / average AUM × 100', loan_to_deposit: 'advances / deposits × 100', share_pct: 'component / total × 100', cagr: '((end / start) ^ (1 / years) − 1) × 100',
}
