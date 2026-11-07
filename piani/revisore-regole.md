---
stato: bozza
ramo: ai/agente-ciclo
modello: esecutore
verifica_globale: timeout 200 python3 -m unittest tests/test_agente.py tests/test_coda.py tests/test_misura.py tests/test_ciclo.py tests/test_esecuzione.py
accettazione: cd piani && timeout 120 python3 -m unittest test_revisore_regole
---
# Piano: il revisore controlla come è scritto il codice

## Contesto
`docs/PROGETTO.md` §4.15: funzioni e classi nelle librerie, riuso invece di copie, niente duplicati. Il revisore deve trattare queste regole come difetti. Il test `piani/test_revisore_regole.py` è già pronto e non si modifica. Python 3.6, sola libreria standard, niente f-string. Ogni comando con `timeout`.

## Passi
- [ ] 1. Regole e funzioni esistenti nel prompt del revisore
  File: `ciclo/ruoli.py`
  Cosa fare: nel prompt di `revisore` aggiungi, prima della richiesta del JSON, le regole di scrittura come difetti da segnalare: funzioni e classi nelle librerie e richiamate dove servono; si riusa ciò che esiste invece di copiarlo; nessun codice duplicato; una funzione fa una cosa sola. Aggiungi anche l'elenco delle funzioni e classi già presenti nel progetto (righe che iniziano con `def ` o `class ` nei file Python, `export function`/`export const`/`export class` nei file TypeScript, trovate con `git grep -n`), al massimo 200 righe, così il revisore vede se il diff ne ricrea una. Non cambiare il resto della funzione.
  Verifica: `cd piani && timeout 120 python3 -m unittest test_revisore_regole && cd .. && timeout 120 python3 -m unittest tests/test_ruoli.py`
