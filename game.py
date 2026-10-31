"""Tkinter board UI; all socket operations run on a worker thread."""
import tkinter as tk
from tkinter import ttk
import ipaddress
from network import Session, DEFAULT_PORT, local_ipv4_addresses
from rules import BOARD

class GameApp:
    def __init__(self, root):
        self.root, self.session = root, None
        root.title('LAN 세계여행 보드게임 · 2인')
        root.protocol('WM_DELETE_WINDOW', self.quit)
        self.menu()
        root.after(100, self.tick)
    def clear(self):
        for child in self.root.winfo_children():
            child.destroy()
    def menu(self):
        if self.session:
            self.session.close()
            self.session = None
        self.clear()
        f = ttk.Frame(self.root, padding=35)
        f.pack()
        ttk.Label(f, text='세계여행 보드게임', font=('맑은 고딕', 22, 'bold')).pack(pady=15)
        ttk.Label(f, text='같은 Wi-Fi / LAN에서 두 노트북으로 플레이').pack()
        ttk.Label(f, text='호스트 IP (참가할 때 입력)').pack(pady=(20, 0))
        address = ttk.Entry(f, width=32)
        address.pack(pady=5)
        ttk.Label(f, text='포트 (두 노트북에서 동일하게 설정)').pack()
        port = ttk.Entry(f)
        port.insert(0, str(DEFAULT_PORT))
        port.pack(pady=5)
        error = ttk.Label(f, foreground='red')
        error.pack()
        def start(host):
            try:
                number = int(port.get())
                if not 1 <= number <= 65535:
                    raise ValueError()
                ip = '' if host else str(ipaddress.IPv4Address(address.get().strip()))
            except ValueError:
                error.config(text='올바른 IPv4 주소와 포트(1~65535)를 입력하세요.')
                return
            self.start(host, ip, number)
        ttk.Button(f, text='방 만들기 (플레이어 1)', command=lambda: start(True)).pack(fill='x', pady=7)
        ttk.Button(f, text='참가하기 (플레이어 2)', command=lambda: start(False)).pack(fill='x', pady=7)
    def start(self, host, address, port):
        self.clear()
        self.me = 0 if host else 1
        self.session = Session(host, address, port)
        self.status = ttk.Label(self.root, padding=5)
        self.status.pack()
        ips = ', '.join(local_ipv4_addresses()) if host else address
        ttk.Label(self.root, text=f'내 플레이어: P{self.me+1} | 호스트 IP: {ips} | 포트: {port}').pack()
        body = ttk.Frame(self.root)
        body.pack()
        self.canvas = tk.Canvas(body, width=720, height=720, bg='#eef2e9', highlightthickness=0)
        self.canvas.pack(side='left')
        self.canvas.bind('<Button-1>', self.select)
        panel = ttk.Frame(body, padding=15, width=290)
        panel.pack(side='left', fill='y')
        self.info = ttk.Label(panel, font=('맑은 고딕', 11), justify='left')
        self.info.pack(anchor='w', pady=12)
        self.detail = ttk.Label(panel, wraplength=260)
        self.detail.pack(pady=10)
        self.buttons = {}
        for action, label in [('roll', '주사위 굴리기'), ('buy', '현재 땅 구매'), ('build', '현재 땅 건설 / 증축'), ('travel', '선택한 칸으로 세계여행'), ('end', '턴 종료')]:
            self.buttons[action] = ttk.Button(panel, text=label, command=lambda a=action: self.session.action(a, self.selected))
            self.buttons[action].pack(fill='x', pady=4)
        self.logs = tk.Text(panel, width=34, height=19, state='disabled', wrap='word', font=('맑은 고딕', 9))
        self.logs.pack(pady=12)
        ttk.Button(panel, text='나가기 / 메인 메뉴', command=self.menu).pack(fill='x')
        self.selected = 0
        self.last = None
        self.session.start()
    def rect(self, i):
        if i <= 8:
            x, y = 8-i, 8
        elif i <= 16:
            x, y = 0, 16-i
        elif i <= 24:
            x, y = i-16, 0
        else:
            x, y = 8, i-24
        return x*80, y*80
    def select(self, event):
        for i in range(32):
            x, y = self.rect(i)
            if x <= event.x < x+80 and y <= event.y < y+80:
                self.selected, self.last = i, None
                break
    def tick(self):
        if self.session:
            s, status, connected = self.session.snapshot()
            self.status.config(text=status)
            key = (s, connected, self.selected)
            if self.last != key:
                self.last = key
                self.draw(s, connected)
        self.root.after(100, self.tick)
    def draw(self, s, connected):
        c = self.canvas
        c.delete('all')
        colors = ['#c5e5ff', '#ffd6ad']
        for i, tile in enumerate(BOARD):
            x, y = self.rect(i)
            owner, level = s['owners'][i], s['levels'][i]
            c.create_rectangle(x+1,y+1,x+79,y+79,fill=colors[owner] if owner >= 0 else '#fffdf5', outline='#178365' if i == self.selected else '#c1c6c0', width=3 if i == self.selected else 1)
            label = tile['name']
            if tile['kind'] == 'city':
                label += f'\n{tile["price"]}만원'
                if owner >= 0:
                    label += f'\nP{owner+1} ' + ['대지','별장','빌딩','호텔'][level]
            c.create_text(x+40,y+30,text=label,font=('맑은 고딕',9),width=76)
        for who, p in enumerate(s['players']):
            x,y = self.rect(p['pos'])
            x += 20 + who*35
            c.create_oval(x-10,y+58,x+10,y+78,fill=['#176bc0','#d56816'][who],outline='white',width=2)
            c.create_text(x,y+68,text=str(who+1),fill='white')
        c.create_text(360,280,text='세계여행',font=('맑은 고딕',32,'bold'),fill='#215a4a')
        c.create_text(360,340,text='땅을 구매하고 건물을 세워\n상대에게 통행료를 받으세요.',font=('맑은 고딕',16),justify='center')
        c.create_text(360,415,text='주사위: '+ (' + '.join(map(str,s['dice'])) or '—'),font=('맑은 고딕',24))
        c.create_text(360,470,text=f'사회복지기금: {s["fund"]}만원',font=('맑은 고딕',14))
        winner = s['winner']
        text = f'P{winner+1} 승리!' if winner is not None else f'현재 차례: P{s["turn"]+1}'
        self.info.config(text=text+'\n\n'+'\n'.join(f'P{i+1}: {p["money"]}만원 / 휴식 {p["jail"]}턴' for i,p in enumerate(s['players'])))
        tile = BOARD[self.selected]
        self.detail.config(text=f'선택: {tile["name"]}\n땅값 {tile["price"]} / 건설비 {tile["build"]}만원' if tile['kind']=='city' else f'선택: {tile["name"]}')
        active = connected and s['turn']==self.me and winner is None
        p = s['players'][self.me]
        i = p['pos']
        allowed = dict(roll=s['phase']=='roll', end=s['phase'] in ('manage','travel'), travel=s['phase']=='travel' and self.selected != 24 and p['money']>=10,
            buy=s['phase']=='manage' and BOARD[i]['kind']=='city' and s['owners'][i]==-1 and p['money']>=BOARD[i]['price'],
            build=s['phase']=='manage' and s['owners'][i]==self.me and s['levels'][i]<3 and p['money']>=BOARD[i]['build'])
        for a,b in self.buttons.items():
            b.config(state='normal' if active and allowed[a] else 'disabled')
        self.logs.config(state='normal')
        self.logs.delete('1.0','end')
        self.logs.insert('end','\n'.join(s['logs']))
        self.logs.see('end')
        self.logs.config(state='disabled')
    def quit(self):
        if self.session:
            self.session.close()
        self.root.destroy()

def run():
    root = tk.Tk()
    GameApp(root)
    root.mainloop()
