---
stato: in-esecuzione
ramo: ai/agente-ciclo
modello: esecutore
verifica_globale: timeout 300 python3 -m unittest tests/test_agente.py tests/test_ciclo.py tests/test_esecuzione.py tests/test_orchestratore.py tests/test_agente_catena.py tests/test_ciclo_qualita.py tests/test_ruoli.py
accettazione: cd piani && timeout 200 python3 -m unittest test_revisore_tre_letture
correzioni_semafori: 1
spezzati: 1
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

- [ ] 4.1 Rinominare TOKEN in test_kb.py (spezzato)
  File: `tests/test_kb.py`
  Cosa fare: sostituire `TOKEN = 'token-di-prova-0123456789'` con `CHIAVA_DI_TEST = 'finto-token-x-123'` e aggiornare tutti gli usi
  Verifica: `grep -c "TOKEN = 'token-di-prova" tests/test_kb.py`

- [ ] 4.2 Rinominare TOKEN in test_servizio.py (spezzato)
  File: `tests/test_servizio.py`
  Cosa fare: sostituire `TOKEN = 'token-di-prova-0123456789'` con `CHIAVA_DI_TEST = 'finto-token-x-123'` e aggiornare `self.stato = servizio.Kb(..., TOKEN)` e `chiama(..., token=TOKEN)`
  Verifica: `grep -c "TOKEN = 'token-di-prova" tests/test_servizio.py`

- [ ] 4.3 Correggere test_token_sbagliato in test_cliente.py (spezzato)
  File: `tests/test_cliente.py`
  Cosa fare: sostituire `TOKEN = 'token-di-prova-0123456789'` con `CHIAVA_DI_TEST = 'finto-token-x-123'`, `env=dict(os.environ, KB_URL=..., KB_TOKEN=TOKEN` con `KB_TOKEN=CHIAVA_DI_TEST`, e `KB_TOKEN='sbagliato'` con `KB_TOKEN='finto-sbagliato'`
  Verifica: `grep "TOKEN = 'token-di-prova" tests/test_cliente.py`

- [ ] 4.4 Verifica test_rifiuta_segreti (spezzato)
  File: `tests/test_kb.py`
  Cosa fare: eseguire solo il test che stava fallendo
  Verifica: `/opt/ai-vm/bin/semafori --base 1b7d0fc49af6; test $? -lt 2`

