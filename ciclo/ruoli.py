"""Ruoli: programmatore usa il ciclo, revisore risponde in JSON e non scrive nulla."""
import json
import os
import re

from ciclo import esegui, _diff, _git, _leggi, _sporchi, _scrivi


def _json_da_risposta(uscita):
    """Estrae il primo oggetto JSON dalla risposta, anche dentro un blocco ```json."""
    if not uscita:
        return None
    # Cerca prima un blocco ```json ... ```
    blocco = re.search(r'```json\s*(.*?)\s*```', uscita, re.DOTALL)
    if blocco:
        testo = blocco.group(1)
    else:
        # Altrimenti cerca JSON nella risposta intera
        testo = uscita
    try:
        return json.loads(testo)
    except (ValueError, TypeError):
        return None


def _annulla_cambi(cartella, prima, perimetro):
    """Annulla i file fuori dal perimetro e restituisce la lista in ordine."""
    scritture = []
    # Controlla tutti i file che potrebbero essere stati modificati
    # prima contiene lo stato di ogni file prima della chiamata
    
    # Ottieni tutti i file che potrebbero essere stati modificati
    # File tracciati da git + file non tracciati che esistevano prima
    tutti_file = set(_sporchi(cartella)) | set(prima.keys())
    
    for nome in sorted(tutti_file):
        if nome in perimetro:
            continue
        
        try:
            contenuto_ora = _leggi(cartella, nome)
        except (OSError, IOError):
            continue
        
        if nome in prima:
            # File esistente: ripristina il contenuto originale
            if contenuto_ora != prima[nome]:
                try:
                    _scrivi(cartella, nome, prima[nome])
                except (OSError, IOError):
                    pass
                scritture.append(nome)
        else:
            # File nuovo: cancellalo se esiste
            if contenuto_ora is not None:
                try:
                    _scrivi(cartella, nome, None)
                except (OSError, IOError):
                    pass
                scritture.append(nome)
    
    return scritture


def _prima_stato(cartella):
    """Restituisce un dict con il contenuto di ogni file prima della chiamata.
    Include file tracciati da git e file non tracciati."""
    prima = {}
    # File tracciati da git
    codice, tracciati = _git(cartella, 'ls-files')
    if tracciati.strip():
        for nome in (n for n in tracciati.strip().split('\n') if n):
            prima[nome] = _leggi(cartella, nome)
    # File non tracciati che esistono
    try:
        for nome in os.listdir(cartella):
            if nome in prima:  # Già tracciato
                continue
            if os.path.isfile(os.path.join(cartella, nome)):
                try:
                    prima[nome] = _leggi(cartella, nome)
                except (OSError, IOError):
                    pass
    except (OSError, IOError):
        pass
    return prima


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
    dati = _json_da_risposta(uscita)
    
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
