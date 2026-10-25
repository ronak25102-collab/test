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
| `REPLAY_DURATION_SECONDS` | `120` |
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
`worker: fresh`. Start an HDFC Bank investigation using today's cutoff and Live
mode; stored evidence playback should complete after approximately two minutes.

The Free service sleeps after 15 minutes without inbound traffic and can take
about a minute to wake. Files written inside the container are temporary; saved
reports and run history are stored in Neon. Both providers have free usage limits.
The worker polls PostgreSQL while the web service is awake, consuming Neon compute.
See <https://render.com/docs/free> and the current Neon plan limits.
