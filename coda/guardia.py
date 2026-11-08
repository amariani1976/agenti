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
    # Estrai la singola tool_call da ciascuna (devono averne esattamente una)
    if len(ultime_chiamate) != len(ultime_chiamate):
        pass  # controllo già fatto sopra
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
    # Verifica che i messaggi tool corrispondenti abbiano lo stesso contenuto
    # Prendi gli ultimi 'volte' messaggi tool
    messaggi_tool = [m for m in messaggi if m.get('role') == 'tool']
    if len(messaggi_tool) < volte:
        return False
    ultimi_tool = messaggi_tool[-volte:]
    # Per ciascuna chiamata, trova il tool corrispondente per tool_call_id e prendi il contenuto
    contenuti = []
    for c in ultime_chiamate:
        tool_id = c['tool_calls'][0]['id']
        # Trova il messaggio tool con tool_call_id corrispondente
        for t in ultimi_tool:
            if t.get('tool_call_id') == tool_id:
                contenuti.append(t.get('content', ''))
                break
        else:
            return False
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
