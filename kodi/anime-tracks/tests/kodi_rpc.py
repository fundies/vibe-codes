"""Tiny Kodi JSON-RPC (TCP 9090) client for testing via `adb forward tcp:9090 tcp:9090`.

Usage: python3 kodi_rpc.py Method '{"json": "params"}'
"""
import json
import socket
import sys

_sock = None
_id = 0


def rpc(method, params=None, host='127.0.0.1', port=9090, timeout=10):
    global _sock, _id
    if _sock is None:
        _sock = socket.create_connection((host, port), timeout=timeout)
    _id += 1
    msg = {'jsonrpc': '2.0', 'method': method, 'id': _id}
    if params is not None:
        msg['params'] = params
    _sock.sendall(json.dumps(msg).encode())
    buf = ''
    dec = json.JSONDecoder()
    while True:
        chunk = _sock.recv(65536)
        if not chunk:
            raise ConnectionError('Kodi closed the connection')
        buf += chunk.decode('utf-8', 'ignore')
        i = 0
        while i < len(buf):
            while i < len(buf) and buf[i].isspace():
                i += 1
            try:
                obj, j = dec.raw_decode(buf, i)
            except ValueError:
                break
            i = j
            if obj.get('id') == _id:
                return obj
        buf = buf[i:]


if __name__ == '__main__':
    params = json.loads(sys.argv[2]) if len(sys.argv) > 2 else None
    print(json.dumps(rpc(sys.argv[1], params), indent=1, ensure_ascii=False))
