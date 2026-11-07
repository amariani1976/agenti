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
    """Revisore: chiede una revisione e annulla ogni scrittura.
    
    - Crea un prompt con il compito
    - Esegue git diff della cartella (inclusi file nuovi)
    - Chiede di rispondere SOLO con JSON {"ok": bool, "difetti": [stringhe]}
    - Dopo la chiamata, annulla ogni cambio fatto durante la chiamata
    - Legge il primo oggetto JSON della risposta (anche dentro ```json)
    - Risposta illeggibile: {'esito': 'non-fatto', 'motivo': ...}
    
    Restituisce:
    - {'esito': 'fatto', 'ok': bool, 'difetti': [stringhe], 'scritture_annullate': [nomi]}
    - {'esito': 'non-fatto', 'motivo': motivo}
    """
    # Traccia lo stato prima della chiamata
    prima = _prima_stato(cartella)
    
    # Ottieni i file nel perimetro (se presenti nel compito)
    file_param = compito.get('file')
    perimetro = set(file_param) if file_param else set()
    
    # Crea il prompt con il compito e il diff
    prompt = 'Compito: ' + compito['compito']
    if perimetro:
        prompt += '\nFile che puoi modificare (solo questi): ' + ', '.join(perimetro)
    
    # Aggiungi il diff della cartella (tutti i file se perimetro vuoto)
    file_per_diff = list(perimetro) if perimetro else []
    # Se non ci sono file nel perimetro, includi tutti i file tracciati
    if not file_per_diff:
        codice, tracciati = _git(cartella, 'ls-files')
        if tracciati.strip():
            file_per_diff = [n for n in tracciati.strip().split('\n') if n]
    
    # Filtra nomi di file invalidi (vuoti, assoluti, con path traversal)
    file_per_diff = [n for n in file_per_diff if n and not n.startswith('/') and '..' not in n]
    
    diff = _diff(cartella, file_per_diff)
    if diff:
        prompt += '\n\nDiff della cartella:\n' + diff
    
    prompt += '\n\nRispondi SOLO con un JSON: {"ok": bool, "difetti": [stringhe]}'
    
    # Lancia il modello con gestione eccezioni
    try:
        codice, uscita = lancia(prompt, cartella)
    except Exception as e:
        # Annulla i cambiamenti anche in caso di errore
        _annulla_cambi(cartella, prima, perimetro)
        return {'esito': 'non-fatto', 'motivo': 'eccezione durante la chiamata: ' + str(e)}
    
    # Annulla i cambiamenti fuori dal perimetro
    scritture_annullate = _annulla_cambi(cartella, prima, perimetro)
    
    # Estrai il JSON dalla risposta
    dati = primo_json(uscita)
    
    if dati is None:
        return {'esito': 'non-fatto', 'motivo': 'risposta illeggibile: non è un JSON valido'}
    
    ok = dati.get('ok', False)
    difetti = dati.get('difetti', [])
    
    return {
        'esito': 'fatto',
        'ok': ok,
        'difetti': difetti,
        'scritture_annullate': scritture_annullate
    }


def ricercatore(compito, cartella, lancia):
    """Ricercatore: cerca nella KB e sul web, salva la sintesi.
    
    - Chiamalancia con il compito e istruzione di cercare nella KB
    - Poi con la skill web
    - Salva la sintesi nella KB
    - Restituisce {'esito': 'fatto', 'testo': uscita} se il codice è 0
    - Stessa lettura del revisore sui file della cartella
    
    Restituisce:
    - {'esito': 'fatto', 'testo': testo} se successo
    - {'esito': 'non-fatto', 'motivo': motivo} se fallito
    """
    # Traccia lo stato prima della chiamata
    prima = _prima_stato(cartella)
    
    # Ottieni i file nel perimetro (se presenti nel compito)
    file_param = compito.get('file')
    perimetro = set(file_param) if file_param else set()
    
    # Crea il prompt per la ricerca KB
    prompt_kb = 'Compito: ' + compito['compito'] + '\n\nCerca nella Knowledge Base e fornisci una sintesi.'
    
    # Lancia la ricerca KB con gestione eccezioni
    try:
        codice_kb, uscita_kb = lancia(prompt_kb, cartella)
    except Exception as e:
        # Annulla i cambiamenti anche in caso di errore
        _annulla_cambi(cartella, prima, perimetro)
        return {'esito': 'non-fatto', 'motivo': 'eccezione durante la ricerca KB: ' + str(e)}
    
    # Crea il prompt per la ricerca web
    prompt_web = 'Compito: ' + compito['compito'] + '\n\nUsa la skill web per cercare e fornisci una sintesi.'
    
    # Lancia la ricerca web con gestione eccezioni
    try:
        codice_web, uscita_web = lancia(prompt_web, cartella)
    except Exception as e:
        # Annulla i cambiamenti anche in caso di errore
        _annulla_cambi(cartella, prima, perimetro)
        return {'esito': 'non-fatto', 'motivo': 'eccezione durante la ricerca web: ' + str(e)}
    
    # Annulla i cambiamenti fuori dal perimetro
    scritture_annullate = _annulla_cambi(cartella, prima, perimetro)
    
    # Se entrambi i codici sono 0, restituisce il testo
    if codice_kb == 0 and codice_web == 0:
        testo_sintesi = uscita_kb + '\n\n' + uscita_web
        return {
            'esito': 'fatto',
            'testo': testo_sintesi,
            'scritture_annullate': scritture_annullate
        }
    else:
        return {
            'esito': 'non-fatto',
            'motivo': 'codice di ritorno non zero: KB={}, Web={}'.format(codice_kb, codice_web)
        }
