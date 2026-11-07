#!/usr/bin/env python3
"""Knowledge Base in Markdown per il progetto agenti.

Questa modulo fornisce funzionalità di salvataggio, lettura e indicizzazione
di documenti Markdown in una knowledge base locale.
"""

import os
import re
import sqlite3
import sys
from datetime import date


# Pattern per rilevare segreti nel testo
SEGRETI = [
    re.compile(r'password\s*[:=]', re.IGNORECASE),
    re.compile(r'(token|secret|api_?key)\s*[:=]', re.IGNORECASE),
    re.compile(r'ghp_[A-Za-z0-9]{30,}'),
    re.compile(r'-----BEGIN [A-Z ]*PRIVATE KEY-----'),
]


def slug(titolo):
    """Converte un titolo in uno slug.
    
    Args:
        titolo: Il titolo da convertire.
        
    Returns:
        Uno slug in minuscolo con caratteri speciali sostituiti da '-'.
        Se il titolo è vuoto o solo spazi, restituisce 'nota'.
    """
    if not titolo or titolo.strip() == '':
        return 'nota'
    # Converti in minuscolo
    s = titolo.lower()
    # Sostituisci caratteri non alfanumerici con '-'
    s = re.sub(r'[^a-z0-9]+', '-', s)
    # Rimuovi '-' all'inizio e alla fine
    s = s.strip('-')
    # Sostituisci doppi o tripli '-' con uno singolo
    s = re.sub(r'-+', '-', s)
    return s if s else 'nota'


def controlla_segreti(testo):
    """Controlla se il testo contiene segreti.
    
    Args:
        testo: Il testo da controllare.
        
    Raises:
        ValueError: Se il testo sembra contenere un segreto.
    """
    for pattern in SEGRETI:
        if pattern.search(testo):
            raise ValueError('il testo sembra contenere un segreto')


def salva(kb, agente, titolo, testo, progetto=None, oggi=None, extra=None):
    """Salva un documento nella knowledge base.
    
    Crea un file Markdown con intestazione YAML contenente metadati.
    Se il file esiste già, prova con suffissi numerici (-2, -3, ...).
    
    Args:
        kb: Directory della knowledge base.
        agente: Nome dell'agente.
        titolo: Titolo del documento.
        testo: Contenuto del documento.
        progetto: Nome del progetto (opzionale).
        oggi: Data in formato AAAA-MM-GG (default: data di oggi).
        extra: Dizionario di campi extra da aggiungere all'intestazione (opzionale).
        
    Returns:
        Il percorso relativo del file creato.
        
    Raises:
        ValueError: Se il testo o il titolo contengono segreti, o se extra ha chiavi non valide.
    """
    if oggi is None:
        oggi = date.today().strftime('%Y-%m-%d')
    
    # Controlla segreti nel testo
    controlla_segreti(testo)
    
    # Controlla segreti anche nel titolo
    controlla_segreti(titolo)
    
    # Controlla e valida extra
    if extra:
        # Chiavi valide: ^[a-z][a-z0-9_-]*$, nessun newline
        for chiave, valore in extra.items():
            if not re.match(r'^[a-z][a-z0-9_-]*$', chiave):
                raise ValueError('chiave non valida in extra')
            if '\n' in str(valore):
                raise ValueError('valore in extra contiene newline')
            # Controlla segreti anche nei valori extra
            controlla_segreti(str(valore))
    
    # Crea directory inbox se non esiste
    inbox_dir = os.path.join(kb, 'inbox')
    os.makedirs(inbox_dir, exist_ok=True)
    
    # Genera nome file
    base_slug = slug(titolo)
    nome_base = f'{oggi}-{base_slug}'
    percorso = os.path.join(inbox_dir, f'{nome_base}.md')
    
    # Trova nome unico
    tentativo = 1
    while os.path.exists(percorso):
        tentativo += 1
        percorso = os.path.join(inbox_dir, f'{nome_base}-{tentativo}.md')
    
    # Costruisci intestazione YAML
    righe = ['---']
    righe.append(f'agente: {agente}')
    if progetto:
        righe.append(f'progetto: {progetto}')
    righe.append(f'data: {oggi}')
    # Aggiungi campi extra se presenti
    if extra:
        for chiave, valore in extra.items():
            righe.append(f'{chiave}: {valore}')
    righe.append('---')
    righe.append(f'# {titolo}')
    righe.append('')
    righe.append(testo)
    
    contenuto = '\n'.join(righe)
    
    # Crea file con 'x' (fallisce se esiste)
    with open(percorso, 'x') as f:
        f.write(contenuto)
    
    # Restituisce percorso relativo
    return os.path.relpath(percorso, kb)


def leggi(kb, path, fonti=None):
    """Legge un file dalla knowledge base o da una fonte esterna.
    
    Args:
        kb: Directory della knowledge base.
        path: Percorso relativo del file da leggere, o @nome/percorso per fonti.
        fonti: Dizionario {nome: cartella} per fonti esterne.
        
    Returns:
        Contenuto del file.
        
    Raises:
        ValueError: Se il percorso non è sicuro o non esiste.
    """
    # Controlla se è un percorso di fonte esterna
    if path.startswith('@'):
        if not fonti:
            raise ValueError('fonti non fornite per percorso di fonte esterna')
        # Estrai nome fonte e percorso relativo
        match = re.match(r'^@([^/]+)/(.+)$', path)
        if not match:
            raise ValueError(f'formato percorso fonte non valido: {path}')
        nome_fonte, percorso_rel = match.groups()
        if nome_fonte not in fonti:
            raise ValueError(f'fonte non trovata: {nome_fonte}')
        cartella_fonte = fonti[nome_fonte]
        percorso_assoluto = os.path.realpath(os.path.join(cartella_fonte, percorso_rel))
        cartella_assoluta = os.path.realpath(cartella_fonte)
        # Verifica che il percorso sia dentro la fonte
        if not percorso_assoluto.startswith(cartella_assoluta + os.sep):
            raise ValueError('percorso non sicuro: fuori dalla fonte')
        if not os.path.exists(percorso_assoluto):
            raise ValueError(f'file non trovato: {path}')
        with open(percorso_assoluto, 'r') as f:
            return f.read()
    else:
        # Percorso normale nella KB
        percorso_assoluto = os.path.realpath(os.path.join(kb, path))
        kb_abs = os.path.realpath(kb)
        if not percorso_assoluto.startswith(kb_abs + os.sep):
            raise ValueError('percorso non sicuro: fuori dalla knowledge base')
        if not os.path.exists(percorso_assoluto):
            raise ValueError(f'file non trovato: {path}')
        with open(percorso_assoluto, 'r') as f:
            return f.read()


def indicizza(kb, db, fonti=None):
    """Crea o aggiorna l'indice SQLite FTS5.
    
    Crea la tabella FTS5 `note` da zero, ignorando le cartelle che iniziano con `.`.
    Il titolo è la prima riga `# …`, altrimenti il nome del file senza `.md`.
    
    Args:
        kb: Directory della knowledge base.
        db: Percorso del file del database.
        fonti: Dizionario {nome: cartella} per fonti esterne in sola lettura.
        
    Returns:
        Numero di documenti indicizzati.
    """
    # Crea la cartella del db se manca
    db_dir = os.path.dirname(db)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
    
    conn = sqlite3.connect(db)
    c = conn.cursor()
    
    # Rimuovi la vecchia tabella se esiste e ricrea da zero
    c.execute('DROP TABLE IF EXISTS note')
    c.execute('''
        CREATE VIRTUAL TABLE note USING fts5(
            path UNINDEXED,
            fonte UNINDEXED,
            titolo,
            testo
        )
    ''')
    
    # Trova tutti i file .md (esclusi . e .git, e cartelle che iniziano con `.`)
    # Note della KB hanno fonte='kb' e percorso relativo
    md_files = []
    for root, dirs, files in os.walk(kb):
        # Rimuovi directory che iniziano con `.`
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for f in files:
            if f.endswith('.md'):
                full_path = os.path.join(root, f)
                rel_path = os.path.relpath(full_path, kb)
                md_files.append((full_path, rel_path, 'kb'))
    
    count = 0
    for full_path, rel_path, fonte in md_files:
        try:
            with open(full_path, 'r') as f:
                testo = f.read()
            
            # Estrai titolo dalla prima riga # ...
            titolo = 'documento'
            for riga in testo.split('\n'):
                if riga.startswith('# '):
                    titolo = riga[2:].strip()
                    break
            # Se non c'è titolo, usa il nome del file senza estensione
            if titolo == 'documento':
                titolo = os.path.splitext(os.path.basename(rel_path))[0]
            
            # Inserisci nella tabella FTS5
            c.execute(
                'INSERT INTO note (path, fonte, titolo, testo) VALUES (?, ?, ?, ?)',
                (rel_path, fonte, titolo, testo)
            )
            count += 1
        except (IOError, OSError):
            pass
    
    # Aggiungi fonti esterne
    if fonti:
        for nome, cartella in fonti.items():
            if not os.path.exists(cartella):
                continue
            for root, dirs, files in os.walk(cartella):
                # Rimuovi directory che iniziano con `.`
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                for f in files:
                    if f.endswith('.md'):
                        full_path = os.path.join(root, f)
                        rel_path = os.path.relpath(full_path, cartella)
                        try:
                            with open(full_path, 'r') as ff:
                                testo = ff.read()
                            
                            # Estrai titolo dalla prima riga # ...
                            titolo = 'documento'
                            for riga in testo.split('\n'):
                                if riga.startswith('# '):
                                    titolo = riga[2:].strip()
                                    break
                            if titolo == 'documento':
                                titolo = os.path.splitext(os.path.basename(rel_path))[0]
                            
                            # Percorso con prefisso @nome
                            percorso_fonte = f'@{nome}/{rel_path}'
                            
                            # Inserisci nella tabella FTS5
                            c.execute(
                                'INSERT INTO note (path, fonte, titolo, testo) VALUES (?, ?, ?, ?)',
                                (percorso_fonte, nome, titolo, testo)
                            )
                            count += 1
                        except (IOError, OSError):
                            pass
    
    conn.commit()
    conn.close()
    
    return count


def cerca(db, query, n=5):
    """Cerca nell'indice FTS5: lista di dict path, titolo, estratto, fonte in ordine di rank.
    
    Se db non esiste, restituisce [].
    La query viene trasformata: ogni parola separata da spazi diventa una frase tra virgolette.
    Query vuota restituisce [].
    """
    if not os.path.exists(db):
        return []
    
    conn = sqlite3.connect(db)
    try:
        # Trasforma la query: separa per spazi, togli virgolette esistenti, riapplica virgolette
        parole = query.split()
        if not parole:
            return []
        # Pulisci le parole dalle virgolette esistenti
        parole_pulite = [p.strip('"') for p in parole]
        # Costruisci nuova query con parole tra virgolette unite da OR
        query_trasformata = ' '.join(f'"{p}"' for p in parole_pulite)
        query_trasformata = ' OR '.join(query_trasformata.split())
        # Se c'è solo una parola, non serve OR
        if len(parole_pulite) == 1:
            query_trasformata = f'"{parole_pulite[0]}"'
        else:
            query_trasformata = ' OR '.join(f'"{p}"' for p in parole_pulite)
        
        righe = conn.execute(
            "SELECT path, fonte, titolo, snippet(note, 3, '', '', '…', 16) FROM note WHERE note MATCH ? ORDER BY rank LIMIT ?",
            (query_trasformata, n)).fetchall()
    finally:
        conn.close()
    return [{'path': p, 'fonte': f, 'titolo': t, 'estratto': e} for p, f, t, e in righe]


def _servizio(metodo, percorso, dati=None):
    """Chiama il servizio della KB (KB_URL, KB_TOKEN) e restituisce la risposta JSON."""
    import json
    import urllib.error
    import urllib.request
    url = os.environ['KB_URL'].rstrip('/') + percorso
    intestazioni = {'Authorization': 'Bearer ' + os.environ.get('KB_TOKEN', '')}
    corpo = None
    if dati is not None:
        corpo = json.dumps(dati).encode('utf-8')
        intestazioni['Content-Type'] = 'application/json'
    richiesta = urllib.request.Request(url, data=corpo, headers=intestazioni, method=metodo)
    try:
        with urllib.request.urlopen(richiesta, timeout=30) as r:
            return json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        try:
            errore = json.loads(e.read().decode('utf-8')).get('errore')
        except ValueError:
            errore = None
        raise ValueError(errore or 'errore HTTP %d' % e.code)


def main(argv=None):
    """Riga di comando: indicizza, cerca, leggi, salva (testo da stdin).
    Con KB_URL impostata cerca, leggi e salva usano il servizio invece dei file."""
    import argparse
    import urllib.parse
    ap = argparse.ArgumentParser(prog='kb', description='Knowledge base in Markdown')
    sub = ap.add_subparsers(dest='comando', required=True)
    sub.add_parser('indicizza', help="ricostruisce l'indice")
    c = sub.add_parser('cerca', help='cerca nelle note')
    c.add_argument('query')
    c.add_argument('-n', type=int, default=5)
    l = sub.add_parser('leggi', help='stampa una nota')
    l.add_argument('nota')
    s = sub.add_parser('salva', help='salva in inbox/ il testo letto da stdin')
    s.add_argument('--agente', required=True)
    s.add_argument('--titolo', required=True)
    s.add_argument('--progetto')
    s.add_argument('--campo', action='append', default=[], metavar='CHIAVE=VALORE',
                   help='campo in più nell\'intestazione (ripetibile)')
    a = ap.parse_args(argv)
    kb_dir = os.environ.get('KB_DIR', '/srv/kb')
    db = os.environ.get('KB_DB', os.path.expanduser('~/.cache/kb/indice.db'))
    remoto = bool(os.environ.get('KB_URL'))
    try:
        if a.comando == 'indicizza':
            print('note indicizzate: %d' % indicizza(kb_dir, db))
        elif a.comando == 'cerca':
            if remoto:
                q = urllib.parse.urlencode({'q': a.query, 'n': a.n})
                risultati = _servizio('GET', '/cerca?' + q)['risultati']
            else:
                risultati = cerca(db, a.query, a.n)
            for r in risultati:
                print('%s: %s' % (r['path'], r['titolo']))
                print('  ' + ' '.join(r['estratto'].split()))
        elif a.comando == 'leggi':
            if remoto:
                q = urllib.parse.urlencode({'nota': a.nota})
                sys.stdout.write(_servizio('GET', '/leggi?' + q)['testo'])
            else:
                sys.stdout.write(leggi(kb_dir, a.nota))
        else:
            extra = {}
            for campo in a.campo:
                chiave, uguale, valore = campo.partition('=')
                if not uguale:
                    raise ValueError('campo non valido (serve CHIAVE=VALORE): %s' % campo)
                extra[chiave] = valore
            testo = sys.stdin.read()
            if remoto:
                print(_servizio('POST', '/salva', {'agente': a.agente, 'titolo': a.titolo, 'testo': testo,
                                                   'progetto': a.progetto, 'extra': extra or None})['path'])
            else:
                print(salva(kb_dir, a.agente, a.titolo, testo, progetto=a.progetto, extra=extra or None))
    except (ValueError, OSError, sqlite3.OperationalError) as e:
        print('kb: %s' % e, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
