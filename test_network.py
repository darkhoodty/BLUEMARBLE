import socket
import time
import unittest
from network import Session, JsonLines, encode
from rules import Game, BOARD

def wait_until(fn, timeout=5):
    end = time.monotonic()+timeout
    while time.monotonic()<end:
        if fn(): return True
        time.sleep(.02)
    return False

class RulesTests(unittest.TestCase):
    def test_purchase_build_rent(self):
        g=Game(); s=g.state
        s['players'][0]['pos']=1; s['phase']='manage'
        self.assertTrue(g.act(0,'buy'))
        self.assertTrue(g.act(0,'build'))
        self.assertEqual(s['players'][0]['money'],300-BOARD[1]['price']-BOARD[1]['build'])
        s['players'][1]['pos']=1
        g.land(1)
        self.assertEqual(s['players'][1]['money'],300-(BOARD[1]['price']//4)*3)
        self.assertFalse(g.act(1,'end'))
    def test_bankruptcy(self):
        g=Game(); g.state['players'][0]['money']=0
        g.state['owners'][1]=0; g.state['levels'][1]=1
        g.pay(0,100,1)
        self.assertEqual(g.state['winner'],1)
        self.assertEqual(g.state['owners'][1],-1)
        self.assertFalse(g.act(0,'roll'))
    def test_travel_and_island(self):
        g=Game(); s=g.state
        s['players'][0]['pos']=24; g.land(0)
        self.assertFalse(g.act(0,'travel',32))
        self.assertTrue(g.act(0,'travel',8))
        self.assertEqual(s['players'][0]['jail'],2)
        g.act(0,'end'); g.state['turn']=0
        self.assertTrue(g.act(0,'roll'))
        self.assertEqual(s['players'][0]['jail'],1)
    def test_framing(self):
        p=JsonLines(); b=encode({'x':1})
        self.assertEqual(p.feed(b[:3]),[])
        self.assertEqual(len(p.feed(b[3:]+b)),2)
        with self.assertRaises(ValueError): p.feed(b'x'*65537)
    def test_host_client_sync_and_disconnect(self):
        with socket.socket() as probe:
            probe.bind(('127.0.0.1',0)); port=probe.getsockname()[1]
        h,c=Session(True,port=port),Session(False,'127.0.0.1',port)
        h.start()
        try:
            self.assertTrue(wait_until(lambda:'Waiting' in h.snapshot()[1]))
            c.start()
            self.assertTrue(wait_until(lambda:h.snapshot()[2] and c.snapshot()[2]))
            c.action('roll')
            time.sleep(.2)
            self.assertEqual(h.snapshot()[0]['dice'],[])
            h.action('roll')
            self.assertTrue(wait_until(lambda:bool(c.snapshot()[0]['dice'])))
            h.action('end')
            self.assertTrue(wait_until(lambda:c.snapshot()[0]['turn']==1))
            c.action('roll')
            self.assertTrue(wait_until(lambda:c.snapshot()[0]['phase']!='roll' or c.snapshot()[0]['turn']==0))
            self.assertTrue(wait_until(lambda:h.snapshot()[0]==c.snapshot()[0]))
            c.close()
            self.assertTrue(wait_until(lambda:not h.snapshot()[2]))
        finally:
            h.close(); c.close()
            h.thread.join(6)
            if c.thread.ident: c.thread.join(6)
            self.assertFalse(h.thread.is_alive())
    def test_cancel_waiting(self):
        h=Session(True,port=0); h.start()
        self.assertTrue(wait_until(lambda:'Waiting' in h.snapshot()[1]))
        h.close(); h.thread.join(2)
        self.assertFalse(h.thread.is_alive())

if __name__=='__main__': unittest.main()
