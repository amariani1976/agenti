"""Ruoli: programmatore usa il ciclo, revisore risponde in JSON e non scrive nulla."""
import os
import sys

from ciclo import esegui, _diff, _git, _leggi, _sporchi, _scrivi

# Importa primo_json da risposta.py
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import risposta
primo_json = risposta.primo_json


def _elenco(cartella):
    """Nomi relativi dei file tracciati e non tracciati (non ignorati), anche in sottocartelle."""
    nomi = set()
    for argomenti in (('ls-files', '-z'), ('ls-files', '-z', '--others', '--exclude-standard')):
        codice, uscita = _git(cartella, *argomenti)
        if codice == 0:
            nomi.update(n for n in uscita.split('\0') if n)
    return sorted(nomi)


def _dentro(cartella, nome):
    """Percorso assoluto del file se sta dentro la cartella, altrimenti None."""
    base = os.path.realpath(cartella)
    percorso = os.path.realpath(os.path.join(base, nome))
    if percorso == base or not percorso.startswith(base + os.sep):
        return None
    return percorso


def _istantanea(cartella):
    """Contenuto in byte di ogni file di _elenco: dict nome -> bytes."""
    prima = {}
    for nome in _elenco(cartella):
        contenuto = _leggi(cartella, nome)
        if contenuto is not None:
            prima[nome] = contenuto
    return prima


def _ripristina(cartella, prima):
    """Riporta la cartella all'istantanea; restituisce in ordine i nomi toccati."""
    toccati = []
    for nome in sorted(set(prima) | set(_elenco(cartella))):
        percorso = _dentro(cartella, nome)
        if percorso is None:
            continue
        ora = _leggi(cartella, nome)
        if nome in prima:
            if ora == prima[nome]:
                continue
            sopra = os.path.dirname(percorso)
            if not os.path.isdir(sopra):
                os.makedirs(sopra)
            with open(percorso, 'wb') as f:
                f.write(prima[nome])
            toccati.append(nome)
        elif ora is not None:
            os.remove(percorso)
            toccati.append(nome)
    return toccati


def programmatore(compito, cartella, esegui=esegui, **k):
    """Programmatore: affida il compito al ciclo.
    
    Chama esegui(compito['compito'], cartella, compito['verifica'], compito['file'], **k).
    Restituisce il risultato di esegui.
    """
    return esegui(
        compito['compito'],
        cartella,
        compito['verifica'],
        compito['file'],
        **k
    )


def revisore(compito, cartella, lancia):
    """Revisore: chiede un giudizio in JSON e annulla ogni scrittura fatta durante la chiamata."""
    prima = _istantanea(cartella)
    prompt = 'Compito: ' + compito['compito']
    diff = _diff(cartella, sorted(_sporchi(cartella)))
    if diff:
        prompt += '\n\nDiff della cartella:\n' + diff
    prompt += '\n\nRispondi SOLO con un JSON: {"ok": bool, "difetti": [stringhe]}'
    try:
        codice, uscita = lancia(prompt, cartella)
    except Exception as e:
        _ripristina(cartella, prima)
        return {'esito': 'non-fatto', 'motivo': 'eccezione durante la chiamata: ' + str(e)}
    scritture_annullate = _ripristina(cartella, prima)
    dati = primo_json(uscita)
    if dati is None:
        return {'esito': 'non-fatto', 'motivo': 'risposta illeggibile: non è un JSON valido'}
    return {
        'esito': 'fatto',
        'ok': dati.get('ok', False),
        'difetti': dati.get('difetti', []),
        'scritture_annullate': scritture_annullate
    }


def ricercatore(compito, cartella, lancia):
    """Ricercatore: una sola chiamata che cerca nella KB e sul web e salva la sintesi; non scrive file."""
    prima = _istantanea(cartella)
    prompt = ('Compito: ' + compito['compito'] +
              '\n\nCerca prima nella KB, poi usa la skill web, e salva la sintesi nella KB con kb_salva.')
    try:
        codice, uscita = lancia(prompt, cartella)
    except Exception as e:
        _ripristina(cartella, prima)
        return {'esito': 'non-fatto', 'motivo': 'eccezione durante la ricerca: ' + str(e)}
    scritture_annullate = _ripristina(cartella, prima)
    if codice != 0:
        return {'esito': 'non-fatto', 'motivo': 'codice di ritorno non zero: ' + str(codice)}
    return {'esito': 'fatto', 'testo': uscita, 'scritture_annullate': scritture_annullate}
