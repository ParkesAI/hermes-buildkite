"""HTTP trust-boundary tests with synthetic provider events and generated keys."""

import hashlib
import hmac
import io
import json
import secrets
import time
import unittest

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from hermes_buildkite.receiver import MAX_BODY_BYTES, Settings, create_app

PIPELINE = "00000000-0000-0000-0000-000000000001"


class ReceiverTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.secret = secrets.token_hex(32)
        self.received = []
        self.upstream_status = 202

        async def native(request):
            self.received.append((dict(request.headers), await request.read()))
            return web.json_response({"status": "accepted"}, status=self.upstream_status)

        app = web.Application()
        app.router.add_post("/p/coordinator/webhooks/buildkite", native)
        self.upstream = TestServer(app)
        await self.upstream.start_server()
        self.addAsyncCleanup(self.upstream.close)
        self.client = TestClient(
            TestServer(
                create_app(
                    Settings(
                        secret=self.secret,
                        pipeline_ids=frozenset({PIPELINE}),
                        upstream_port=self.upstream.port,
                        profile="coordinator",
                    )
                )
            )
        )
        await self.client.start_server()
        self.addAsyncCleanup(self.client.close)
        self.body = json.dumps(
            {
                "event": "build.finished",
                "pipeline": {"id": PIPELINE},
                "build": {"state": "failed", "branch": "master"},
            }
        ).encode()

    def headers(self, body, timestamp=None):
        stamp = str(int(time.time()) if timestamp is None else timestamp)
        sig = hmac.new(
            self.secret.encode(), stamp.encode() + b"." + body, hashlib.sha256
        ).hexdigest()
        return {"X-Buildkite-Signature": f"timestamp={stamp},signature={sig}"}

    async def test_forward_preserves_signed_bytes_and_derives_identity(self):
        headers = self.headers(self.body)
        headers.update(
            {
                "X-GitHub-Delivery": "untrusted",
                "X-Request-ID": "untrusted",
                "X-Webhook-Signature": "untrusted",
                "X-Buildkite-Event": "ping",
            }
        )
        response = await self.client.post("/buildkite", data=self.body, headers=headers)
        self.assertEqual(response.status, 202)
        forwarded, body = self.received[0]
        self.assertEqual(body, self.body)
        stamp = forwarded["X-Webhook-Timestamp"]
        expected = hmac.new(
            self.secret.encode(), stamp.encode() + b"." + body, hashlib.sha256
        ).hexdigest()
        self.assertEqual(forwarded["X-Webhook-Signature-V2"], expected)
        self.assertEqual(forwarded["X-GitHub-Event"], "build.finished")
        self.assertEqual(forwarded["X-Request-ID"], "buildkite-" + hashlib.sha256(body).hexdigest())
        self.assertNotIn("X-GitHub-Delivery", forwarded)
        self.assertNotIn("X-Webhook-Signature", forwarded)

    async def test_invalid_auth_never_reaches_native(self):
        cases = [
            {},
            {"X-Buildkite-Signature": "bad"},
            self.headers(self.body + b" "),
            self.headers(self.body, int(time.time()) - 600),
            self.headers(self.body, int(time.time()) + 600),
        ]
        for headers in cases:
            with self.subTest(headers=list(headers)):
                response = await self.client.post("/buildkite", data=self.body, headers=headers)
                self.assertEqual(response.status, 401)
        self.assertEqual(self.received, [])

    async def test_signed_irrelevant_events_are_ignored(self):
        changes = [
            ("event", "ping"),
            ("event", "build.failing"),
            ("state", "passed"),
            ("state", "canceled"),
            ("branch", "feature"),
            ("id", "00000000-0000-0000-0000-000000000002"),
        ]
        for key, value in changes:
            payload = json.loads(self.body)
            parent = payload if key == "event" else payload["pipeline" if key == "id" else "build"]
            parent[key] = value
            body = json.dumps(payload).encode()
            response = await self.client.post("/buildkite", data=body, headers=self.headers(body))
            self.assertEqual(response.status, 200)
            self.assertEqual((await response.json())["status"], "ignored")
        self.assertEqual(self.received, [])

    async def test_bad_payloads_and_size_limits(self):
        for body in [
            b"not-json",
            b"[]",
            b'{"event":"build.finished"}',
            b'{"event":"build.finished","pipeline":{"id":[]},"build":{}}',
        ]:
            response = await self.client.post("/buildkite", data=body, headers=self.headers(body))
            self.assertEqual(response.status, 400)
        body = b"x" * (MAX_BODY_BYTES + 1)
        response = await self.client.post(
            "/buildkite", data=io.BytesIO(body), headers=self.headers(body)
        )
        self.assertEqual(response.status, 413)
        self.assertEqual(self.received, [])

    async def test_upstream_errors_are_retryable_and_redirects_not_followed(self):
        for status in [302, 401, 429, 500]:
            self.upstream_status = status
            response = await self.client.post(
                "/buildkite", data=self.body, headers=self.headers(self.body)
            )
            self.assertEqual(response.status, 503)
        await self.upstream.close()
        response = await self.client.post(
            "/buildkite", data=self.body, headers=self.headers(self.body)
        )
        self.assertEqual(response.status, 503)


class SettingsTests(unittest.TestCase):
    def test_rejects_unsafe_configuration(self):
        token = secrets.token_hex(32)
        for extra in [
            {},
            {"pipeline_ids": "not-a-list"},
            {"pipeline_ids": [PIPELINE], "host": "0.0.0.0"},
            {"pipeline_ids": [PIPELINE], "profile": "../admin"},
            {"pipeline_ids": [PIPELINE], "port": 8644},
            {"pipeline_ids": [PIPELINE], "branches": []},
        ]:
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                Settings.from_config(token, extra)
        with self.assertRaises(ValueError):
            Settings.from_config("", {"pipeline_ids": [PIPELINE]})
