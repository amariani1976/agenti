---
stato: in-esecuzione
ramo: ai/agente-ciclo
modello: esecutore
verifica_globale: timeout 300 python3 -m unittest tests/test_agente.py tests/test_ciclo.py tests/test_esecuzione.py tests/test_orchestratore.py tests/test_agente_catena.py tests/test_ciclo_qualita.py
accettazione: cd piani && timeout 200 python3 -m unittest test_revisore_affidabile
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
