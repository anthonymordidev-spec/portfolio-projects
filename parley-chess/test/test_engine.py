import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from chess_engine import Position
from server import Room

class ChessRules(unittest.TestCase):
    def test_opening_has_twenty_legal(self):
        pos=Position.from_fen();self.assertEqual(len(pos.legal()),20)
        self.assertTrue(pos.find_uci('e2e4'))
        self.assertIsNone(pos.find_uci('e2e5'))
    def test_scholars_and_checkmate(self):
        pos=Position.from_fen();path=[pos]
        for move in ('f2f3','e7e5','g2g4','d8h4'):
            m=pos.find_uci(move);self.assertIsNotNone(m,move)
            pos=pos.apply(m);path.append(pos)
        self.assertEqual(pos.terminal(path)[0],'checkmate')
    def test_castles_rooks_update(self):
        pos=Position.from_fen('r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1')
        self.assertEqual(pos.notation(pos.find_uci('e1g1')),'O-O')
        self.assertEqual(pos.notation(pos.find_uci('e1c1')),'O-O-O')
        nxt=pos.apply(pos.find_uci('e1g1'))
        self.assertEqual(nxt.board[117],'R')
        self.assertEqual(nxt.board[119],'.')
        self.assertEqual(nxt.castling & 3,0)
    def test_en_passant(self):
        pos=Position.from_fen()
        for u in ('e2e4','a7a6','e4e5','d7d5'):
            pos=pos.apply(pos.find_uci(u))
        move=pos.find_uci('e5d6');self.assertIsNotNone(move)
        self.assertEqual(move[3],'ep')
        nxt=pos.apply(move)
        self.assertEqual(nxt.board[Position.from_fen('4k3/8/8/3p4/8/8/8/4K3 w - - 0 1').board.index('p')],'.')
    def test_all_promotion_types(self):
        pos=Position.from_fen('4k3/P7/8/8/8/8/8/4K3 w - - 0 1')
        for q in 'qrbn':
            m=pos.find_uci('a7a8'+q);self.assertIsNotNone(m)
            nxt=pos.apply(m);self.assertEqual(nxt.board[0],q.upper())
    def test_stalemate(self):
        pos=Position.from_fen('7k/5K2/6Q1/8/8/8/8/8 b - - 0 1')
        self.assertEqual(pos.terminal([pos])[0],'stalemate')
    def test_king_cannot_walk_into_check(self):
        pos=Position.from_fen('4k3/8/8/1b6/8/8/4r3/4K3 w - - 0 1')
        self.assertIsNone(pos.find_uci('e1e2')) # king would capture protected rook? verify on file
    def test_fen_roundtrip(self):
        pos=Position.from_fen('r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1')
        self.assertEqual(pos.fen(),'r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1')

class ConsensusUnit(unittest.TestCase):
    def test_invalid_player_capacity(self):
        r=Room('ABCDEFG',4,'t1','Host')
        self.assertEqual(r.players['t1']['team'],'w')
        r.add('t2','B');r.add('t3','C');r.add('t4','D')
        self.assertEqual([p['team'] for p in r.players.values()],['w','b','w','b'])
        self.assertRaises(ValueError,r.add,'t5','E')
    def test_unanimous_4_players(self):
        r=Room('QWERTY',4,'t1','Host')
        for t in ['t2','t3','t4']:r.add(t,t)
        r.sockets={p:object() for p in r.players}
        r.start('t1')
        r.proposal('t1','e2e4');r.proposal('t3','d2d4')
        self.assertIsNone(r.confirm('t1'));self.assertEqual(r.confirm('t3'),'disagreement')
        self.assertEqual(r.round,0)
        r.proposal('t3','e2e4');self.assertEqual(r.confirm('t3'),'committed')
        self.assertEqual(r.round,1);self.assertEqual(r.game.turn,-1)
        self.assertEqual(r.last_move['san'],'e4')
        self.assertEqual(r.proposals,{})
    def test_illegal_move_rejected(self):
        r=Room('QWERTY',2,'t1','Host');r.add('t2','B')
        r.sockets={'t1':object(),'t2':object()};r.start('t1')
        self.assertRaisesRegex(ValueError,'legal',r.proposal,'t1','e2e5')
        self.assertRaisesRegex(ValueError,'other team',r.proposal,'t2','e7e5')
    def test_chat_privacy(self):
        r=Room('QWERTY',4,'t1','A');r.add('t2','B');r.add('t3','C');r.add('t4','D')
        r.chat('t1','Attack on e4')
        self.assertEqual(len(r.snapshot('t3')['chats']),1)
        self.assertEqual(len(r.snapshot('t2')['chats']),0)
        self.assertEqual(r.snapshot('t2')['legal'],[])

if __name__=='__main__':unittest.main()
