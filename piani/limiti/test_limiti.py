"""Limiti del proxy validi per qualunque modello: (1) un tetto di chiamate agli strumenti nello stesso turno dell'agente
(dall'ultimo messaggio dell'utente): oltre, il proxy chiude il turno «lavoro concluso» e il ciclo verifica cosa è stato
fatto; copre anche i cicli non identici (stesso file letto a pezzi diversi); (2) il tetto delle risposte preso dal profilo
del modello richiesto (modelli.json di AI-VM), se la richiesta non lo indica."""
import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

QUI = os.path.dirname(os.path.abspath(__file__))
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(QUI, '..', 'coda'))
import ammissione  # noqa: E402
import guardia  # noqa: E402
import proxy  # noqa: E402

PROFILI = {'attivo': 'a', 'profili': {
    'a': {'senza_pensiero': 'esecutore', 'con_pensiero': 'esecutore-pensiero', 'contesto': 1000, 'risposta_max': 16384,
          'risposta_max_pensiero': 32768},
    'b': {'senza_pensiero': 'piccolo', 'con_pensiero': 'piccolo-pensiero', 'contesto': 1000, 'risposta_max': 4096}}}


def turno(n, utente_dopo=None):
    m = [{'role': 'system', 'content': 's'}, {'role': 'user', 'content': 'fai X'}]
    for i in range(n):
        m += [{'role': 'assistant', 'content': None, 'tool_calls': [{'id': 'c%d' % i, 'type': 'function', 'function': {
            'name': 'read', 'arguments': json.dumps({'path': 'a.py', 'offset': i})}}]},
              {'role': 'tool', 'tool_call_id': 'c%d' % i, 'content': 'riga %d' % i}]
    return m


class Funzioni(unittest.TestCase):
    def test_troppe_chiamate(self):
        self.assertFalse(guardia.troppe_chiamate(turno(39), 40))
        self.assertTrue(guardia.troppe_chiamate(turno(40), 40))
        self.assertFalse(guardia.troppe_chiamate(turno(40), None), 'senza tetto non scatta')
        self.assertFalse(guardia.troppe_chiamate(turno(40), 0))
        self.assertFalse(guardia.troppe_chiamate(None, 40))

    def test_conta_solo_il_turno_corrente(self):
        m = turno(30) + [{'role': 'user', 'content': 'nuovo compito'}] + turno(15)[2:]
        self.assertFalse(guardia.troppe_chiamate(m, 40), 'le chiamate prima dell\'ultimo messaggio dell\'utente non contano')
        doppie = turno(0)
        for i in range(20):
            doppie += [{'role': 'assistant', 'content': None, 'tool_calls': [
                {'id': 'x%d' % i, 'type': 'function', 'function': {'name': 'read', 'arguments': '{}'}},
                {'id': 'y%d' % i, 'type': 'function', 'function': {'name': 'ls', 'arguments': '{}'}}]}]
        self.assertTrue(guardia.troppe_chiamate(doppie, 40), 'si contano le chiamate, non i messaggi')

    def test_tetto_dal_profilo(self):
        self.assertEqual(guardia.tetto_profilo(PROFILI, 'esecutore'), 16384)
        self.assertEqual(guardia.tetto_profilo(PROFILI, 'esecutore-pensiero'), 32768)
        self.assertEqual(guardia.tetto_profilo(PROFILI, 'piccolo-pensiero'), 4096)
        self.assertIsNone(guardia.tetto_profilo(PROFILI, 'sconosciuto'))
        self.assertIsNone(guardia.tetto_profilo(None, 'esecutore'))

    def test_carica_profili(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        p = os.path.join(d, 'modelli.json')
        self.assertIsNone(guardia.carica_profili(p))
        with open(p, 'w') as f:
            f.write('{')
        self.assertIsNone(guardia.carica_profili(p))
        with open(p, 'w') as f:
            json.dump(PROFILI, f)
        self.assertEqual(guardia.carica_profili(p)['attivo'], 'a')


class Motore(BaseHTTPRequestHandler):
    ricevuti = []

    def log_message(self, *a):
        pass

    def do_POST(self):
        Motore.ricevuti.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
        b = json.dumps({'object': 'chat.completion', 'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': 'dal motore'},
                                                                  'finish_reason': 'stop'}]}).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(b)))
        self.end_headers()
        self.wfile.write(b)


class Proxy(unittest.TestCase):
    def setUp(self):
        Motore.ricevuti = []
        self.motore = ThreadingHTTPServer(('127.0.0.1', 0), Motore)
        threading.Thread(target=self.motore.serve_forever, daemon=True).start()
        self.srv = proxy.crea(ammissione.Coda(2000000, 2), 'http://127.0.0.1:%d' % self.motore.server_address[1], '127.0.0.1', 0,
                              attesa_max=10, max_chiamate=40, profili=PROFILI)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.url = 'http://127.0.0.1:%d/v1/chat/completions' % self.srv.server_address[1]

    def tearDown(self):
        for s in (self.srv, self.motore):
            s.shutdown()
            s.server_close()

    def post(self, dati):
        req = urllib.request.Request(self.url, data=json.dumps(dati).encode(), method='POST', headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.read().decode()

    def test_troppe_chiamate_chiuse_dal_proxy(self):
        r = json.loads(self.post({'model': 'piccolo', 'messages': turno(40)}))
        self.assertEqual(r['choices'][0]['finish_reason'], 'stop')
        self.assertEqual(Motore.ricevuti, [])

    def test_tetto_del_modello_richiesto(self):
        self.post({'model': 'piccolo', 'messages': turno(1)})
        self.post({'model': 'esecutore-pensiero', 'messages': turno(1)})
        self.post({'model': 'sconosciuto', 'messages': turno(1)})
        self.post({'model': 'piccolo', 'max_tokens': 77, 'messages': turno(1)})
        self.assertEqual([r.get('max_tokens') for r in Motore.ricevuti], [4096, 32768, None, 77])


if __name__ == '__main__':
    unittest.main()
