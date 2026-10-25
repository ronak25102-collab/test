import { useCallback, useEffect, useState } from 'react'

export const reportSections = ['overview', 'figures', 'calculations', 'sources', 'review'] as const
export type ReportSection = typeof reportSections[number]
export type AppRoute = { view: 'home' | 'workspace' | 'run' | 'progress' | 'report' | 'sign-in' | 'sign-up'; runId?: string; section?: ReportSection }

function readRoute(): AppRoute {
  const params = new URLSearchParams(location.search)
  const runId = params.get('run') || undefined
  const requested = params.get('view')
  const section = params.get('section') || location.hash.replace('#report-', '')
  if (requested === 'sign-in' || requested === 'sign-up') return { view: requested }
  if (runId) return {
    view: requested === 'report' || requested === 'progress' ? requested : 'run', runId,
    section: reportSections.includes(section as ReportSection) ? section as ReportSection : 'overview',
  }
  return { view: requested ? 'workspace' : 'home' }
}

export function routeHref(route: AppRoute) {
  const params = new URLSearchParams()
  if (route.view !== 'home' && route.view !== 'run') params.set('view', route.view)
  if (route.runId) params.set('run', route.runId)
  if (route.view === 'report') params.set('section', route.section || 'overview')
  return params.size ? `?${params}` : '/'
}

export function useAppRoute() {
  const [route, setRoute] = useState<AppRoute>(readRoute)
  useEffect(() => {
    const onPop = () => setRoute(readRoute())
    window.addEventListener('popstate', onPop)
    window.addEventListener('beyond:navigate', onPop)
    return () => { window.removeEventListener('popstate', onPop); window.removeEventListener('beyond:navigate', onPop) }
  }, [])
  const navigate = useCallback((next: AppRoute, options: { replace?: boolean; scroll?: boolean } = {}) => {
    const href = routeHref(next)
    if (`${location.search}${location.hash}` !== href) {
      if (options.replace) history.replaceState({}, '', href)
      else history.pushState({}, '', href)
    }
    setRoute(next)
    window.dispatchEvent(new Event('beyond:navigate'))
    if (options.scroll !== false) window.scrollTo({ top: 0, behavior: 'instant' })
  }, [])
  return { route, navigate }
}
