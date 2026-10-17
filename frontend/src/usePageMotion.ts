import { useEffect, useRef, useState } from 'react'
import { isPageDeferred, PAGE_REVEALED_EVENT } from './pageReveal'

/** Scroll work is event-driven and batched into one frame, never an idle loop. */
export function usePageMotion(paused: boolean, landingVisible: boolean) {
  const shellRef = useRef<HTMLDivElement>(null)
  const [activeSection, setActiveSection] = useState('platform')

  useEffect(() => {
    const shell = shellRef.current
    if (!shell) return
    const hero = shell.querySelector<HTMLElement>('.landing-hero')
    const scenerySections = Array.from(shell.querySelectorAll<HTMLElement>('.why-section, .landing-end'))
    const sections = ['platform', 'how-it-works', 'why-beyond']
      .map(id => document.getElementById(id)).filter((el): el is HTMLElement => Boolean(el))
    let frame = 0
    const update = () => {
      frame = 0
      if (isPageDeferred()) return
      const range = document.documentElement.scrollHeight - innerHeight
      const progress = range > 0 ? Math.min(1, Math.max(0, scrollY / range)) : 0
      shell.style.setProperty('--page-progress', String(progress))
      shell.classList.toggle('has-scrolled', scrollY > 24)
      // Depth belongs to artwork and badges; interactive controls stay in place.
      const heroBounds = hero?.getBoundingClientRect()
      const heroProgress = !paused && heroBounds ? Math.min(1, Math.max(0, -heroBounds.top / heroBounds.height)) : 0
      const motionScale = innerWidth <= 760 ? .5 : 1
      const shift = !paused && heroBounds && heroBounds.bottom > 0
        ? Math.min(90, Math.max(0, -heroBounds.top) * 0.1) : 0
      shell.style.setProperty('--hero-shift', `${shift.toFixed(1)}px`)
      shell.style.setProperty('--hero-scale', String(1.14 + heroProgress * .04 * motionScale))
      shell.style.setProperty('--badge-shift', `${(-heroProgress * 22 * motionScale).toFixed(1)}px`)
      for (const section of scenerySections) {
        const bounds = section.getBoundingClientRect()
        const through = Math.min(1, Math.max(0, (innerHeight - bounds.top) / (innerHeight + bounds.height)))
        section.style.setProperty('--section-drift', `${(paused ? 0 : (through - .5) * 24 * motionScale).toFixed(1)}px`)
      }
      let current = 'platform'
      for (const section of sections) {
        if (section.getBoundingClientRect().top <= innerHeight * 0.4) current = section.id
      }
      setActiveSection(previous => previous === current ? previous : current)
    }
    const schedule = () => { if (!frame) frame = requestAnimationFrame(update) }
    const resize = new ResizeObserver(schedule)
    resize.observe(document.documentElement)
    window.addEventListener('scroll', schedule, { passive: true })
    window.addEventListener('resize', schedule, { passive: true })
    window.addEventListener(PAGE_REVEALED_EVENT, update)
    update()
    return () => {
      cancelAnimationFrame(frame)
      resize.disconnect()
      window.removeEventListener('scroll', schedule)
      window.removeEventListener('resize', schedule)
      window.removeEventListener(PAGE_REVEALED_EVENT, update)
      shell.style.removeProperty('--hero-shift')
      shell.style.removeProperty('--hero-scale')
      shell.style.removeProperty('--badge-shift')
      scenerySections.forEach(section => section.style.removeProperty('--section-drift'))
    }
  }, [paused, landingVisible])

  return { shellRef, activeSection }
}
