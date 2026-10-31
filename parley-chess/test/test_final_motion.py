"""Animation and app-surface regression: browser rendering, no visual-only fakes."""
from pathlib import Path
import json,re,unittest
from playwright.sync_api import sync_playwright
from chess_engine import Position, to_sq

ROOT=Path(__file__).resolve().parents[1]
HTML=re.sub(r'^@import[^\n]*\n','',(ROOT/'public/index.html').read_text(),flags=re.M)
FIXTURE=json.loads((ROOT/'test/game_state.json').read_text())

class FinalPolishTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.p=sync_playwright().start()
  cls.browser=cls.p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox','--disable-dev-shm-usage'])
 @classmethod
 def tearDownClass(cls):cls.browser.close();cls.p.stop()
 def screen(self,width=393,height=852):
  p=self.browser.new_page(viewport={'width':width,'height':height},device_scale_factor=1)
  errors=[];p.on('pageerror',lambda e:errors.append(str(e)))
  p.evaluate("() => {let st={};Object.defineProperty(window,'localStorage',{value:{getItem:k=>st[k]??null,setItem:(k,v)=>st[k]=String(v)}});if(!crypto.randomUUID){Object.defineProperty(crypto,'randomUUID',{value:()=> 'abcdefab-cdef-4abc-8def-123456789012'})}}")
  p.set_content(HTML,wait_until='domcontentloaded',timeout=15000)
  return p,errors
 def state(self,p,fen,move=None):
  s={**FIXTURE,'fen':fen,'lastMove':move,'turn':fen.split(' ')[1], 'round':1 if move else 0}
  p.evaluate('s=>{lastState=s;me=s.me;render(s)}',s)
 def perform(self,pos,uci):
  m=pos.find_uci(uci);self.assertIsNotNone(m,uci)
  mdata={'uci':uci,'from':to_sq(m[0]),'to':to_sq(m[1]),'promotion':m[2], 'san':pos.notation(m),'team':'w' if pos.turn==1 else 'b'}
  return pos.apply(m),mdata
 def test_move_glides_without_rebuilding_on_chat(self):
  p,errors=self.screen();pos=Position.from_fen();self.state(p,pos.fen())
  src_before=p.locator('[data-square="e2"]').evaluate('(e)=>e')
  pos,m=self.perform(pos,'e2e4');self.state(p,pos.fen(),m)
  self.assertEqual(p.locator('.move-sprite').count(),1)
  self.assertEqual(p.locator('#boardMoveTag').text_content(),'e4')
  board_square=p.locator('[data-square="e4"]').element_handle()
  s={**FIXTURE,'fen':pos.fen(),'lastMove':m,'turn':'b','round':1}
  p.evaluate('s=>{lastState=s;render(s)}',s)
  self.assertTrue(board_square.evaluate('(el)=>el.isConnected'), 'State-only updates must not reconstruct the board')
  p.wait_for_timeout(440)
  self.assertEqual(p.locator('.move-sprite').count(),0)
  self.assertEqual(errors,[]);p.close()
 def test_capture_and_check_sound_state(self):
  p,errors=self.screen();pos=Position.from_fen()
  for u in ['e2e4','d7d5']:
   pos,m=self.perform(pos,u)
  self.state(p,pos.fen())
  pos,m=self.perform(pos,'e4d5');self.state(p,pos.fen(),m)
  self.assertEqual(p.locator('.move-sprite').count(),1)
  self.assertEqual(p.locator('.capture-ring').count(),1)
  self.assertTrue(p.locator('#boardMoveTag').text_content().startswith('exd5'))
  p.wait_for_timeout(490)
  self.assertEqual(p.locator('.capture-ring').count(),0)
  self.assertEqual(errors,[]);p.close()
 def test_castling_and_promotion(self):
  for fen,uci in [('r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1','e1g1'),('4k3/P7/8/8/8/8/8/4K3 w - - 0 1','a7a8q')]:
   p,errors=self.screen();pos=Position.from_fen(fen);self.state(p,pos.fen());pos,m=self.perform(pos,uci);self.state(p,pos.fen(),m)
   self.assertTrue(p.locator('.move-sprite').count()>=1,(fen,uci))
   p.wait_for_timeout(460)
   self.assertEqual(p.locator('.move-sprite').count(),0)
   self.assertEqual(errors,[]);p.close()
 def test_en_passant_capture_animation(self):
  p,errors=self.screen();pos=Position.from_fen('4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1')
  self.state(p,pos.fen());pos,m=self.perform(pos,'e5d6');self.state(p,pos.fen(),m)
  self.assertEqual(p.locator('.capture-sprite').count(),1)
  self.assertEqual(p.locator('.capture-ring').count(),1)
  p.wait_for_timeout(450)
  self.assertEqual(p.locator('.capture-sprite').count(),0)
  self.assertEqual(errors,[]);p.close()
 def test_drawer_closes_and_no_width_overflow(self):
  for w,h in [(320,640),(375,667),(393,852),(430,932),(844,390)]:
   p,errors=self.screen(w,h);self.state(p,Position.from_fen().fen())
   self.assertLessEqual(p.evaluate('document.documentElement.scrollWidth'),w+1)
   if w<=760 and h>450:
    p.locator('#mobileChat').click()
    self.assertTrue(p.locator('body').evaluate("el=>el.classList.contains('chat-open')"))
    p.locator('#panelBackdrop').click(position={'x':10,'y':100})
    self.assertFalse(p.locator('body').evaluate("el=>el.classList.contains('chat-open')"))
   self.assertEqual(errors,[])
   p.close()
 def test_home_screen_manifest_is_valid(self):
  manifest=json.loads((ROOT/'public/manifest.webmanifest').read_text())
  self.assertEqual(manifest['display'],'standalone')
  for item in manifest['icons']:
   self.assertTrue((ROOT/'public'/item['src'].split('/')[-1]).is_file())
  self.assertTrue((ROOT/'public/parley-icon.png').is_file())

if __name__=='__main__':unittest.main()
