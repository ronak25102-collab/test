export function displayNumber(value?: string) {
  if (value == null) return 'Unavailable'
  const number = Number(value)
  return Number.isFinite(number) ? number.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : value
}

export function displayUnit(value?: string) {
  return value?.replaceAll('_', ' ') || ''
}
