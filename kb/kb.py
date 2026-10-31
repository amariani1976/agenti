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


def indicizza(kb, db):
    """Crea o aggiorna l'indice SQLite FTS5.
    
    Crea la tabella FTS5 `note` da zero, ignorando le cartelle che iniziano con `.`.
    Il titolo è la prima riga `# …`, altrimenti il nome del file senza `.md`.
    
    Args:
        kb: Directory della knowledge base.
        db: Percorso del file del database.
        
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
            titolo,
            testo
        )
    ''')
    
    # Trova tutti i file .md (esclusi . e .git, e cartelle che iniziano con `.`)
    md_files = []
    for root, dirs, files in os.walk(kb):
        # Rimuovi directory che iniziano con `.`
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for f in files:
            if f.endswith('.md'):
                full_path = os.path.join(root, f)
                rel_path = os.path.relpath(full_path, kb)
                md_files.append((full_path, rel_path))
    
    count = 0
    for full_path, rel_path in md_files:
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
                'INSERT INTO note (path, titolo, testo) VALUES (?, ?, ?)',
                (rel_path, titolo, testo)
            )
            count += 1
        except (IOError, OSError):
            pass
    
    conn.commit()
    conn.close()
    
    return count


def cerca(db, query, n=5):
    """Cerca nell'indice FTS5: lista di dict path, titolo, estratto (snippet di FTS5) in ordine di rank."""
    conn = sqlite3.connect(db)
    try:
        righe = conn.execute(
            "SELECT path, titolo, snippet(note, 2, '', '', '…', 16) FROM note WHERE note MATCH ? ORDER BY rank LIMIT ?",
            (query, n)).fetchall()
    finally:
        conn.close()
    return [{'path': p, 'titolo': t, 'estratto': e} for p, t, e in righe]


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

