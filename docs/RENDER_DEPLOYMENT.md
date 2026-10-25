# Deploy Beyond on Render with one Docker container

The root `Dockerfile` builds React, then serves the built website and API from FastAPI.
The worker runs in the same process with `AUTO_START_WORKER=true`. Keep one Uvicorn
worker. Production browser requests use the same origin, so no frontend API URL or
additional CORS origin is required. Existing report links use query parameters and
work directly with the static file server.

## 1. Create a Neon database

Create a free PostgreSQL project at <https://neon.com/> and copy its connection URI.
Change only the prefix from `postgresql://` to `postgresql+psycopg://`. Preserve the
credentials, database name and all query parameters, including `sslmode=require`.
Enter the URI only in Render's private environment settings.

## 2. Create one Render Web Service

Connect <https://github.com/ronak25102-collab/test> through Render's GitHub integration.
Use these settings:

| Setting | Value |
| --- | --- |
| Branch | `main` |
| Runtime / Language | `Docker` |
| Root directory | Leave blank |
| Dockerfile path | `Dockerfile` |
| Docker build context | `.` (repository root) |
| Instance type | `Free` |
| Docker Command | Leave blank; use the image's command |
| Health check path | `/api/v1/health/live` |

Choose a region close to your Neon database. Add these environment variables:

| Variable | Value |
| --- | --- |
| `DATABASE_URL` | Your private `postgresql+psycopg://...` Neon URI |
| `PIPELINE_MODE` | `precomputed` |
| `AUTO_START_WORKER` | `true` |
| `REPLAY_DURATION_SECONDS` | `147` |
| `FREE_SERVICES_ONLY` | `true` |
| `MAX_RUN_COST_USD` | `0` |

Do not set `VITE_API_BASE_URL` for this combined deployment. If reusing a service,
clear any previous Docker Command override and select the root `Dockerfile`.
The image sets the static file and data directories, migrates the database before
startup and binds to Render's `PORT` on `0.0.0.0`. No separate static site or worker
service is needed.

## 3. Deploy and check

Click **Deploy Web Service**. When live, open its `https://...onrender.com` URL.
Check `/api/v1/health/configuration` for `ready: true` and `mode: precomputed`.
After the worker starts, `/api/v1/health/ready` should return `database: ok` and
`worker: fresh` (working) or `worker: idle` (waiting). Start an HDFC Bank investigation using today's cutoff and Live
mode; stored evidence playback runs for 147 seconds before saving the report.

The Free service sleeps after 15 minutes without inbound traffic and can take
about a minute to wake. Files written inside the container are temporary; saved
reports and run history are stored in Neon. Both providers have free usage limits.
The embedded worker wakes immediately when the API creates or resumes a run. When
idle it waits in memory rather than polling PostgreSQL every second, allowing Neon
to scale to zero. A 15-minute fallback checks for externally queued work, and an
outstanding lease causes an earlier check when that lease expires. Standalone CLI
workers retain their one-second polling behavior. `WORKER_IDLE_POLL_SECONDS` adjusts
the embedded fallback interval (default 900). Work queued directly by another
process can wait until the next fallback check.
See <https://render.com/docs/free> and the current Neon plan limits.

## External keep-alive

The deployed [Neon Function](../functions/neonkeepalive/README.md), `beyondkeepalive`,
is invoked every five minutes by the production branch's `beyond-keepalive`
scheduled Function Trigger. It calls the public `/api/v1/health/live` endpoint
without querying Postgres or creating research runs. Neon can fire the schedule
while Postgres is suspended. A scheduled invocation has been verified successfully.

The GitHub workflow **Check Beyond health manually** is available from Actions →
Run workflow for troubleshooting, but it no longer has an automatic schedule.

This helps prevent Render's inactivity sleep; it does not guarantee 24/7 uptime.
Render can restart free instances and enforces shared monthly compute, bandwidth
and build limits. Neon Functions have their own usage allowances; database compute
and storage quotas still apply when the application is used. No paid plan or
automatic upgrade is enabled. To stop the recurring check, disable `beyond-keepalive`
in Neon Console → Functions → beyondkeepalive → Manage Triggers.
