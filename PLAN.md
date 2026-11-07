---
stato: in-esecuzione
ramo: ai/agente-ciclo
modello: esecutore
verifica_globale: timeout 200 python3 -m unittest tests/test_agente.py tests/test_coda.py tests/test_misura.py
accettazione: timeout 200 python3 -m unittest tests/test_ciclo.py tests/test_esecuzione.py
---
# Piano: un agente unico che usa il modello locale nel modo migliore

## Contesto
Hermes e Claude devono poter affidare un compito al modello locale con lo stesso metodo che fa funzionare il runner dei piani: comando di verifica che deve passare, al massimo 3 tentativi con l'errore del tentativo prima, perimetro dei file con annullamento di ciò che esce, lezioni dalla KB, esito chiaro. Agente e verifica passano da `esegui-passo` (utente `esecutore`, rete solo locale, guardiano dei comandi appesi). I test sono già pronti e non si modificano: sono il contratto. Python 3.6, sola libreria standard, niente f-string nei file nuovi. Ogni comando con `timeout`. Non usare git per fare commit: il ciclo usa git solo per leggere e ripristinare.

## Passi
- [ ] 1. Il ciclo
  File: `ciclo/ciclo.py`
  Cosa fare: `esegui(compito, cartella, verifica, file, tentativi=3, lancia=None, verifica_fn=None, lezioni=None)`. Controlli d'ingresso, con `ValueError`: `cartella` è la radice di un repository git (`git rev-parse --show-toplevel` uguale a `os.path.realpath(cartella)`); `file` non vuoto, ogni voce relativa, senza `..` e dentro la cartella; `verifica` non vuota. All'inizio ricorda lo stato: file già modificati o nuovi (`git status --porcelain`) e il contenuto dei file del perimetro. A ogni tentativo costruisce il prompt: compito, elenco dei file che si possono modificare, comando di verifica, lezioni (`lezioni(compito)`, se data), e dal secondo tentativo l'uscita della verifica precedente e i file fuori perimetro annullati; al massimo 20000 caratteri. Poi `lancia(prompt, cartella)`, poi annulla i cambi fuori perimetro rispetto all'inizio (file tracciati: contenuto di prima; file nuovi: cancellati; quelli già modificati all'inizio non si toccano), poi `verifica_fn(verifica, cartella)`. Riesce se la verifica esce con 0 e niente era fuori perimetro. Se tutti i tentativi falliscono, rimette i file del perimetro come all'inizio. Restituisce `{'esito': 'fatto'|'non-fatto', 'tentativi': [{'n', 'codice_agente', 'verifica', 'uscita' (ultimi 3000 caratteri), 'fuori_perimetro'}], 'file': [file del perimetro cambiati], 'diff': testo}`; il diff comprende i file nuovi (`git diff` più `git diff --no-index /dev/null file` per i nuovi). Non scrivere test.
  Verifica: `timeout 120 python3 -m unittest tests/test_ciclo.py`
- [ ] 2. L'esecuzione vera
  File: `ciclo/esecuzione.py`
  Cosa fare: classe `Esecuzione(radice='/srv/progetti', esegui=['sudo', '-n', '-u', 'esecutore', '/opt/ai-vm/libexec/esegui-passo'], modello='esecutore-pensiero', tempo=1900)`. `progetto(cartella)`: il nome se `realpath(cartella)` è esattamente `radice/<nome>`, altrimenti `ValueError`. `lancia(prompt, cartella)`: esegue `esegui + ['agente', nome, modello]` con il prompt su stdin; restituisce `(codice, uscita)`. `verifica(comando, cartella)`: `esegui + ['verifica', nome]` con il comando su stdin. `lezioni(compito)`: `kb cerca` con le prime parole del compito, al massimo 1500 caratteri, lista vuota se `kb` manca o fallisce. Ogni chiamata con `timeout=self.tempo`; un tempo scaduto diventa `(124, 'tempo massimo superato')`.
  Verifica: `timeout 120 python3 -m unittest tests/test_esecuzione.py`
- [ ] 3. Il comando `agente` col ciclo
  File: `bin/agente`
  Cosa fare: nuove opzioni `--file a,b`, `--verifica "comando"`, `--tentativi N` (1-5, predefinito 3), `--json`. Con `--verifica` il comando usa `ciclo.esegui` con `Esecuzione` (import da `../ciclo`), stampa l'esito (in JSON con `--json`, altrimenti esito, tentativi e file) ed esce con 0 se `fatto`, 1 se `non-fatto`, 2 per errori d'ingresso; senza `--verifica` resta tutto com'è oggi. Aggiungi le opzioni all'aiuto.
  Verifica: `timeout 120 python3 -m unittest tests/test_agente.py && python3 bin/agente --aiuto 2>&1 | grep -q -- "--verifica" || python3 bin/agente 2>&1 | grep -q -- "--verifica"`
