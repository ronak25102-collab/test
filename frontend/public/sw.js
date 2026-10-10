// Retire a legacy worker previously registered on this address. This app does
// not register a service worker or provide offline navigation responses.
self.addEventListener('install', () => self.skipWaiting())
self.addEventListener('activate', event => {
  event.waitUntil((async () => {
    await self.registration.unregister()
    const windows = await self.clients.matchAll({ type: 'window' })
    await Promise.allSettled(windows.map(client => client.navigate(client.url)))
  })())
})
