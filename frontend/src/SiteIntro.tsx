import { type CSSProperties, type ReactNode, useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import './site-intro.css'

const shouldPlay = () => !window.matchMedia('(prefers-reduced-motion: reduce)').matches
  && new URLSearchParams(location.search).get('print') !== '1'

/** A fresh intro for each document visit; in-app navigation keeps the app mounted. */
export function SiteIntro({ children }: { children: ReactNode }) {
  const [playing, setPlaying] = useState(shouldPlay)
  const finish = useCallback(() => setPlaying(false), [])
  const introRef = useRef<HTMLDivElement>(null)
  const stageRef = useRef<HTMLDivElement>(null)
  const logoRef = useRef<HTMLSpanElement>(null)

  useLayoutEffect(() => {
    if (!playing) return
    const position = () => {
      const intro = introRef.current
      const stage = stageRef.current?.getBoundingClientRect()
      const logo = logoRef.current?.getBoundingClientRect()
      if (!intro || !stage || !logo) return
      // Land above the first b's bowl, in the same position as the logo's cross.
      intro.style.setProperty('--dock-x', `${logo.left + logo.width * 23 / 32 - innerWidth / 2}px`)
      intro.style.setProperty('--dock-y', `${logo.top + logo.height * 6 / 32 - innerHeight / 2}px`)
      intro.style.setProperty('--dock-scale', String((logo.width * 8 / 32) / (stage.width * 100 / 120)))
      intro.style.setProperty('--logo-center-x', `${innerWidth / 2 - logo.left - logo.width / 2}px`)
      intro.style.setProperty('--logo-center-y', `${innerHeight / 2 - logo.top - logo.height / 2}px`)
    }
    position()
    window.addEventListener('resize', position)
    return () => window.removeEventListener('resize', position)
  }, [playing])

  useEffect(() => {
    const onPageShow = (event: PageTransitionEvent) => {
      if (event.persisted) setPlaying(shouldPlay())
    }
    window.addEventListener('pageshow', onPageShow)
    return () => window.removeEventListener('pageshow', onPageShow)
  }, [])

  useEffect(() => {
    if (!playing) return
    const preference = window.matchMedia('(prefers-reduced-motion: reduce)')
    const onPreference = () => { if (preference.matches) finish() }
    const onKey = (event: KeyboardEvent) => { if (event.key === 'Escape') finish() }
    const previousOverflow = document.documentElement.style.overflow
    document.documentElement.style.overflow = 'hidden'
    preference.addEventListener('change', onPreference)
    window.addEventListener('keydown', onKey)
    // Always release the page, including when an animation is disabled or interrupted.
    const timeout = window.setTimeout(finish, 4400)
    return () => {
      document.documentElement.style.overflow = previousOverflow
      window.clearTimeout(timeout)
      preference.removeEventListener('change', onPreference)
      window.removeEventListener('keydown', onKey)
    }
  }, [playing, finish])

  return <>
    <div className="site-content" inert={playing} aria-hidden={playing ? true : undefined} data-intro-playing={playing}>
      {children}
    </div>
    {playing && <div className="site-intro" ref={introRef} data-testid="site-intro" onAnimationEnd={event => {
      if (event.target === event.currentTarget && event.animationName === 'intro-lifetime') finish()
    }}>
      <button className="intro-skip" type="button" onClick={finish}>Skip intro <span aria-hidden="true">↗</span></button>
      <div className="intro-final-brand" aria-hidden="true">
        <span className="intro-final-logo" ref={logoRef}><svg viewBox="0 0 32 32" fill="none"><path d="M7 5v22h9a8 8 0 1 0 0-16h-3V5H7ZM13 17h3a2 2 0 1 1 0 4h-3v-4Z" fill="currentColor" fillRule="evenodd" /><path d="m20 3 6 6m0-6-6 6" stroke="currentColor" strokeWidth="2" /></svg></span>
        <span className="intro-final-name">{'beyond.'.split('').map((letter, index) => <span className="intro-name-letter" style={{ '--letter': index } as CSSProperties} key={index}>{letter}</span>)}</span>
      </div>
      <div className="intro-character-stage" ref={stageRef} aria-hidden="true">
        <svg className="intro-character" viewBox="0 0 120 120" fill="none">
          <path className="intro-character-body" d="M10 26 26 10 60 44 94 10 110 26 76 60 110 94 94 110 60 76 26 110 10 94 44 60Z" />
        </svg>
        <span className="intro-dust"><i /><i /><i /></span>
      </div>
      <span className="intro-announcement" role="status">Welcome to Beyond.</span>
    </div>}
  </>
}
