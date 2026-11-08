"""Guardia del proxy: rileva chiamate ripetute e applica tetto alle risposte.

Se l'agente ripete la stessa chiamata a uno strumento con lo stesso risultato,
il proxy risponde da sé «lavoro concluso» (senza strumenti) e l'agente chiude il turno;
poi il ciclo verifica il lavoro. Inoltre un tetto alla lunghezza delle risposte quando
la richiesta non lo indica."""
import json


TESTO = "Ho già eseguito la stessa operazione più volte con lo stesso risultato: il lavoro è concluso."


def _arg_json(a):
    """Normalizza un argomento JSON per il confronto."""
    try:
        return json.dumps(json.loads(a), sort_keys=True)
    except (json.JSONDecodeError, TypeError):
        return a


def ripetizione(messaggi, volte=3):
    """Verifica se l'ultimo messaggio è tool e se gli ultimi 'volte' messaggi assistant
    hanno tool_calls identici (stessa funzione, stessi argomenti, stesso risultato tool).
    
    Ritorna False se:
    - messaggi è vuoto o None
    - l'ultimo messaggio non ha role 'tool'
    - ci sono meno di 'volte' messaggi assistant con tool_calls
    - le ultime 'volte' chiamate non sono identiche
    
    Ritorna True se le ultime 'volte' chiamate assistant hanno ciascuna esattamente
    una tool_call con lo stesso nome di funzione, stessi argomenti (confrontati come JSON)
    e lo stesso contenuto del messaggio tool associato."""
    if not messaggi:
        return False
    # L'ultimo messaggio deve essere di tipo tool
    ultimo = messaggi[-1]
    if ultimo.get('role') != 'tool':
        return False
    # Prendi i messaggi assistant con tool_calls
    chiamate = [m for m in messaggi if m.get('role') == 'assistant' and m.get('tool_calls')]
    if len(chiamate) < volte:
        return False
    # Prendi le ultime 'volte' chiamate
    ultime_chiamate = chiamate[-volte:]
    # Verifica che ognuna abbia esattamente una tool_call
    for c in ultime_chiamate:
        if len(c['tool_calls']) != 1:
            return False
    # Estrai nome funzione, argomenti, tool_call_id per ciascuna
    info = []
    for c in ultime_chiamate:
        tc = c['tool_calls'][0]
        nome = tc['function']['name']
        args = _arg_json(tc['function']['arguments'])
        info.append((nome, args))
    # Verifica che nome e argomenti siano uguali per tutte le chiamate
    primo = info[0]
    for i in range(1, len(info)):
        if info[i] != primo:
            return False
    # Per ciascuna chiamata, trova il tool message corrispondente per tool_call_id
    # e verifica che abbiano lo stesso contenuto (non usare tutti i tool messages)
    contenuti = []
    for c in ultime_chiamate:
        tool_id = c['tool_calls'][0]['id']
        # Cerca il tool message con tool_call_id ESATTO in TUTTI i messaggi tool
        contenuto_trovato = None
        for m in messaggi:
            if m.get('role') == 'tool' and m.get('tool_call_id') == tool_id:
                contenuto_trovato = m.get('content', '')
                break
        if contenuto_trovato is None:
            return False
        contenuti.append(contenuto_trovato)
    # Verifica che tutti i contenuti siano uguali (non gli ID, ma il contenuto del risultato)
    primo_contenuto = contenuti[0]
    for c in contenuti[1:]:
        if c != primo_contenuto:
            return False
    return True


def chiusura(dati):
    """Restituisce una risposta di chiusura nel formato OpenAI."""
    return {
        'id': 'guardia',
        'object': 'chat.completion',
        'model': dati.get('model'),
        'choices': [{
            'index': 0,
            'message': {
                'role': 'assistant',
                'content': TESTO
            },
            'finish_reason': 'stop'
        }]
    }


def chiusura_sse(dati):
    """Restituisce testo in formato SSE con due chunk di chiusura."""
    # Primo chunk: delta con contenuto, finish_reason None
    primo = {
        'id': 'guardia',
        'object': 'chat.completion.chunk',
        'model': dati.get('model'),
        'choices': [{
            'index': 0,
            'delta': {
                'role': 'assistant',
                'content': TESTO
            },
            'finish_reason': None
        }]
    }
    # Secondo chunk: delta vuoto, finish_reason 'stop'
    secondo = {
        'id': 'guardia',
        'object': 'chat.completion.chunk',
        'model': dati.get('model'),
        'choices': [{
            'index': 0,
            'delta': {},
            'finish_reason': 'stop'
        }]
    }
    # Formato SSE: data: <json>\n\n per ogni pezzo, poi data: [DONE]\n\n
    return 'data: {}\n\ndata: {}\n\ndata: [DONE]\n\n'.format(
        json.dumps(primo),
        json.dumps(secondo)
    )


def con_tetto(dati, tetto):
    """Restituisce una copia di dati con max_tokens = tetto solo se:
    - tetto è truthy
    - mancano sia max_tokens che max_completion_tokens."""
    if not tetto:
        return dati
    copia = dict(dati)
    # Aggiungi max_tokens solo se mancano entrambi
    if 'max_tokens' not in copia and 'max_completion_tokens' not in copia:
        copia['max_tokens'] = tetto
    return copia


def troppe_chiamate(messaggi, massimo):
    """Verifica se ci sono troppe chiamate agli strumenti nel turno corrente.
    
    Conta le tool_calls dai messaggi assistant dall'ultimo messaggio user in poi.
    Restituisce True se il numero di chiamate è almeno 'massimo', False altrimenti.
    Restituisce False se messaggi è vuoto/None o massimo è falso (0 o None).
    """
    if not messaggi or not massimo:
        return False
    # Scorre all'indietro per trovare l'ultimo messaggio user
    ultimo_user = -1
    for i in range(len(messaggi) - 1, -1, -1):
        # Gestione messaggio non-dizionario (es. None o stringa)
        if not isinstance(messaggi[i], dict):
            continue
        if messaggi[i].get('role') == 'user':
            ultimo_user = i
            break
    # Se non c'è un messaggio user, considera tutti i messaggi assistant
    inizio = 0 if ultimo_user == -1 else ultimo_user + 1
    # Conta le tool_calls dai messaggi assistant dopo l'ultimo user
    chiamate = 0
    for m in messaggi[inizio:]:
        # Gestione messaggio non-dizionario e tool_calls non-lista
        if not isinstance(m, dict):
            continue
        if m.get('role') == 'assistant' and m.get('tool_calls'):
            tool_calls = m['tool_calls']
            # Gestione caso in cui tool_calls sia None invece di lista
            if not isinstance(tool_calls, list):
                continue
            chiamate += len(tool_calls)
    return chiamate >= massimo


def carica_profili(percorso):
    """Carica i profili da un file JSON.
    
    Restituisce il dict del file se ha una chiave 'profili' con valore dict,
    altrimenti None (anche se il file manca o non è JSON valido).
    """
    try:
        with open(percorso, 'r') as f:
            dati = json.load(f)
        # json.load restituisce sempre un tipo, ma verifichiamo che sia dict con 'profili'
        if isinstance(dati, dict) and 'profili' in dati and isinstance(dati['profili'], dict):
            return dati
        return None
    except (FileNotFoundError, json.JSONDecodeError, TypeError):
        return None


def tetto_profilo(dati, modello):
    """Ottiene il tetto di risposta dal profilo del modello richiesto.
    
    dati è il dict completo (es. da modelli.json) che ha una chiave 'profili'.
    Restituisce None se dati è None, non ha 'profili', o il modello non è in nessun profilo.
    Se il modello è 'senza_pensiero' di un profilo, restituisce risposta_max.
    Se è 'con_pensiero', restituisce risposta_max_pensiero se esiste,
    altrimenti risposta_max.
    """
    if dati is None:
        return None
    profili = dati.get('profili')
    if profili is None or not isinstance(profili, dict):
        return None
    for profilo in profili.values():
        if not isinstance(profilo, dict):
            continue
        if modello == profilo.get('senza_pensiero'):
            return profilo.get('risposta_max')
        if modello == profilo.get('con_pensiero'):
            # risposta_max_pensiero se esiste, altrimenti risposta_max
            return profilo.get('risposta_max_pensiero') or profilo.get('risposta_max')
    return None
