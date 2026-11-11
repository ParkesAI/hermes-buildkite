import copy
import hashlib
import hmac
import time
import unittest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from hermes_buildkite import receiver
class AdapterTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.seen=[]
        async def hermes(request):
            body=await request.read();self.seen.append((dict(request.headers),body))
            timestamp=request.headers['X-Webhook-Timestamp']
            expected=hmac.new(b'test-secret',timestamp.encode()+b'.'+body,hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected,request.headers['X-Webhook-Signature-V2']) or abs(int(timestamp)-time.time())>300:
                return web.json_response({'error':'unauthorized'},status=401)
            return web.json_response({'status':'accepted'},status=202)
        app=web.Application();app.router.add_post('/webhooks/target',hermes)
        self.upstream=TestServer(app);await self.upstream.start_server()
        settings=receiver.Settings(upstream_port=self.upstream.port,route='target')
        self.client=TestClient(TestServer(receiver.create_app(settings)));await self.client.start_server()
    async def asyncTearDown(self):
        await self.client.close();await self.upstream.close()
    async def test_signature_translation_and_rejections(self):
        body=b'{"event":"ping", "unicode":"\\u03b1"}'
        stamp=str(int(time.time()));signature=hmac.new(b'test-secret',stamp.encode()+b'.'+body,hashlib.sha256).hexdigest()
        header={'X-Buildkite-Signature':f'timestamp={stamp},signature={signature}','X-GitHub-Delivery':'attacker','X-Webhook-Signature':'attacker'}
        response=await self.client.post('/buildkite',data=body,headers=header);self.assertEqual(response.status,202)
        headers,actual=self.seen[-1];self.assertEqual(body,actual);self.assertNotIn('X-GitHub-Delivery',headers)
        self.assertEqual(headers['X-Request-ID'],'buildkite-'+hashlib.sha256(body).hexdigest())
        response=await self.client.post('/buildkite',data=body+b' ',headers=header);self.assertEqual(response.status,401)
        stale=str(int(time.time())-600);sig=hmac.new(b'test-secret',stale.encode()+b'.'+body,hashlib.sha256).hexdigest()
        response=await self.client.post('/buildkite',data=body,headers={'X-Buildkite-Signature':f'timestamp={stale},signature={sig}'});self.assertEqual(response.status,401)
        before=len(self.seen)
        response=await self.client.post('/buildkite',data=body);self.assertEqual(response.status,401);self.assertEqual(len(self.seen),before)
        response=await self.client.post('/buildkite',data=b'x'*(2*1024*1024+1),headers=header);self.assertEqual(response.status,413)
        await self.upstream.close()
        response=await self.client.post('/buildkite',data=body,headers=header);self.assertEqual(response.status,503)

if __name__=='__main__':unittest.main()
