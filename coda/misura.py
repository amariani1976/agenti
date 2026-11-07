"""Misura delle risposte del motore, per capire dove si ferma il modello: token, motivo di fine, ripetizioni.

Legge una copia del flusso mentre il proxy lo inoltra, senza modificarlo; un errore qui non tocca mai la risposta."""
import json
import os
import threading
import time

REGISTRO = os.environ.get('CODA_MISURE', os.path.expanduser('~/.local/state/ai-vm/misure-motore.jsonl'))
CODA_TESTO = 6000
FINESTRA = 40
_scrittura = threading.Lock()


def ripetizione(testo, finestra=FINESTRA):
    """Quota della coda del testo coperta dal pezzo di «finestra» caratteri più ripetuto: vicino a 1 vuol dire ciclo."""
    t = testo[-CODA_TESTO:]
    if len(t) < finestra * 4:
        return 0.0
    conti = {}
    for i in range(0, len(t) - finestra + 1, finestra // 2):
        p = t[i:i + finestra]
        conti[p] = conti.get(p, 0) + 1
    massimo = max(conti.values())
    return round(min(1.0, massimo * finestra / 2.0 / len(t) * 2), 3)


class Osservatore:
    def __init__(self, richiesta, percorso):
        self.inizio = time.time()
        self.percorso = percorso
        self.modello = richiesta.get('model', '') if isinstance(richiesta, dict) else ''
        self.max_token = richiesta.get('max_tokens') if isinstance(richiesta, dict) else None
        self.flusso = bool(richiesta.get('stream')) if isinstance(richiesta, dict) else False
        self.resto = b''
        self.corpo = []
        self.testo = ''
        self.pensiero = 0
        self.fine = None
        self.uso = {}
        self.stato = None

    def _testo(self, s):
        self.testo = (self.testo + s)[-CODA_TESTO:]

    def _scelta(self, c, chiave):
        d = c.get(chiave) or {}
        if d.get('content'):
            self._testo(d['content'])
        if d.get('reasoning_content'):
            self.pensiero += len(d['reasoning_content'])
            self._testo(d['reasoning_content'])
        for t in d.get('tool_calls') or []:
            self._testo(json.dumps(t.get('function', {}).get('arguments', ''))[:2000])
        if c.get('finish_reason'):
            self.fine = c['finish_reason']

    def _oggetto(self, o):
        for c in o.get('choices') or []:
            self._scelta(c, 'delta' if self.flusso else 'message')
        if o.get('usage'):
            self.uso = o['usage']
        if o.get('timings'):
            self.uso.setdefault('timings', {k: o['timings'].get(k) for k in ('prompt_n', 'predicted_n', 'predicted_ms')})

    def dati(self, pezzo):
        try:
            if not self.flusso:
                self.corpo.append(pezzo)
                return
            self.resto += pezzo
            righe = self.resto.split(b'\n')
            self.resto = righe.pop()
            for r in righe:
                r = r.strip()
                if r.startswith(b'data:') and r[5:].strip() not in (b'', b'[DONE]'):
                    self._oggetto(json.loads(r[5:]))
        except Exception:
            pass

    def chiudi(self, stato, errore=None):
        try:
            if not self.flusso and self.corpo:
                self._oggetto(json.loads(b''.join(self.corpo)))
        except Exception:
            pass
        t = self.uso.get('timings') or {}
        voce = {'at': int(self.inizio), 'secondi': round(time.time() - self.inizio, 1), 'percorso': self.percorso,
                'modello': self.modello, 'stato': stato, 'fine': self.fine, 'max_token': self.max_token,
                'token_prompt': self.uso.get('prompt_tokens', t.get('prompt_n')),
                'token_risposta': self.uso.get('completion_tokens', t.get('predicted_n')),
                'caratteri_pensiero': self.pensiero, 'ripetizione': ripetizione(self.testo), 'coda': self.testo[-300:]}
        if errore:
            voce['errore'] = str(errore)[:200]
        try:
            with _scrittura, open(os.environ.get('CODA_MISURE', REGISTRO), 'a', encoding='utf-8') as f:
                f.write(json.dumps(voce, ensure_ascii=False) + '\n')
        except OSError:
            pass
        return voce
