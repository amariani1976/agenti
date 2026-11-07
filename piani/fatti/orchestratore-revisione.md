---
stato: completato
ramo: ai/orchestratore-revisione
modello: esecutore
verifica_globale: timeout 300 python3 -m unittest tests/test_agente.py tests/test_agente_catena.py tests/test_orchestratore.py tests/test_ciclo_qualita.py
accettazione: timeout 60 python3 -m unittest tests/test_orchestratore_revisione_compito.py tests/test_orchestratore_revisione.py
collaudi: 2
collaudo: superato
aiuti: 1
---
# Piano: il programmatore dell'orchestratore usa il revisore

## Contesto
Dal comando diretto il programmatore passa dal revisore; dall'orchestratore no, perché `_orchestratore` in `bin/agente` non gli passa `revisione`. Il test `piani/test_orchestratore_revisione.py` è già pronto e non si modifica. Ogni comando con `timeout`.

## Passi
- [x] 1. Revisione al programmatore dell'orchestratore
  File: `bin/agente`
  Cosa fare: nella riga `'programmatore': lambda c, d: ruoli.programmatore(...)` di `_orchestratore` aggiungi `revisione=lambda compito, cartella: ruoli.revisore({'agente': 'revisore', 'compito': compito}, cartella, e.lancia)`. Nient'altro.
  Verifica: `cd piani && timeout 60 python3 -m unittest test_orchestratore_revisione && cd .. && timeout 200 python3 -m unittest tests/test_agente_catena.py tests/test_orchestratore.py`
- [x] 2. Il test al suo posto
  File: `tests/test_orchestratore_revisione.py`
  Esegui:
  ```bash
mv piani/test_orchestratore_revisione.py tests/
  ```
  Verifica: `test -f tests/test_orchestratore_revisione.py && timeout 60 python3 -m unittest tests/test_orchestratore_revisione.py`

## Correzioni del collaudo
- [x] 3. La revisione riceve il compito come testo
  File: `bin/agente`
  Perché: `ciclo.esegui` chiama `revisione(compito, cartella)` con `compito` già testo; `compito['compito']` nella lambda del passo 1 solleva TypeError alla prima revisione. Il test `piani/test_orchestratore_revisione_compito.py` è già pronto e non si modifica.
  Esegui:
  ```bash
sed -i "s/'compito': compito\['compito'\]}/'compito': compito}/" bin/agente
  ```
  Verifica: `cd piani && timeout 60 python3 -m unittest test_orchestratore_revisione_compito && cd .. && timeout 200 python3 -m unittest tests/test_orchestratore_revisione.py tests/test_agente_catena.py tests/test_orchestratore.py`
- [x] 4.1 Il test del compito al suo posto
  File: `piani/test_orchestratore_revisione_compito.py`, `tests/test_orchestratore_revisione_compito.py`
  Perché: il test `test_la_revisione_accetta_il_compito_come_testo` si sposta da `piani/` a `tests/`, non si toglie: il contenuto resta identico.
  Esegui:
  ```bash
mv piani/test_orchestratore_revisione_compito.py tests/test_orchestratore_revisione_compito.py
  ```
  Verifica: `test -f tests/test_orchestratore_revisione_compito.py && test ! -e piani/test_orchestratore_revisione_compito.py && grep -q test_la_revisione_accetta_il_compito_come_testo tests/test_orchestratore_revisione_compito.py && timeout 60 python3 -m unittest tests/test_orchestratore_revisione_compito.py`
- [x] 4.2 Via il doppione in piani/
  File: `piani/test_orchestratore_revisione.py`
  Perché: il passo 2 l'ha copiato invece di spostarlo; il test `test_il_programmatore_dell_orchestratore_ha_la_revisione` resta identico in `tests/test_orchestratore_revisione.py`, qui si toglie solo il doppione.
  Esegui:
  ```bash
cmp piani/test_orchestratore_revisione.py tests/test_orchestratore_revisione.py && rm piani/test_orchestratore_revisione.py
  ```
  Verifica: `test ! -e piani/test_orchestratore_revisione.py && grep -q test_il_programmatore_dell_orchestratore_ha_la_revisione tests/test_orchestratore_revisione.py && timeout 60 python3 -m unittest tests/test_orchestratore_revisione.py tests/test_orchestratore_revisione_compito.py`
