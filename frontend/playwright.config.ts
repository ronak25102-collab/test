import { defineConfig } from '@playwright/test'
// The startup intro covers the page for ~5.4s. Reduced motion skips it, so most tests start on a usable page;
// tests that exercise the intro or full motion opt in with page.emulateMedia({ reducedMotion: 'no-preference' }).
export default defineConfig({ testDir: './tests', use: { baseURL: 'http://127.0.0.1:5173', channel: process.env.PLAYWRIGHT_CHANNEL, reducedMotion: 'reduce' }, webServer: { command: 'npm run dev', url: 'http://127.0.0.1:5173', reuseExistingServer: !process.env.CI } })
