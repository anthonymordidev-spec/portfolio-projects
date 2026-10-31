"""End-to-end multiplayer test: four distinct live websocket clients."""
import asyncio
import json
import unittest
from aiohttp import ClientSession, WSMsgType, web
from server import create_app, rooms



class Client:
    def __init__(self,session,name,url):self.name=name;self.session=session;self.url=url;self.ws=None;self.states=[];self.messages=[]
    async def open(self):self.ws=await self.session.ws_connect(self.url);await self.expect('hello');return self
    async def send(self,type,**kwargs):await self.ws.send_json(dict(type=type,**kwargs))
    async def expect(self,kind=None,predicate=None,timeout=4):
        async def receive():
            while True:
                m=await self.ws.receive(timeout=timeout)
                if m.type != WSMsgType.TEXT:raise Exception('Socket closed '+str(m.type))
                d=json.loads(m.data);self.messages.append(d)
                if d['type']=='state':self.states.append(d)
                if (kind is None or d['type']==kind) and (predicate is None or predicate(d)):
                    return d
        return await asyncio.wait_for(receive(),timeout=timeout)
    async def close(self):await self.ws.close()

class LiveTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        rooms.clear()
        self.runner=web.AppRunner(create_app())
        await self.runner.setup()
        self.site=web.TCPSite(self.runner,'127.0.0.1',0)
        await self.site.start()
        port=self.site._server.sockets[0].getsockname()[1]
        self.url=f'http://127.0.0.1:{port}/ws'

    async def asyncTearDown(self):
        await self.runner.cleanup()
        rooms.clear()

    async def test_4_player_consensus_and_chat_reconnect(self):
        async with ClientSession() as session:
            cs=[]
            try:
                for i,name in enumerate(('Alice','Bob','Charlie','Dana')):
                    c=await Client(session,name,self.url).open();cs.append(c)
                    if i==0:
                        await c.send('create',token=f'tokenfortest_{i:02d}_123456789',name=name,capacity=4)
                        joined=await c.expect('joined');room=joined['code']
                    else:
                        await c.send('join',token=f'tokenfortest_{i:02d}_123456789',name=name,code=room)
                        await c.expect('joined')
                    await c.expect('state',lambda s:len(s['roster'])==i+1)
                for c in cs[:-1]:await c.expect('state',lambda s:len(s['roster'])==4)
                self.assertEqual([c.states[-1]['me']['team'] for c in cs],['w','b','w','b'])
                await cs[1].send('start')
                err=await cs[1].expect('error')
                self.assertIn('host',err['message'])
                await cs[0].send('start')
                for c in cs:await c.expect('state',lambda s:s['phase']=='playing')
                self.assertEqual(cs[1].states[-1]['legal'],[])
                self.assertEqual(len(cs[0].states[-1]['legal']),20)
                await cs[0].send('chat',text='Try e4.')
                for c in cs[::2]:await c.expect('state',lambda s:len(s['chats'])==1)
                for c in cs[1::2]:await c.expect('state')
                self.assertEqual(cs[1].states[-1]['chats'],[])
                await cs[0].send('propose',uci='e2e4')
                for c in cs:await c.expect('state',lambda s:s['room']==room and len(s['proposals'])>0 if s['me']['team']=='w' else True)
                await cs[2].send('propose',uci='d2d4')
                for c in cs:await c.expect('state')
                await cs[0].send('confirm')
                for c in cs:await c.expect('state')
                await cs[2].send('confirm')
                await cs[2].expect('notice')
                for c in cs:await c.expect('state')
                self.assertEqual(cs[0].states[-1]['round'],0)
                await cs[2].send('propose',uci='e2e4')
                for c in cs:await c.expect('state')
                await cs[2].send('confirm')
                for c in cs:await c.expect('moved')
                for c in cs:await c.expect('state',lambda s:s['round']==1)
                self.assertEqual(cs[0].states[-1]['turn'],'b')
                self.assertEqual(cs[1].states[-1]['lastMove']['san'],'e4')
                # Reconnect a black player and require their new session to receive current game.
                await cs[1].close()
                for c in cs[::2]+cs[3:]:await c.expect('state',lambda s: not next(x for x in s['roster'] if x['name']=='Bob')['online'])
                replacement=await Client(session,'Bob',self.url).open()
                await replacement.send('join',code=room,name='Bob',token='tokenfortest_01_123456789')
                await replacement.expect('joined')
                latest=await replacement.expect('state')
                self.assertEqual(latest['round'],1)
                self.assertTrue(any(p['name']=='Bob' and p['online'] for p in latest['roster']))
                await replacement.close()
            finally:
                for c in cs:
                    if c.ws and not c.ws.closed:await c.close()

if __name__=='__main__':unittest.main()
