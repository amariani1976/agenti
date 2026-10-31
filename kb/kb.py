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


def salva(kb, agente, titolo, testo, progetto=None, oggi=None):
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
        
    Returns:
        Il percorso relativo del file creato.
        
    Raises:
        ValueError: Se il testo contiene segreti.
    """
    if oggi is None:
        oggi = date.today().strftime('%Y-%m-%d')
    
    # Controlla segreti prima di creare qualsiasi cosa
    controlla_segreti(testo)
    
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


def leggi(kb, path):
    """Legge un file dalla knowledge base.
    
    Args:
        kb: Directory della knowledge base.
        path: Percorso relativo del file da leggere.
        
    Returns:
        Contenuto del file.
        
    Raises:
        ValueError: Se il percorso non è sicuro (fuori dalla KB).
    """
    # Normalizza il percorso usando realpath per risolvere .. e link simbolici
    percorso_assoluto = os.path.realpath(os.path.join(kb, path))
    
    # Verifica che il percorso sia dentro la KB
    kb_abs = os.path.realpath(kb)
    if not percorso_assoluto.startswith(kb_abs + os.sep):
        raise ValueError('percorso non sicuro: fuori dalla knowledge base')
    
    if not os.path.exists(percorso_assoluto):
        raise ValueError(f'file non trovato: {path}')
    
    with open(percorso_assoluto, 'r') as f:
        return f.read()


def indicizza(kb, db_path):
    """Crea o aggiorna l'indice SQLite FTS5.
    
    Args:
        kb: Directory della knowledge base.
        db_path: Percorso del file del database.
        
    Returns:
        Numero di documenti indicizzati.
    """
    # Assicurati che la directory del database esista
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # Crea tabella se non esiste
    c.execute('''
        CREATE TABLE IF NOT EXISTS documenti (
            id INTEGER PRIMARY KEY,
            path TEXT UNIQUE,
            titolo TEXT,
            contenuto TEXT
        )
    ''')
    
    # Crea indice FTS5 se non esiste
    c.execute('''
        CREATE VIRTUAL TABLE IF NOT EXISTS documenti_fts USING fts5(
            contenuto
        )
    ''')
    
    # Crea tabella di mapping id -> rowid
    c.execute('''
        CREATE TABLE IF NOT EXISTS documenti_fts_mapping (
            id INTEGER PRIMARY KEY,
            rowid INTEGER
        )
    ''')
    
    # Trova tutti i file .md (esclusi .git)
    md_files = []
    for root, dirs, files in os.walk(kb):
        # Ignora directory .git
        if '.git' in dirs:
            dirs.remove('.git')
        for f in files:
            if f.endswith('.md'):
                full_path = os.path.join(root, f)
                rel_path = os.path.relpath(full_path, kb)
                if '.git' not in rel_path:
                    md_files.append((full_path, rel_path))
    
    # Pulisci il database (ricomincia da zero)
    c.execute('DELETE FROM documenti')
    c.execute('DELETE FROM documenti_fts')
    c.execute('DELETE FROM documenti_fts_mapping')
    
    count = 0
    for full_path, rel_path in md_files:
        try:
            with open(full_path, 'r') as f:
                contenuto = f.read()
            
            # Estrai titolo dalla prima riga # ...
            titolo = 'documento'
            for riga in contenuto.split('\n'):
                if riga.startswith('#'):
                    titolo = riga[1:].strip()
                    break
            # Se non c'è titolo, usa il nome del file senza estensione
            if titolo == 'documento':
                titolo = os.path.splitext(rel_path)[0].replace('/', '-')
            
            # Inserisci nel database
            c.execute(
                'INSERT OR REPLACE INTO documenti (path, titolo, contenuto) VALUES (?, ?, ?)',
                (rel_path, titolo, contenuto)
            )
            
            # Inserisci nell'indice FTS5
            c.execute(
                'INSERT INTO documenti_fts (contenuto) VALUES (?)',
                (contenuto,)
            )
            
            # Salva il mapping
            c.execute(
                'INSERT OR REPLACE INTO documenti_fts_mapping (id, rowid) VALUES (?, ?)',
                (count + 1, count + 1)
            )
            count += 1
        except (IOError, OSError):
            pass
    
    conn.commit()
    conn.close()
    
    return count


def cerca(db_path, query):
    """Cerca documenti nell'indice FTS5.
    
    Args:
        db_path: Percorso del file del database.
        query: Termine di ricerca.
        
    Returns:
        Lista di dizionari con path, titolo e estratto.
    """
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    risultati = []
    
    try:
        # Cerca usando FTS5
        c.execute('''
            SELECT d.path, d.titolo, d.contenuto
            FROM documenti d
            JOIN documenti_fts_mapping m ON d.id = m.id
            JOIN documenti_fts f ON f.rowid = m.rowid
            WHERE f.contenuto MATCH ?
            ORDER BY f.rowid
        ''', (query,))
        
        for riga in c.fetchall():
            path, titolo, contenuto = riga
            
            # Estrai un estratto dal contenuto
            estratto = ''
            idx = contenuto.lower().find(query.lower())
            if idx >= 0:
                # Prendi 50 caratteri prima e dopo
                start = max(0, idx - 50)
                end = min(len(contenuto), idx + len(query) + 50)
                estratto = contenuto[start:end]
                # Aggiungi ... se necessario
                if start > 0:
                    estratto = '...' + estratto
                if end < len(contenuto):
                    estratto = estratto + '...'
            else:
                estratto = contenuto[:200]
            
            risultati.append({
                'path': path,
                'titolo': titolo,
                'estratto': estratto
            })
    except sqlite3.OperationalError:
        # FTS5 non esiste, torna lista vuota
        pass
    
    conn.close()
    return risultati


def main():
    """Interfaccia da riga di comando."""
    if len(sys.argv) < 2:
        print('Uso: kb.py <comando> [argomenti]')
        print('Comandi: salva, leggi, indicizza, cerca')
        return 1
    
    cmd = sys.argv[1]
    
    if cmd == 'salva':
        # Salva: kb.py salva --agente N --titolo T --progetto P
        agente = None
        titolo = None
        progetto = None
        i = 2
        while i < len(sys.argv):
            if sys.argv[i] == '--agente':
                agente = sys.argv[i + 1]
                i += 2
            elif sys.argv[i] == '--titolo':
                titolo = sys.argv[i + 1]
                i += 2
            elif sys.argv[i] == '--progetto':
                progetto = sys.argv[i + 1]
                i += 2
            else:
                i += 1
        
        if not agente or not titolo:
            print('Errore: --agente e --titolo sono richiesti')
            return 1
        
        # Leggi il corpo da stdin
        testo = sys.stdin.read()
        
        kb_dir = os.environ.get('KB_DIR', '.')
        oggi = os.environ.get('KB_ODO', None)
        
        rel = salva(kb_dir, agente, titolo, testo, progetto=progetto, oggi=oggi)
        print(rel)
        return 0
    
    elif cmd == 'leggi':
        if len(sys.argv) < 3:
            print('Uso: kb.py leggi <percorso>')
            return 1
        
        kb_dir = os.environ.get('KB_DIR', '.')
        path = sys.argv[2]
        
        try:
            print(leggi(kb_dir, path))
            return 0
        except ValueError as e:
            print(f'Errore: {e}', file=sys.stderr)
            return 1
    
    elif cmd == 'indicizza':
        kb_dir = os.environ.get('KB_DIR', '.')
        db_path = os.environ.get('KB_DB', os.path.join(kb_dir, 'indice.db'))
        
        count = indicizza(kb_dir, db_path)
        print(f'Indicizzati: {count}')
        return 0
    
    elif cmd == 'cerca':
        if len(sys.argv) < 3:
            print('Uso: kb.py cerca <query>')
            return 1
        
        db_path = os.environ.get('KB_DB', 'indice.db')
        query = sys.argv[2]
        
        risultati = cerca(db_path, query)
        for r in risultati:
            print(f'{r["path"]}: {r["titolo"]}')
            print(f'  {r["estratto"]}')
        return 0
    
    else:
        print(f'Comando non riconosciuto: {cmd}')
        return 1


if __name__ == '__main__':
    sys.exit(main())
