export async function removeLegacyLocalWorker(): Promise<boolean> {
  if (!import.meta.env.DEV || !('serviceWorker' in navigator)) return false
  // This app has no service worker. Another app previously served on Vite's
  // localhost port can leave a root worker intercepting its navigations.
  const rootScope = `${location.origin}/`
  const registrations = await navigator.serviceWorker.getRegistrations()
  let removed = false
  for (const registration of registrations) {
    if (registration.scope === rootScope) removed = await registration.unregister() || removed
  }
  return removed && navigator.serviceWorker.controller !== null
}
