/** While the intro plays, the page is mounted but its layout is deferred (see SiteIntro). Measuring it then
 *  would force that whole layout mid-animation, so scroll effects wait for the reveal event instead. */
export const PAGE_REVEALED_EVENT = 'beyond:page-revealed'

export const isPageDeferred = () => document.querySelector('.site-content[data-deferred]') !== null
