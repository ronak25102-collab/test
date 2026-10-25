"""Verify Clerk sessions and authorize all run, evidence and export endpoints."""
import base64
import re
from uuid import UUID

import jwt
from fastapi.responses import JSONResponse
from jwt import PyJWKClient
from jwt.exceptions import InvalidTokenError, PyJWKClientError
from starlette.concurrency import run_in_threadpool


class ClerkSessions:
    def __init__(self, settings):
        encoded = settings.clerk_publishable_key.split("_", 2)[2]
        host = base64.b64decode(encoded + "=" * (-len(encoded) % 4)).decode().rstrip("$")
        if not re.fullmatch(r"[A-Za-z0-9.-]+", host) or "." not in host:
            raise ValueError("Invalid Clerk publishable key")
        self.issuer = f"https://{host}"
        self.parties = set(settings.clerk_authorized_parties)
        self.keys = PyJWKClient(f"{self.issuer}/.well-known/jwks.json",
                               cache_keys=True, lifespan=3600, timeout=10)

    def verify(self, token):
        if len(token) > 16_384:
            raise InvalidTokenError("Invalid session")
        key = self.keys.get_signing_key_from_jwt(token)
        claims = jwt.decode(token, key.key, algorithms=["RS256"], issuer=self.issuer,
                            leeway=5, options={"require": ["exp", "iat", "nbf", "sub", "iss", "sid"]})
        if (claims.get("azp") not in self.parties or claims.get("sts") == "pending"
                or not isinstance(claims["sub"], str) or not claims["sub"].startswith("user_")
                or len(claims["sub"]) > 128 or not isinstance(claims["sid"], str) or not claims["sid"]):
            raise InvalidTokenError("Invalid session")
        return claims["sub"]


def current_user(request):
    return getattr(request.state, "user_id", None)


def install_auth(application, settings):
    if not settings.clerk_publishable_key:
        if settings.auth_required:
            raise ValueError("CLERK_PUBLISHABLE_KEY is required when AUTH_REQUIRED=true")
        return  # Local/offline workflows without Clerk retain their existing behavior.
    application.state.clerk_sessions = ClerkSessions(settings)

    def failure(status, code, message):
        return JSONResponse({"code": code, "message": message, "retryable": status == 503},
                            status_code=status, headers={"Cache-Control": "private, no-store"})

    @application.middleware("http")
    async def protect_investigations(request, call_next):
        path = request.url.path
        protected = any(path == f"/api/v1/{name}" or path.startswith(f"/api/v1/{name}/")
                        for name in ("runs", "claims", "documents", "calculations"))
        if not protected or request.method == "OPTIONS":
            return await call_next(request)
        authorization = request.headers.get("authorization", "")
        if authorization:
            scheme, _, token = authorization.partition(" ")
            if scheme.lower() != "bearer":
                token = ""
        else:
            token = request.cookies.get("__session", "")
            if token and request.method not in {"GET", "HEAD"}:
                if request.headers.get("origin") not in settings.clerk_authorized_parties:
                    return failure(403, "ORIGIN_NOT_ALLOWED", "This request origin is not allowed.")
        if not token:
            return failure(401, "SIGN_IN_REQUIRED", "Sign in to open your investigations.")
        try:
            user_id = await run_in_threadpool(application.state.clerk_sessions.verify, token)
        except PyJWKClientError:
            return failure(401, "INVALID_SESSION", "Your session could not be verified. Please sign in again.")
        except InvalidTokenError:
            return failure(401, "INVALID_SESSION", "Your session has expired or is invalid. Please sign in again.")
        request.state.user_id = user_id
        run_id = None
        match = re.match(r"^/api/v1/runs/([^/]+)(?:/|$)", path)
        candidate = match.group(1) if match and match.group(1) not in {"queue", "history"} else None
        if path.startswith(("/api/v1/claims/", "/api/v1/documents/", "/api/v1/calculations/")):
            candidate = request.query_params.get("run_id")
        if candidate:
            try:
                run_id = str(UUID(candidate))
            except ValueError:
                return failure(404, "RUN_NOT_FOUND", "Investigation not found.")
        if run_id:
            owner = await run_in_threadpool(application.state.store.run_owner, run_id)
            if owner != user_id:
                return failure(404, "RUN_NOT_FOUND", "Investigation not found.")
        response = await call_next(request)
        response.headers["Cache-Control"] = "private, no-store"
        response.headers["Vary"] = ", ".join(filter(None, [response.headers.get("Vary"), "Authorization", "Cookie"]))
        return response
