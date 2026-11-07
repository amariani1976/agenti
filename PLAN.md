---
stato: in-esecuzione
ramo: ai/orchestratore-revisione
modello: esecutore
verifica_globale: timeout 300 python3 -m unittest tests/test_agente.py tests/test_agente_catena.py tests/test_orchestratore.py tests/test_ciclo_qualita.py
accettazione: cd piani && timeout 60 python3 -m unittest test_orchestratore_revisione
---
# Piano: il programmatore dell'orchestratore usa il revisore

## Contesto
Dal comando diretto il programmatore passa dal revisore; dall'orchestratore no, perché `_orchestratore` in `bin/agente` non gli passa `revisione`. Il test `piani/test_orchestratore_revisione.py` è già pronto e non si modifica. Ogni comando con `timeout`.

## Passi
- [x] 1. Revisione al programmatore dell'orchestratore
  File: `bin/agente`
  Cosa fare: nella riga `'programmatore': lambda c, d: ruoli.programmatore(...)` di `_orchestratore` aggiungi `revisione=lambda compito, cartella: ruoli.revisore({'agente': 'revisore', 'compito': compito}, cartella, e.lancia)`. Nient'altro.
  Verifica: `cd piani && timeout 60 python3 -m unittest test_orchestratore_revisione && cd .. && timeout 200 python3 -m unittest tests/test_agente_catena.py tests/test_orchestratore.py`
- [ ] 2. Il test al suo posto
  File: `tests/test_orchestratore_revisione.py`
  Esegui:
  ```bash
mv piani/test_orchestratore_revisione.py tests/
  ```
  Verifica: `test -f tests/test_orchestratore_revisione.py && timeout 60 python3 -m unittest tests/test_orchestratore_revisione.py`
