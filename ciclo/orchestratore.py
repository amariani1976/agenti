"""Orchestratore: il modello propone il piano, il programma lo convalida, richiama gli agenti in sequenza e avvisa."""
import json
import os
import sys

# Importa primo_json da risposta.py
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import risposta
primo_json = risposta.primo_json


def _convalida_piano(piano, agenti, max_compiti):
    """Convalida un piano. Restituisce (valido, motivo).
    
    Un piano valido ha:
    - 1 <= len(compiti) <= max_compiti
    - Ogni compito ha agente fra quelli dati
    - Ogni compito ha compito non vuoto
    - Per il programmatore: file relativi senza .. e verifica non vuota
    """
    if not isinstance(piano, dict):
        return False, 'piano non è un oggetto JSON'
    
    compiti = piano.get('compiti')
    if not isinstance(compiti, list):
        return False, 'piano non ha una lista "compiti"'
    
    if len(compiti) < 1:
        return False, 'piano ha zero compiti (minimo 1)'
    
    if len(compiti) > max_compiti:
        return False, 'piano ha troppi compiti (max ' + str(max_compiti) + ')'
    
    for i, compito in enumerate(compiti):
        if not isinstance(compito, dict):
            return False, 'compito ' + str(i) + ' non è un oggetto JSON'
        
        agente = compito.get('agente')
        if agente not in agenti:
            return False, 'agente non ammesso: ' + str(agente)
        
        compito_str = compito.get('compito')
        if not compito_str or not compito_str.strip():
            return False, 'compito vuoto'
        
        # Per il programmatore: controlla file e verifica
        if agente == 'programmatore':
            file_param = compito.get('file')
            verifica = compito.get('verifica')
            
            if not file_param or not isinstance(file_param, list):
                return False, 'programmatore senza file'
            
            for f in file_param:
                if not f or not isinstance(f, str):
                    return False, 'file non valido: ' + repr(f)
                if f.startswith('/'):
                    return False, 'file assoluto: ' + f
                if '..' in f:
                    return False, 'path traversal nel file: ' + f
            
            if not verifica or not verifica.strip():
                return False, 'programmatore senza verifica'
    
    return True, None


def _prompt_per_chiedi(richiesta, agenti):
    """Crea il prompt per il modello: descrive i ruoli e la forma del piano."""
    ruoli_desc = []
    for agente in agenti:
        if agente == 'programmatore':
            ruoli_desc.append('programmatore: scrive codice finché la verifica passa')
        elif agente == 'revisore':
            ruoli_desc.append('revisore: legge il codice e trova difetti')
        elif agente == 'ricercatore':
            ruoli_desc.append('ricercatore: cerca nella KB e sul web')
        else:
            ruoli_desc.append(agente + ': ' + agente)
    
    prompt = 'Richiesta: ' + richiesta + '\n\n'
    prompt += 'Ruoli disponibili:\n' + '\n'.join(ruoli_desc) + '\n\n'
    prompt += 'Rispondi con un JSON della forma:\n'
    prompt += '{"compiti": [{"agente": "nome", "compito": "descrizione", "file": ["a.py", "b.py"], "verifica": "comando"}]}\n'
    prompt += '(file e verifica obbligatori per il programmatore)\n'
    
    return prompt


def _esegui_compito(agenti, compito, cartella):
    """Esegue un compito con l'agente corrispondente. Restituisce l'esito."""
    nome = compito.get('agente')
    # Usa la funzione dell'agente dal dict
    agente_fn = agenti[nome]
    return agente_fn(compito, cartella)


def esegui(richiesta, cartella, chiedi, agenti, avvisa=None, max_compiti=6):
    """Esegue un piano proposto dal modello.
    
    parametri:
    - richiesta: la richiesta dell'utente
    - cartella: la cartella del progetto
    - chiedi: funzione che chiama il modello, restituisce una stringa
    - agenti: dict {nome: funzione} degli agenti disponibili
    - avvisa: funzione(tipo, testo) per gli avvisi finali
    - max_compiti: massimo numero di compiti nel piano
    
    Restituisce:
    - {'esito': 'fatto'|'aiuto', 'piano': piano, 'risultati': [...], 'motivo': ...}
    """
    # Crea il prompt per il modello
    prompt = _prompt_per_chiedi(richiesta, list(agenti.keys()))
    
    # Chiede il piano
    risposta = chiedi(prompt)
    
    # Leggere il primo JSON dalla risposta
    piano = primo_json(risposta)
    
    # Convalida il piano
    valido, motivo = _convalida_piano(piano, list(agenti.keys()), max_compiti)
    
    # Se non valido, chiede una volta con il motivo
    if not valido:
        risposta2 = chiedi('piano non valido: ' + motivo)
        piano = primo_json(risposta2)
        valido, motivo = _convalida_piano(piano, list(agenti.keys()), max_compiti)
    
    # Se ancora non valido, esito aiuto
    if not valido:
        if avvisa:
            avvisa('aiuto', 'richiesta: ' + richiesta + ', motivo: ' + motivo)
        return {'esito': 'aiuto', 'piano': [], 'risultati': [], 'motivo': motivo}
    
    # Esegui i compiti in ordine
    compiti = piano.get('compiti', [])
    risultati = []
    
    # Traccia l'ultimo compito del programmatore per la correzione
    ultimo_programmatore_idx = -1
    ultimo_programmatore = None
    
    # Fase 1: esegui tutti i compiti in ordine
    for i, compito in enumerate(compiti):
        agente = compito.get('agente')
        esito = _esegui_compito(agenti, compito, cartella)
        risultati.append(esito)
        
        # Controlla se l'esito è diverso da 'fatto'
        if esito.get('esito') != 'fatto':
            if avvisa:
                avvisa('aiuto', 'richiesta: ' + richiesta + ', motivo: agente ' + agente + ' non ha fatto il compito')
            return {'esito': 'aiuto', 'piano': compiti, 'risultati': risultati, 'motivo': 'agente ' + agente + ' non ha fatto il compito'}
        
        # Traccia l'ultimo compito del programmatore
        if agente == 'programmatore':
            ultimo_programmatore_idx = i
            ultimo_programmatore = compito
    
    # Fase 2: controlla se c'è un revisore con ok=False dopo l'ultimo programmatore
    # Se c'è, un giro di correzione
    for i, esito in enumerate(risultati):
        if esito.get('esito') == 'fatto' and esito.get('ok') is False:
            # Un giro di correzione: il programmatore dell'ultimo compito del programmatore rifà con i difetti
            if ultimo_programmatore and ultimo_programmatore_idx >= 0:
                difetti = esito.get('difetti', [])
                # Aggiorna il compito del programmatore con i difetti
                nuovo_compito = dict(ultimo_programmatore)
                nuovo_compito['compito'] = nuovo_compito['compito'] + ' (' + ', '.join(difetti) + ')'
                # Esegui di nuovo il programmatore
                esito_correzione = _esegui_compito(agenti, nuovo_compito, cartella)
                risultati.append(esito_correzione)
                
                # Il revisore ripassa
                # Crea un nuovo compito per il revisore (usa lo stesso file)
                compito_revisore = {
                    'agente': 'revisore',
                    'compito': 'verifica di nuovo',
                    'file': nuovo_compito.get('file', []),
                    'verifica': nuovo_compito.get('verifica', '')
                }
                
                esito_revisore = _esegui_compito(agenti, compito_revisore, cartella)
                risultati.append(esito_revisore)
                
                # Se dopo la correzione ci sono ancora difetti, esito aiuto
                if esito_revisore.get('esito') != 'fatto' or esito_revisore.get('ok') is False:
                    motivo_difetti = esito_revisore.get('difetti', ['difetti persistenti'])
                    if avvisa:
                        avvisa('aiuto', 'richiesta: ' + richiesta + ', motivo: ' + ', '.join(motivo_difetti))
                    return {'esito': 'aiuto', 'piano': compiti, 'risultati': risultati, 'motivo': ', '.join(motivo_difetti)}
            break
    
    # Tutto finito, esito fatto
    if avvisa:
        avvisa('fatto', 'richiesta: ' + richiesta)
    
    return {'esito': 'fatto', 'piano': compiti, 'risultati': risultati, 'motivo': ''}
