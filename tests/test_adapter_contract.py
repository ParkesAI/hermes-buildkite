"""Real Hermes SDK qualification; set HERMES_SOURCE to a checked-out release."""

import hashlib
import hmac
import os
from pathlib import Path
import secrets
import socket
import sys
import time
import unittest

from aiohttp import web
from aiohttp.test_utils import TestServer

HERMES_SOURCE = os.environ.get("HERMES_SOURCE")
if HERMES_SOURCE:
    sys.path.insert(0, str(Path(HERMES_SOURCE).resolve()))


@unittest.skipUnless(HERMES_SOURCE, "set HERMES_SOURCE to run actual Hermes SDK tests")
class AdapterContractTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from gateway.config import PlatformConfig
        from gateway.platform_registry import PlatformEntry, platform_registry
        from gateway.platforms.webhook import WebhookAdapter

        from hermes_buildkite.adapter import BuildkiteAdapter

        self.config_type = PlatformConfig
        self.adapter_type = BuildkiteAdapter
        platform_registry.register(
            PlatformEntry(
                name="buildkite",
                label="Buildkite",
                adapter_factory=BuildkiteAdapter,
                check_fn=lambda: True,
                source="plugin",
            )
        )
        self.secret = secrets.token_hex(32)
        self.native = WebhookAdapter(PlatformConfig(enabled=True))
        self.accepted = 0

        async def native_auth_boundary(request):
            body = await request.read()
            # Qualification only: exercise the installed native verifier, never in production code.
            if not self.native._validate_signature(request, body, self.secret):
                return web.json_response({"error": "signature refused"}, status=401)
            self.accepted += 1
            return web.json_response({"status": "accepted"}, status=202)

        backend = web.Application()
        backend.router.add_post("/webhooks/buildkite", native_auth_boundary)
        self.backend = TestServer(backend, host="127.0.0.1")
        await self.backend.start_server()
        self.addAsyncCleanup(self.backend.close)

    def config(self, port):
        return self.config_type(
            enabled=True,
            token=self.secret,
            extra={
                "pipeline_ids": ["00000000-0000-0000-0000-000000000001"],
                "port": port,
                "upstream_port": self.backend.port,
            },
        )

    async def test_adapter_passes_explicit_profile_to_native_webhook_url(self):
        config = self.config(self.free_port())
        config.extra["profile"] = "reviewer"
        adapter = self.adapter_type(config)
        self.assertEqual(
            adapter.settings.upstream_url,
            f"http://127.0.0.1:{self.backend.port}/p/reviewer/webhooks/buildkite",
        )

    def free_port(self):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            return sock.getsockname()[1]

    async def test_construct_connect_native_auth_disconnect_and_reconnect(self):
        import aiohttp

        port = self.free_port()
        adapter = self.adapter_type(self.config(port))
        self.addAsyncCleanup(adapter.disconnect)
        self.assertTrue(await adapter.connect())
        self.assertTrue(await adapter.connect(is_reconnect=True))
        self.assertTrue(adapter.is_connected)
        async with aiohttp.ClientSession() as client:
            response = await client.get(f"http://127.0.0.1:{port}/health")
            self.assertEqual(response.status, 200)
            body = b'{"event":"build.finished","pipeline":{"id":"00000000-0000-0000-0000-000000000001"},"build":{"state":"failed","branch":"master"}}'
            stamp = str(int(time.time()))
            signature = hmac.new(
                self.secret.encode(), stamp.encode() + b"." + body, hashlib.sha256
            ).hexdigest()
            response = await client.post(
                f"http://127.0.0.1:{port}/buildkite",
                data=body,
                headers={"X-Buildkite-Signature": f"timestamp={stamp},signature={signature}"},
            )
            self.assertEqual(response.status, 202)
        self.assertEqual(self.accepted, 1)
        self.assertEqual((await adapter.get_chat_info("test"))["type"], "channel")
        self.assertFalse((await adapter.send("test", "no outbound channel")).success)
        await adapter.disconnect()
        self.assertFalse(adapter.is_connected)
        self.assertTrue(await adapter.connect(is_reconnect=True))
        await adapter.disconnect()
        with socket.socket() as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("127.0.0.1", port))

    async def test_failed_bind_cleans_up_and_can_retry(self):
        with socket.socket() as blocker:
            blocker.bind(("127.0.0.1", 0))
            blocker.listen()
            adapter = self.adapter_type(self.config(blocker.getsockname()[1]))
            self.addAsyncCleanup(adapter.disconnect)
            with self.assertRaises(OSError):
                await adapter.connect()
            self.assertIsNone(adapter.runner)
        self.assertTrue(await adapter.connect())
