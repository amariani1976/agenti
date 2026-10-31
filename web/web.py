#!/usr/bin/env python3
"""Modulo per la ricerca su internet e la lettura delle pagine web.

Fornisce funzioni per cercare tramite SearXNG e leggere pagine web,
estraendo il testo in formato Markdown semplice.
"""

import argparse
import html.parser
import ipaddress
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

# Costanti
SEARXNG = 'http://10.0.0.100:8888'
MAX_CAR = 12000
LIMITI = {'cerca': 3, 'leggi': 5}
FINESTRA = 600

# Tag da saltare (non vengono inclusi nel testo estratto)
SALTA = {'script', 'style', 'noscript', 'svg', 'nav', 'footer', 'header',
         'aside', 'form', 'iframe', 'template'}

# Tag di blocco (aggiungono una riga vuota prima e dopo)
BLOCCHI = {'p', 'div', 'section', 'article', 'main', 'br', 'tr', 'table',
           'pre', 'blockquote'}

# Mappa dei titoli (da h1 a h6)
TITOLI = {f'h{i}': '#' * i for i in range(1, 7)}


class Testo(html.parser.HTMLParser):
    """Parser HTML che estrae il testo in formato Markdown semplice."""

    def __init__(self):
        super().__init__()
        self.titolo = ''
        self.testo = []
        self.in_pre = False
        self.in_lista = False
        self.in_salto = False
        self.tag_corrente = None
        self.pre_linee = []
        self.paragrafo_attivo = False
        self.paragrafo_testo = ''

    def _aggiungi_paragrafo(self):
        """Aggiunge il testo del paragrafo corrente al testo."""
        if self.paragrafo_testo.strip():
            testo = ' '.join(self.paragrafo_testo.split())
            if self.testo and self.testo[-1] != '':
                self.testo.append('')
            self.testo.append(testo)
        self.paragrafo_testo = ''
        self.paragrafo_attivo = False

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        self.tag_corrente = tag

        if tag in SALTA:
            self.in_salto = True
        elif tag == 'pre':
            if self.paragrafo_attivo:
                self._aggiungi_paragrafo()
            self.in_pre = True
            self.pre_linee = []
        elif tag == 'title':
            pass
        elif tag == 'li':
            if not self.in_lista:
                self.in_lista = True
                if self.testo and self.testo[-1] != '':
                    self.testo.append('')

    def handle_endtag(self, tag):
        tag = tag.lower()

        if tag in SALTA:
            self.in_salto = False
        elif tag == 'pre':
            self.in_pre = False
            if self.pre_linee:
                if self.testo and self.testo[-1] != '':
                    self.testo.append('')
                # Rimuovi i newline finali dalle linee del pre
                linee_pulite = [linea.rstrip('\n') for linea in self.pre_linee]
                self.testo.extend(linee_pulite)
        elif tag in ('p', 'div', 'section', 'article', 'main', 'blockquote'):
            if self.paragrafo_attivo:
                self._aggiungi_paragrafo()
                self.testo.append('')
        elif tag == 'li':
            pass
        elif tag == 'ul':
            self.in_lista = False
        elif tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
            # Titolo già gestito in handle_data
            pass

    def handle_data(self, data):
        if self.in_salto:
            return

        if self.tag_corrente == 'title':
            self.titolo = ' '.join(data.split())
            return

        if self.in_pre:
            self.pre_linee.append(data)
            return

        if self.tag_corrente == 'li':
            testo = data.strip()
            if testo:
                self.testo.append(f'- {testo}')
            return

        if self.tag_corrente in TITOLI:
            prefix = TITOLI[self.tag_corrente]
            testo = data.strip()
            if testo:
                if self.testo and self.testo[-1] != '':
                    self.testo.append('')
                self.testo.append(f'{prefix} {testo}')
                self.testo.append('')
            return

        if self.tag_corrente in BLOCCHI and self.tag_corrente not in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'pre'):
            # Paragrafo o altro blocco di testo
            if not self.paragrafo_attivo:
                self.paragrafo_attivo = True
                self.paragrafo_testo = ''
            self.paragrafo_testo += data
            return

        # Testo normale (dentro un paragrafo o altro)
        testo = ' '.join(data.split())
        if testo:
            if self.testo and self.testo[-1] != '':
                self.testo.append('')
            self.testo.append(testo)
            self.testo.append('')

    def get_testo(self):
        # Chiudi il paragrafo corrente se attivo
        if self.paragrafo_attivo:
            self._aggiungi_paragrafo()

        # Pulisci il testo: rimuovi righe vuote duplicate e TUTTE quelle finali
        risultato = []
        for riga in self.testo:
            if riga == '':
                if risultato and risultato[-1] != '':
                    risultato.append('')
            else:
                risultato.append(riga)

        # Rimuovi tutte le righe vuote finali
        while risultato and risultato[-1] == '':
            risultato.pop()

        return '\n'.join(risultato)


def estrai(pagina):
    """Estrae titolo e testo da una pagina HTML.

    Args:
        pagina: contenuto HTML come stringa.

    Returns:
        Tuple (titolo, testo) dove titolo è la stringa del <title>
        e testo è il contenuto in formato Markdown semplice.
    """
    parser = Testo()
    parser.feed(pagina)
    parser.get_testo()
    return parser.titolo, parser.get_testo()


def indirizzo_permesso(host, risolvi=socket.getaddrinfo):
    """Verifica se un host ha solo indirizzi pubblici.

    Args:
        host: nome da risolvere.
        risolvi: funzione di risoluzione (default socket.getaddrinfo).

    Returns:
        True se il nome non esiste o non ha indirizzi pubblici,
        False se tutti gli indirizzi sono globali e non multicast.
    """
    try:
        risultati = risolvi(host, 0)
    except (socket.gaierror, OSError):
        return False

    for _famiglia, _tipo, _proto, _, (host_addr, _) in risultati:
        try:
            addr = ipaddress.ip_address(host_addr)
        except ValueError:
            return False
        if not addr.is_global or addr.is_multicast:
            return False
    return True


def scarica(url, timeout=15, massimo=2 << 20):
    """Scarica una pagina web senza redirect automatici.

    Args:
        url: URL da scaricare.
        timeout: timeout in secondi per la connessione.
        massimo: numero massimo di byte da leggere.

    Returns:
        Tuple (codice, dizionario_intestazioni, corpo_in_byte).
        Un HTTPError viene trattato come risposta normale.
    """
    class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
        """Handler che blocca i redirect automatici."""
        def redirect_request(self, req, *args, **kwargs):
            return None

    # Crea un opener con l'handler per bloccare i redirect
    opener = urllib.request.build_opener(NoRedirectHandler())
    opener.addheaders = [('User-Agent', 'Mozilla/5.0 (agente locale; sola lettura)')]

    try:
        with opener.open(url, timeout=timeout) as risposta:
            corpo = risposta.read()
            # Leggi fino a massimo byte
            corpo = corpo[:massimo]
            intestazioni = dict(risposta.headers)
            return risposta.status, intestazioni, corpo
    except urllib.error.HTTPError as e:
        # Tratta HTTPError come risposta normale
        corpo = e.read()[:massimo]
        intestazioni = dict(e.headers)
        return e.code, intestazioni, corpo


def conta(tipo, file=None, ora=None, limiti=None, finestra=FINESTRA):
    """Controlla e aggiorna il conteggio degli usi per un tipo.

    Args:
        tipo: nome del tipo di uso (es. 'cerca', 'leggi').
        file: percorso del file JSON di conteggio (default ~/.cache/web/usi.json).
        ora: istante corrente in secondi (default time.time()).
        limiti: dizionario {tipo: massimo} (default LIMITI).
        finestra: durata della finestra in secondi (default FINESTRA).

    Returns:
        Il nuovo conteggio dopo l'aggiunta.

    Raises:
        ValueError: se il limite per il tipo è stato raggiunto.
    """
    import time as time_mod
    import json as json_mod
    import os as os_mod

    if file is None:
        file = os.path.expanduser('~/.cache/web/usi.json')
    if ora is None:
        ora = time_mod.time()
    if limiti is None:
        limiti = LIMITI

    # Carica il file JSON o usa un dizionario vuoto
    conteggi = {}
    try:
        with open(file, 'r') as f:
            conteggi = json_mod.load(f)
    except (IOError, json_mod.JSONDecodeError, OSError):
        # File rovinato o non esistente: usa vuoto
        conteggi = {}

    # Pulizia: tiene solo gli istanti dentro la finestra
    for t in conteggi:
        conteggi[t] = [i for i in conteggi[t] if ora - i < finestra]

    # Controlla se il limite è stato raggiunto
    istanti = conteggi.get(tipo, [])
    if len(istanti) >= limiti.get(tipo, 0):
        raise ValueError(f'limite raggiunto: {tipo}')

    # Aggiungi l'istante corrente e riscrivi il file
    istanti.append(ora)
    conteggi[tipo] = istanti

    # Crea la cartella se manca
    cartella = os.path.dirname(file)
    if cartella and not os.path.exists(cartella):
        os.makedirs(cartella, exist_ok=True)

    # Riscrive il file
    with open(file, 'w') as f:
        json_mod.dump(conteggi, f)

    return len(istanti)


def cerca(query, n=5, base=None, scarica=scarica):
    """Cerca su internet tramite SearXNG.

    Args:
        query: query di ricerca.
        n: numero massimo di risultati da restituire.
        base: URL base del motore di ricerca (opzionale).
        scarica: funzione per scaricare la risposta JSON.

    Returns:
        Lista di dizionari con 'titolo', 'url', 'estratto'.

    Raises:
        ValueError: se il codice HTTP non è 200.
    """
    # Determina la base: argomento, poi variabile WEB_SEARXNG, poi SEARXNG
    if base is None:
        base = os.environ.get('WEB_SEARXNG', SEARXNG)
    # Rimuovi la slash finale se presente
    base = base.rstrip('/')

    # Costruisci l'URL con i parametri
    params = {'q': query, 'format': 'json', 'categories': 'general,it'}
    url = base + '/search?' + urllib.parse.urlencode(params)

    # Scarica la risposta
    codice, intestazioni, corpo = scarica(url)
    if codice != 200:
        raise ValueError(f'errore HTTP: {codice}')

    # Parsa il JSON
    try:
        risposta = json.loads(corpo.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise ValueError(f'risposta JSON non valida: {e}')

    # Estrai i risultati
    results = risposta.get('results', [])
    risultati = []
    url_visti = set()

    for r in results:
        url = r.get('url', '')
        # Solo URL http(s)
        if not url.startswith(('http://', 'https://')):
            continue
        # Non duplicati
        if url in url_visti:
            continue
        url_visti.add(url)

        # Titolo: spazi compattati
        titolo = ' '.join(r.get('title', '').split())
        # Estratto: spazi compattati, max 300 caratteri
        estratto = r.get('content', '')
        estratto = ' '.join(estratto.split())
        if len(estratto) > 300:
            estratto = estratto[:300]

        risultati.append({'titolo': titolo, 'url': url, 'estratto': estratto})
        if len(risultati) >= n:
            break

    return risultati


if __name__ == '__main__':
    # Punto di ingresso per test manuali
    print('Modulo web.py caricato.')
