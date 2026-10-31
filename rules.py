"""Authoritative two-player property game. Amounts are in 만원."""
import copy
import random

NAMES = ['출발', '타이베이', '황금열쇠', '베이징', '마닐라', '기금 납부', '싱가포르', '카이로',
         '무인도', '이스탄불', '황금열쇠', '아테네', '코펜하겐', '스톡홀름', '베른', '베를린',
         '사회복지기금', '오타와', '황금열쇠', '부에노스아이레스', '상파울루', '시드니', '하와이', '리스본',
         '세계여행', '마드리드', '황금열쇠', '도쿄', '파리', '로마', '런던', '서울']
SPECIAL = {0: 'start', 2: 'card', 5: 'tax', 8: 'island', 10: 'card', 16: 'fund', 18: 'card', 24: 'travel', 26: 'card'}
BOARD = [dict(name=n, kind=SPECIAL.get(i, 'city'), price=10 + i * 2,
              build=10 + (i // 8) * 5) for i, n in enumerate(NAMES)]


class Game:
    def __init__(self, rng=None):
        self.rng = rng or random.Random()
        self.state = dict(players=[dict(money=300, pos=0, jail=0) for _ in range(2)],
                          owners=[-1]*32, levels=[0]*32, turn=0, phase='roll', dice=[],
                          fund=0, winner=None, logs=['게임 시작! 플레이어 1이 먼저 진행합니다.'])

    def snapshot(self):
        return copy.deepcopy(self.state)

    def log(self, message):
        self.state['logs'] = (self.state['logs'] + [message])[-14:]

    def pay(self, who, amount, recipient=None):
        p = self.state['players'][who]
        # Automatically liquidate improvements, then land, at half cost.
        while p['money'] < amount:
            owned = [i for i, o in enumerate(self.state['owners']) if o == who]
            if not owned:
                break
            i = max(owned, key=lambda x: self.state['levels'][x])
            if self.state['levels'][i]:
                self.state['levels'][i] -= 1
                value = BOARD[i]['build']//2
            else:
                self.state['owners'][i] = -1
                value = BOARD[i]['price']//2
            p['money'] += value
            self.log(f'P{who+1}: {BOARD[i]["name"]} 자산 매각 +{value}')
        paid = min(p['money'], amount)
        p['money'] -= paid
        if recipient is not None:
            self.state['players'][recipient]['money'] += paid
        if paid < amount:
            self.state['winner'] = 1-who
            self.state['phase'] = 'over'
            self.log(f'P{who+1} 파산! P{2-who} 승리')
        return paid

    def land(self, who):
        s = self.state
        p = s['players'][who]
        i = p['pos']
        tile = BOARD[i]
        self.log(f'P{who+1}: {tile["name"]} 도착')
        if tile['kind'] == 'city':
            owner = s['owners'][i]
            if owner not in (-1, who):
                rent = (tile['price']//4) * [1, 3, 7, 14][s['levels'][i]]
                self.log(f'P{who+1} → P{owner+1} 통행료 {rent}')
                self.pay(who, rent, owner)
        elif tile['kind'] == 'tax':
            s['fund'] += self.pay(who, 20)
            self.log('사회복지기금 20 납부')
        elif tile['kind'] == 'fund':
            self.log(f'사회복지기금 {s["fund"]} 수령')
            p['money'] += s['fund']
            s['fund'] = 0
        elif tile['kind'] == 'island':
            p['jail'] = 2
            self.log('무인도: 다음 2턴 휴식')
        elif tile['kind'] == 'travel':
            self.log('세계여행: 목적지를 선택하세요 (비용 10)')
            s['phase'] = 'travel'
        elif tile['kind'] == 'card':
            card = self.rng.randrange(5)
            if card < 2:
                p['money'] += 30 if card == 0 else 50
                self.log(f'황금열쇠: 보너스 {30 if card == 0 else 50} 수령')
            elif card == 2:
                self.log('황금열쇠: 수리비 30 납부')
                self.pay(who, 30)
            elif card == 3:
                p['pos'] = 0
                p['money'] += 30
                self.log('황금열쇠: 출발로 이동, 월급 30 수령')
            else:
                p['pos'], p['jail'] = 8, 2
                self.log('황금열쇠: 무인도로 이동, 2턴 휴식')

    def act(self, who, action, target=None):
        s = self.state
        if type(who) is not int or who != s['turn'] or s['winner'] is not None:
            return False
        p = s['players'][who]
        i = p['pos']
        if action == 'roll' and s['phase'] == 'roll':
            if p['jail']:
                p['jail'] -= 1
                self.log(f'P{who+1} 무인도 휴식 (남은 횟수 {p["jail"]})')
                s['turn'] = 1-who
                return True
            s['dice'] = [self.rng.randint(1, 6), self.rng.randint(1, 6)]
            new = i + sum(s['dice'])
            if new >= 32:
                p['money'] += 30
                self.log(f'P{who+1} 출발 통과: 월급 30')
            p['pos'] = new % 32
            s['phase'] = 'manage'
            self.land(who)
        elif action == 'travel' and s['phase'] == 'travel' and type(target) is int and 0 <= target < 32 and target != 24:
            if p['money'] < 10:
                return False
            p['money'] -= 10
            p['pos'] = target
            s['phase'] = 'manage'
            self.land(who)
        elif action == 'buy' and s['phase'] == 'manage' and BOARD[i]['kind'] == 'city' and s['owners'][i] == -1 and p['money'] >= BOARD[i]['price']:
            p['money'] -= BOARD[i]['price']
            s['owners'][i] = who
            self.log(f'P{who+1}: {BOARD[i]["name"]} 구매')
        elif action == 'build' and s['phase'] == 'manage' and s['owners'][i] == who and s['levels'][i] < 3 and p['money'] >= BOARD[i]['build']:
            p['money'] -= BOARD[i]['build']
            s['levels'][i] += 1
            self.log(f'{BOARD[i]["name"]}: {s["levels"][i]}단계 건물 건설')
        elif action == 'end' and s['phase'] in ('manage', 'travel'):
            s['turn'], s['phase'] = 1-who, 'roll'
        else:
            return False
        return True
