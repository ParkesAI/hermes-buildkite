"""Authenticated, bounded Buildkite ingress for native Hermes webhooks."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import time
from dataclasses import dataclass, field

from aiohttp import ClientError, ClientSession, ClientTimeout, web

CLIENT = web.AppKey("client", ClientSession)
MAX_BODY_BYTES = 2 * 1024 * 1024
SIGNATURE = re.compile(r"timestamp=([0-9]{1,12}),\s*signature=([a-fA-F0-9]{64})")


@dataclass(frozen=True)
class Settings:
    secret: str = field(repr=False)
    pipeline_ids: frozenset[str]
    branches: frozenset[str] = frozenset({"master"})
    port: int = 8653
    upstream_port: int = 8644
    route: str = "buildkite"
    profile: str | None = None

    def __post_init__(self):
        if (
            not isinstance(self.secret, str)
            or len(self.secret) < 32
            or any(c.isspace() for c in self.secret)
        ):
            raise ValueError("A Buildkite signing token of at least 32 characters is required")
        if not self.pipeline_ids or any(
            not isinstance(p, str) or not re.fullmatch(r"[a-fA-F0-9-]{36}", p)
            for p in self.pipeline_ids
        ):
            raise ValueError("Provide an explicit allowlist of Buildkite pipeline UUIDs")
        if not self.branches or any(not isinstance(b, str) or not b for b in self.branches):
            raise ValueError("Provide an explicit allowlist of branch names")
        for port in (self.port, self.upstream_port):
            if type(port) is not int or not 1 <= port <= 65535:
                raise ValueError("Ports must be integers from 1 to 65535")
        if self.port == self.upstream_port:
            raise ValueError("Receiver and upstream ports must differ")
        for name in (self.route, self.profile):
            if name is not None and (
                not isinstance(name, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", name)
            ):
                raise ValueError("Invalid route or profile")
        if self.route is None:
            raise ValueError("A native webhook route is required")

    @classmethod
    def from_config(cls, token, extra):
        if extra.get("host", "127.0.0.1") != "127.0.0.1":
            raise ValueError("The receiver must bind to loopback")
        pipelines, branches = extra.get("pipeline_ids", []), extra.get("branches", ["master"])
        if not isinstance(pipelines, list) or not isinstance(branches, list):
            raise ValueError("pipeline_ids and branches must be lists")
        if any(not isinstance(value, str) for value in pipelines + branches):
            raise ValueError("pipeline_ids and branches must contain strings")
        return cls(
            secret=token,
            pipeline_ids=frozenset(pipelines),
            branches=frozenset(branches),
            port=extra.get("port", 8653),
            upstream_port=extra.get("upstream_port", 8644),
            route=extra.get("route", "buildkite"),
            profile=extra.get("profile"),
        )

    @property
    def upstream_url(self):
        prefix = f"/p/{self.profile}" if self.profile else ""
        return f"http://127.0.0.1:{self.upstream_port}{prefix}/webhooks/{self.route}"


def create_app(settings: Settings) -> web.Application:
    app = web.Application(client_max_size=MAX_BODY_BYTES)

    async def lifespan(app):
        async with ClientSession(timeout=ClientTimeout(total=10), trust_env=False) as client:
            app[CLIENT] = client
            yield

    async def health(request):
        return web.json_response({"status": "ok"})

    async def receive(request):
        match = SIGNATURE.fullmatch(request.headers.get("X-Buildkite-Signature", ""))
        if not match:
            return web.json_response({"error": "Buildkite HMAC signature required"}, status=401)
        body = await request.read()
        timestamp, signature = match.groups()
        expected = hmac.new(
            settings.secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256
        ).hexdigest()
        if (
            not hmac.compare_digest(signature.lower(), expected)
            or abs(int(timestamp) - time.time()) > 300
        ):
            return web.json_response({"error": "Invalid or expired signature"}, status=401)
        try:
            payload = json.loads(body)
        except (ValueError, UnicodeDecodeError):
            return web.json_response({"error": "Invalid JSON"}, status=400)
        if not isinstance(payload, dict):
            return web.json_response({"error": "Expected JSON object"}, status=400)
        event = payload.get("event")
        if event != "build.finished":
            return web.json_response({"status": "ignored", "reason": "event"})
        pipeline, build = payload.get("pipeline"), payload.get("build")
        if not isinstance(pipeline, dict) or not isinstance(build, dict):
            return web.json_response({"error": "Missing pipeline or build"}, status=400)
        pipeline_id, branch = pipeline.get("id"), build.get("branch")
        if not isinstance(pipeline_id, str) or not isinstance(branch, str):
            return web.json_response({"error": "Invalid pipeline or branch"}, status=400)
        if (
            pipeline_id not in settings.pipeline_ids
            or branch not in settings.branches
            or build.get("state") != "failed"
        ):
            return web.json_response({"status": "ignored", "reason": "scope or state"})
        # Preserve signed bytes. Native Hermes authenticates again and owns admission.
        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Timestamp": timestamp,
            "X-Webhook-Signature-V2": signature.lower(),
            "X-GitHub-Event": event,
            "X-Request-ID": "buildkite-" + hashlib.sha256(body).hexdigest(),
        }
        try:
            async with app[CLIENT].post(
                settings.upstream_url, data=body, headers=headers, allow_redirects=False
            ) as response:
                if response.status >= 300:
                    return web.json_response({"error": "Native receiver unavailable"}, status=503)
                return web.json_response({"status": "accepted"}, status=202)
        except (ClientError, TimeoutError):
            return web.json_response({"error": "Native receiver unavailable"}, status=503)

    app.cleanup_ctx.append(lifespan)
    app.router.add_post("/buildkite", receive)
    app.router.add_get("/health", health)
    return app
