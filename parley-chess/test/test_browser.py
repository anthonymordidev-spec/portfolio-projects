"""Visual and interaction QA; no network navigation is required in this sandbox."""
from pathlib import Path
import json
import re
import unittest
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
SRC=re.sub(r'^@import[^\n]*\n','',(ROOT/'public/index.html').read_text(),flags=re.M)

class BrowserQA(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p=sync_playwright().start()
        cls.browser=cls.p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox','--disable-dev-shm-usage'])
    @classmethod
    def tearDownClass(cls):cls.browser.close();cls.p.stop()

    def make(self,width,height):
        page=self.browser.new_page(viewport={'width':width,'height':height},device_scale_factor=1)
        errors=[]
        page.on('pageerror',lambda err:errors.append(str(err)))
        page.evaluate("() => {const data={};Object.defineProperty(window,'localStorage',{configurable:true,value:{getItem:k=>data[k]??null,setItem:(k,v)=>data[k]=String(v),removeItem:k=>delete data[k]}});if(!crypto.randomUUID){Object.defineProperty(crypto,'randomUUID',{value:()=> 'abcdefab-cdef-4abc-8def-123456789012'})}}")
        page.set_content(SRC,wait_until='domcontentloaded',timeout=15000)
        state=json.loads((ROOT/'test/game_state.json').read_text())
        page.evaluate("s => {lastState=s;me=s.me;code=s.room;render(s)}",state)
        return page,errors

    def test_initial_board_and_input(self):
        page,errors=self.make(393,852)
        self.assertEqual(page.locator('.square').count(),64)
        self.assertIn('light',page.locator('[data-square="a8"]').get_attribute('class'))
        self.assertIn('dark',page.locator('[data-square="a1"]').get_attribute('class'))
        self.assertIn('light',page.locator('[data-square="h1"]').get_attribute('class'))
        self.assertIn('♕',page.locator('[data-square="d1"]').inner_text())
        self.assertIn('♛',page.locator('[data-square="d8"]').inner_text())
        page.evaluate("() => {window._sent=[];ws={readyState:1,send:x=>window._sent.push(JSON.parse(x))}}")
        page.locator('[data-square="e2"]').click()
        self.assertIn('selected',page.locator('[data-square="e2"]').get_attribute('class'))
        self.assertIn('target',page.locator('[data-square="e4"]').get_attribute('class'))
        page.locator('[data-square="e4"]').click()
        self.assertEqual(page.evaluate('window._sent[0].uci'),'e2e4')
        page.evaluate("() => {lastState.proposals=[{name:'Alex',id:me.id,uci:'e2e4',san:'e4',confirmed:false},{name:'Dee',id:'other',uci:null,san:null,confirmed:false}];lastState.consensus={needed:2,confirmed:0,distinct:0};proposed=lastState.proposals[0];render(lastState)}")
        self.assertEqual(page.locator('#decisionChoice').inner_text(),'e4')
        self.assertEqual(page.locator('.proposal-chip').count(),2)
        page.locator('#confirmBtn').click()
        self.assertEqual(page.evaluate('window._sent.at(-1).type'),'confirm')
        self.assertEqual(errors,[])
        page.close()

    def test_mobile_chat_and_fit(self):
        for width,height in [(393,852),(375,667),(360,740)]:
            page,errors=self.make(width,height)
            page.locator('#mobileChat').click()
            self.assertTrue(page.locator('#chatPanel').evaluate("el => el.classList.contains('open')"))
            self.assertTrue(page.locator('#chatInput').is_visible())
            page.locator('#closeChat').click()
            self.assertFalse(page.locator('#chatPanel').evaluate("el => el.classList.contains('open')"))
            bottom=page.locator('#mobileMoves').bounding_box()['y']+page.locator('#mobileMoves').bounding_box()['height']
            self.assertLessEqual(bottom,height+1,(width,height,bottom))
            self.assertEqual(page.evaluate('document.documentElement.scrollWidth'),width)
            self.assertEqual(errors,[])
            page.close()

    def test_desktop_roster(self):
        page,errors=self.make(1440,900)
        self.assertTrue(page.locator('#chatPanel').is_visible())
        self.assertEqual(page.locator('#whiteList .member').count(),2)
        self.assertEqual(page.locator('#blackList .member').count(),2)
        self.assertEqual(errors,[])
        page.close()

if __name__=='__main__':unittest.main()
