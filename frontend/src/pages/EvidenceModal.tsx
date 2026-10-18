import { type ReactNode, useEffect, useRef } from 'react'

/**
 * Centred popup shared by every evidence view: a fixed header with a close button and a
 * scrolling body. Closes on Escape, the close button, or a click on the backdrop, and
 * returns focus to the element that opened it.
 */
export function EvidenceModal({ className, label, kicker, closeLabel, onClose, children }: { className: string; label: string; kicker: string; closeLabel: string; onClose: () => void; children: ReactNode }) {
  const ref = useRef<HTMLDialogElement>(null)
  useEffect(() => {
    const dialog = ref.current
    const previous = document.activeElement as HTMLElement | null
    dialog?.showModal()
    return () => { if (dialog?.open) dialog.close(); previous?.focus({ preventScroll: true }) }
  }, [])
  return <dialog ref={ref} className={`evidence-modal ${className}`} aria-label={label}
    onCancel={event => { event.preventDefault(); onClose() }}
    onClick={event => {
      // A click on the dialog element itself outside its box is a click on the backdrop.
      if (event.target !== event.currentTarget) return
      const rect = event.currentTarget.getBoundingClientRect()
      if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) onClose()
    }}>
    <div className="inspector-top"><span className="section-kicker">{kicker}</span><button className="close" onClick={onClose} aria-label={closeLabel}>×</button></div>
    <div className="modal-body">{children}</div>
  </dialog>
}
