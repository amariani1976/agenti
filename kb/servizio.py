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
