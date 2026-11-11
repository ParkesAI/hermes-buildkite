"""Translate Buildkite HMAC headers; Hermes owns authentication and dispatch."""
import asyncio
import hashlib
import re
from aiohttp import web, ClientSession, ClientTimeout, ClientError

from dataclasses import dataclass

@dataclass(frozen=True)
class Settings:
    port: int = 8653
    upstream_port: int = 8644
    route: str = 'buildkite'
    profile: str | None = None

    def __post_init__(self):
        for port in (self.port, self.upstream_port):
            if type(port) is not int or not 1 <= port <= 65535:
                raise ValueError('Ports must be integers from 1 to 65535')
        if self.port == self.upstream_port:
            raise ValueError('Receiver and upstream ports must differ')
        for name in (self.route, self.profile):
            if name is not None and (not isinstance(name, str) or not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,63}', name)):
                raise ValueError('Invalid route or profile')
        if self.route is None:
            raise ValueError('A native webhook route is required')

    @property
    def upstream_url(self):
        prefix = f'/p/{self.profile}' if self.profile else ''
        return f'http://127.0.0.1:{self.upstream_port}{prefix}/webhooks/{self.route}'

SETTINGS = web.AppKey('settings', Settings)
CLIENT = web.AppKey('client', ClientSession)
SLOTS = web.AppKey('slots', asyncio.Semaphore)
SIGNATURE = re.compile(r'timestamp=([0-9]{1,12}),\s*signature=([a-f0-9]{64})')

async def forward(request):
    match = SIGNATURE.fullmatch(request.headers.get('X-Buildkite-Signature', ''))
    if not match:
        return web.json_response({'error': 'Buildkite HMAC signature required'}, status=401)
    body = await request.read()
    # The signature covers the exact bytes and timestamp. Never reserialize the body.
    headers = {'Content-Type': 'application/json',
               'X-Webhook-Timestamp': match[1],
               'X-Webhook-Signature-V2': match[2],
               'X-Request-ID': 'buildkite-' + hashlib.sha256(body).hexdigest()}
    try:
        async with request.app[SLOTS]:
            async with request.app[CLIENT].post(request.app[SETTINGS].upstream_url, data=body, headers=headers, allow_redirects=False) as response:
                result = await response.read()
                return web.Response(status=response.status, body=result, content_type='application/json')
    except (ClientError, asyncio.TimeoutError):
        return web.json_response({'error': 'Hermes unavailable; retry delivery'}, status=503)

async def lifespan(app):
    app[SLOTS] = asyncio.Semaphore(8)
    async with ClientSession(timeout=ClientTimeout(total=20)) as client:
        app[CLIENT] = client
        yield

def create_app(settings: Settings):
    app = web.Application(client_max_size=2 * 1024 * 1024)
    app[SETTINGS] = settings
    app.cleanup_ctx.append(lifespan)
    app.router.add_post('/buildkite', forward)
    return app

