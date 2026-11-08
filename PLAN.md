---
stato: in-esecuzione
ramo: ai/letture-pubbliche
modello: esecutore
verifica_globale: timeout 300 python3 -m unittest discover -s tests
---
# Piano: le tre letture del revisore diventano una costante pubblica

Il runner di AI-VM userà le stesse tre letture del revisore degli agenti, importandole da qui invece di copiarle.
Nessun cambio di comportamento. Il test è già scritto e provato in `piani/letture/test_letture.py`.

- [ ] 1. Costante LETTURE in ciclo/ruoli.py
  File: `ciclo/ruoli.py`, `tests/test_letture.py`
  Cosa fare: prima copia il test con `cp piani/letture/test_letture.py tests/test_letture.py` e non modificarlo. In `ciclo/ruoli.py` sposta la lista `compiti` che oggi sta dentro la funzione `revisore` (i tre testi: richieste del compito, errori che si vedono solo quando il codice gira, cambi oltre il richiesto) in una costante di modulo `LETTURE`, una tupla con gli stessi tre testi identici e nello stesso ordine, definita prima di `_elenco`, con un commento in italiano: «Le tre letture del revisore; le usa anche il runner di AI-VM». Dentro `revisore` il ciclo diventa `for compito_lettura in LETTURE:`. Non cambiare altro.
  Verifica: `cp piani/letture/test_letture.py tests/test_letture.py && timeout 120 python3 -m unittest tests/test_letture.py tests/test_revisore_tre_letture.py`
