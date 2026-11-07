---
stato: in-esecuzione
ramo: ai/agente-ciclo
modello: esecutore
verifica_globale: timeout 200 python3 -m unittest tests/test_agente.py tests/test_coda.py tests/test_misura.py tests/test_ciclo.py tests/test_esecuzione.py
accettazione: cd piani && timeout 200 python3 -m unittest test_ruoli test_orchestratore
---
# Piano: ruoli e orchestratore

## Contesto
`docs/PROGETTO.md` §4.1: un solo modello, più agenti con capacità specifiche, e un orchestratore che li richiama. Il modello decide il piano, il programma lo convalida e lo esegue in sequenza. I test sono già pronti in `piani/test_ruoli.py` e `piani/test_orchestratore.py` e non si modificano: sono il contratto. Restano in `piani/` finché la fase non è finita, perché fuori da qui farebbero fallire i controlli generali prima che il codice esista. Python 3.6, sola libreria standard, niente f-string nei file nuovi. Ogni comando con `timeout`.

## Passi
- [x] 1. I ruoli
  File: `ciclo/ruoli.py`
  Cosa fare: `programmatore(compito, cartella, esegui=ciclo.esegui, **k)`: chiama `esegui(compito['compito'], cartella, compito['verifica'], compito['file'], **k)`. `revisore(compito, cartella, lancia)`: prompt con il compito, `git diff` della cartella (anche i file nuovi) e la richiesta di rispondere SOLO con un JSON `{"ok": bool, "difetti": [stringhe]}`; dopo `lancia`, annulla ogni cambio fatto durante la chiamata rispetto a prima (file tracciati al contenuto di prima, file nuovi cancellati, quelli già cambiati prima restano come erano) e li elenca in `scritture_annullate` in ordine; legge il primo oggetto JSON della risposta (anche dentro un blocco ```json). Risposta illeggibile: `{'esito': 'non-fatto', 'motivo': ...}`. `ricercatore(compito, cartella, lancia)`: chiama `lancia` con il compito e l'istruzione di cercare nella KB, poi con la skill web, e salvare la sintesi nella KB; restituisce `{'esito': 'fatto', 'testo': uscita}` se il codice è 0, con la stessa sola lettura del revisore sui file della cartella.
  Verifica: `cd piani && timeout 120 python3 -m unittest test_ruoli`
- [x] 2. L'orchestratore
  File: `ciclo/orchestratore.py`
  Cosa fare: `esegui(richiesta, cartella, chiedi, agenti, avvisa=None, max_compiti=6)`. Prompt per `chiedi`: la richiesta, i ruoli disponibili (`agenti`) con cosa sanno fare, la forma `{"compiti": [{"agente", "compito", "file", "verifica"}]}` (`file` e `verifica` obbligatori per il programmatore). Legge il primo oggetto JSON della risposta e lo convalida: da 1 a `max_compiti` compiti, agente fra quelli dati, compito non vuoto, per il programmatore file relativi senza `..` e verifica non vuota. Se non è valido richiede una sola volta con il motivo («piano non valido: …»); se resta non valido, esito `aiuto`. Esegue i compiti in ordine: un esito diverso da `fatto` ferma tutto con `aiuto`; un revisore con `ok` falso porta a un solo giro di correzione: il programmatore dell'ultimo compito del programmatore rifà con i difetti nel compito, poi il revisore ripassa; se trova ancora difetti, `aiuto`. `avvisa(tipo, testo)` alla fine (`fatto` o `aiuto`) con la richiesta e, se serve, il motivo e i difetti. Restituisce `{'esito', 'piano', 'risultati', 'motivo'}`.
  Verifica: `cd piani && timeout 120 python3 -m unittest test_orchestratore`
- [x] 3. L'orchestratore dal comando `agente`
  File: `bin/agente`
  Cosa fare: `agente orchestratore --cartella DIR "richiesta"` usa `orchestratore.esegui` con: `chiedi` = una chiamata al modello attraverso `Esecuzione.lancia` con prompt «rispondi solo con il JSON»; gli agenti `programmatore`, `revisore`, `ricercatore` di `ruoli` collegati a `Esecuzione`; `avvisa` che scrive sulla FIFO `orchestratore` con `avviso.scrivi` di `/opt/ai-vm/lib/avviso.py` (se manca, non fa nulla) e stampa l'avviso. Esce con 0 se `fatto`, 1 altrimenti, e stampa il resoconto in JSON con `--json`.
  Verifica: `timeout 120 python3 -m unittest tests/test_agente.py && grep -q "orchestratore" bin/agente`
- [x] 4. I test al loro posto
  File: `tests/test_ruoli.py`, `tests/test_orchestratore.py`
  Esegui:
  ```bash
mv piani/test_ruoli.py piani/test_orchestratore.py tests/
  ```
  Verifica: `test -f tests/test_ruoli.py && test -f tests/test_orchestratore.py && timeout 200 python3 -m unittest tests/test_ruoli.py tests/test_orchestratore.py`

