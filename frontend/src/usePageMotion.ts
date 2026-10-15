import { useEffect, useRef, useState } from 'react'

/** Scroll work is event-driven and batched into one frame, never an idle loop. */
export function usePageMotion(paused: boolean, landingVisible: boolean) {
  const shellRef = useRef<HTMLDivElement>(null)
  const [activeSection, setActiveSection] = useState('platform')

  useEffect(() => {
    const shell = shellRef.current
    if (!shell) return
    const hero = shell.querySelector<HTMLElement>('.landing-hero')
    const sections = ['platform', 'how-it-works', 'why-beyond']
      .map(id => document.getElementById(id)).filter((el): el is HTMLElement => Boolean(el))
    let frame = 0
    const update = () => {
      frame = 0
      const range = document.documentElement.scrollHeight - innerHeight
      const progress = range > 0 ? Math.min(1, Math.max(0, scrollY / range)) : 0
      shell.style.setProperty('--page-progress', String(progress))
      shell.classList.toggle('has-scrolled', scrollY > 24)
      // Only the decorative background moves. Controls stay in document flow.
      const heroBounds = hero?.getBoundingClientRect()
      const shift = !paused && heroBounds && heroBounds.bottom > 0
        ? Math.min(90, Math.max(0, -heroBounds.top) * 0.1) : 0
      shell.style.setProperty('--hero-shift', `${shift.toFixed(1)}px`)
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
    update()
    return () => {
      cancelAnimationFrame(frame)
      resize.disconnect()
      window.removeEventListener('scroll', schedule)
      window.removeEventListener('resize', schedule)
      shell.style.removeProperty('--hero-shift')
    }
  }, [paused, landingVisible])

  return { shellRef, activeSection }
}
