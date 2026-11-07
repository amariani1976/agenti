---
stato: in-esecuzione
ramo: ai/agente-ciclo
modello: esecutore
verifica_globale: timeout 300 python3 -m unittest tests/test_agente.py tests/test_ciclo.py tests/test_esecuzione.py tests/test_orchestratore.py tests/test_agente_catena.py tests/test_ciclo_qualita.py tests/test_ruoli.py
accettazione: cd piani && timeout 200 python3 -m unittest test_revisore_tre_letture
correzioni_semafori: 1
---
# Piano: tre letture del revisore, ciascuna con il suo compito

## Contesto
Due letture uguali sbagliano allo stesso modo: sul banco sono passati lavori con un errore che si rompe a runtime (`peek` su un file gzip) o con cambi oltre il richiesto. Le tre letture guardano ciascuna una cosa diversa; basta un difetto in una per non consegnare. Il test `piani/test_revisore_tre_letture.py` è già pronto e non si modifica; `tests/test_revisore_affidabile.py` va aggiornato solo dove contava due letture. Python 3.6, sola libreria standard, niente f-string. Ogni comando con `timeout`.

## Passi
- [x] 1. Tre letture con tre compiti
  File: `ciclo/ruoli.py`
  Cosa fare: in `revisore` la parte comune del prompt resta (compito, diff, regole di scrittura, funzioni esistenti, forma del JSON); le letture diventano tre, ciascuna con una frase propria in testa: (1) «Controlla che il compito sia fatto tutto: elenca le richieste una per una e di' per ciascuna se il diff la soddisfa.» (2) «Cerca gli errori che si vedono solo quando il codice gira: metodi o attributi che non esistono sugli oggetti usati, file o flussi non chiusi, casi limite (vuoto, assente, errore), eccezioni non gestite.» (3) «Cerca i cambi oltre quello che il compito chiede: righe riscritte, traduzioni, commenti o nomi cambiati senza che il compito lo chieda; se il compito diceva di eseguire un comando, controlla che il risultato sia quello del comando.» Le regole di unione restano quelle di oggi: una lettura illeggibile non conta, `ok` solo se tutte le leggibili sono ok e senza richieste non fatte, difetti uniti senza doppioni.
  Verifica: `cd piani && timeout 200 python3 -m unittest test_revisore_tre_letture`
- [x] 2. Il test delle due letture conta tre letture
  File: `tests/test_revisore_affidabile.py`
  Cosa fare: dove i test danno due risposte o contano due prompt, aggiungi una terza risposta uguale alla seconda e conta tre prompt. Non cambiare cosa si controlla.
  Verifica: `timeout 200 python3 -m unittest tests/test_revisore_affidabile.py tests/test_ruoli.py`
- [x] 3. Il test al suo posto
  File: `tests/test_revisore_tre_letture.py`
  Esegui:
  ```bash
mv piani/test_revisore_tre_letture.py tests/
  ```
  Verifica: `test -f tests/test_revisore_tre_letture.py && timeout 200 python3 -m unittest tests/test_revisore_tre_letture.py`

- [ ] 4. Correzione dei semafori rossi (giro 1)
  File: `tests/test_cliente.py`, `tests/test_kb.py`, `tests/test_servizio.py`
  Cosa fare: a fine piano le regole di verifica del progetto (semafori) sono ROSSE. Capisci la causa di ogni
  controllo segnato con ❌ qui sotto e correggila nel codice, senza spegnere controlli, saltare test o cambiare
  `controlli.toml`. I ⚠️ sono avvisi: correggili solo se riguardano i file del piano.
  ## Semafori: 🔴 ROSSO
  
  - Base `1b7d0fc49af6`; controlli del progetto: `controlli.toml`.
  
  - ✅ **verifica generale del piano** (1.2 s)
    - Ran 39 tests in 1.130s
    - OK
  - ✅ **test finali della fase** (0.2 s)
    - Ran 3 tests in 0.133s
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
  - ❌ **Test** (22.3 s)
    - uscita 1
    - FAIL: test_da_capo_a_fondo (test_agente_orchestratore.Orchestratore.test_da_capo_a_fondo)
    - Ran 149 tests in 22.229s
    - FAILED (failures=1)
  - ✅ **Solo libreria standard di Python**
  Verifica: `/opt/ai-vm/bin/semafori --base 1b7d0fc49af6; test $? -lt 2`
