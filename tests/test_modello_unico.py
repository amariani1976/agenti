"""Il modello si sceglie solo in modelli.json: il proxy traduce i nomi generici nel modello attivo."""
import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'coda'))
import ammissione  # noqa: E402
import guardia  # noqa: E402
import proxy  # noqa: E402

PROFILI = {'attivo': 'piccolo', 'profili': {
    'piccolo': {'senza_pensiero': 'p-no', 'con_pensiero': 'p-si', 'contesto': 1000, 'risposta_max': 100, 'risposta_max_pensiero': 200},
    'grande': {'senza_pensiero': 'g-no', 'con_pensiero': 'g-si', 'contesto': 2000, 'risposta_max': 300}}}


class Risolvi(unittest.TestCase):
    def test_generici(self):
        self.assertEqual(guardia.risolvi_modello(PROFILI, 'esecutore'), 'p-no')
        self.assertEqual(guardia.risolvi_modello(PROFILI, 'esecutore-pensiero'), 'p-si')
        self.assertEqual(guardia.risolvi_modello(PROFILI, 'hermes'), 'p-no', 'Hermes prima senza ragionamento')

    def test_ragionamento_dopo_un_errore(self):
        ok = [{'role': 'user', 'content': 'fai'}, {'role': 'assistant', 'content': ''},
              {'role': 'tool', 'tool_call_id': '1', 'content': 'tutto bene'}]
        rotto = ok[:2] + [{'role': 'tool', 'tool_call_id': '1', 'content': [{'type': 'text', 'text': 'Traceback (most recent call last):'}]}]
        for nome in ('esecutore', 'hermes'):
            self.assertEqual(guardia.risolvi_modello(PROFILI, nome, ok), 'p-no')
            self.assertEqual(guardia.risolvi_modello(PROFILI, nome, rotto), 'p-si')
        nuova = rotto + [{'role': 'assistant', 'content': 'ok'}, {'role': 'user', 'content': 'altro'}]
        self.assertEqual(guardia.risolvi_modello(PROFILI, 'hermes', nuova), 'p-no', 'una richiesta nuova riparte senza')

    def test_altri_invariati(self):
        self.assertEqual(guardia.risolvi_modello(PROFILI, 'g-no'), 'g-no')
        self.assertEqual(guardia.risolvi_modello(None, 'esecutore'), 'esecutore')

    def test_senza_variante_con_pensiero(self):
        d = {'attivo': 'x', 'profili': {'x': {'senza_pensiero': 'x-no'}}}
        self.assertEqual(guardia.risolvi_modello(d, 'esecutore-pensiero'), 'x-no')


class Motore(BaseHTTPRequestHandler):
    visti = []

    def log_message(self, *a):
        pass

    def do_POST(self):
        d = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        Motore.visti.append((d.get('model'), d.get('max_tokens')))
        b = json.dumps({'choices': [{'message': {'role': 'assistant', 'content': 'ok'}}]}).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(b)))
        self.end_headers()
        self.wfile.write(b)


class Proxy(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.p = os.path.join(self.d, 'modelli.json')
        self.scrivi('piccolo')
        self.motore = ThreadingHTTPServer(('127.0.0.1', 0), Motore)
        threading.Thread(target=self.motore.serve_forever, daemon=True).start()
        self.srv = proxy.crea(ammissione.Coda(100000, 2), 'http://127.0.0.1:%d' % self.motore.server_port, porta=0, profili=self.p)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        Motore.visti = []

    def tearDown(self):
        self.srv.shutdown()
        self.motore.shutdown()

    def scrivi(self, attivo):
        d = dict(PROFILI, attivo=attivo)
        with open(self.p, 'w') as f:
            json.dump(d, f)

    def chiedi(self, modello):
        b = json.dumps({'model': modello, 'messages': [{'role': 'user', 'content': 'ciao'}]}).encode()
        r = urllib.request.Request('http://127.0.0.1:%d/v1/chat/completions' % self.srv.server_port, data=b,
                                   headers={'Content-Type': 'application/json'})
        urllib.request.urlopen(r, timeout=10).read()
        return Motore.visti[-1]

    def test_traduce_e_applica_il_tetto(self):
        self.assertEqual(self.chiedi('esecutore'), ('p-no', 100))
        self.assertEqual(self.chiedi('esecutore-pensiero'), ('p-si', 200))

    def test_cambio_del_modello_attivo_senza_riavvio(self):
        self.chiedi('esecutore')
        self.scrivi('grande')
        self.assertEqual(self.chiedi('esecutore'), ('g-no', 300))
        self.assertEqual(self.chiedi('hermes'), ('g-no', 300))


class AccordaCoda(unittest.TestCase):
    def test_dai_valori_del_motore(self):
        d = tempfile.mkdtemp()
        p = os.path.join(d, 'applicato.json')
        c = ammissione.Coda(10 ** 9, 1)
        self.assertFalse(guardia.accorda_coda(c, p), 'senza valori la coda resta com\'è')
        with open(p, 'w') as f:
            json.dump({'contesto': 1000, 'parallelo': 3}, f)
        self.assertTrue(guardia.accorda_coda(c, p))
        self.assertEqual((c.capacita, c.slot_max), (950, 3))
        self.assertFalse(guardia.accorda_coda(c, p), 'stessi valori: nessun cambio')


if __name__ == '__main__':
    unittest.main()
