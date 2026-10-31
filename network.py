"""Host-authoritative TCP transport with bounded JSON frames."""
import copy
import json
import queue
import socket
import threading
from rules import Game
DEFAULT_PORT = 5000

def local_ipv4_addresses():
    try:
        return sorted({x[4][0] for x in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET) if not x[4][0].startswith('127.')})
    except OSError:
        return []

def encode(message):
    return (json.dumps(message, ensure_ascii=True) + '\n').encode()

class JsonLines:
    def __init__(self):
        self.buffer = bytearray()
    def feed(self, data):
        self.buffer.extend(data)
        result = []
        while b'\n' in self.buffer:
            line, _, rest = self.buffer.partition(b'\n')
            if len(line) > 65536:
                raise ValueError('Message too large')
            self.buffer = bytearray(rest)
            item = json.loads(line)
            if not isinstance(item, dict):
                raise ValueError('Expected object')
            result.append(item)
        if len(self.buffer) > 65536:
            raise ValueError('Message too large')
        return result

class Session:
    def __init__(self, host, address='', port=DEFAULT_PORT):
        self.host, self.address, self.port = host, address, port
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.actions = queue.Queue(maxsize=16)
        self.game = Game()
        self.state = self.game.snapshot()
        self.status, self.connected = 'Starting...', False
        self.thread = threading.Thread(target=self._run, daemon=True)
    def start(self):
        self.thread.start()
    def close(self):
        self.stop_event.set()
    def action(self, action, target=None):
        if self.connected:
            try:
                self.actions.put_nowait(dict(type='action', action=action, target=target))
            except queue.Full:
                pass
    def snapshot(self):
        with self.lock:
            return copy.deepcopy(self.state), self.status, self.connected
    def _status(self, text, connected=False):
        with self.lock:
            self.status, self.connected = text, connected
    def _run(self):
        listener = peer = None
        try:
            if self.host:
                listener = socket.socket()
                if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
                    listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
                listener.bind(('0.0.0.0', self.port))
                listener.listen(1)
                listener.settimeout(.2)
                self._status(f'Waiting / 상대 접속 대기 (포트 {listener.getsockname()[1]})')
                while not self.stop_event.is_set():
                    try:
                        peer, _ = listener.accept()
                        break
                    except socket.timeout:
                        pass
                if peer is None:
                    return
            else:
                peer = socket.create_connection((self.address, self.port), timeout=5)
            peer.settimeout(5)
            peer.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self._status('연결됨', True)
            parser = JsonLines()
            # Lockstep exchange prevents unbounded outgoing buffering.
            while not self.stop_event.is_set():
                if self.host:
                    while not self.actions.empty():
                        item = self.actions.get_nowait()
                        self.game.act(0, item['action'], item['target'])
                    with self.lock:
                        self.state = self.game.snapshot()
                    peer.sendall(encode(dict(type='state', state=self.state)))
                else:
                    messages = []
                    while not self.actions.empty():
                        messages.append(self.actions.get_nowait())
                    peer.sendall(encode(dict(type='actions', items=messages)))
                messages = []
                while not messages and not self.stop_event.is_set():
                    data = peer.recv(16384)
                    if not data:
                        raise ConnectionError('상대방이 나갔습니다')
                    messages = parser.feed(data)
                for item in messages:
                    if self.host:
                        actions = item.get('items')
                        if item.get('type') != 'actions' or not isinstance(actions, list) or len(actions) > 16:
                            raise ValueError('Invalid actions')
                        for action in actions:
                            if not isinstance(action, dict):
                                raise ValueError('Invalid action')
                            self.game.act(1, action.get('action'), action.get('target'))
                    else:
                        if item.get('type') != 'state' or not isinstance(item.get('state'), dict):
                            raise ValueError('Invalid state')
                        with self.lock:
                            self.state = item['state']
                self.stop_event.wait(.05)
        except (OSError, ValueError, TypeError, RecursionError) as exc:
            self._status(f'Disconnected / 연결 종료: {exc}')
        finally:
            for sock in (peer, listener):
                if sock:
                    sock.close()
            if self.stop_event.is_set():
                self._status('종료됨')
