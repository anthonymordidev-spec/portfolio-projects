import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from server import Room
from chess_engine import Position

class EdgeCases(unittest.TestCase):
    def create(self,capacity):
        r=Room('ROOM88',capacity,'token0','A')
        for i in range(1,capacity):r.add(f'token{i}',f'Player {i}')
        r.sockets={p:object() for p in r.players}
        r.start('token0')
        return r

    def test_all_even_room_capacities(self):
        for capacity in (2,4,6,8):
            with self.subTest(capacity=capacity):
                r=self.create(capacity)
                self.assertEqual(r.capacity,capacity)
                self.assertEqual(sum(p['team']=='w' for p in r.players.values()),capacity//2)
                self.assertEqual(sum(p['team']=='b' for p in r.players.values()),capacity//2)
                ws=[t for t,p in r.players.items() if p['team']=='w']
                for t in ws:r.proposal(t,'e2e4')
                for t in ws[:-1]:
                    self.assertIsNone(r.confirm(t))
                    self.assertEqual(r.round,0)
                self.assertEqual(r.confirm(ws[-1]),'committed')
                self.assertEqual(r.round,1)
                self.assertEqual(r.game.turn,-1)

    def test_disagreement_never_commits_and_unconfirm_withdraws(self):
        r=self.create(8)
        ws=[t for t,p in r.players.items() if p['team']=='w']
        for i,t in enumerate(ws):r.proposal(t,'e2e4' if i<3 else 'd2d4')
        for t in ws[:-1]:r.confirm(t)
        self.assertEqual(r.confirm(ws[-1]),'disagreement')
        self.assertEqual(r.round,0)
        r.proposal(ws[-1],'e2e4')
        self.assertEqual(r.confirm(ws[-1]),'committed')
        self.assertEqual(r.round,1)

    def test_disconnected_teammate_stops_vote(self):
        r=self.create(4)
        r.sockets.pop('token2')
        r.proposal('token0','e2e4')
        self.assertIsNone(r.confirm('token0'))
        r.proposal('token2','e2e4')
        self.assertIsNone(r.confirm('token2'))
        self.assertEqual(r.round,0)
        r.sockets['token2']=object()
        self.assertEqual(r.confirm('token2'),'committed')
        self.assertEqual(r.round,1)

    def test_legal_moves_hidden_from_opponent(self):
        r=self.create(4)
        self.assertEqual(len(r.snapshot('token0')['legal']),20)
        self.assertEqual(r.snapshot('token1')['legal'],[])
        self.assertEqual(r.snapshot('token1')['proposals'],[])
        r.proposal('token0','e2e4')
        self.assertEqual(r.snapshot('token1')['proposals'],[])

    def test_halfmove_draw_not_automatically_triggered_at_fifty(self):
        # 100 halfmoves allow a claim, but do not automatically end the game.
        p=Position.from_fen('7k/8/8/8/8/8/1Q6/K7 w - - 100 56')
        self.assertIsNone(p.terminal([p]))
        q=Position.from_fen('7k/8/8/8/8/8/1Q6/K7 w - - 150 81')
        self.assertEqual(q.terminal([q])[0],'seventyfive')

if __name__=='__main__':unittest.main()
