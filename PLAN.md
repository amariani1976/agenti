---
stato: in-esecuzione
ramo: ai/agenti-base
modello: esecutore
verifica_globale: python3 -m unittest tests/test_kb.py tests/test_agente.py
---
# Piano: parte 2 — KB come servizio (API JSON + MCP), fonti esterne, git, client

## Contesto
Progetto `agenti` (leggi `CLAUDE.md` e `docs/PROGETTO.md` §6). La parte 1 ha creato `kb/kb.py` (salva, leggi,
indicizza, cerca, riga di comando) e `bin/agente`. Questa parte:
- estende `kb/kb.py`: **fonti esterne** in sola lettura (percorsi `@nome/…`), colonna `fonte` nei risultati, ricerca
  robusta, campi `extra` nell'intestazione, controllo dei segreti anche sul titolo (la modalità client `KB_URL` è
  nella parte 4);
- crea `kb/servizio.py`: servizio HTTP con token (API `/cerca`, `/leggi`, `/salva`) e **server MCP** su `/mcp`
  (JSON-RPC: `initialize`, `ping`, `tools/list`, `tools/call`), un commit git a ogni salvataggio.

Solo libreria standard di Python 3. I test sono già scritti nei passi e sono la specifica. Comando dei test:
`python3 -m unittest tests/NOME.py` (niente pytest). Commenti e messaggi in italiano. Non usare git (lo usa solo il
codice del servizio, nei test). Non toccare `tests/test_kb.py` e `tests/test_agente.py`: devono continuare a passare.

## Passi

- [x] 1. Test delle aggiunte a `kb.py`
  File: `tests/test_kb_fonti.py` (nuovo)
  Cosa fare: crea `tests/test_kb_fonti.py` con **esattamente** questo contenuto, senza cambiare nulla:
```
"""Test delle aggiunte a kb/kb.py per la parte 2: fonti esterne, campi extra, fonte nei risultati."""
import os
import shutil
import sys
import tempfile
import unittest

QUI = os.path.dirname(os.path.abspath(__file__))
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(QUI, '..', 'kb'))
import kb  # noqa: E402


class FontiTest(unittest.TestCase):
    def setUp(self):
        self.kb = tempfile.mkdtemp()
        self.fonte = tempfile.mkdtemp()
        self.db = os.path.join(tempfile.mkdtemp(), 'indice.db')
        with open(os.path.join(self.kb, 'nota.md'), 'w') as f:
            f.write('# Nota\n\nIl motore usa llama-swap.\n')
        os.makedirs(os.path.join(self.fonte, 'docs'))
        with open(os.path.join(self.fonte, 'docs', 'GUIDA.md'), 'w') as f:
            f.write('# Guida AI-VM\n\nSearXNG risponde sulla porta 8888.\n')

    def tearDown(self):
        for d in (self.kb, self.fonte, os.path.dirname(self.db)):
            shutil.rmtree(d, ignore_errors=True)

    def test_indicizza_con_fonti(self):
        self.assertEqual(kb.indicizza(self.kb, self.db, {'aivm': self.fonte}), 2)
        r = kb.cerca(self.db, 'SearXNG')
        self.assertEqual(r[0]['path'], '@aivm/docs/GUIDA.md')
        self.assertEqual(r[0]['fonte'], 'aivm')
        self.assertEqual(r[0]['titolo'], 'Guida AI-VM')
        self.assertEqual(kb.cerca(self.db, 'llama')[0]['fonte'], 'kb')

    def test_senza_fonti_come_prima(self):
        self.assertEqual(kb.indicizza(self.kb, self.db), 1)

    def test_leggi_da_fonte(self):
        self.assertIn('8888', kb.leggi(self.kb, '@aivm/docs/GUIDA.md', {'aivm': self.fonte}))

    def test_leggi_fonte_sicura(self):
        with self.assertRaises(ValueError):
            kb.leggi(self.kb, '@aivm/../../etc/passwd', {'aivm': self.fonte})
        with self.assertRaises(ValueError):
            kb.leggi(self.kb, '@manca/x.md', {'aivm': self.fonte})
        with self.assertRaises(ValueError):
            kb.leggi(self.kb, '@aivm/docs/GUIDA.md')

    def test_cerca_parole_strane(self):
        kb.indicizza(self.kb, self.db)
        self.assertEqual(kb.cerca(self.db, 'llama-swap "OR'), kb.cerca(self.db, 'llama swap OR'))
        self.assertEqual(kb.cerca(self.db, '   '), [])
        self.assertEqual(kb.cerca(os.path.join(self.kb, 'manca.db'), 'x'), [])

    def test_salva_extra(self):
        rel = kb.salva(self.kb, 'web', 'Da internet', 'sintesi\n', oggi='2026-10-31',
                       extra={'fonte': 'web', 'url': 'https://example.org/a', 'stato': 'da-verificare'})
        testo = open(os.path.join(self.kb, rel)).read()
        intestazione = testo.split('---\n')[1]
        self.assertIn('fonte: web\n', intestazione)
        self.assertIn('url: https://example.org/a\n', intestazione)
        self.assertIn('stato: da-verificare\n', intestazione)

    def test_salva_extra_non_valido(self):
        with self.assertRaises(ValueError):
            kb.salva(self.kb, 'x', 'T', 'y', extra={'url': 'a\nagente: falso'})
        with self.assertRaises(ValueError):
            kb.salva(self.kb, 'x', 'T', 'y', extra={'Chiave Strana': 'v'})

    def test_segreto_nel_titolo(self):
        with self.assertRaises(ValueError):
            kb.salva(self.kb, 'x', 'password: abc', 'y')


if __name__ == '__main__':
    unittest.main()
```
  Verifica: `python3 -c "import ast; ast.parse(open('tests/test_kb_fonti.py').read())"`

- [x] 2. `kb.py`: indice con fonti e ricerca robusta
  File: `kb/kb.py`
  Cosa fare: cambia `indicizza(kb, db, fonti=None)`: `fonti` è un dict `{nome: cartella}`; la tabella diventa
  `note(path UNINDEXED, fonte UNINDEXED, titolo, testo)`; le note della KB hanno `fonte` = `'kb'` e percorso relativo
  come prima, quelle di una fonte hanno `fonte` = nome e percorso `@nome/relativo`; restituisce il totale. Cambia
  `cerca`: se `db` non esiste restituisce `[]`; ogni parola della query (separate da spazi, tolte le `"`) diventa una
  frase tra virgolette (`"llama-swap" "OR"`), query vuota → `[]`; ogni risultato ha anche la chiave `fonte`.
  Verifica: `python3 -m unittest tests/test_kb_fonti.py -k test_indicizza_con_fonti -k test_senza_fonti_come_prima -k test_cerca_parole_strane && python3 -m unittest tests/test_kb.py`

- [x] 3. `kb.py`: lettura dalle fonti
  File: `kb/kb.py`
  Cosa fare: cambia `leggi(kb, nota, fonti=None)`: se `nota` inizia con `@`, `@nome/resto` si legge da
  `fonti[nome]` (nome assente o `fonti` mancante → `ValueError`), altrimenti dalla KB; per entrambe valgono gli
  stessi controlli di sicurezza di prima (niente percorsi assoluti, niente uscite dalla cartella dopo `realpath`).
  Verifica: `python3 -m unittest tests/test_kb_fonti.py -k test_leggi && python3 -m unittest tests/test_kb.py`

- [x] 4. `kb.py`: campi extra e segreti nel titolo
  File: `kb/kb.py`
  Cosa fare: aggiungi a `salva` il parametro `extra=None` (dict): ogni coppia diventa una riga `chiave: valore`
  nell'intestazione, dopo `data:`. Chiave valida solo se `^[a-z][a-z0-9_-]*$` e valore senza a capo, altrimenti
  `ValueError` prima di creare file. `controlla_segreti` si applica a titolo e testo insieme.
  Verifica: `python3 -m unittest tests/test_kb_fonti.py && python3 -m unittest tests/test_kb.py`

- [x] 5. Test del servizio
  File: `tests/test_servizio.py` (nuovo)
  Cosa fare: crea `tests/test_servizio.py` con **esattamente** questo contenuto, senza cambiare nulla:
```
"""Test di kb/servizio.py: API JSON con token, server MCP, git a ogni salvataggio, fonti esterne."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request

QUI = os.path.dirname(os.path.abspath(__file__))
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(QUI, '..', 'kb'))
import servizio  # noqa: E402

TOKEN = 'token-di-prova-0123456789'


class Base(unittest.TestCase):
    def setUp(self):
        self.kb = tempfile.mkdtemp()
        self.fonti = tempfile.mkdtemp()
        self.db = os.path.join(tempfile.mkdtemp(), 'indice.db')
        with open(os.path.join(self.kb, 'neteye.md'), 'w') as f:
            f.write('# NetEye\n\nSolo verifica sul server.\n')
        os.makedirs(os.path.join(self.fonti, 'aivm'))
        with open(os.path.join(self.fonti, 'aivm', 'GUIDA.md'), 'w') as f:
            f.write('# Guida\n\nSearXNG sulla porta 8888.\n')
        os.makedirs(os.path.join(self.fonti, '.nascosta'))
        subprocess.run(['git', 'init', '-q', self.kb], check=True)
        self.stato = servizio.Kb(self.kb, self.db, servizio.carica_fonti(self.fonti), TOKEN)
        self.srv = servizio.crea(self.stato, '127.0.0.1', 0)
        self.url = 'http://127.0.0.1:%d' % self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        for d in (self.kb, self.fonti, os.path.dirname(self.db)):
            shutil.rmtree(d, ignore_errors=True)

    def chiama(self, metodo, percorso, dati=None, token=TOKEN, query=None):
        u = self.url + percorso + ('?' + urllib.parse.urlencode(query) if query else '')
        h = {'Content-Type': 'application/json'}
        if token:
            h['Authorization'] = 'Bearer ' + token
        req = urllib.request.Request(u, data=json.dumps(dati).encode() if dati is not None else None,
                                     method=metodo, headers=h)
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                corpo = r.read().decode()
                return r.status, json.loads(corpo) if corpo else None
        except urllib.error.HTTPError as e:
            corpo = e.read().decode()
            return e.code, json.loads(corpo) if corpo else None


class ApiTest(Base):
    def test_carica_fonti(self):
        self.assertEqual(servizio.carica_fonti(self.fonti), {'aivm': os.path.join(self.fonti, 'aivm')})
        self.assertEqual(servizio.carica_fonti(os.path.join(self.fonti, 'manca')), {})

    def test_salute_senza_token(self):
        self.assertEqual(self.chiama('GET', '/salute', token=None), (200, {'ok': True}))

    def test_token_obbligatorio(self):
        self.assertEqual(self.chiama('GET', '/cerca', token=None, query={'q': 'x'})[0], 401)
        self.assertEqual(self.chiama('GET', '/cerca', token='sbagliato', query={'q': 'x'})[0], 401)
        self.assertEqual(self.chiama('POST', '/salva', {'agente': 'a', 'titolo': 't', 'testo': 'x'}, token=None)[0], 401)
        self.assertEqual(self.chiama('POST', '/mcp', {'jsonrpc': '2.0', 'id': 1, 'method': 'ping'}, token=None)[0], 401)

    def test_cerca_e_leggi(self):
        codice, d = self.chiama('GET', '/cerca', query={'q': 'SearXNG'})
        self.assertEqual(codice, 200)
        self.assertEqual(d['risultati'][0]['path'], '@aivm/GUIDA.md')
        codice, d = self.chiama('GET', '/leggi', query={'nota': 'neteye.md'})
        self.assertEqual((codice, 'Solo verifica' in d['testo']), (200, True))
        self.assertEqual(self.chiama('GET', '/leggi', query={'nota': '../x.md'})[0], 400)
        self.assertEqual(self.chiama('GET', '/niente')[0], 404)

    def test_salva_commit_e_indice(self):
        codice, d = self.chiama('POST', '/salva', {'agente': 'programmatore', 'titolo': 'Lezione', 'testo': 'Usare iterator.\n',
                                                   'progetto': 'icinga-ui', 'extra': {'stato': 'da-verificare'}})
        self.assertEqual(codice, 200)
        self.assertTrue(d['path'].startswith('inbox/'))
        log = subprocess.run(['git', '-C', self.kb, 'log', '--format=%an|%s'], capture_output=True, text=True).stdout
        self.assertEqual(log.strip(), 'programmatore|kb: %s (programmatore)' % d['path'])
        self.assertEqual(self.chiama('GET', '/cerca', query={'q': 'iterator'})[1]['risultati'][0]['path'], d['path'])

    def test_salva_errori(self):
        self.assertEqual(self.chiama('POST', '/salva', {'agente': 'a'})[0], 400)
        codice, d = self.chiama('POST', '/salva', {'agente': 'a', 'titolo': 't', 'testo': 'password: x'})
        self.assertEqual(codice, 400)
        self.assertIn('segreto', d['errore'])


class McpTest(Base):
    def rpc(self, metodo, params=None, mid=1):
        msg = {'jsonrpc': '2.0', 'id': mid, 'method': metodo}
        if params is not None:
            msg['params'] = params
        return self.chiama('POST', '/mcp', msg)

    def test_initialize(self):
        codice, d = self.rpc('initialize', {'protocolVersion': '2025-06-18', 'capabilities': {},
                                            'clientInfo': {'name': 'prova', 'version': '0'}})
        self.assertEqual(codice, 200)
        self.assertEqual(d['id'], 1)
        self.assertEqual(d['result']['serverInfo']['name'], 'kb')
        self.assertIn('tools', d['result']['capabilities'])

    def test_notifica(self):
        codice, d = self.chiama('POST', '/mcp', {'jsonrpc': '2.0', 'method': 'notifications/initialized'})
        self.assertEqual((codice, d), (202, None))

    def test_tools_list(self):
        nomi = [t['name'] for t in self.rpc('tools/list')[1]['result']['tools']]
        self.assertEqual(nomi, ['kb_cerca', 'kb_leggi', 'kb_salva'])

    def test_tools_call(self):
        r = self.rpc('tools/call', {'name': 'kb_cerca', 'arguments': {'query': 'verifica'}})[1]['result']
        self.assertFalse(r['isError'])
        self.assertEqual(json.loads(r['content'][0]['text'])[0]['path'], 'neteye.md')
        r = self.rpc('tools/call', {'name': 'kb_salva', 'arguments': {'agente': 'claude', 'titolo': 'Da MCP', 'testo': 'ok'}})[1]['result']
        self.assertTrue(r['content'][0]['text'].startswith('inbox/'))
        r = self.rpc('tools/call', {'name': 'kb_leggi', 'arguments': {'nota': '/etc/passwd'}})[1]['result']
        self.assertTrue(r['isError'])

    def test_errori_jsonrpc(self):
        self.assertEqual(self.rpc('sconosciuto')[1]['error']['code'], -32601)
        self.assertEqual(self.rpc('tools/call', {'name': 'kb_cancella', 'arguments': {}})[1]['error']['code'], -32602)


class AvvioTest(unittest.TestCase):
    def test_senza_token_non_parte(self):
        env = dict(os.environ, KB_TOKEN='corto', PYTHONDONTWRITEBYTECODE='1')
        r = subprocess.run([sys.executable, os.path.join(QUI, '..', 'kb', 'servizio.py')], env=env,
                           capture_output=True, text=True, timeout=20)
        self.assertEqual(r.returncode, 1)
        self.assertIn('KB_TOKEN', r.stderr)


if __name__ == '__main__':
    unittest.main()
```
  Verifica: `python3 -c "import ast; ast.parse(open('tests/test_servizio.py').read())"`

- [x] 6. Servizio: parte HTTP già pronta
  File: `kb/servizio.py` (nuovo)
  Cosa fare: **non scrivere il file a mano.** Esegui soltanto, dalla radice del progetto, questo comando: crea il
  file con la parte HTTP completa e quattro funzioni ancora da scrivere (passi 7 e 8).
```
cat > kb/servizio.py <<'FINE'
"""Servizio HTTP della KB: API JSON e server MCP (Streamable HTTP, risposte JSON) sulla stessa porta."""
import hmac
import json
import os
import subprocess
import sys
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kb  # noqa: E402

VERSIONE_MCP = '2025-06-18'
STRUMENTI = [
    {'name': 'kb_cerca', 'description': 'Cerca nella knowledge base personale; restituisce percorso, titolo, estratto.',
     'inputSchema': {'type': 'object', 'properties': {'query': {'type': 'string'}, 'n': {'type': 'integer'}},
                     'required': ['query']}},
    {'name': 'kb_leggi', 'description': 'Legge una nota della knowledge base dal suo percorso.',
     'inputSchema': {'type': 'object', 'properties': {'nota': {'type': 'string'}}, 'required': ['nota']}},
    {'name': 'kb_salva', 'description': 'Salva una nota nella inbox della knowledge base (mai segreti).',
     'inputSchema': {'type': 'object', 'properties': {
         'agente': {'type': 'string'}, 'titolo': {'type': 'string'}, 'testo': {'type': 'string'},
         'progetto': {'type': 'string'}, 'extra': {'type': 'object'}},
         'required': ['agente', 'titolo', 'testo']}},
]
def carica_fonti(cartella):
    """Ogni sottocartella di `cartella` è una fonte esterna in sola lettura; cartella assente → nessuna fonte."""
    raise NotImplementedError


class Kb:
    """Stato condiviso del servizio: cartelle, indice e lucchetto per le scritture (passo 7)."""


def registra_git(kbdir, rel, agente):
    """Se la KB è un repository git, ogni salvataggio è un commit (annullabile)."""
    raise NotImplementedError


def chiama_strumento(stato, nome, args):
    raise NotImplementedError


def mcp(stato, msg):
    """Una richiesta JSON-RPC → risposta (dict) oppure None per le notifiche."""
    raise NotImplementedError


class Gestore(BaseHTTPRequestHandler):
    stato = None
    MAX_CORPO = 1 << 20

    def log_message(self, *a):
        pass

    def _rispondi(self, codice, dati=None):
        corpo = json.dumps(dati, ensure_ascii=False).encode() if dati is not None else b''
        self.send_response(codice)
        if dati is not None:
            self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def _autorizzato(self):
        atteso = 'Bearer ' + self.stato.token
        return bool(self.stato.token) and hmac.compare_digest(self.headers.get('Authorization', ''), atteso)

    def _corpo(self):
        n = int(self.headers.get('Content-Length') or 0)
        if n > self.MAX_CORPO:
            raise ValueError('richiesta troppo grande')
        return json.loads(self.rfile.read(n).decode() or 'null')

    def do_GET(self):
        u = urllib.parse.urlsplit(self.path)
        q = dict(urllib.parse.parse_qsl(u.query))
        if u.path == '/salute':
            return self._rispondi(200, {'ok': True})
        if not self._autorizzato():
            return self._rispondi(401, {'errore': 'non autorizzato'})
        try:
            if u.path == '/cerca':
                return self._rispondi(200, {'risultati': self.stato.cerca(q.get('q', ''), q.get('n', 5))})
            if u.path == '/leggi':
                return self._rispondi(200, {'testo': self.stato.leggi(q.get('nota', ''))})
        except (ValueError, OSError) as e:
            return self._rispondi(400, {'errore': str(e)})
        self._rispondi(404, {'errore': 'percorso sconosciuto'})

    def do_POST(self):
        u = urllib.parse.urlsplit(self.path)
        if not self._autorizzato():
            return self._rispondi(401, {'errore': 'non autorizzato'})
        try:
            dati = self._corpo()
        except ValueError as e:
            return self._rispondi(400, {'errore': str(e)})
        if u.path == '/salva':
            try:
                rel = self.stato.salva(dati['agente'], dati['titolo'], dati['testo'], dati.get('progetto'),
                                       dati.get('extra'))
                return self._rispondi(200, {'path': rel})
            except (KeyError, TypeError):
                return self._rispondi(400, {'errore': 'servono agente, titolo e testo'})
            except (ValueError, OSError) as e:
                return self._rispondi(400, {'errore': str(e)})
        if u.path == '/mcp':
            r = mcp(self.stato, dati) if isinstance(dati, dict) else None
            return self._rispondi(202) if r is None else self._rispondi(200, r)
        self._rispondi(404, {'errore': 'percorso sconosciuto'})


def crea(stato, host='0.0.0.0', porta=8787):
    gestore = type('G', (Gestore,), {'stato': stato})
    return ThreadingHTTPServer((host, porta), gestore)


def main():
    token = os.environ.get('KB_TOKEN', '')
    if len(token) < 16:
        print('kb-servizio: KB_TOKEN mancante o troppo corto (minimo 16 caratteri)', file=sys.stderr)
        return 1
    stato = Kb(os.environ.get('KB_DIR', '/kb'), os.environ.get('KB_DB', '/dati/indice.db'),
               carica_fonti(os.environ.get('KB_FONTI', '/fonti')), token)
    srv = crea(stato, os.environ.get('KB_HOST', '0.0.0.0'), int(os.environ.get('KB_PORTA', '8787')))
    print('kb-servizio in ascolto su %s:%d' % srv.server_address[:2], flush=True)
    srv.serve_forever()


if __name__ == '__main__':
    sys.exit(main())
FINE
```
  Verifica: `python3 -c "import ast; ast.parse(open('kb/servizio.py').read())" && grep -q "def do_POST" kb/servizio.py`

- [ ] 7. Servizio: fonti, stato e git
  File: `kb/servizio.py`
  Cosa fare: scrivi `carica_fonti`, la classe `Kb` e `registra_git` (leggi `tests/test_servizio.py`, classe
  `ApiTest`, e la parte HTTP già nel file: è la specifica).
  - `carica_fonti(cartella)`: `{nome: percorso}` delle sottocartelle non nascoste, in ordine; cartella assente → `{}`.
  - `Kb(kbdir, db, fonti=None, token='')`: salva gli attributi `kbdir`, `db`, `fonti` (dict), `token`, crea
    `self.lucchetto = threading.Lock()` e indicizza subito (`kb.indicizza(kbdir, db, fonti)`). Metodi:
    `cerca(query, n=5)` (`n` convertito con `int`), `leggi(nota)` (con le fonti),
    `salva(agente, titolo, testo, progetto=None, extra=None)`: sotto il lucchetto `kb.salva`, poi `registra_git`,
    poi re-indicizza; restituisce il percorso.
  - `registra_git(kbdir, rel, agente)`: se non esiste `kbdir/.git` restituisce `False`; altrimenti `git -C kbdir add --
    rel` e `git -C kbdir commit -q -m "kb: <rel> (<agente>)"` con `subprocess.run(..., check=True,
    capture_output=True)` e ambiente con `GIT_AUTHOR_NAME=agente`, `GIT_AUTHOR_EMAIL=kb@locale`,
    `GIT_COMMITTER_NAME=kb`, `GIT_COMMITTER_EMAIL=kb@locale`; restituisce `True`.
  Verifica: `python3 -m unittest tests/test_servizio.py -k ApiTest -k AvvioTest`

- [ ] 8. Servizio: MCP
  File: `kb/servizio.py`
  Cosa fare: scrivi `chiama_strumento` e `mcp` (classe `McpTest` dei test).
  - `chiama_strumento(stato, nome, args)`: `kb_cerca` → `json.dumps(stato.cerca(args['query'], args.get('n', 5)),
    ensure_ascii=False)`; `kb_leggi` → `stato.leggi(args['nota'])`; `kb_salva` → `stato.salva(args['agente'],
    args['titolo'], args['testo'], args.get('progetto'), args.get('extra'))`; altro nome → `KeyError(nome)`.
  - `mcp(stato, msg)`: messaggio senza `id` → `None` (notifica). Altrimenti risposta `{'jsonrpc': '2.0', 'id': …}` con
    `result`: `initialize` → `{'protocolVersion': VERSIONE_MCP, 'capabilities': {'tools': {}}, 'serverInfo':
    {'name': 'kb', 'version': '1'}}`; `ping` → `{}`; `tools/list` → `{'tools': STRUMENTI}`; `tools/call` →
    `{'content': [{'type': 'text', 'text': <testo>}], 'isError': False}`, con `ValueError`/`OSError` →
    stesso formato con il messaggio e `'isError': True`, con `KeyError` → `error` codice `-32602`. Metodo sconosciuto
    → `error` `{'code': -32601, 'message': 'metodo sconosciuto'}`.
  Verifica: `python3 -m unittest tests/test_servizio.py`

- [ ] 9. Controllo finale
  File: nessuno (correggi solo ciò che i comandi segnalano)
  Cosa fare: esegui tutti i test.
  Verifica: `python3 -m unittest tests/test_kb.py tests/test_agente.py tests/test_kb_fonti.py tests/test_servizio.py`
