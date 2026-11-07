---
stato: bozza
ramo: ai/agente-ciclo
modello: esecutore
verifica_globale: timeout 300 python3 -m unittest tests/test_agente.py tests/test_ciclo.py tests/test_esecuzione.py tests/test_orchestratore.py tests/test_agente_catena.py tests/test_ciclo_qualita.py tests/test_ruoli.py
accettazione: cd piani && timeout 200 python3 -m unittest test_revisore_tre_letture
---
# Piano: tre letture del revisore, ciascuna con il suo compito

## Contesto
Due letture uguali sbagliano allo stesso modo: sul banco sono passati lavori con un errore che si rompe a runtime (`peek` su un file gzip) o con cambi oltre il richiesto. Le tre letture guardano ciascuna una cosa diversa; basta un difetto in una per non consegnare. Il test `piani/test_revisore_tre_letture.py` è già pronto e non si modifica; `tests/test_revisore_affidabile.py` va aggiornato solo dove contava due letture. Python 3.6, sola libreria standard, niente f-string. Ogni comando con `timeout`.

## Passi
- [ ] 1. Tre letture con tre compiti
  File: `ciclo/ruoli.py`
  Cosa fare: in `revisore` la parte comune del prompt resta (compito, diff, regole di scrittura, funzioni esistenti, forma del JSON); le letture diventano tre, ciascuna con una frase propria in testa: (1) «Controlla che il compito sia fatto tutto: elenca le richieste una per una e di' per ciascuna se il diff la soddisfa.» (2) «Cerca gli errori che si vedono solo quando il codice gira: metodi o attributi che non esistono sugli oggetti usati, file o flussi non chiusi, casi limite (vuoto, assente, errore), eccezioni non gestite.» (3) «Cerca i cambi oltre quello che il compito chiede: righe riscritte, traduzioni, commenti o nomi cambiati senza che il compito lo chieda; se il compito diceva di eseguire un comando, controlla che il risultato sia quello del comando.» Le regole di unione restano quelle di oggi: una lettura illeggibile non conta, `ok` solo se tutte le leggibili sono ok e senza richieste non fatte, difetti uniti senza doppioni.
  Verifica: `cd piani && timeout 200 python3 -m unittest test_revisore_tre_letture`
- [ ] 2. Il test delle due letture conta tre letture
  File: `tests/test_revisore_affidabile.py`
  Cosa fare: dove i test danno due risposte o contano due prompt, aggiungi una terza risposta uguale alla seconda e conta tre prompt. Non cambiare cosa si controlla.
  Verifica: `timeout 200 python3 -m unittest tests/test_revisore_affidabile.py tests/test_ruoli.py`
- [ ] 3. Il test al suo posto
  File: `tests/test_revisore_tre_letture.py`
  Esegui:
  ```bash
mv piani/test_revisore_tre_letture.py tests/
  ```
  Verifica: `test -f tests/test_revisore_tre_letture.py && timeout 200 python3 -m unittest tests/test_revisore_tre_letture.py`
