---
stato: in-esecuzione
ramo: ai/agente-ciclo
modello: esecutore
verifica_globale: timeout 300 python3 -m unittest tests/test_agente.py tests/test_ciclo.py tests/test_esecuzione.py tests/test_orchestratore.py tests/test_agente_catena.py tests/test_ciclo_qualita.py
accettazione: cd piani && timeout 200 python3 -m unittest test_revisore_affidabile
correzioni_semafori: 1
---
# Piano: un revisore affidabile

## Contesto
Sulla stessa modifica il revisore una volta trova un difetto vero e una volta no. Due rimedi: il revisore elenca le richieste del compito una per una e dice per ciascuna se il diff la soddisfa; la revisione si legge due volte ed è ok solo se lo sono entrambe. Il test `piani/test_revisore_affidabile.py` è già pronto e non si modifica. Python 3.6, sola libreria standard, niente f-string. Ogni comando con `timeout`.

## Passi
- [x] 1. Richieste una per una e due letture
  File: `ciclo/ruoli.py`
  Cosa fare: in `revisore` il prompt chiede di elencare le richieste del compito una per una e di rispondere SOLO con `{"richieste": [{"richiesta": testo, "fatta": bool}], "ok": bool, "difetti": [testi]}`, con `ok` vero solo se tutte le richieste sono fatte e non ci sono difetti. La funzione chiama `lancia` due volte, con lo stesso prompt, ripristinando la cartella dopo ciascuna come fa oggi. Una lettura illeggibile non conta; se entrambe lo sono, esito `non-fatto` come oggi. `ok` è vero solo se ogni lettura leggibile ha `ok` vero e nessuna richiesta con `fatta` falso; i difetti sono l'unione, senza doppioni, dei `difetti` e delle richieste non fatte («richiesta non fatta: …»). Il resto del risultato resta com'è (`esito`, `scritture_annullate` di entrambe le letture).
  Verifica: `cd piani && timeout 200 python3 -m unittest test_revisore_affidabile && cd .. && timeout 200 python3 -m unittest tests/test_ruoli.py`
- [x] 2. Il test al suo posto
  File: `tests/test_revisore_affidabile.py`
  Esegui:
  ```bash
mv piani/test_revisore_affidabile.py tests/
  ```
  Verifica: `test -f tests/test_revisore_affidabile.py && timeout 200 python3 -m unittest tests/test_revisore_affidabile.py`

- [ ] 3. Correzione dei semafori rossi (giro 1)
  File: `tests/test_cliente.py`, `tests/test_kb.py`, `tests/test_servizio.py`
  Cosa fare: a fine piano le regole di verifica del progetto (semafori) sono ROSSE. Capisci la causa di ogni
  controllo segnato con ❌ qui sotto e correggila nel codice, senza spegnere controlli, saltare test o cambiare
  `controlli.toml`. I ⚠️ sono avvisi: correggili solo se riguardano i file del piano.
  ## Semafori: 🔴 ROSSO
  
  - Base `1b7d0fc49af6`; controlli del progetto: `controlli.toml`.
  
  - ✅ **verifica generale del piano** (1.0 s)
    - Ran 35 tests in 0.975s
    - OK
  - ✅ **test finali della fase** (0.2 s)
    - Ran 5 tests in 0.168s
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
    - Ran 146 tests in 22.176s
    - FAILED (failures=1)
  - ✅ **Solo libreria standard di Python**
  Verifica: `/opt/ai-vm/bin/semafori --base 1b7d0fc49af6; test $? -lt 2`
