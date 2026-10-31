"""Real-time, server-authoritative cooperative chess for even groups of 2–8.
Run: python server.py. No paid services or external chess API required.
"""
import asyncio
import json
import logging
import os
import random
import re
import secrets
import time
from collections import deque
from pathlib import Path
from aiohttp import web, WSMsgType
from chess_engine import Position, to_sq
from app_icon import png as app_icon_png

BASE = Path(__file__).parent
ALPHABET = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'
MAX_PLAYERS = 8
ROOM_IDLE_SECONDS = 60 * 60 * 3
rooms = {}


def now(): return int(time.time() * 1000)


def good_name(value):
    if not isinstance(value,str):return 'Player'
    return ' '.join(value.replace('\u200b','').split())[:22] or 'Player'


def make_code():
    while True:
        code = ''.join(secrets.choice(ALPHABET) for _ in range(6))
        if code not in rooms:return code


def normalize_code(value):
    if not isinstance(value,str):return ''
    return re.sub('[^A-Z2-9]','',value.upper())[:6]


def valid_token(value):return isinstance(value,str) and re.fullmatch('[A-Za-z0-9_-]{16,128}',value) is not None


class Room:
    def __init__(self,code,capacity,host_token,host_name):
        self.code=code;self.capacity=capacity;self.host=host_token
        self.players={};self.sockets={};self.phase='lobby';self.game=Position.from_fen()
        self.positions=[self.game];self.history=[];self.last_move=None
        self.proposals={};self.chats={'w':deque(maxlen=90),'b':deque(maxlen=90)}
        self.round=0;self.terminal=None;self.rematch=set();self.created=now();self.active=now()
        self.add(host_token,host_name)

    def add(self,token,name):
        if len(self.players)>=self.capacity:raise ValueError('This room is full.')
        if self.phase!='lobby':raise ValueError('This match has already started.')
        half=self.capacity//2
        whites=sum(p['team']=='w' for p in self.players.values())
        blacks=sum(p['team']=='b' for p in self.players.values())
        team='w' if whites<=blacks and whites<half else 'b'
        if (team=='w' and whites>=half) or (team=='b' and blacks>=half):raise ValueError('Team is full.')
        self.players[token]={'id':secrets.token_hex(5),'name':good_name(name),'team':team,'joined':now()}
        self.active=now()
        return self.players[token]

    def public_roster(self):
        return [{'id':p['id'],'name':p['name'],'team':p['team'],'online':t in self.sockets,'host':t==self.host} for t,p in self.players.items()]

    def consensus(self,team):
        teammates=[t for t,p in self.players.items() if p['team']==team]
        confirmed=[(t,self.proposals[t]) for t in teammates if t in self.proposals and self.proposals[t]['confirmed']]
        return {'needed':len(teammates),'confirmed':len(confirmed),'distinct':len({p['uci'] for _,p in confirmed}),
                'online':sum(t in self.sockets for t in teammates)}

    def snapshot(self,token):
        me=self.players[token];team=me['team'];turn='w' if self.game.turn==1 else 'b'
        playing=self.phase=='playing' and turn==team
        possible=[]
        if playing:
            possible=[{'from':to_sq(m[0]),'to':to_sq(m[1]),'promotion':m[2],
                       'uci':Position.uci(m),'san':self.game.notation(m)} for m in self.game.legal()]
        proposals=[]
        if playing:
            proposals=[{'id':self.players[t]['id'],'name':self.players[t]['name'],'uci':self.proposals[t]['uci'] if t in self.proposals else None,
                        'san':self.proposals[t]['san'] if t in self.proposals else None,
                        'confirmed':self.proposals[t]['confirmed'] if t in self.proposals else False} for t,p in self.players.items() if p['team']==team]
        return {'type':'state','room':self.code,'capacity':self.capacity,'phase':self.phase,'host':token==self.host,
                'me':{'id':me['id'],'name':me['name'],'team':team},'roster':self.public_roster(),
                'fen':self.game.fen(),'turn':turn,'round':self.round,'legal':possible,'proposals':proposals,
                'consensus':self.consensus(turn),'lastMove':self.last_move,'history':self.history[-60:],
                'chats':list(self.chats[team]),'terminal':self.terminal,'rematchReady':len(self.rematch),
                'rematchMe':token in self.rematch,'note':'Agree on the same legal move, then every teammate confirms.'}

    async def broadcast(self):
        self.active=now()
        for token,ws in list(self.sockets.items()):
            if not ws.closed:
                try:await ws.send_json(self.snapshot(token))
                except (ConnectionResetError,RuntimeError):pass

    async def join(self,token,name,ws):
        if token not in self.players:self.add(token,name)
        old=self.sockets.get(token)
        if old is not None and old is not ws and not old.closed:
            try:await old.close(code=4001,message=b'Reconnected on another tab')
            except Exception:pass
        self.sockets[token]=ws
        self.active=now()
        await ws.send_json({'type':'joined','code':self.code,'token':token})
        await self.broadcast()

    async def leave(self,token,ws):
        if self.sockets.get(token) is ws:
            self.sockets.pop(token,None)
            if token in self.proposals:self.proposals[token]['confirmed']=False
            self.rematch.discard(token)
            await self.broadcast()

    def start(self,token):
        if token!=self.host:raise ValueError('Only the room host can start.')
        if self.phase!='lobby':raise ValueError('This game already started.')
        if len(self.players)!=self.capacity or len(self.sockets)!=self.capacity:raise ValueError('Wait for all players to join and connect.')
        if sum(p['team']=='w' for p in self.players.values())!=self.capacity//2:raise ValueError('Teams must be equal.')
        self.phase='playing';self.proposals.clear();self.active=now()

    def proposal(self,token,uci):
        if self.phase!='playing':raise ValueError('No active match.')
        if self.players[token]['team'] != ('w' if self.game.turn==1 else 'b'):raise ValueError('The other team is deciding.')
        move=self.game.find_uci(uci)
        if move is None:raise ValueError('Not a legal move.')
        self.proposals[token]={'uci':uci,'san':self.game.notation(move),'confirmed':False}

    def confirm(self,token):
        if self.phase!='playing':raise ValueError('Match is not running.')
        if self.players[token]['team'] != ('w' if self.game.turn==1 else 'b'):raise ValueError('It is not your team’s turn.')
        if token not in self.proposals:raise ValueError('Choose a move before confirming.')
        mine=self.proposals[token]
        if not self.game.find_uci(mine['uci']):raise ValueError('Move is no longer legal.')
        mine['confirmed']=True
        team=self.players[token]['team']
        mates=[t for t,p in self.players.items() if p['team']==team]
        if not all(t in self.sockets and t in self.proposals and self.proposals[t]['confirmed'] for t in mates):return None
        choices={self.proposals[t]['uci'] for t in mates}
        if len(choices)!=1:return 'disagreement'
        move=self.game.find_uci(mine['uci'])
        if not move:raise ValueError('Move has gone stale.')
        san=self.game.notation(move);old_turn=self.game.turn
        self.game=self.game.apply(move)
        self.positions.append(self.game)
        self.round+=1
        self.last_move={'from':to_sq(move[0]),'to':to_sq(move[1]),'promotion':move[2], 'san':san,'uci':mine['uci'],'team':team,'at':now()}
        self.history.append({'ply':self.round,'number':self.game.fullmove-(old_turn==-1),'team':team,'san':san,'uci':mine['uci']})
        self.proposals.clear();self.terminal=self.game.terminal(self.positions)
        if self.terminal:self.phase='ended'
        return 'committed'

    def chat(self,token,text):
        if not isinstance(text,str):raise ValueError('Invalid chat text.')
        text=' '.join(text.split())[:280]
        if not text:raise ValueError('Write a message first.')
        if not hasattr(self,'chat_times'):self.chat_times={}
        last=self.chat_times.get(token,0)
        if now()-last<450:raise ValueError('Please slow down.')
        self.chat_times[token]=now()
        team=self.players[token]['team'];p=self.players[token]
        self.chats[team].append({'id':secrets.token_hex(5),'name':p['name'],'person':p['id'],'text':text,'time':now()})

    def vote_rematch(self,token):
        if self.phase!='ended':raise ValueError('Finish this game first.')
        if token not in self.sockets:raise ValueError('Connect first.')
        if token in self.rematch:self.rematch.remove(token)
        else:self.rematch.add(token)
        if len(self.rematch)==self.capacity and len(self.sockets)==self.capacity:
            self.game=Position.from_fen();self.positions=[self.game];self.history=[];self.last_move=None
            self.round=0;self.phase='playing';self.terminal=None;self.proposals.clear();self.rematch.clear()
            self.chats={'w':deque(maxlen=90),'b':deque(maxlen=90)}


async def health(request):return web.json_response({'ok':True,'rooms':len(rooms),'version':'1.0.0'})

async def index(request):return web.FileResponse(BASE/'public'/'index.html')

async def app_icon(request):
    size=int(request.match_info.get('size') or 192)
    return web.Response(body=app_icon_png(size),content_type='image/png',headers={'Cache-Control':'public, max-age=86400'})

async def ws_handler(request):
    ws=web.WebSocketResponse(heartbeat=25,max_msg_size=4096)
    await ws.prepare(request)
    current=None;token=None
    await ws.send_json({'type':'hello','version':'1.0.0'})
    try:
        async for msg in ws:
            if msg.type!=WSMsgType.TEXT:continue
            try:
                data=json.loads(msg.data)
                if not isinstance(data,dict):raise ValueError('Invalid request.')
                kind=data.get('type')
                if kind in ('create','join'):
                    if current:raise ValueError('Already in a room.')
                    tok=data.get('token')
                    if not valid_token(tok):raise ValueError('Invalid browser identity.')
                    if kind=='create':
                        capacity=data.get('capacity')
                        if type(capacity) is not int or capacity not in (2,4,6,8):raise ValueError('Choose 2, 4, 6, or 8 players.')
                        room=Room(make_code(),capacity,tok,data.get('name','Player'))
                        rooms[room.code]=room
                    else:
                        code=normalize_code(data.get('code'))
                        room=rooms.get(code)
                        if not room:raise ValueError('Room not found. Double-check the invite code.')
                        if tok not in room.players and len(room.players)>=room.capacity:raise ValueError('Room full. Rejoin with your original browser.')
                    await room.join(tok,data.get('name','Player'),ws)
                    current=room;token=tok
                else:
                    if not current or token not in current.players or current.sockets.get(token) is not ws:raise ValueError('Join a room first.')
                    if kind=='start':current.start(token)
                    elif kind=='propose':current.proposal(token,data.get('uci'))
                    elif kind=='confirm':
                        out=current.confirm(token)
                        if out=='disagreement':await ws.send_json({'type':'notice','message':'Your team confirmed different moves. Discuss and align your selections.'})
                        if out=='committed':
                            for socket in list(current.sockets.values()):
                                if not socket.closed:await socket.send_json({'type':'moved','lastMove':current.last_move})
                    elif kind=='unconfirm':
                        if token in current.proposals:current.proposals[token]['confirmed']=False
                    elif kind=='chat':current.chat(token,data.get('text'))
                    elif kind=='rematch':current.vote_rematch(token)
                    elif kind=='ping':await ws.send_json({'type':'pong','time':now()});continue
                    else:raise ValueError('Unknown action.')
                    await current.broadcast()
            except (ValueError,TypeError,KeyError,json.JSONDecodeError) as exc:
                await ws.send_json({'type':'error','message':str(exc)[:180]})
            except Exception:
                logging.exception('Unexpected request failure')
                await ws.send_json({'type':'error','message':'Unexpected server error.'})
    finally:
        if current and token:await current.leave(token,ws)
    return ws


async def housekeeping(app):
    while True:
        await asyncio.sleep(600)
        ts=now()
        for code,room in list(rooms.items()):
            if not room.sockets and ts-room.active >ROOM_IDLE_SECONDS*1000:rooms.pop(code,None)


async def on_start(app):app['cleaner']=asyncio.create_task(housekeeping(app))
async def on_cleanup(app):app['cleaner'].cancel()


def create_app():
    app=web.Application(client_max_size=1024*16)
    app.router.add_get('/api/health',health)
    app.router.add_get('/ws',ws_handler)
    app.router.add_get('/assets/parley-icon.png',app_icon)
    app.router.add_get('/assets/parley-icon-{size:192|512}.png',app_icon)
    app.router.add_get('/',index)
    app.router.add_static('/assets/',BASE/'public',show_index=False)
    app.on_startup.append(on_start);app.on_cleanup.append(on_cleanup)
    return app

if __name__=='__main__':
    logging.basicConfig(level=logging.INFO)
    web.run_app(create_app(),host='0.0.0.0',port=int(os.getenv('PORT','8080')))
