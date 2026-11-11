"""Hermes owns receiver startup and shutdown through its public platform contract."""

from aiohttp import web
from gateway.config import Platform
from gateway.platforms.base import BasePlatformAdapter, SendResult

from .receiver import Settings, create_app


class BuildkiteAdapter(BasePlatformAdapter):
    def __init__(self, config, **kwargs):
        super().__init__(config=config, platform=Platform("buildkite"))
        extra = config.extra or {}
        self.settings = Settings.from_config(config.token, extra)
        self.runner = None

    async def connect(self, *, is_reconnect=False):
        if self.runner is not None:
            return True
        runner = web.AppRunner(create_app(self.settings), access_log=None)
        await runner.setup()
        try:
            await web.TCPSite(runner, "127.0.0.1", self.settings.port).start()
        except Exception:
            await runner.cleanup()
            raise
        self.runner = runner
        self._mark_connected()
        return True

    async def disconnect(self):
        if self.runner is not None:
            await self.runner.cleanup()
            self.runner = None
        self._mark_disconnected()

    async def send(self, chat_id, content, reply_to=None, metadata=None):
        return SendResult(
            success=False, error="Buildkite ingress has no outbound messaging channel"
        )

    async def get_chat_info(self, chat_id):
        return {"name": "Buildkite webhook ingress", "type": "channel"}
