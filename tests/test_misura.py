"""Misura delle risposte: il flusso arriva intatto al cliente e il registro dice token, fine e ripetizioni."""
import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'coda'))
REG = tempfile.mktemp(suffix='.jsonl')
os.environ['CODA_MISURE'] = REG
import ammissione  # noqa: E402
import misura  # noqa: E402
import proxy  # noqa: E402

PEZZI = [{'choices': [{'delta': {'reasoning_content': 'penso '}}]}, {'choices': [{'delta': {'content': 'ciao ' * 50}}]},
         {'choices': [{'delta': {}, 'finish_reason': 'length'}], 'timings': {'prompt_n': 120, 'predicted_n': 51, 'predicted_ms': 900}}]


class Finto(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        self.rfile.read(int(self.headers.get('Content-Length') or 0))
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.end_headers()
        for p in PEZZI:
            self.wfile.write(b'data: ' + json.dumps(p).encode() + b'\n\n')
        self.wfile.write(b'data: [DONE]\n\n')


class Misura(unittest.TestCase):
    def setUp(self):
        self.motore = ThreadingHTTPServer(('127.0.0.1', 0), Finto)
        threading.Thread(target=self.motore.serve_forever, daemon=True).start()
        self.srv = proxy.crea(ammissione.Coda(100000, 2), 'http://127.0.0.1:%d' % self.motore.server_address[1], porta=0)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.addCleanup(self.motore.shutdown)
        self.addCleanup(self.srv.shutdown)
        if os.path.exists(REG):
            os.remove(REG)

    def test_flusso_intatto_e_registro(self):
        corpo = json.dumps({'model': 'esecutore', 'stream': True, 'max_tokens': 51, 'messages': [{'role': 'user', 'content': 'x'}]}).encode()
        r = urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:%d/v1/chat/completions' % self.srv.server_address[1], data=corpo,
                                                          headers={'Content-Type': 'application/json'}), timeout=10).read()
        self.assertIn(b'"finish_reason": "length"', r)
        self.assertTrue(r.endswith(b'data: [DONE]\n\n'))
        v = json.loads(open(REG).read().splitlines()[-1])
        self.assertEqual((v['modello'], v['fine'], v['token_prompt'], v['token_risposta'], v['stato']), ('esecutore', 'length', 120, 51, 200))
        self.assertEqual(v['caratteri_pensiero'], 6)
        self.assertGreater(v['ripetizione'], 0.8)

    def test_testo_vario_non_e_ciclo(self):
        self.assertLess(misura.ripetizione(' '.join(str(i * 7919) for i in range(2000))), 0.2)

    def test_motore_spento(self):
        self.motore.shutdown()
        self.motore.server_close()
        corpo = json.dumps({'model': 'esecutore', 'messages': []}).encode()
        try:
            urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:%d/v1/chat/completions' % self.srv.server_address[1], data=corpo), timeout=10)
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 502)
        self.assertEqual(json.loads(open(REG).read().splitlines()[-1])['stato'], 502)


if __name__ == '__main__':
    unittest.main()
