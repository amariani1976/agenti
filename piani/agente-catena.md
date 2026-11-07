---
stato: bozza
ramo: ai/agente-ciclo
modello: esecutore
verifica_globale: timeout 300 python3 -m unittest tests/test_agente.py tests/test_coda.py tests/test_misura.py tests/test_ciclo.py tests/test_esecuzione.py tests/test_ruoli.py tests/test_orchestratore.py
accettazione: cd piani && timeout 200 python3 -m unittest test_agente_catena
---
# Piano: il comando agente con la catena vera

## Contesto
La prova vera ha mostrato che `_esegui_con_verifica` in `bin/agente` non funziona: lancia `pi` direttamente come l'utente che chiama (fuori dalla rete chiusa), poi usa un nome non definito (`Esecuzione`); filtra il comando di verifica rifiutando virgolette e `>`; controlla i file rispetto alla radice degli agenti invece che alla cartella di lavoro; da un collegamento simbolico non trova i suoi moduli. Il test `piani/test_agente_catena.py` è già pronto, non si modifica, e prova la catena con un `esegui-passo` finto. Python 3.6, sola libreria standard. Ogni comando con `timeout`.

## Passi
- [ ] 1. Collegamento vero tra comando, ciclo ed esecuzione
  File: `bin/agente`
  Cosa fare: riscrivi solo `_esegui_con_verifica` e il calcolo della cartella dei moduli. La cartella dei moduli si ricava da `os.path.realpath(__file__)`, in tutto il file. In `_esegui_con_verifica`: niente chiamata diretta a `pi` e niente filtro dei caratteri della verifica (la verifica gira come `esecutore` dentro `esegui-passo`); crea `Esecuzione` come fa `_orchestratore` (stesse variabili `AGENTE_ESEGUI` e `AGENTE_PROGETTI`, modello `esecutore-pensiero`); se `e.progetto(cartella)` solleva `ValueError`, errore con uscita 2; i file devono essere relativi, senza `..`, dentro la cartella di lavoro, altrimenti uscita 2; tentativi da 1 a 5, altrimenti uscita 2; poi `ciclo.esegui(compito, cartella, verifica, file, tentativi, lancia=e.lancia, verifica_fn=e.verifica, lezioni=e.lezioni)`. Lascia com'è il resto del file, compreso il percorso senza `--verifica` e l'orchestratore. Non scrivere test.
  Verifica: `cd piani && timeout 200 python3 -m unittest test_agente_catena && cd .. && timeout 200 python3 -m unittest tests/test_agente.py`
- [ ] 2. Il test al suo posto
  File: `tests/test_agente_catena.py`
  Esegui:
  ```bash
mv piani/test_agente_catena.py tests/
  ```
  Verifica: `test -f tests/test_agente_catena.py && timeout 200 python3 -m unittest tests/test_agente_catena.py`
