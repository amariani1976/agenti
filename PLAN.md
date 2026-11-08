---
stato: in-esecuzione
ramo: ai/modello-scelto
modello: esecutore
verifica_globale: timeout 300 python3 -m unittest discover -s tests
---
# Piano: il modello dell'agente si sceglie con AGENTE_MODELLO

Per confrontare modelli diversi col banco degli agenti (stesso ciclo, stesse lezioni della KB, stessa revisione), il
modello di `bin/agente` non deve essere fisso. Di serie resta `esecutore-pensiero`. Il test è già scritto e provato in
`piani/modello/test_agente_modello.py`.

- [x] 1. AGENTE_MODELLO in bin/agente
  File: `bin/agente`, `tests/test_agente_modello.py`
  Cosa fare: prima copia il test con `cp piani/modello/test_agente_modello.py tests/test_agente_modello.py` e non modificarlo. In `bin/agente` aggiungi una funzione `modello_scelto()` (docstring in italiano) che restituisce `os.environ.get('AGENTE_MODELLO')` oppure `'esecutore-pensiero'` se la variabile manca o è vuota; se il nome non corrisponde a `^[A-Za-z0-9][A-Za-z0-9._:/-]{0,100}\Z` (lo stesso controllo di esegui-passo) scrive su stderr `AGENTE_MODELLO non valido` ed esce con codice 2, prima di lanciare qualsiasi cosa. Nei due punti dove oggi c'è `modello='esecutore-pensiero'` usa `modello=modello_scelto()`. Aggiungi `import re` se manca. Non cambiare altro.
  Verifica: `cp piani/modello/test_agente_modello.py tests/test_agente_modello.py && timeout 300 python3 -m unittest tests/test_agente_modello.py tests/test_agente_catena.py`
