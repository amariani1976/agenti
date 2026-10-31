---
stato: in-esecuzione
ramo: ai/coda-gpu
modello: esecutore
verifica_globale: python3 -m unittest tests/test_kb.py tests/test_agente.py tests/test_kb_fonti.py tests/test_servizio.py tests/test_cliente.py tests/test_web.py
aiuti: 1
collaudi: 1
---
# Piano: coda di ammissione davanti al motore (più agenti insieme sullo stesso modello)

## Contesto
Progetto `agenti` (leggi `CLAUDE.md`). Il motore (llama-swap + llama.cpp su Unraid) tiene un solo modello in GPU con
una riserva di contesto condivisa fra più slot (`-np 4 --kv-unified`). llama.cpp non mette in coda le richieste che
non ci stanno: lo fa questo componente, un proxy compatibile OpenAI sulla AI-VM (porta 9393) davanti a llama-swap.
Ogni richiesta `POST /v1/chat/completions` o `/v1/completions` dichiara (intestazione `X-Contesto`) o si vede stimare
(`stima.py`) i token che le servono; la coda (`ammissione.py`) la fa entrare solo se la somma dei token in uso più la
sua sta nella capacità e c'è uno slot libero, altrimenti la tiene in attesa: prima per priorità (`X-Priorita`: alta,
normale, bassa), poi per arrivo; chi aspetta sale di un livello ogni `invecchiamento` secondi; chi è in testa non viene
scavalcato. Le altre richieste passano senza coda. Solo libreria standard. Test già scritti nel passo 1: sono la
specifica. Comando: `python3 -m unittest tests/test_coda.py` (niente pytest). Commenti e messaggi in italiano. Non usare git.

## Passi

- [x] 1. Test della coda
  File: `tests/test_coda.py` (nuovo)
  Cosa fare: crea `tests/test_coda.py` con **esattamente** questo contenuto, senza cambiare nulla:
```
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
```
  Verifica: `python3 -c "import ast; ast.parse(open('tests/test_coda.py').read())"`

- [x] 2. Stima dei token (già pronta)
  File: `coda/stima.py` (nuovo)
  Cosa fare: **non scrivere il file a mano.** Esegui soltanto, dalla radice del progetto, questo comando. Non creare
  né toccare `coda/ammissione.py` o `coda/proxy.py` (sono i passi 3 e 4): la verifica sotto li sostituisce con moduli
  vuoti, quindi `ModuleNotFoundError: ammissione` qui non può più comparire.
```
mkdir -p coda
cat > coda/stima.py <<'FINE'
"""Stima dei token che servono a una richiesta OpenAI: caratteri // 3 + risposta massima + margine."""

MAX_RISPOSTA = 8192


def testo(contenuto):
    """Testo di un campo `content`: stringa così com'è, lista di parti → concatenazione dei `text`, altro → ''."""
    if isinstance(contenuto, str):
        return contenuto
    if isinstance(contenuto, list):
        return ''.join(str(p.get('text') or '') for p in contenuto if isinstance(p, dict))
    return ''


def stima(corpo):
    """Token stimati per la richiesta `corpo` (dict già decodificato dal JSON)."""
    caratteri = sum(len(testo(m.get('content'))) for m in corpo.get('messages') or [] if isinstance(m, dict))
    caratteri += len(str(corpo.get('prompt') or ''))
    caratteri += len(str(corpo.get('tools') or ''))
    risposta = corpo.get('max_tokens') or corpo.get('max_completion_tokens') or MAX_RISPOSTA
    return caratteri // 3 + int(risposta) + 64
FINE
```
  Verifica: `python3 -c "import sys, types, unittest; [sys.modules.setdefault(m, types.ModuleType(m)) for m in ('ammissione', 'proxy')]; sys.path.insert(0, 'tests'); import test_coda; r = unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(test_coda.StimaTest)); sys.exit(not r.wasSuccessful() or r.testsRun != 1)"`

- [x] 3. Coda: capacità e slot
  File: `coda/ammissione.py` (nuovo)
  Cosa fare: crea `coda/ammissione.py` (docstring in italiano; import `itertools`, `threading`, `time`) con
  `PRIORITA = {'alta': 0, 'normale': 1, 'bassa': 2}`, l'eccezione `Pieno(Exception)` e la classe
  `Coda(capacita, slot_max, invecchiamento=60.0, orologio=time.monotonic)`. Attributi: `self.cv =
  threading.Condition()`, `self.attivi = {}` (biglietto → token), `self.attesa = []` (voci `(numero, bisogno,
  priorita, arrivo)`), `self.numeri = itertools.count(1)`. Metodi:
  - `_ordine(voce)`: `promozione = int((self.orologio() - arrivo) // self.invecchiamento)` se `invecchiamento`,
    altrimenti 0; restituisce `(max(0, PRIORITA[priorita] - promozione), arrivo, numero)`;
  - `_primo()`: la voce di `self.attesa` con `_ordine` minimo (`None` se vuota);
  - `_entra_ora(bisogno)`: `len(self.attivi) < self.slot_max` e `sum(self.attivi.values()) + bisogno <= capacita`;
  - `entra(bisogno, priorita='normale', attesa_max=None)`: priorità sconosciuta → `ValueError`; `bisogno =
    min(int(bisogno), capacita)`; sotto `with self.cv`: crea la voce (`arrivo = self.orologio()`), la aggiunge ad
    `attesa`, poi ripete `self.cv.wait(...)` finché la voce non è `_primo()` **e** `_entra_ora(bisogno)`; il tempo
    massimo si conta con `time.monotonic()` (non con `orologio`): scaduto → toglie la voce, `notify_all()`, `raise
    Pieno(...)`; senza limite attende a intervalli di 1 s. Entrata: toglie la voce da `attesa`, `attivi[numero] =
    bisogno`, `notify_all()`, restituisce `numero`;
  - `esci(biglietto)`: toglie da `attivi` (se c'è) e `notify_all()`;
  - `stato()` → `{'capacita', 'slot_max', 'attivi': len, 'in_uso': somma, 'in_attesa': len(attesa)}`.
  Nota: `coda/proxy.py` non esiste ancora (passo 4): non crearlo; la verifica lo sostituisce con un modulo vuoto.
  Verifica: `python3 -c "import sys, types, unittest; sys.modules.setdefault('proxy', types.ModuleType('proxy')); sys.path.insert(0, 'tests'); import test_coda; r = unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(test_coda.CodaTest)); sys.exit(not r.wasSuccessful() or r.testsRun != 6)"`

- [x] 4. Proxy HTTP (già pronto)
  File: `coda/proxy.py` (nuovo)
  Cosa fare: **non scrivere il file a mano.** Esegui soltanto, dalla radice del progetto, questo comando:
```
cat > coda/proxy.py <<'FINE'
"""Proxy OpenAI con coda di ammissione davanti a llama-swap (parte HTTP già pronta: non modificarla)."""
import json
import os
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ammissione  # noqa: E402
import stima  # noqa: E402

AMMESSI = ('/v1/chat/completions', '/v1/completions')
SALTA = {'connection', 'keep-alive', 'transfer-encoding', 'content-length', 'host'}


class Gestore(BaseHTTPRequestHandler):
    coda = None
    upstream = None
    attesa_max = 600

    def log_message(self, *a):
        pass

    def _json(self, codice, dati):
        b = json.dumps(dati).encode()
        self.send_response(codice)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def _inoltra(self, corpo):
        h = {k: v for k, v in self.headers.items() if k.lower() not in SALTA and not k.lower().startswith('x-')}
        req = urllib.request.Request(self.upstream.rstrip('/') + self.path, data=corpo, method=self.command, headers=h)
        try:
            r = urllib.request.urlopen(req, timeout=3600)
        except urllib.error.HTTPError as e:
            r = e
        except (urllib.error.URLError, OSError) as e:
            return self._json(502, {'error': {'message': 'motore non raggiungibile: %s' % e}})
        with r:
            self.send_response(r.status if hasattr(r, 'status') else r.code)
            for k, v in r.headers.items():
                if k.lower() not in SALTA:
                    self.send_header(k, v)
            self.send_header('Connection', 'close')
            self.end_headers()
            while True:
                pezzo = r.read1(65536) if hasattr(r, 'read1') else r.read(65536)
                if not pezzo:
                    break
                self.wfile.write(pezzo)
                self.wfile.flush()

    def do_GET(self):
        if self.path == '/coda/stato':
            return self._json(200, self.coda.stato())
        self._inoltra(None)

    def do_POST(self):
        corpo = self.rfile.read(int(self.headers.get('Content-Length') or 0))
        if self.path.split('?')[0] not in AMMESSI:
            return self._inoltra(corpo)
        try:
            dati = json.loads(corpo or b'{}')
        except ValueError:
            return self._json(400, {'error': {'message': 'JSON non valido'}})
        bisogno = int(self.headers.get('X-Contesto') or stima.stima(dati))
        priorita = self.headers.get('X-Priorita', 'normale')
        try:
            biglietto = self.coda.entra(bisogno, priorita, self.attesa_max)
        except ValueError as e:
            return self._json(400, {'error': {'message': str(e)}})
        except ammissione.Pieno as e:
            return self._json(503, {'error': {'message': 'coda piena: %s' % e}})
        try:
            self._inoltra(corpo)
        finally:
            self.coda.esci(biglietto)


def crea(coda, upstream, host='127.0.0.1', porta=9393, attesa_max=600):
    g = type('G', (Gestore,), {'coda': coda, 'upstream': upstream, 'attesa_max': attesa_max})
    return ThreadingHTTPServer((host, porta), g)


def main():
    coda = ammissione.Coda(int(os.environ.get('CODA_CAPACITA', '186000')), int(os.environ.get('CODA_SLOT', '4')))
    srv = crea(coda, os.environ.get('CODA_UPSTREAM', 'http://10.0.0.100:9292'), os.environ.get('CODA_HOST', '127.0.0.1'),
               int(os.environ.get('CODA_PORTA', '9393')))
    srv.serve_forever()


if __name__ == '__main__':
    sys.exit(main())
FINE
```
  Verifica: `python3 -m unittest tests/test_coda.py`

- [x] 5. Controllo finale
  File: nessuno (correggi solo ciò che i comandi segnalano)
  Cosa fare: esegui tutti i test.
  Verifica: `python3 -m unittest tests/test_coda.py && python3 -m unittest discover -s tests -p 'test_*.py'`
