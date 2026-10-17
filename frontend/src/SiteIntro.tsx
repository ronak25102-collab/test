import { type CSSProperties, type ReactNode, useCallback, useEffect, useState } from 'react'
import './site-intro.css'
import { PAGE_REVEALED_EVENT } from './pageReveal'

const shouldPlay = () => !window.matchMedia('(prefers-reduced-motion: reduce)').matches
  && new URLSearchParams(location.search).get('print') !== '1'

// Safety net: the intro always releases the page shortly after its 5.4s animation.
const INTRO_TIMEOUT_MS = 5800
// A still moment in the mosaic: every tile has popped in (last pop ends at .08s + .75s + .55s = 1.38s) and
// the shapes hold their half turn until the tiles start to fall at 42% of 3.7s = 1.55s (see site-intro.css).
const CONTENT_RENDER_MS = 1400
const HERO_IMAGE = '/images/beyond-financial-research.png'

const logoBodyPath = 'M7 5v22h9a8 8 0 1 0 0-16h-3V5H7ZM13 17h3a2 2 0 1 1 0 4h-3v-4Z'

// Custom lettering follows the logo's six-unit stems and compact round counters.
const wordmarkGlyphs = [
  { letter: 'b', width: 22, path: logoBodyPath, transform: 'translate(-5 0)' },
  { letter: 'e', width: 22, path: 'M20 20H8C8.5 23 12 24 15 21L19 24C16 28 9 29 4 24C-1 18 3 11 10 11C17 10 21 14 20 20ZM8 16H14C13 13 9 13 8 16Z' },
  { letter: 'y', width: 24, path: 'M1 11h7l4 9 3-9h7L11 34H4l4-9Z' },
  { letter: 'o', width: 22, path: 'M20 19a9 8 0 1 1-18 0 9 8 0 1 1 18 0ZM8 19a3 3 0 1 0 6 0 3 3 0 1 0-6 0Z' },
  { letter: 'n', width: 24, path: 'M2 11h6v2c2-3 12-4 12 5v9h-6v-8c0-3-6-3-6 0v8H2V11Z' },
  { letter: 'd', width: 22, path: logoBodyPath, transform: 'translate(27 0) scale(-1 1)' },
  { letter: '.', width: 10, path: 'M2 21h6v6H2Z' },
]

// Mosaic: flat geometric tiles in the site palette (greens, sage, cream and gold) covering the whole screen.
const CELL = 1.1, ROW_GAP = 1.15
type Shape = 'circle' | 'half' | 'ring' | 'diamond' | 'triangle' | 'quarter' | 'arch'
const shapes: Shape[] = ['half', 'ring', 'quarter', 'circle', 'triangle', 'diamond', 'arch']
const palette: [string, string][] = [
  ['#f3eddf', '#254f39'], ['#8a9a6b', '#f6f5ef'], ['#2f5a40', '#b3c59b'], ['#a77a43', '#f3eddf'],
  ['#dce6ce', '#3f6049'], ['#1b3328', '#a77a43'], ['#b3c59b', '#1b3328'], ['#f6f5ef', '#8a9a6b'],
]
// Where each letter's tile starts, as a fraction of the grid, scattered so every tile travels.
const letterStarts: [number, number][] = [[.18, .22], [.8, .76], [.62, .16], [.3, .8], [.48, .42], [.86, .3], [.12, .6]]

const wordWidth = wordmarkGlyphs.reduce((sum, glyph) => sum + glyph.width, 0) / 32
const finalCenters = wordmarkGlyphs.map((glyph, index) => {
  const before = wordmarkGlyphs.slice(0, index).reduce((sum, item) => sum + item.width, 0) / 32
  return -wordWidth / 2 + before + glyph.width / 64
})

// Lay out enough tiles to cover the viewport, with one spare row and column so the edges stay filled.
function mosaicLayout() {
  const fontSize = Math.min(96, Math.max(40, innerWidth * .085))
  const cell = fontSize * CELL
  const cols = Math.ceil(innerWidth / cell) + 1
  const rows = Math.ceil(innerHeight / cell) + 1
  const count = cols * rows
  const taken = new Set<number>()
  const letterCells = letterStarts.map(([fx, fy]) => {
    const row = Math.min(rows - 2, Math.max(1, Math.round(fy * (rows - 1))))
    let col = Math.min(cols - 2, Math.max(1, Math.round(fx * (cols - 1))))
    while (taken.has(row * cols + col)) col = (col + 1) % cols
    taken.add(row * cols + col)
    return row * cols + col
  })
  const tiles = Array.from({ length: count }, (_, cell) => {
    const col = cell % cols, row = Math.floor(cell / cols)
    const [bg, fg] = palette[(col * 3 + row * 5) % palette.length]
    return {
      cell, bg, fg,
      letterIndex: letterCells.indexOf(cell),
      shape: shapes[(col * 2 + row * 3) % shapes.length],
      turn: ((col + row) * 90) % 360,
      spin: (col + row) % 2 ? 1 : -1,
      order: ((cell * 37) % count) / count,
      x: (col - (cols - 1) / 2) * CELL,
      y: (row - (rows - 1) / 2) * CELL,
    }
  })
  // The assembled "beyond." grows to span most of the screen (capped by height), independent of the tile size.
  const wordPx = Math.min(innerWidth * .74, innerHeight * .34 * wordWidth)
  const wordScale = Math.max(1, wordPx / (wordWidth * fontSize))
  // The final b× logo is sized from the viewport so it reads as a centrepiece, never smaller than the "b" it replaces.
  const logoScale = Math.max(wordScale * 1.25, Math.min(innerWidth * .42, innerHeight * .42) / fontSize)
  return { fontSize, tiles, wordScale, logoScale }
}

function TileShape({ shape, fg }: { shape: Shape; fg: string }) {
  switch (shape) {
    case 'circle': return <circle cx="50" cy="50" r="30" fill={fg} />
    case 'half': return <path d="M14 64a36 36 0 0 1 72 0Z" fill={fg} />
    case 'ring': return <circle cx="50" cy="50" r="25" fill="none" stroke={fg} strokeWidth="15" />
    case 'diamond': return <rect x="27" y="27" width="46" height="46" fill={fg} transform="rotate(45 50 50)" />
    case 'triangle': return <path d="M50 18 84 80H16Z" fill={fg} />
    case 'quarter': return <path d="M0 100V28a72 72 0 0 1 72 72Z" fill={fg} />
    case 'arch': return <path d="M20 100V52a30 30 0 0 1 60 0v48H62V52a12 12 0 0 0-24 0v48Z" fill={fg} />
  }
}

/** A fresh intro for each document visit; in-app navigation keeps the app mounted. */
export function SiteIntro({ children }: { children: ReactNode }) {
  const [playing, setPlaying] = useState(shouldPlay)
  const [layout, setLayout] = useState(mosaicLayout)
  // The page mounts (and starts loading data) at once, but its first layout and paint are heavy, so they are
  // skipped behind the intro until the tiles have popped in and hold still, where a dropped frame is invisible.
  const [contentRendered, setContentRendered] = useState(() => !playing)
  const finish = useCallback(() => { setPlaying(false); setContentRendered(true) }, [])

  useEffect(() => {
    if (contentRendered) return
    // Decode the hero artwork off the main thread so it is ready when the page is first painted.
    const hero = new Image()
    hero.src = HERO_IMAGE
    void hero.decode?.().catch(() => undefined)
    const timeout = window.setTimeout(() => setContentRendered(true), CONTENT_RENDER_MS)
    return () => window.clearTimeout(timeout)
  }, [contentRendered])

  // Runs after the deferral attribute is removed from the DOM, so scroll effects can now measure the page.
  useEffect(() => {
    if (contentRendered) window.dispatchEvent(new Event(PAGE_REVEALED_EVENT))
  }, [contentRendered])

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
    const onResize = () => setLayout(mosaicLayout())
    const previousOverflow = document.documentElement.style.overflow
    document.documentElement.style.overflow = 'hidden'
    preference.addEventListener('change', onPreference)
    window.addEventListener('keydown', onKey)
    window.addEventListener('resize', onResize)
    // Always release the page, including when an animation is disabled or interrupted.
    const timeout = window.setTimeout(finish, INTRO_TIMEOUT_MS)
    return () => {
      document.documentElement.style.overflow = previousOverflow
      window.clearTimeout(timeout)
      preference.removeEventListener('change', onPreference)
      window.removeEventListener('keydown', onKey)
      window.removeEventListener('resize', onResize)
    }
  }, [playing, finish])

  return <>
    <div className="site-content" inert={playing} aria-hidden={playing ? true : undefined} data-intro-playing={playing} data-deferred={!contentRendered || undefined}>
      {children}
    </div>
    {playing && <div className="site-intro" data-testid="site-intro" onAnimationEnd={event => {
      if (event.target === event.currentTarget && event.animationName === 'intro-lifetime') finish()
    }}>
      <button className="intro-skip" type="button" onClick={finish}>Skip intro <span aria-hidden="true">↗</span></button>
      <div className="intro-mosaic" aria-hidden="true" style={{ fontSize: `${layout.fontSize}px`, '--bx': `${finalCenters[0]}em`, '--ws': layout.wordScale, '--ls': layout.logoScale } as CSSProperties}>
        {layout.tiles.map(tile => {
          const glyph = tile.letterIndex >= 0 ? wordmarkGlyphs[tile.letterIndex] : undefined
          const style = {
            '--x': `${tile.x}em`, '--y': `${tile.y}em`, '--order': tile.order, '--spin': tile.spin, '--bg': tile.bg,
            ...(glyph ? { '--rx': `${(tile.letterIndex - 3) * ROW_GAP}em`, '--fx': `${finalCenters[tile.letterIndex]}em` } : {}),
          } as CSSProperties
          return <span className={`intro-tile ${glyph ? 'intro-tile-letter' : ''} ${glyph?.letter === 'b' ? 'is-b' : ''}`} style={style} key={tile.cell}>
            <span className="intro-tile-face">
              <svg className="intro-tile-shape" viewBox="0 0 100 100" style={{ transform: `rotate(${tile.turn}deg)` }}><TileShape shape={tile.shape} fg={tile.fg} /></svg>
            </span>
            {glyph && <svg className={`intro-tile-glyph ${glyph.letter === '.' ? 'is-dot' : ''}`} viewBox={`0 0 ${glyph.width} 32`} style={{ width: `${glyph.width / 32}em` }} fill="currentColor"><path d={glyph.path} transform={glyph.transform} fillRule="evenodd" /></svg>}
          </span>
        })}
        {/* The "b" hands over to the full b× logo, which then settles in the centre. */}
        <svg className="intro-logo" viewBox="0 0 32 32" fill="none">
          <path d={logoBodyPath} fill="currentColor" fillRule="evenodd" />
          <path className="intro-logo-cross" d="m20 3 6 6m0-6-6 6" stroke="currentColor" strokeWidth="2" />
        </svg>
      </div>
      <span className="intro-announcement" role="status">Welcome to Beyond.</span>
    </div>}
  </>
}
