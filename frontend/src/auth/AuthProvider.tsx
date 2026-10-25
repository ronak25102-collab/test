import { ClerkProvider, UserButton, useAuth, useUser } from '@clerk/react'
import { createContext, type ReactNode, useContext } from 'react'
import { setAccessTokenGetter } from '../api/client'

export const clerkPublishableKey = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY || ''
const AuthContext = createContext({ enabled: false, loaded: true, signedIn: true, userId: null as string | null, name: '' })

function Session({ children }: { children: ReactNode }) {
  const { isLoaded, isSignedIn, userId, getToken } = useAuth()
  const { user } = useUser()
  setAccessTokenGetter(() => getToken())
  return <AuthContext.Provider value={{ enabled: true, loaded: isLoaded, signedIn: Boolean(isSignedIn),
    userId: userId || null, name: user?.firstName || user?.fullName || 'Your account' }}>{children}</AuthContext.Provider>
}

export function AuthProvider({ children }: { children: ReactNode }) {
  if (!clerkPublishableKey) return <>{children}</>
  return <ClerkProvider publishableKey={clerkPublishableKey} signInUrl="/?view=sign-in" signUpUrl="/?view=sign-up"
    signInFallbackRedirectUrl="/?view=workspace" signUpFallbackRedirectUrl="/?view=workspace" afterSignOutUrl="/">
    <Session>{children}</Session>
  </ClerkProvider>
}

export const useSiteAuth = () => useContext(AuthContext)

export function AccountActions() {
  const auth = useSiteAuth()
  if (!auth.enabled) return null
  if (!auth.loaded) return <span className="account-name">Connecting…</span>
  return auth.signedIn
    ? <div className="account-actions"><span className="account-name">{auth.name}</span><UserButton appearance={{
      variables: { colorPrimary: '#1e392d' }, elements: { avatarBox: { width: 36, height: 36 } },
    }} /></div>
    : <a className="account-signin" href="/?view=sign-in">Sign in <span aria-hidden="true">↗</span></a>
}
