---
stato: in-esecuzione
ramo: ai/agente-ciclo
modello: esecutore
verifica_globale: timeout 300 python3 -m unittest tests/test_agente.py tests/test_ciclo.py tests/test_esecuzione.py tests/test_ruoli.py tests/test_orchestratore.py tests/test_agente_catena.py
accettazione: cd piani && timeout 200 python3 -m unittest test_ciclo_qualita
correzioni_semafori: 1
aiuti: 1
---
# Piano: il ciclo consegna solo lavoro fatto bene

## Contesto
Il banco ha mostrato che l'agente si ferma appena passa la verifica del passo: in metà dei casi la verifica generale si rompe, il compito è fatto a metà o l'agente riscrive più del richiesto. Il ciclo deve controllare anche la verifica generale e passare dal revisore prima di consegnare. Il test `piani/test_ciclo_qualita.py` è già pronto e non si modifica. Python 3.6, sola libreria standard, niente f-string. Ogni comando con `timeout`.

## Passi
- [x] 1. Verifica generale, revisore e tempo massimo nel ciclo
  File: `ciclo/ciclo.py`
  Cosa fare: `esegui` riceve in più `verifica_globale=None`, `revisione=None`, `tempo_max=1800`, `orologio=time.time`. Dopo che la verifica del passo passa e nulla è fuori perimetro: se c'è `verifica_globale`, la esegue con `verifica_fn`; se fallisce, il tentativo fallisce e la sua uscita va nel prompt successivo. Poi, se c'è `revisione`, chiama `revisione(compito, cartella)`: con `ok` falso il tentativo fallisce e i `difetti` vanno nel prompt successivo; una revisione senza `ok` (risposta illeggibile) non ferma e il suo esito si mette in `risultato['revisione']`. Prima di ogni tentativo, se `orologio() - inizio >= tempo_max`, ci si ferma. A esito `non-fatto` il risultato ha `motivo` (ultimo errore, difetti o «tempo massimo del compito superato»). Nel prompt aggiungi: «Cambia solo quello che il compito chiede: non riscrivere codice che funziona, non aggiungere altro. Se il compito dice di eseguire un comando, eseguilo invece di modificare il file a mano.» Il resto della funzione non cambia.
  Verifica: `cd piani && timeout 200 python3 -m unittest test_ciclo_qualita && cd .. && timeout 200 python3 -m unittest tests/test_ciclo.py`
- [x] 2. Opzioni del comando
  File: `bin/agente`
  Cosa fare: nuove opzioni `--verifica-globale "comando"` e `--senza-revisione`. Col ciclo, passa `verifica_globale` e, se non c'è `--senza-revisione`, `revisione=lambda compito, cartella: ruoli.revisore({'agente': 'revisore', 'compito': compito}, cartella, e.lancia)` con lo stesso `Esecuzione` del programmatore. Nient'altro cambia.
  Verifica: `timeout 200 python3 -m unittest tests/test_agente_catena.py tests/test_agente.py && grep -q -- "--verifica-globale" bin/agente`
- [x] 3. Il test al suo posto
  File: `tests/test_ciclo_qualita.py`
  Esegui:
  ```bash
mv piani/test_ciclo_qualita.py tests/
  ```
  Verifica: `test -f tests/test_ciclo_qualita.py && timeout 200 python3 -m unittest tests/test_ciclo_qualita.py`

- [!] 4. Correzione dei semafori rossi (giro 1)
  File: `tests/test_cliente.py`, `tests/test_kb.py`, `tests/test_servizio.py`
  Cosa fare: a fine piano le regole di verifica del progetto (semafori) sono ROSSE. Capisci la causa di ogni
  controllo segnato con ❌ qui sotto e correggila nel codice, senza spegnere controlli, saltare test o cambiare
  `controlli.toml`. I ⚠️ sono avvisi: correggili solo se riguardano i file del piano.
  ## Semafori: 🔴 ROSSO
  
  - Base `1b7d0fc49af6`; controlli del progetto: `controlli.toml`.
  
  - ✅ **verifica generale del piano** (0.9 s)
    - Ran 33 tests in 0.824s
    - OK
  - ✅ **test finali della fase** (0.2 s)
    - Ran 6 tests in 0.150s
    - OK
  - ✅ **segreti**
  - ✅ **conflitti**
  - ✅ **file-spuri**
  - ✅ **test-saltati**
  - ✅ **test-cancellati**
  - ✅ **todo**
  - ✅ **file-grandi**
  - ⚠️ **file-monolitici** — File di codice oltre 500 righe modificati: dividere in moduli piccoli
    - web/web.py (545 righe)
  - ✅ **codice-ripetuto**
  - ⚠️ **segreti-nei-test** — Valori simili a segreti nei file di test (controllare che siano finti)
    - tests/test_cliente.py:15: …TOKEN = 'tok…
    - tests/test_cliente.py:62: …TOKEN='sbagl…
    - tests/test_kb.py:53: …-----BEGIN O…
    - tests/test_servizio.py:19: …TOKEN = 'tok…
    - tests/test_servizio.py:71: …token='sbagl…
  - ❌ **Test** (21.9 s)
    - uscita 1
    - FAIL: test_da_capo_a_fondo (test_agente_orchestratore.Orchestratore.test_da_capo_a_fondo)
    - Ran 141 tests in 21.784s
    - FAILED (failures=1)
  - ✅ **Solo libreria standard di Python**
  Verifica: `/opt/ai-vm/bin/semafori --base 1b7d0fc49af6; test $? -lt 2`
