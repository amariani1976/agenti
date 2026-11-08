"""Guardia del proxy davanti al motore: se l'agente ripete la stessa chiamata a uno strumento con lo stesso risultato,
il proxy risponde da sé «lavoro concluso» (senza strumenti) e l'agente chiude il turno; poi il ciclo verifica il lavoro.
Inoltre un tetto alla lunghezza delle risposte quando la richiesta non lo indica."""
import json
import os
import sys
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


def chiamata(i, comando='python3 bin/agente --aiuto', nome='bash'):
    return {'role': 'assistant', 'content': None, 'tool_calls': [{'id': 'c%d' % i, 'type': 'function', 'function': {
        'name': nome, 'arguments': json.dumps({'command': comando})}}]}


def risultato(i, testo='Uso: agente'):
    return {'role': 'tool', 'tool_call_id': 'c%d' % i, 'content': testo}


def storia(n, **k):
    m = [{'role': 'system', 'content': 's'}, {'role': 'user', 'content': 'fai X'}]
    for i in range(n):
        m += [chiamata(i, **{x: v for x, v in k.items() if x in ('comando', 'nome')}), risultato(i, k.get('testo', 'Uso: agente'))]
    return m


class Funzioni(unittest.TestCase):
    def test_ripetizione(self):
        self.assertFalse(guardia.ripetizione(storia(2)))
        self.assertTrue(guardia.ripetizione(storia(3)))
        self.assertTrue(guardia.ripetizione(storia(5)))

    def test_non_ripetizione(self):
        m = storia(2) + [chiamata(9, comando='ls'), risultato(9)]
        self.assertFalse(guardia.ripetizione(m), 'comando diverso')
        m = storia(2) + [chiamata(9), risultato(9, 'altro risultato')]
        self.assertFalse(guardia.ripetizione(m), 'risultato diverso: il modello sta vedendo qualcosa di nuovo')
        m = storia(3) + [{'role': 'user', 'content': 'nuova richiesta'}]
        self.assertFalse(guardia.ripetizione(m), 'l\'ultimo messaggio non è un risultato di strumento')
        doppio = chiamata(9)
        doppio['tool_calls'].append(dict(doppio['tool_calls'][0], id='c10'))
        m = storia(2) + [doppio, risultato(9), risultato(10)]
        self.assertFalse(guardia.ripetizione(m), 'più chiamate nello stesso messaggio: non è la ripetizione semplice')
        self.assertFalse(guardia.ripetizione([]))
        self.assertFalse(guardia.ripetizione(None))

    def test_argomenti_equivalenti(self):
        m = storia(2)
        c = chiamata(9)
        c['tool_calls'][0]['function']['arguments'] = '{ "command" : "python3 bin/agente --aiuto" }'
        self.assertTrue(guardia.ripetizione(m + [c, risultato(9)]), 'stesso JSON scritto con spazi diversi')

    def test_chiusura_normale(self):
        r = guardia.chiusura({'model': 'm1'})
        self.assertEqual(r['object'], 'chat.completion')
        self.assertEqual(r['model'], 'm1')
        s = r['choices'][0]
        self.assertEqual(s['finish_reason'], 'stop')
        self.assertEqual(s['message']['role'], 'assistant')
        self.assertTrue(s['message']['content'])
        self.assertNotIn('tool_calls', s['message'])

    def test_chiusura_streaming(self):
        testo = guardia.chiusura_sse({'model': 'm1', 'stream': True})
        righe = [r for r in testo.split('\n\n') if r]
        self.assertTrue(all(r.startswith('data: ') for r in righe))
        self.assertEqual(righe[-1], 'data: [DONE]')
        pezzi = [json.loads(r[6:]) for r in righe[:-1]]
        self.assertTrue(pezzi[0]['choices'][0]['delta']['content'])
        self.assertEqual(pezzi[-1]['choices'][0]['finish_reason'], 'stop')
        self.assertTrue(all(p['object'] == 'chat.completion.chunk' and p['model'] == 'm1' for p in pezzi))

    def test_tetto(self):
        self.assertEqual(guardia.con_tetto({'messages': []}, 4096)['max_tokens'], 4096)
        self.assertEqual(guardia.con_tetto({'max_tokens': 100}, 4096)['max_tokens'], 100)
        self.assertNotIn('max_tokens', guardia.con_tetto({'max_completion_tokens': 100}, 4096))
        self.assertNotIn('max_tokens', guardia.con_tetto({'messages': []}, None))
        self.assertNotIn('max_tokens', guardia.con_tetto({'messages': []}, 0))


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
        self.srv = proxy.crea(ammissione.Coda(200000, 2), 'http://127.0.0.1:%d' % self.motore.server_address[1], '127.0.0.1', 0,
                              attesa_max=10, tetto=4096)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.url = 'http://127.0.0.1:%d/v1/chat/completions' % self.srv.server_address[1]

    def tearDown(self):
        for s in (self.srv, self.motore):
            s.shutdown()
            s.server_close()

    def post(self, dati):
        req = urllib.request.Request(self.url, data=json.dumps(dati).encode(), method='POST', headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, r.headers.get('Content-Type', ''), r.read().decode()

    def test_ripetizione_chiusa_dal_proxy_in_streaming(self):
        codice, tipo, testo = self.post({'model': 'm1', 'stream': True, 'messages': storia(3)})
        self.assertEqual(codice, 200)
        self.assertIn('text/event-stream', tipo)
        self.assertTrue(testo.rstrip().endswith('data: [DONE]'))
        self.assertIn('"finish_reason": "stop"', testo.replace('":"', '": "'))
        self.assertEqual(Motore.ricevuti, [], 'il motore non deve ricevere la richiesta ripetuta')

    def test_ripetizione_chiusa_dal_proxy_normale(self):
        codice, tipo, testo = self.post({'model': 'm1', 'messages': storia(4)})
        self.assertEqual(json.loads(testo)['choices'][0]['finish_reason'], 'stop')
        self.assertEqual(Motore.ricevuti, [])

    def test_richiesta_normale_passa_col_tetto(self):
        codice, tipo, testo = self.post({'model': 'm1', 'messages': storia(1)})
        self.assertEqual(json.loads(testo)['choices'][0]['message']['content'], 'dal motore')
        self.assertEqual(Motore.ricevuti[0]['max_tokens'], 4096)
        self.post({'model': 'm1', 'max_tokens': 50, 'messages': storia(1)})
        self.assertEqual(Motore.ricevuti[1]['max_tokens'], 50)


if __name__ == '__main__':
    unittest.main()
