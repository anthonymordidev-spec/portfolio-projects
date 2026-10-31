"""Pure-Python high-resolution PARLEY PNG icon for iOS/PWA; no imaging dependency."""
from functools import lru_cache
from math import sqrt
import struct, zlib

BG=(16,22,18);PANEL=(36,53,42);OUTLINE=(216,239,181)

def _near_segment(x,y,x0,y0,x1,y1,width):
    vx=x1-x0;vy=y1-y0;den=vx*vx+vy*vy
    t=max(0,min(1,((x-x0)*vx+(y-y0)*vy)/den))
    return (x-x0-vx*t)**2+(y-y0-vy*t)**2<width*width

def _pixel(x,y):
    # Dark tile with gently rounded corners; center is a simple original chess tower mark.
    u=abs(x-.5);v=abs(y-.5)
    outside=max(u-.385,v-.385,0);corners=sqrt(max(0,u-.385)**2+max(0,v-.385)**2)
    panel=corners<.095 and u<.48 and v<.48
    col=PANEL if panel else BG
    if panel and abs(corners-.091)<.012:col=OUTLINE
    if panel:
        lines=[(.29,.755,.71,.755),(.33,.68,.67,.68),(.35,.68,.387,.3),(.387,.3,.50,.17),(.50,.17,.615,.3),(.615,.3,.65,.68),(.41,.47,.59,.47)]
        if any(_near_segment(x,y,*ln,.021) for ln in lines):col=OUTLINE
        if (x-.5)**2+(y-.34)**2<.027**2:col=OUTLINE
    return col

@lru_cache(maxsize=3)
def png(size=192):
    if size not in (192,512):raise ValueError('Supported sizes: 192, 512')
    rows=[]
    for j in range(size):
        row=bytearray([0])
        for i in range(size):
            # Four samples give sufficiently clean icon edges on retina displays.
            samples=[_pixel((i+dx)/size,(j+dy)/size) for dx,dy in ((.25,.25),(.75,.25),(.25,.75),(.75,.75))]
            row.extend(sum(c[channel] for c in samples)//4 for channel in range(3))
        rows.append(bytes(row))
    def chunk(typ,body):return struct.pack('!I',len(body))+typ+body+struct.pack('!I',zlib.crc32(typ+body)&0xffffffff)
    header=b'\x89PNG\r\n\x1a\n'
    return header+chunk(b'IHDR',struct.pack('!2I5B',size,size,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(b''.join(rows),9))+chunk(b'IEND',b'')
