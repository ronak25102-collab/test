# Clerk sign-in and personal investigations

The landing page is public. Opening the workspace or a report requires Clerk
sign-in in the Docker deployment. The sign-in and sign-up screens use Beyond's
cream, sage and dark-green styling, existing landscape artwork and responsive layout.

New investigations store their verified Clerk user ID in `research_runs.owner_user_id`.
History, queue counts and queue clearing are scoped to that user. Reading runs,
events, reports, claims, passages, calculations and exports, or cancelling/resuming
a run, requires a verified session and ownership. Another user's run returns 404.
Idempotency keys are scoped to each user. Signing out or switching accounts clears
the browser's loaded research state. Saved investigations remain available across
devices through Neon, without copying Clerk user profiles into the database.

## Configuration

The Dockerfile uses the supplied **public development publishable key** as its
overridable `CLERK_PUBLISHABLE_KEY` build argument. It sets the frontend's
`VITE_CLERK_PUBLISHABLE_KEY` and backend's matching public key. `AUTH_REQUIRED=true`
prevents the Docker service from silently becoming anonymous if configuration is
removed. No Clerk secret key is embedded in source, browser assets or the image.

The API verifies RS256 session signatures against this Clerk instance's cached
public JWKS, including issuer, expiry, not-before time, session ID and authorized
party. Pending sessions are rejected. Verification does not require a Clerk secret
key. API requests send a Bearer session token; same-origin session cookies also
support authenticated downloads. Cookie-based mutations require an allowed Origin.
Private responses use `Cache-Control: private, no-store`.

`CLERK_AUTHORIZED_PARTIES` defaults to the deployed Render origin and localhost
port 5173. Set a JSON array of exact allowed frontend origins when adding a domain.
For production Clerk credentials, set Render's `CLERK_PUBLISHABLE_KEY` to the live
publishable key and redeploy; both Docker stages consume that build argument.

For local development, place the public key in the backend's private `.env` as
`CLERK_PUBLISHABLE_KEY` and in `frontend/.env.local` as `VITE_CLERK_PUBLISHABLE_KEY`.
Apply `uv run alembic -c backend/alembic.ini upgrade head` before starting an existing
local database. Without Clerk configuration, local offline demos retain their
previous behavior; this fallback is disabled in the Docker deployment.

## Existing reports

Migration `0006_run_ownership` adds a nullable owner and index. Existing anonymous
runs are preserved with no owner. They are not assigned to the first person who
signs in and are not exposed through another user's history or private report API.
New runs are saved to the signed-in account automatically. Downgrade refuses to
drop ownership while private runs exist.

References:
- https://clerk.com/docs/react/getting-started/quickstart
- https://clerk.com/docs/guides/sessions/manual-jwt-verification
