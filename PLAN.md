---
stato: in-pausa
ramo: ai/limiti-proxy
modello: qwen35-9b-nopensiero
modello_pensiero: qwen35-9b-pensiero
verifica_globale: timeout 300 python3 -m unittest discover -s tests
---
# Piano: limiti del proxy validi per qualunque modello

Criterio dell'utente (8/11): il sistema deve funzionare con qualsiasi modello e non impazzire nei cicli. La guardia di
oggi ferma solo le chiamate identiche; un modello può girare a vuoto anche con chiamate simili (stesso file letto a
pezzi diversi). Si aggiunge un tetto di chiamate agli strumenti per turno e il tetto delle risposte preso dal profilo
del modello richiesto (`modelli.json` di AI-VM). Il test è già scritto e provato in `piani/limiti/test_limiti.py`.

- [x] 1. Tetto di chiamate per turno e tetto delle risposte dal profilo
  File: `coda/guardia.py`, `coda/proxy.py`, `tests/test_limiti.py`
  Cosa fare: prima copia il test con `cp piani/limiti/test_limiti.py tests/test_limiti.py` e non modificarlo. Docstring e commenti in italiano.
  1. `coda/guardia.py`, tre funzioni nuove: `troppe_chiamate(messaggi, massimo)` — `False` se `messaggi` è vuoto/`None` o `massimo` è falso; altrimenti conta le chiamate (`tool_calls`, non i messaggi) dei messaggi `assistant` dall'ultimo messaggio con `role` `user` in poi (scorrendo all'indietro fino a quello) e restituisce `True` se sono almeno `massimo`; `carica_profili(percorso)` — il dict del file JSON se ha `profili` dict, altrimenti `None` (anche se il file manca o non è JSON); `tetto_profilo(profili, modello)` — `None` se `profili` è `None` o il modello non è in nessun profilo; `risposta_max` se `modello` è `senza_pensiero` di un profilo; se è `con_pensiero`, `risposta_max_pensiero` se c'è, altrimenti `risposta_max`;
  2. `coda/proxy.py`: attributi di classe `max_chiamate = None` e `profili = None`; in `do_POST` la condizione che oggi chiama `guardia.ripetizione(...)` vale anche quando `guardia.troppe_chiamate(dati.get('messages'), self.max_chiamate)` (stessa risposta di chiusura); il tetto applicato è `guardia.tetto_profilo(self.profili, dati.get('model'))` oppure, se è `None`, `self.tetto`, sempre con `guardia.con_tetto`; `crea(..., tetto=None, max_chiamate=None, profili=None)` passa i due nuovi valori alla classe; `main()` usa `int(os.environ.get('CODA_MAX_CHIAMATE', '40')) or None` e `guardia.carica_profili(os.environ.get('CODA_PROFILI', '/opt/ai-vm/modelli.json'))`. Il resto non cambia.
  Verifica: `cp piani/limiti/test_limiti.py tests/test_limiti.py && timeout 200 python3 -m unittest tests/test_limiti.py tests/test_guardia.py tests/test_coda.py`
