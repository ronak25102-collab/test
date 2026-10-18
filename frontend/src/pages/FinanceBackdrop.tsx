import { useId } from 'react'
import './finance-backdrop.css'

/** Decorative light follows the existing artwork's native 1536 × 1024 coordinates. */
export function FinanceBackdrop() {
  const id = useId()
  const glass = `${id}-glass`
  const lens = `${id}-lens`
  const reflection = `${id}-reflection`
  const artwork = `${id}-artwork`
  const pillars = [
    { name: 'rear', origin: '1490px 550px', shape: 'M1438 249 1498 221 1511 221 1536 226 1536 511 1438 547Z' },
    { name: 'middle', origin: '1305px 636px', shape: 'M1252 394 1290 376 1356 381 1356 583 1252 636Z' },
    { name: 'front', origin: '1390px 585px', shape: 'M1327 433 1368 416 1458 421 1458 540 1327 585Z' },
    { name: 'left', origin: '485px 806px', shape: 'M454 524 500 520 516 527 516 806 454 806Z' },
  ]
  const marketLine = 'M1279 688 1298 675 1309 666 1321 676 1335 663 1351 650 1360 655 1367 650 1373 664 1384 662 1393 675 1400 672 1411 677 1420 669 1431 652 1450 641 1463 659 1470 654 1480 647 1490 648 1500 639 1510 627 1524 610 1535 617'

  return <div className="hero-finance" aria-hidden="true">
    <div className="finance-artboard">
      <div className="finance-artwork">
        <div className="finance-artwork-image" />
        <svg className="finance-artwork-light" viewBox="0 0 1536 1024" fill="none" focusable="false">
          <defs>
            <image id={artwork} href="/images/beyond-financial-research.png" width="1536" height="1024" />
            {pillars.map(pillar => <clipPath id={`${id}-${pillar.name}`} key={pillar.name}><path d={pillar.shape} /></clipPath>)}
            <clipPath id={glass}>
              <path d="M3 229 77 225 77 322 3 326Z M344 436 386 434 386 585 344 566Z M459 527 499 524 499 803 459 803Z M1205 525 1234 520 1234 635 1205 638Z M1256 397 1287 383 1287 620 1256 633Z M1295 383 1350 386 1350 579 1295 600Z M1332 438 1367 424 1367 573 1332 585Z M1375 424 1420 427 1420 555 1375 570Z M1443 253 1494 230 1494 527 1443 546Z M1519 231 1535 231 1535 512 1519 519Z" />
            </clipPath>
            <clipPath id={lens}>
              <ellipse cx="1303" cy="811" rx="92" ry="48" transform="rotate(8 1303 811)" />
            </clipPath>
            <linearGradient id={reflection} x1="0" y1="0" x2="1" y2="0">
              <stop offset="0" stopColor="#fff9dd" stopOpacity="0" />
              <stop offset=".48" stopColor="#fff9dd" stopOpacity="0" />
              <stop offset=".55" stopColor="#fff9dd" stopOpacity=".48" />
              <stop offset=".62" stopColor="#fffdf2" stopOpacity=".08" />
              <stop offset="1" stopColor="#fff9dd" stopOpacity="0" />
            </linearGradient>
          </defs>
          {pillars.map(pillar => <g className={`finance-pillar finance-pillar-${pillar.name}`} key={pillar.name} style={{ transformOrigin: pillar.origin }}>
            <g clipPath={`url(#${id}-${pillar.name})`}><use href={`#${artwork}`} /></g>
          </g>)}
          <g clipPath={`url(#${glass})`}>
            <rect className="finance-glass-light" x="-900" y="180" width="2700" height="660" fill={`url(#${reflection})`} />
          </g>
          <path className="finance-market-trace" d={marketLine} pathLength="100" />
          <path className="finance-market-signal" d={marketLine} pathLength="100" />
          <g clipPath={`url(#${lens})`}>
            <path className="finance-lens-light" d="m1180 726 60-10 130 210-60 10Z" fill="#fffdf0" />
          </g>
          <path className="finance-lens-rim" d="M1215 785c24-45 123-57 164-10" />
          <path className="finance-bank-light" d="M51 454 331 533 M62 463 62 747 M210 512 210 771" />
        </svg>
      </div>
    </div>
    <div className="finance-atmosphere" />
  </div>
}
