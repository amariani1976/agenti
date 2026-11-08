---
stato: in-esecuzione
ramo: ai/guardia
modello: esecutore
verifica_globale: timeout 300 python3 -m unittest discover -s tests
collaudi: 1
---
# Piano: guardia delle chiamate ripetute e tetto delle risposte nel proxy della coda

Nelle prove dei modelli (8/11) l'agente ripeteva all'infinito la stessa chiamata a uno strumento con lo stesso risultato:
il lavoro era fatto ma il modello non chiudeva il turno. Il proxy `coda/proxy.py` (tutte le richieste passano da lì)
riconosce la ripetizione e risponde da sé «lavoro concluso», senza strumenti: l'agente chiude e il ciclo verifica il lavoro.
In più un tetto alla lunghezza delle risposte, solo se la richiesta non lo indica e solo se acceso con `CODA_TETTO`.
Il test è già scritto e provato in `piani/guardia/test_guardia.py`.

- [x] 1. Modulo guardia e collegamento nel proxy
  File: `coda/guardia.py`, `coda/proxy.py`, `tests/test_guardia.py`
  Cosa fare: prima copia il test con `cp piani/guardia/test_guardia.py tests/test_guardia.py` e non modificarlo. Python 3, solo libreria standard, docstring e commenti in italiano.
  1. `coda/guardia.py`: costante `TESTO` con la frase di chiusura («Ho già eseguito la stessa operazione più volte con lo stesso risultato: il lavoro è concluso.»);
  2. `ripetizione(messaggi, volte=3)`: `False` se `messaggi` è vuoto o `None` o se l'ultimo messaggio non ha `role` `tool`; prende i messaggi `assistant` con `tool_calls`; se sono meno di `volte`, `False`; le ultime `volte` devono avere ciascuna esattamente una chiamata, con lo stesso nome di funzione, gli stessi argomenti (confrontati come JSON normalizzato con `json.dumps(json.loads(a), sort_keys=True)`; se non sono JSON, come testo) e lo stesso contenuto del messaggio `tool` col loro `tool_call_id`; allora `True`;
  3. `chiusura(dati)`: dict `{'id': 'guardia', 'object': 'chat.completion', 'model': dati.get('model'), 'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': TESTO}, 'finish_reason': 'stop'}]}`;
  4. `chiusura_sse(dati)`: testo SSE con due pezzi `chat.completion.chunk` (il primo con `delta` `{'role': 'assistant', 'content': TESTO}` e `finish_reason` `None`, il secondo con `delta` `{}` e `finish_reason` `'stop'`), ognuno come `data: <json>\n\n`, e in fondo `data: [DONE]\n\n`;
  5. `con_tetto(dati, tetto)`: copia di `dati` con `max_tokens = tetto` solo se `tetto` è vero e mancano sia `max_tokens` sia `max_completion_tokens`;
  6. `coda/proxy.py`: `import guardia`; attributo di classe `tetto = None` in `Gestore`; in `do_POST`, subito dopo aver letto il JSON e prima di entrare in coda: se `guardia.ripetizione(dati.get('messages'))` risponde senza chiamare il motore — con `stream` vero manda 200, `Content-Type: text/event-stream`, `Content-Length` e il testo di `chiusura_sse`, altrimenti `self._json(200, guardia.chiusura(dati))`; se `self.tetto` è impostato, `dati = guardia.con_tetto(dati, self.tetto)` e `corpo` diventa il JSON di `dati`; `crea(..., attesa_max=600, tetto=None)` passa `tetto` alla classe; `main()` legge `tetto` da `int(os.environ.get('CODA_TETTO', '0')) or None`. Il resto del proxy non cambia.
  Verifica: `cp piani/guardia/test_guardia.py tests/test_guardia.py && timeout 200 python3 -m unittest tests/test_guardia.py tests/test_coda.py`
