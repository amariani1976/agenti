"""Test della coda di ammissione davanti al motore: riserva di contesto, slot, priorità, proxy con streaming."""
import json
import os
import sys
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

QUI = os.path.dirname(os.path.abspath(__file__))
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(QUI, '..', 'coda'))
import ammissione  # noqa: E402
import proxy  # noqa: E402
import stima  # noqa: E402


class StimaTest(unittest.TestCase):
    def test_stima(self):
        corpo = {'messages': [{'role': 'user', 'content': 'x' * 300},
                              {'role': 'user', 'content': [{'type': 'text', 'text': 'y' * 30}, {'type': 'image_url'}]}],
                 'max_tokens': 100}
        self.assertEqual(stima.stima(corpo), 330 // 3 + 100 + 64)
        self.assertEqual(stima.stima({'messages': []}), stima.MAX_RISPOSTA + 64)
        self.assertEqual(stima.stima({'prompt': 'abc', 'max_completion_tokens': 10}), 1 + 10 + 64)


class CodaTest(unittest.TestCase):
    def test_capacita_e_slot(self):
        c = ammissione.Coda(100, 3)
        a = c.entra(60)
        b = c.entra(40)
        self.assertEqual(c.stato(), {'capacita': 100, 'slot_max': 3, 'attivi': 2, 'in_uso': 100, 'in_attesa': 0})
        with self.assertRaises(ammissione.Pieno):
            c.entra(1, attesa_max=0.2)
        c.esci(a)
        self.assertIsInstance(c.entra(60, attesa_max=1), int)
        c.esci(b)
        c.entra(10)
        c.entra(10)
        with self.assertRaises(ammissione.Pieno):          # 3 slot occupati anche se c'è contesto
            c.entra(1, attesa_max=0.2)

    def test_troppo_grande_ridotto_alla_capacita(self):
        c = ammissione.Coda(100, 2)
        c.esci(c.entra(500, attesa_max=1))

    def test_priorita_sconosciuta(self):
        with self.assertRaises(ValueError):
            ammissione.Coda(100, 2).entra(1, 'urgentissima')

    def test_attesa_e_ordine(self):
        c = ammissione.Coda(100, 1, invecchiamento=0)
        primo = c.entra(50)
        ordine = []
        def lavoro(nome, pr, ritardo):
            time.sleep(ritardo)
            b = c.entra(50, pr, attesa_max=5)
            ordine.append(nome)
            c.esci(b)
        th = [threading.Thread(target=lavoro, args=('bassa', 'bassa', 0)),
              threading.Thread(target=lavoro, args=('normale', 'normale', 0.05)),
              threading.Thread(target=lavoro, args=('alta', 'alta', 0.1))]
        [t.start() for t in th]
        time.sleep(0.3)
        self.assertEqual(c.stato()['in_attesa'], 3)
        c.esci(primo)
        [t.join(5) for t in th]
        self.assertEqual(ordine, ['alta', 'normale', 'bassa'])

    def test_grande_non_scavalcato(self):
        # un compito grande in testa alla coda non viene superato da uno piccolo arrivato dopo
        c = ammissione.Coda(100, 4, invecchiamento=0)
        a = c.entra(60)
        ordine = []
        def lavoro(nome, bisogno, ritardo):
            time.sleep(ritardo)
            b = c.entra(bisogno, attesa_max=5)
            ordine.append(nome)
            time.sleep(0.05)
            c.esci(b)
        th = [threading.Thread(target=lavoro, args=('grande', 90, 0)),
              threading.Thread(target=lavoro, args=('piccolo', 10, 0.1))]
        [t.start() for t in th]
        time.sleep(0.3)
        self.assertEqual(ordine, [])
        c.esci(a)
        [t.join(5) for t in th]
        self.assertEqual(ordine, ['grande', 'piccolo'])

    def test_invecchiamento(self):
        ora = [0.0]
        c = ammissione.Coda(100, 1, invecchiamento=10, orologio=lambda: ora[0])
        primo = c.entra(10)
        ordine = []
        def lavoro(nome, pr):
            b = c.entra(10, pr, attesa_max=5)
            ordine.append(nome)
            c.esci(b)
        t1 = threading.Thread(target=lavoro, args=('vecchia-bassa', 'bassa'))
        t1.start()
        time.sleep(0.1)
        ora[0] = 25.0                                        # la bassa aspetta da 25 s: due livelli in su
        t2 = threading.Thread(target=lavoro, args=('nuova-normale', 'normale'))
        t2.start()
        time.sleep(0.1)
        c.esci(primo)
        t1.join(5)
        t2.join(5)
        self.assertEqual(ordine, ['vecchia-bassa', 'nuova-normale'])


class Motore(BaseHTTPRequestHandler):
    """Motore finto: risponde in streaming a pezzi, lentamente; conta le richieste contemporanee."""
    attivi = 0
    massimo = 0
    lucchetto = threading.Lock()

    def log_message(self, *a):
        pass

    def do_GET(self):
        b = json.dumps({'data': [{'id': 'esecutore'}]}).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_POST(self):
        corpo = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        with Motore.lucchetto:
            Motore.attivi += 1
            Motore.massimo = max(Motore.massimo, Motore.attivi)
        try:
            if self.headers.get('X-Priorita'):
                self.send_response(500)
                self.end_headers()
                return
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.end_headers()
            for i in range(3):
                self.wfile.write(('data: {"pezzo": %d, "modello": "%s"}\n\n' % (i, corpo.get('model'))).encode())
                self.wfile.flush()
                time.sleep(0.1)
            self.wfile.write(b'data: [DONE]\n\n')
        finally:
            with Motore.lucchetto:
                Motore.attivi -= 1


class ProxyTest(unittest.TestCase):
    def setUp(self):
        Motore.attivi = Motore.massimo = 0
        self.motore = ThreadingHTTPServer(('127.0.0.1', 0), Motore)
        threading.Thread(target=self.motore.serve_forever, daemon=True).start()
        self.coda = ammissione.Coda(20000, 2)
        self.srv = proxy.crea(self.coda, 'http://127.0.0.1:%d' % self.motore.server_address[1], '127.0.0.1', 0, attesa_max=10)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.url = 'http://127.0.0.1:%d' % self.srv.server_address[1]

    def tearDown(self):
        for s in (self.srv, self.motore):
            s.shutdown()
            s.server_close()

    def libero(self):
        # la coda si libera subito dopo la risposta (nel finally del proxy): si attende al massimo 2 s
        for _ in range(40):
            if self.coda.stato()['attivi'] == 0:
                return True
            time.sleep(0.05)
        return False

    def post(self, percorso, dati, intestazioni=None):
        req = urllib.request.Request(self.url + percorso, data=json.dumps(dati).encode(), method='POST',
                                     headers=dict({'Content-Type': 'application/json'}, **(intestazioni or {})))
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return r.status, r.read().decode()
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode()

    def test_streaming_passa(self):
        codice, testo = self.post('/v1/chat/completions', {'model': 'esecutore', 'max_tokens': 10,
                                                           'messages': [{'role': 'user', 'content': 'ciao'}]})
        self.assertEqual(codice, 200)
        self.assertIn('"pezzo": 2, "modello": "esecutore"', testo)
        self.assertTrue(testo.rstrip().endswith('[DONE]'))
        self.assertTrue(self.libero())

    def test_get_e_stato(self):
        with urllib.request.urlopen(self.url + '/v1/models', timeout=10) as r:
            self.assertEqual(json.loads(r.read())['data'][0]['id'], 'esecutore')
        with urllib.request.urlopen(self.url + '/coda/stato', timeout=10) as r:
            self.assertEqual(json.loads(r.read())['slot_max'], 2)

    def test_massimo_due_insieme(self):
        th = [threading.Thread(target=self.post, args=('/v1/chat/completions', {'max_tokens': 10, 'messages': []}))
              for _ in range(5)]
        [t.start() for t in th]
        [t.join(20) for t in th]
        self.assertEqual(Motore.massimo, 2)

    def test_contesto_dichiarato(self):
        # due richieste da 15000 non stanno insieme in 20000: passano una alla volta
        th = [threading.Thread(target=self.post, args=('/v1/chat/completions', {'messages': []}, {'X-Contesto': '15000'}))
              for _ in range(2)]
        [t.start() for t in th]
        [t.join(20) for t in th]
        self.assertEqual(Motore.massimo, 1)

    def test_errori(self):
        self.assertEqual(self.post('/v1/chat/completions', {'messages': []}, {'X-Priorita': 'boh'})[0], 400)
        req = urllib.request.Request(self.url + '/v1/chat/completions', data=b'{rotto', method='POST')
        with self.assertRaises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(req, timeout=10)
        self.assertEqual(e.exception.code, 400)

    def test_motore_spento(self):
        self.motore.shutdown()
        self.motore.server_close()
        codice, testo = self.post('/v1/chat/completions', {'messages': []})
        self.assertEqual(codice, 502)
        self.assertTrue(self.libero())
        self.motore = type('Spento', (), {'shutdown': lambda s: None, 'server_close': lambda s: None})()


if __name__ == '__main__':
    unittest.main()
