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
