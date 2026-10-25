# Neon keep-alive function

This JavaScript function checks Beyond's public liveness endpoint. It uses no SQL
connection, database credentials, or third-party dependencies. A Neon scheduled
Function Trigger can invoke it while the Postgres compute is suspended.

## Active deployment

- Project: `broad-scene-67325815`, branch: `production`.
- Function: `beyondkeepalive`, runtime: Node.js 24.
- Trigger: `beyond-keepalive` (`trigger-111c2f10-2dd9-494e-8d55-e55817ca58b2`).
- Schedule: `*/5 * * * *` (every five minutes, UTC).
- Verified scheduled invocation: 2026-10-25 08:36 UTC, HTTP 200, `ok: true`.

GitHub's health workflow is now a manual diagnostic fallback, with no cron schedule.

## Deploy

Use the Neon CLI from the repository root. Sign in with the Neon account that owns
project `broad-scene-67325815`; the database connection string alone cannot deploy
functions. Do not commit CLI credentials, API keys or `.neon` connection settings.

```powershell
npm exec --yes --package=neon@8.11.3 -- neon login
npm exec --yes --package=neon@8.11.3 -- neon functions deploy beyondkeepalive --project-id broad-scene-67325815 --branch production --src functions/neonkeepalive/index.mjs
```

After the function deployment succeeds, open the production branch in Neon Console:

1. **Functions → beyondkeepalive → ⋮ → Manage Triggers → Create trigger**.
2. Choose **Schedule**, name it `beyond-keepalive`, and use path `/`.
3. Set cron to `*/5 * * * *` (UTC) and leave the trigger enabled.
4. Check Functions logs for an `ok: true` result after the next scheduled run.

When setting this up elsewhere, keep any existing scheduler until a Neon scheduled
invocation succeeds, then disable that scheduler to avoid duplicate checks.
Neon Functions have their own free usage allowances. This is an inactivity
keep-alive, not a guarantee against Render outages or resource limits.

## Verify locally

```powershell
node --test functions/neonkeepalive/index.test.mjs
```

References:
- https://neon.com/docs/compute/functions/get-started
- https://neon.com/docs/compute/functions/triggers/schedule
