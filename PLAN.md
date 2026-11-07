---
stato: in-esecuzione
ramo: ai/agente-ciclo
modello: esecutore
verifica_globale: timeout 200 python3 -m unittest tests/test_agente.py tests/test_coda.py tests/test_misura.py
accettazione: timeout 200 python3 -m unittest tests/test_ciclo.py tests/test_esecuzione.py
spezzati: 1
---
# Piano: un agente unico che usa il modello locale nel modo migliore

## Contesto
Hermes e Claude devono poter affidare un compito al modello locale con lo stesso metodo che fa funzionare il runner dei piani: comando di verifica che deve passare, al massimo 3 tentativi con l'errore del tentativo prima, perimetro dei file con annullamento di ciò che esce, lezioni dalla KB, esito chiaro. Agente e verifica passano da `esegui-passo` (utente `esecutore`, rete solo locale, guardiano dei comandi appesi). I test sono già pronti e non si modificano: sono il contratto. Python 3.6, sola libreria standard, niente f-string nei file nuovi. Ogni comando con `timeout`. Non usare git per fare commit: il ciclo usa git solo per leggere e ripristinare.

## Passi
- [ ] 1.1 Creare il ciclo di base con validazione (spezzato)
  File: `ciclo/ciclo.py`
  Cosa fare: creare il file con la funzione `esegui` che fa: validazione input (ValueError per cartella non git, file vuoti/con.., verifica vuota), ritorno iniziale `{'esito': 'non-fatto', 'tentativi': [], 'file': [], 'diff': ''}`
  Verifica: `timeout 120 python3 -m unittest tests/test_ciclo.py Ciclo.test_errori_di_ingresso`

- [ ] 1.2 Implementare il loop con tentativi e tracking (spezzato)
  File: `ciclo/ciclo.py`
  Cosa fare: aggiungere all'inizio di `esegui` il salvatato stato git iniziale (`git status --porcelain`) e contenuti file perimetro; loop per tentativi con chiamata a `lancia(prompt, cartella)` che restituisce (codice, uscita); registrare tentativi in lista
  Verifica: `timeout 120 python3 -m unittest tests/test_ciclo.py Ciclo.test_il_prompt_dice_file_verifica_e_lezioni`

- [ ] 1.3 Gestione perimetro e rollback (spezzato)
  File: `ciclo/ciclo.py`
  Cosa fare: dopo ogni `lancia`, confrontare stato git con iniziale, identificare file fuori perimetro, annullare file nuovi (cancellare) e tracciati (ripristinare contenuto), riportare file fuori perimetro nel prompt del tentativo successivo
  Verifica: `timeout 120 python3 -m unittest tests/test_ciclo.py Ciclo.test_fuori_perimetro_si_annulla`

- [ ] 1.4 Completamento e diff (spezzato)
  File: `ciclo/ciclo.py`
  Cosa fare: se verifica passa e niente fuori perimetro, set `esito='fatto'`, se tutti tentativi falliscono ripristina perimetro come iniziale; calcolare diff con `git diff` e `git diff --no-index /dev/null` per nuovi; troncare uscita a 3000 caratteri; costruire prompt max 20000 caratteri; restituire risultato completo
  Verifica: `timeout 120 python3 -m unittest tests/test_ciclo.py`

- [ ] 2. L'esecuzione vera
  File: `ciclo/esecuzione.py`
  Cosa fare: classe `Esecuzione(radice='/srv/progetti', esegui=['sudo', '-n', '-u', 'esecutore', '/opt/ai-vm/libexec/esegui-passo'], modello='esecutore-pensiero', tempo=1900)`. `progetto(cartella)`: il nome se `realpath(cartella)` è esattamente `radice/<nome>`, altrimenti `ValueError`. `lancia(prompt, cartella)`: esegue `esegui + ['agente', nome, modello]` con il prompt su stdin; restituisce `(codice, uscita)`. `verifica(comando, cartella)`: `esegui + ['verifica', nome]` con il comando su stdin. `lezioni(compito)`: `kb cerca` con le prime parole del compito, al massimo 1500 caratteri, lista vuota se `kb` manca o fallisce. Ogni chiamata con `timeout=self.tempo`; un tempo scaduto diventa `(124, 'tempo massimo superato')`.
  Verifica: `timeout 120 python3 -m unittest tests/test_esecuzione.py`
- [ ] 3. Il comando `agente` col ciclo
  File: `bin/agente`
  Cosa fare: nuove opzioni `--file a,b`, `--verifica "comando"`, `--tentativi N` (1-5, predefinito 3), `--json`. Con `--verifica` il comando usa `ciclo.esegui` con `Esecuzione` (import da `../ciclo`), stampa l'esito (in JSON con `--json`, altrimenti esito, tentativi e file) ed esce con 0 se `fatto`, 1 se `non-fatto`, 2 per errori d'ingresso; senza `--verifica` resta tutto com'è oggi. Aggiungi le opzioni all'aiuto.
  Verifica: `timeout 120 python3 -m unittest tests/test_agente.py && python3 bin/agente --aiuto 2>&1 | grep -q -- "--verifica" || python3 bin/agente 2>&1 | grep -q -- "--verifica"`
