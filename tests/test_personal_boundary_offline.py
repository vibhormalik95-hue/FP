"""ASGI-only synthetic personal browser-boundary tests; no socket/model/browser."""
import asyncio
import os
import re
import unittest
import httpx
from feedctrl.claude_personal_app import create_claude_personal_app, _personal_origin
from feedctrl.model_adapters import HostedRunBudget
from feedctrl.api import create_app

ORIGIN='http://127.0.0.1:8000'

def app():
    return create_claude_personal_app(allowed_origin=ORIGIN,fixture=True,
       executable=os.path.abspath('/synthetic/not-a-cli'),workdir=os.path.abspath('/synthetic/workdir'),model='claude-opus-5-5',
       effort='max',run_budget=HostedRunBudget(3),estimated_per_invocation_usd=.1,
       output_mode='plain_json',runtime_authorized=True,data_authorized=True,
       subscription_and_usage_authorized=True,executable_reviewed=True,
       managed_runtime_reviewed=True,process_containment_reviewed=True,reviewed_cli_version='2.1.321')

class Tests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.app=app();self.transport=httpx.ASGITransport(app=self.app,client=('127.0.0.1',54321))
        self.client=httpx.AsyncClient(transport=self.transport,base_url=ORIGIN)
    async def asyncTearDown(self):await self.client.aclose()
    async def test_public_index_and_exact_built_assets_only(self):
        r=await self.client.get('/');self.assertEqual(r.status_code,200)
        self.assertIn('data-personal-mode="loopback"',r.text)
        self.assertNotIn('data-personal-auth',r.text)
        self.assertEqual(r.headers['cache-control'],'no-store')
        self.assertIn("frame-ancestors 'none'",r.headers['content-security-policy'])
        assets=re.findall(r'(?:src|href)="(/assets/[^"]+)"',r.text)
        self.assertTrue(assets)
        for asset in assets:
            response=await self.client.get(asset);self.assertEqual(response.status_code,200)
            self.assertNotIn('X-Personal-Operator-Token',response.text)
        self.assertNotEqual((await self.client.get('/assets/does-not-exist.js')).status_code,200)
    async def test_same_origin_api_session_reset_without_token(self):
        h={'Origin':ORIGIN,'Sec-Fetch-Site':'same-origin'}
        status=await self.client.get('/api/status',headers=h);self.assertEqual(status.status_code,200)
        self.assertIn('no-store',status.headers['cache-control'])
        self.assertIn("frame-ancestors 'none'",status.headers['content-security-policy'])
        session=await self.client.post('/api/session',json={},headers=h);self.assertEqual(session.status_code,201)
        sid=session.json()['session_id']
        reset=await self.client.post('/api/reset',json={'user_id':1},headers={**h,'X-Session-ID':sid})
        self.assertEqual(reset.status_code,200)
        self.assertEqual((await self.client.get('/api/status')).status_code,200)
    async def test_remote_host_origin_and_proxy_rejected(self):
        for headers in ({'Host':'evil.test:8000'}, {'Host':'127.0.0.1:8001'},
                        {'Origin':'http://evil.test'}, {'Origin':'null'},
                        {'X-Forwarded-For':'127.0.0.1'}, {'Forwarded':'for=127.0.0.1'},
                        {'Sec-Fetch-Site':'cross-site'}, {'Sec-Fetch-Site':'same-site'}):
            with self.subTest(headers=headers):self.assertEqual((await self.client.get('/api/status',headers=headers)).status_code,403)
        r=await self.client.post('/api/session',json={},headers={'Sec-Fetch-Site':'same-origin'})
        self.assertEqual(r.status_code,403)  # browser unsafe request requires Origin
        remote=httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app,client=('192.0.2.9',1234)),base_url=ORIGIN)
        try:
            self.assertEqual((await remote.get('/')).status_code,403)
            self.assertEqual((await remote.get('/api/status')).status_code,403)
        finally:await remote.aclose()
    async def test_duplicate_host_origin_and_fetch_site_rejected(self):
        transport=httpx.ASGITransport(app=self.app,client=('127.0.0.1',8))
        async with httpx.AsyncClient(transport=transport,base_url=ORIGIN) as client:
            for headers in ([('Host','127.0.0.1:8000'),('Host','127.0.0.1:8000')],
                            [('Origin',ORIGIN),('Origin',ORIGIN)],
                            [('Sec-Fetch-Site','same-origin'),('Sec-Fetch-Site','same-origin')]):
                with self.subTest(headers=headers):
                    self.assertEqual((await client.get('/api/status',headers=headers)).status_code,403)
    async def test_normal_app_has_no_personal_marker(self):
        normal=create_app(fixture=True,allow_local_models=False,allow_local_recommender=False)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=normal),base_url=ORIGIN) as c:
            index=await c.get('/');self.assertEqual(index.status_code,200)
            self.assertNotIn('data-personal-mode',index.text)
            self.assertEqual((await c.get('/api/status')).status_code,200)
    async def test_invalid_origin_configuration_rejected(self):
        for value in ('http://evil.test:8000','http://127.0.0.1','https://127.0.0.1:8000',
                      'http://127.0.0.1:8000/path','http://user@127.0.0.1:8000','http://127.0.0.1:08000',
                      'http://127.0.0.1:80','http://localhost:80','http://[::1]:80'):
            with self.subTest(value=value),self.assertRaises(ValueError):_personal_origin(value)

if __name__=='__main__':unittest.main()
