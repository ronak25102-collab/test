import { SignIn, SignUp } from '@clerk/react'
import { BeyondMark } from '../pages/Landing'
import { clerkPublishableKey, useSiteAuth } from './AuthProvider'
import './auth.css'

export function AuthPage({ signUp = false }: { signUp?: boolean }) {
  const auth = useSiteAuth()
  const params = new URLSearchParams(location.search)
  const authRoute = ['sign-in', 'sign-up'].includes(params.get('view') || '')
  const returnTo = authRoute ? '/?view=workspace' : `${location.pathname}${location.search}`
  const appearance = {
    variables: { colorPrimary: '#1d382c', colorBackground: '#fcfcf8', colorText: '#23372c',
      colorTextSecondary: '#64715d', colorInputBackground: '#f4f5ec', colorInputText: '#23372c',
      colorDanger: '#963f2d', borderRadius: '10px', fontFamily: 'Inter, ui-sans-serif, system-ui, sans-serif' },
    elements: { rootBox: 'beyond-clerk-root', cardBox: 'beyond-clerk-box', card: 'beyond-clerk-card',
      headerTitle: 'beyond-clerk-title', headerSubtitle: 'beyond-clerk-subtitle',
      formButtonPrimary: 'beyond-clerk-primary', formFieldInput: 'beyond-clerk-input',
      socialButtonsBlockButton: 'beyond-clerk-social', footer: 'beyond-clerk-footer' },
  }
  return <div className="auth-shell">
    <header className="auth-topbar"><a className="brand" href="/" aria-label="Beyond home"><BeyondMark /><span>beyond<span className="brand-period">.</span></span></a><a className="auth-back" href="/">Back to Beyond <span aria-hidden="true">↗</span></a></header>
    <main className="auth-layout">
      <section className="auth-story" aria-labelledby="auth-story-title">
        <span className="auth-eyebrow">YOUR PERSONAL RESEARCH WORKSPACE</span>
        <h1 id="auth-story-title">Follow the evidence.<br /><span>Keep your discoveries.</span></h1>
        <p>One place for the questions you pursue, the sources you check, and the investigations you come back to.</p>
        <div className="auth-landscape" aria-hidden="true"><img src="/images/beyond-landscape.png" alt="" /><div className="auth-evidence-card"><span className="auth-card-mark">↗</span><div><strong>Every investigation, connected.</strong><span>Saved to your account. Ready when you return.</span></div><span className="auth-card-check">✓</span></div></div>
        <div className="auth-story-footer"><span>01 / EVIDENCE FIRST</span><span>Sources. Reasoning. Perspective.</span></div>
      </section>
      <section className="auth-form-panel" aria-label={signUp ? 'Create your Beyond account' : 'Sign in to Beyond'}>
        <div className="auth-panel-heading"><span className="auth-eyebrow">{signUp ? 'BEGIN YOUR NEXT CHAPTER' : 'PICK UP WHERE YOU LEFT OFF'}</span><h2>{signUp ? 'Make room for insight.' : 'Welcome back.'}</h2><p>{signUp ? 'Create an account to start investigating and keep your recent runs together.' : 'Sign in to start an investigation and revisit your saved research.'}</p></div>
        {clerkPublishableKey ? auth.loaded
          ? signUp ? <SignUp routing="hash" signInUrl="/?view=sign-in" forceRedirectUrl={returnTo} appearance={appearance} />
            : <SignIn routing="hash" signUpUrl="/?view=sign-up" forceRedirectUrl={returnTo} appearance={appearance} />
          : <div className="auth-loading" role="status"><span />Connecting to secure sign-in…</div>
          : <p className="auth-loading" role="status">Sign-in is available on the deployed Beyond website.</p>}
        <p className="auth-privacy"><span aria-hidden="true">⌑</span> Your investigations stay with your account.</p>
      </section>
    </main>
    <footer className="auth-footer"><span>Evidence first. Perspective beyond.</span><span>BEYOND / FINANCIAL RESEARCH</span></footer>
  </div>
}
