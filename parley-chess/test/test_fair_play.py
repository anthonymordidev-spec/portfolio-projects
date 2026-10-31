import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from server import Room

class FairPlayActions(unittest.TestCase):
    def create(self,capacity=4):
        r=Room('ROOM88',capacity,'token0','A')
        for i in range(1,capacity):r.add(f'token{i}',f'Player {i}')
        r.sockets={p:object() for p in r.players}
        r.start('token0')
        return r
    def test_draw_offer_requires_full_team_and_opponent_acceptance(self):
        r=self.create(4)
        self.assertEqual(r.offer_draw('token0'),'pending')
        self.assertIsNone(r.draw_offer)
        self.assertEqual(r.offer_draw('token2'),'offered')
        self.assertEqual(r.draw_offer,'w')
        self.assertEqual(r.snapshot('token1')['matchActions']['drawOfferedBy'],'w')
        self.assertEqual(r.accept_draw('token1'),'pending')
        self.assertEqual(r.phase,'playing')
        self.assertEqual(r.accept_draw('token3'),'accepted')
        self.assertEqual(r.phase,'ended')
        self.assertEqual(r.terminal[0],'agreed_draw')
    def test_withdraw_revokes_offer_and_acceptances(self):
        r=self.create(4)
        r.offer_draw('token0')
        r.offer_draw('token2')
        r.accept_draw('token1')
        self.assertEqual(r.offer_draw('token2'),'revoked')
        self.assertIsNone(r.draw_offer)
        self.assertEqual(r.draw_votes['b'],set())
        with self.assertRaisesRegex(ValueError,'no opponent draw offer'):r.accept_draw('token3')
    def test_resign_requires_full_team_consensus(self):
        r=self.create(4)
        self.assertEqual(r.resign('token1'),'pending')
        self.assertEqual(r.phase,'playing')
        self.assertEqual(r.resign('token3'),'resigned')
        self.assertEqual(r.terminal[0],'resignation')
        self.assertIn('White wins by resignation',r.terminal[1])
    def test_move_clears_pending_draw_offer(self):
        r=self.create(4)
        r.offer_draw('token0')
        r.offer_draw('token2')
        r.proposal('token0','e2e4');r.proposal('token2','e2e4')
        r.confirm('token0')
        self.assertEqual(r.confirm('token2'),'committed')
        self.assertIsNone(r.snapshot('token0')['matchActions']['drawOfferedBy'])

if __name__=='__main__':unittest.main()
