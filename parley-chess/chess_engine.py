"""Standalone 0x88 chess rules engine for Consensus Chess.
Legal move generation: checks, castling, en passant, all promotions, draw detection.
Server authority only; never trust a submitted browser move.
"""
from dataclasses import dataclass, replace

START_FEN = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'
FILES = 'abcdefgh'
DIRECTIONS = {'n': (-33,-31,-18,-14,14,18,31,33), 'b': (-17,-15,15,17), 'r': (-16,-1,1,16), 'k': (-17,-16,-15,-1,1,15,16,17)}
ROOK_BIT = {119:1,112:2,7:4,0:8}


def on(i): return 0 <= i < 128 and not i & 0x88

def side(piece): return 0 if piece == '.' else (1 if piece.isupper() else -1)

def to_sq(i): return FILES[i & 7] + str(8-(i >> 4))

def from_sq(s):
    if not isinstance(s,str) or len(s) != 2 or s[0] not in FILES or s[1] not in '12345678': raise ValueError('Invalid square')
    return (8-int(s[1]))*16+FILES.index(s[0])

@dataclass
class Position:
    board: tuple
    turn: int=1
    castling: int=15
    ep: int=-1
    halfmove: int=0
    fullmove: int=1

    @classmethod
    def from_fen(cls, fen=START_FEN):
        fields=fen.strip().split()
        if len(fields)!=6 or len(fields[0].split('/'))!=8: raise ValueError('Invalid FEN')
        board=['.']*128
        for rank, row in enumerate(fields[0].split('/')):
            col=0
            for ch in row:
                if ch.isdigit(): col+=int(ch)
                else:
                    if ch not in 'prnbqkPRNBQK' or col>7: raise ValueError('Invalid FEN piece')
                    board[rank*16+col]=ch;col+=1
            if col!=8: raise ValueError('Invalid FEN rank')
        if board.count('K')!=1 or board.count('k')!=1: raise ValueError('FEN requires both kings')
        rights=fields[2]
        castling=sum(bit for letter,bit in [('K',1),('Q',2),('k',4),('q',8)] if letter in rights)
        return cls(tuple(board),1 if fields[1]=='w' else -1,castling,-1 if fields[3]=='-' else from_sq(fields[3]),int(fields[4]),int(fields[5]))

    def fen(self):
        ranks=[]
        for r in range(8):
            out='';empty=0
            for c in range(8):
                p=self.board[r*16+c]
                if p=='.': empty+=1
                else:
                    if empty:out+=str(empty);empty=0
                    out+=p
            if empty:out+=str(empty)
            ranks.append(out)
        rights=''.join(letter for letter,bit in [('K',1),('Q',2),('k',4),('q',8)] if self.castling & bit) or '-'
        return '/'.join(ranks)+f" {'w' if self.turn==1 else 'b'} {rights} {to_sq(self.ep) if self.ep>=0 else '-'} {self.halfmove} {self.fullmove}"

    def key(self):
        # Official repetition compares en-passant target only if a legal capture exists.
        effective_ep=self.ep if self.ep>=0 and any(m[3]=='ep' for m in self.legal()) else -1
        return (self.board,self.turn,self.castling,effective_ep)

    def attacked(self,target,by):
        b=self.board
        for f in range(128):
            if not on(f) or side(b[f])!=by: continue
            p=b[f].lower()
            if p=='p':
                if target in (f-16*by-1,f-16*by+1):return True
                continue
            for d in DIRECTIONS.get(p,DIRECTIONS['k']):
                t=f+d
                while on(t):
                    if t==target:return True
                    if b[t]!='.' or p in ('n','k'):break
                    t+=d
        return False

    def checked(self,color=None):
        color=self.turn if color is None else color
        return self.attacked(self.board.index('K' if color==1 else 'k'),-color)

    def pseudo(self):
        b=self.board; out=[]
        for f in range(128):
            if not on(f) or side(b[f])!=self.turn:continue
            piece=b[f].lower()
            def add(t,flag=''):
                if not on(t) or b[t].lower()=='k':return
                if piece=='p' and (t>>4 in (0,7)):
                    out.extend((f,t,q,flag) for q in 'qrbn')
                else:out.append((f,t,'',flag))
            if piece=='p':
                t=f-16*self.turn
                if on(t) and b[t]=='.':
                    add(t)
                    u=t-16*self.turn
                    if (f>>4)==(6 if self.turn==1 else 1) and b[u]=='.':add(u)
                for delta in (-1,1):
                    u=t+delta
                    if not on(u):continue
                    if side(b[u])==-self.turn:add(u)
                    elif u==self.ep and b[u]=='.' and b[u+16*self.turn]==('p' if self.turn==1 else 'P'): add(u,'ep')
            else:
                for delta in DIRECTIONS.get(piece,DIRECTIONS['k']):
                    t=f+delta
                    while on(t):
                        if side(b[t])==self.turn:break
                        add(t)
                        if b[t]!='.' or piece in ('n','k'):break
                        t+=delta
                home=116 if self.turn==1 else 4
                rook='R' if self.turn==1 else 'r'
                kingside,queenside=(1,2) if self.turn==1 else (4,8)
                if piece=='k' and f==home and not self.checked():
                    if self.castling & kingside and b[f+3]==rook and b[f+1]=='.' and b[f+2]=='.' and not self.attacked(f+1,-self.turn) and not self.attacked(f+2,-self.turn):add(f+2,'castle')
                    if self.castling & queenside and b[f-4]==rook and all(b[f-j]=='.' for j in (1,2,3)) and not self.attacked(f-1,-self.turn) and not self.attacked(f-2,-self.turn):add(f-2,'castle')
        return out

    def apply(self,m):
        f,t,promotion,flag=m
        b=list(self.board);piece=b[f];captured=b[t];rights=self.castling
        b[f]='.';b[t]=promotion.upper() if self.turn==1 and promotion else (promotion if promotion else piece)
        if flag=='ep': b[t+16*self.turn]='.'
        if flag=='castle':
            rf=f+3 if t>f else f-4
            rt=f+1 if t>f else f-1
            b[rt]=b[rf];b[rf]='.'
        if piece=='K':rights &= ~3
        if piece=='k':rights &= ~12
        if piece.lower()=='r':rights &= ~ROOK_BIT.get(f,0)
        if captured.lower()=='r':rights &= ~ROOK_BIT.get(t,0)
        ep=(t+f)//2 if piece.lower()=='p' and abs(t-f)==32 else -1
        half=0 if piece.lower()=='p' or captured!='.' or flag=='ep' else self.halfmove+1
        return Position(tuple(b),-self.turn,rights,ep,half,self.fullmove+(self.turn==-1))

    def legal(self):
        return [m for m in self.pseudo() if not self.apply(m).checked(self.turn)]

    def notation(self,m):
        f,t,promo,flag=m;piece=self.board[f].upper();capture=self.board[t]!='.' or flag=='ep'
        if flag=='castle': text='O-O' if t>f else 'O-O-O'
        else:
            text=''
            if piece!='P':
                text=piece
                others=[x for x in self.legal() if x[0]!=f and x[1]==t and self.board[x[0]]==self.board[f]]
                if others:
                    same_file=any(x[0]&7==f&7 for x in others)
                    same_rank=any(x[0]>>4==f>>4 for x in others)
                    text+=to_sq(f)[0] if not same_file else to_sq(f)[1] if not same_rank else to_sq(f)
            elif capture: text=to_sq(f)[0]
            text+=('x' if capture else '')+to_sq(t)+('='+promo.upper() if promo else '')
        next_pos=self.apply(m)
        if next_pos.checked():text+='#' if not next_pos.legal() else '+'
        return text

    @staticmethod
    def uci(move):return to_sq(move[0])+to_sq(move[1])+move[2]

    def find_uci(self,uci):
        if not isinstance(uci,str) or len(uci) not in (4,5):return None
        for m in self.legal():
            if self.uci(m)==uci:return m
        return None

    def terminal(self,positions):
        if not self.legal():
            return ('checkmate',('Black' if self.turn==1 else 'White')+' wins by checkmate') if self.checked() else ('stalemate','Draw by stalemate')
        pieces=[(p.lower(),(i//16+i%16)%2) for i,p in enumerate(self.board) if on(i) and p!='.' and p.lower()!='k']
        if not pieces or (len(pieces)==1 and pieces[0][0] in ('b','n')) or (pieces and all(p=='b' for p,_ in pieces) and len({c for _,c in pieces})==1):return ('insufficient','Draw by insufficient material')
        if self.halfmove>=150:return ('seventyfive','Draw by the 75-move rule')
        # 50-move and threefold draws are player-claimed, not automatic.
        # Automatically stop only on mandatory 75-move / fivefold outcomes.
        if sum(p.key()==self.key() for p in positions)>=5:return ('fivefold','Draw by fivefold repetition')
        return None
