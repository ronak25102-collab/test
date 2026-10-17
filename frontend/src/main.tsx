import React from 'react'
import ReactDOM from 'react-dom/client'
import { App } from './pages/App'
import { removeLegacyLocalWorker } from './localServiceWorker'
import { SiteIntro } from './SiteIntro'
import './styles.css'
import './experience.css'
import './research-progress.css'
import './research-results.css'
import './scroll-details.css'

async function start() {
  let reload = false
  try { reload = await removeLegacyLocalWorker() } catch { /* Load normally if browser access is restricted. */ }
  if (reload) { location.reload(); return }
  ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><SiteIntro><App /></SiteIntro></React.StrictMode>)
}
void start()
