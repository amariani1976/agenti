"""Ciclo dell'agente: il metodo del runner per un compito solo (verifica, tentativi, perimetro, lezioni)."""
import os
import subprocess

MAX_USCITA = 3000
MAX_PROMPT = 20000


def _git(cartella, *argomenti):
    """Esegue git nella cartella; restituisce (codice, uscita)."""
    try:
        r = subprocess.run(['git', '-C', cartella] + list(argomenti), stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, universal_newlines=True, timeout=60)
        return r.returncode, r.stdout
    except (FileNotFoundError, OSError) as e:
        return -1, str(e)


def _leggi(cartella, nome):
    """Contenuto del file in byte, None se non esiste."""
    percorso = os.path.join(cartella, nome)
    if not os.path.isfile(percorso):
        return None
    with open(percorso, 'rb') as f:
        return f.read()


def _scrivi(cartella, nome, contenuto):
    """Riporta il file al contenuto dato; None vuol dire cancellarlo."""
    # Prevenire path traversal: il nome non deve contenere .. o /
    if '..' in nome or '/' in nome or '\\' in nome:
        return
    percorso = os.path.join(cartella, nome)
    if contenuto is None:
        if os.path.isfile(percorso):
            os.remove(percorso)
        return
    cartella_file = os.path.dirname(percorso)
    if not os.path.isdir(cartella_file):
        os.makedirs(cartella_file)
    # Gestire stringa o bytes
    if isinstance(contenuto, str):
        contenuto = contenuto.encode('utf-8')
    with open(percorso, 'wb') as f:
        f.write(contenuto)


def _sporchi(cartella):
    """Insieme dei file modificati, cancellati o nuovi secondo git status."""
    codice, uscita = _git(cartella, 'status', '--porcelain', '-z', '--untracked-files=all')
    voci = uscita.split('\0')
    nomi = set()
    i = 0
    while i < len(voci):
        voce = voci[i]
        if voce:
            # Per rename (R) o copy (C), il formato è "R old -> new" o "C old -> new"
            if voce[0] in 'RC':
                # Estrai il nuovo nome (dopo " -> ")
                freccia = ' -> '
                idx = voce.find(freccia)
                if idx != -1:
                    nuovo_nome = voce[idx + len(freccia):]
                    nomi.add(nuovo_nome)
                i += 2
            else:
                nomi.add(voce[3:])
                i += 1
        else:
            i += 1
    return nomi


def _ripristina_pulito(cartella, nome):
    """Riporta un file che era pulito allo stato di HEAD (lo cancella se HEAD non lo ha)."""
    # Controlla se il file esiste in HEAD
    codice, tracciato = _git(cartella, 'ls-files', '--', nome)
    if tracciato.strip():
        # Esiste in HEAD: ripristina con checkout
        _git(cartella, 'checkout', '-q', 'HEAD', '--', nome)
    else:
        # Non esiste in HEAD: cancella localmente se esiste
        _scrivi(cartella, nome, None)


def _diff(cartella, file):
    """Diff dei file del perimetro rispetto a HEAD, inclusi i file nuovi."""
    parti = []
    for nome in file:
        codice, tracciato = _git(cartella, 'ls-files', '--', nome)
        if tracciato.strip():
            codice, uscita = _git(cartella, 'diff', 'HEAD', '--', nome)
        elif os.path.isfile(os.path.join(cartella, nome)):
            # Usa /dev/null che funziona su tutti i sistemi (su Windows è un file speciale)
            codice, uscita = _git(cartella, 'diff', '--no-index', '--', '/dev/null', nome)
        else:
            uscita = ''
        if uscita:
            parti.append(uscita)
    return ''.join(parti)


def _prompt(compito, file, verifica, lezioni, errore, fuori):
    """Prompt per l'agente: compito, perimetro, verifica, lezioni ed errore del tentativo prima."""
    parti = ['Compito: ' + compito,
             'File che puoi modificare (solo questi): ' + ', '.join(file),
             'Verifica che deve passare: ' + verifica]
    if lezioni:
        parti.append('Lezioni dalla KB:\n' + '\n'.join('- ' + l for l in lezioni))
    if fuori:
        parti.append('Il tentativo precedente ha toccato file fuori dal perimetro (annullati): ' + ', '.join(fuori))
    if errore:
        parti.append('Errore della verifica nel tentativo precedente:\n' + errore)
    return '\n\n'.join(parti)[:MAX_PROMPT]
