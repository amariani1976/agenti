---
stato: in-esecuzione
ramo: ai/agente-ciclo
modello: esecutore
verifica_globale: timeout 200 python3 -m unittest tests/test_agente.py tests/test_coda.py tests/test_misura.py tests/test_ciclo.py tests/test_esecuzione.py
accettazione: cd piani && timeout 200 python3 -m unittest test_ruoli test_orchestratore
collaudi: 1
spezzati: 1
aiuti: 1
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


## Correzioni del collaudo
Il collaudo ha trovato difetti che i test della fase non coprivano: `agente orchestratore` non parte (`ModuleNotFoundError: ciclo`, poi `import sys` locale dopo l'uso di `sys` → `UnboundLocalError`; gli agenti ricevono solo `(compito, cartella)` e il revisore non ha `lancia`; `Esecuzione` lancia `bin/agente` invece di esegui-passo); il revisore puo' scrivere i file del campo `file` e non ripristina le sottocartelle (`_scrivi` rifiuta i nomi con `/`), e `_prima_stato` vede solo i file non tracciati in cima, quindi cancellerebbe i file nuovi del programmatore in sottocartella; il JSON con testo intorno non si legge; il ricercatore fa due chiamate e non chiede di salvare nella KB; l'orchestratore richiede il piano senza ripetere richiesta e ruoli, chiude «fatto» se il revisore boccia e non c'e' programmatore, ignora una correzione non fatta, va in errore con tipi sbagliati nel piano; `_json_da_risposta` e' copiato in due file. I test nuovi sono gia' pronti in `piani/` e non si modificano. Python 3.6, sola libreria standard, niente f-string.

- [x] 5. Una sola lettura del JSON
  File: `ciclo/risposta.py`, `ciclo/ruoli.py`, `ciclo/orchestratore.py`
  Cosa fare: nuovo `ciclo/risposta.py` con `primo_json(testo)`: `None` se il testo e' vuoto o `None`; se c'e' un blocco ```json … ``` usa il suo contenuto; poi prova `json.JSONDecoder().raw_decode(testo, i)` da ogni posizione `i` in cui c'e' `{`, in ordine, e restituisce il primo risultato che e' un `dict`; altrimenti `None`. In `ruoli.py` e `orchestratore.py` togliere `_json_da_risposta` e usare `from risposta import primo_json` (i moduli si importano con `ciclo/` in `sys.path`, come gia' fa `from ciclo import …`).
  Verifica: `cd piani && timeout 120 python3 -m unittest test_risposta test_ruoli test_orchestratore`
- [!] 6.1 Implementare `_elenco` (spezzato)
  File: `ciclo/ruoli.py`
  Cosa fare: sostituire `_prima_stato` con `_elenco(cartella)` che restituisce nomi di `git ls-files` più `git ls-files --others --exclude-standard` (percorsi relativi anche in sottocartelle)
  Verifica: `cd piani && timeout 120 python3 -m unittest test_ruoli_lettura.test_ruoli_lettura.SolaLettura.test_sottocartella_ripristinata`

- [ ] 6.2 Implementare `_istantanea` (spezzato)
  File: `ciclo/ruoli.py`
  Cosa fare: aggiungere `_istantanea(cartella)` che restituisce dict nome → bytes del contenuto per ogni nome di `_elenco` che è un file
  Verifica: `cd piani && timeout 120 python3 -m unittest test_ruoli_lettura`

- [ ] 6.3 Implementare `_ripristina` con path validation (spezzato)
  File: `ciclo/ruoli.py`
  Cosa fare: aggiungere `_ripristina(cartella, prima)` che per ogni nome in `sorted(set(prima) | set(_elenco(cartella)))`: se era in `prima` e ora manca o è diverso riscrive i bytes di prima (creando cartelle); se non era in `prima` ed esiste lo cancella; restituisce nomi toccati; validare con `os.path.realpath` che i percorsi stanno dentro `realpath(cartella)`
  Verifica: `cd piani && timeout 120 python3 -m unittest test_ruoli_lettura.test_ruoli_lettura.SolaLettura.test_sottocartella_ripristinata`

- [ ] 6.4 Aggiornare `revisore` per sola lettura (spezzato)
  File: `ciclo/ruoli.py`
  Cosa fare: rimuovere `_annulla_cambi` e `_prima_stato`; usare `_istantanea` e `_ripristina`; ignorare `compito['file']` (niente perimetro e niente «File che puoi modificare» nel prompt); diff usa `_sporchi(cartella)`; chiamare `_ripristina` sempre dopo `lancia`, anche se eccezione
  Verifica: `cd piani && timeout 120 python3 -m unittest test_ruoli_lettura.test_ruoli_lettura.SolaLettura.test_sottocartella_ripristinata`

- [ ] 6.5 Aggiornare `ricercatore` per una sola chiamata (spezzato)
  File: `ciclo/ruoli.py`
  Cosa fare: il ricercatore fa UNA sola chiamata a `lancia` con prompt: il compito, «Cerca prima nella KB, poi usa la skill web, e salva la sintesi nella KB con kb_salva.»; codice 0 → `{'esito': 'fatto', 'testo': uscita, 'scritture_annullate': [...]}`, altrimenti `{'esito': 'non-fatto', 'motivo': ...}`; usa `_ripristina` per annullare
  Verifica: `cd piani && timeout 120 python3 -m unittest test_ruoli_lettura test_ruoli`

- [ ] 7. Orchestratore: casi mancanti
  File: `ciclo/orchestratore.py`
  Cosa fare: (a) la seconda richiesta al modello e' il prompt completo della prima piu' una riga «piano non valido: <motivo>; rispondi di nuovo con il JSON.»; (b) `_convalida_piano` non va mai in errore: `compito` e `verifica` devono essere stringhe non vuote, `file` una lista non vuota di stringhe relative, senza `\\`, senza componenti `..` (controllare `f.split('/')`); con risposta non `dict` motivo «il piano non è un oggetto»; (c) i compiti si eseguono in ordine e la correzione avviene subito quando un revisore restituisce `ok` falso: se prima non c'e' stato un programmatore → `aiuto` con i difetti nel motivo; altrimenti il programmatore rifà l'ultimo compito del programmatore con i difetti aggiunti al testo del compito; se questo esito non e' `fatto` → `aiuto`; poi lo stesso compito del revisore (lo stesso dict del piano) ripassa; se l'esito non e' `fatto` o `ok` e' ancora falso → `aiuto` con i difetti; altrimenti si prosegue con i compiti successivi; un secondo revisore con `ok` falso dopo la correzione gia' fatta → `aiuto`. `avvisa` riceve sempre la richiesta, e in caso di `aiuto` il motivo con i difetti.
  Verifica: `cd piani && timeout 120 python3 -m unittest test_orchestratore_casi test_orchestratore`
- [ ] 8. `agente orchestratore` funzionante
  File: `bin/agente`
  Cosa fare: togliere l'opzione `--orchestratore` e far riconoscere `orchestratore` come primo argomento (`nome`): `agente orchestratore --cartella DIR [--json] "richiesta"`. Senza richiesta o senza `--cartella`: messaggio su stderr e uscita 2, senza traceback. In `_orchestratore`: niente `import sys` locale; `sys.path.insert(0, <radice repo>/ciclo)` e poi `import ruoli, orchestratore, esecuzione` (togliere gli `spec_from_file_location`); `Esecuzione(radice=os.environ.get('AGENTE_PROGETTI', '/srv/progetti'), esegui=[os.environ['AGENTE_ESEGUI']] se la variabile c'e', altrimenti ['sudo', '-n', '-u', 'esecutore', '/opt/ai-vm/libexec/esegui-passo'], modello='esecutore-pensiero')`; se `esecuzione.progetto(cartella)` solleva `ValueError`: messaggio su stderr e uscita 2. Agenti collegati: `'programmatore': lambda c, d: ruoli.programmatore(c, d, lancia=e.lancia, verifica_fn=e.verifica, lezioni=e.lezioni)`, `'revisore': lambda c, d: ruoli.revisore(c, d, e.lancia)`, `'ricercatore': lambda c, d: ruoli.ricercatore(c, d, e.lancia)`. `chiedi` restituisce l'uscita di `e.lancia(prompt + '\n\nRispondi solo con il JSON.', cartella)` (stringa vuota se il codice non e' 0). `avvisa` come ora (FIFO `orchestratore` se `/opt/ai-vm/lib/avviso.py` c'e', e stampa su stderr). Con `--json` stampa il resoconto in JSON su stdout, e nient'altro su stdout; uscita 0 se `fatto`, 1 altrimenti.
  Verifica: `timeout 200 python3 -m unittest tests/test_agente.py piani/test_agente_orchestratore.py`
- [ ] 9. I test nuovi al loro posto
  File: `tests/test_risposta.py`, `tests/test_ruoli_lettura.py`, `tests/test_orchestratore_casi.py`, `tests/test_agente_orchestratore.py`
  Esegui:
  ```bash
mv piani/test_risposta.py piani/test_ruoli_lettura.py piani/test_orchestratore_casi.py piani/test_agente_orchestratore.py tests/
  ```
  Verifica: `test ! -f piani/test_risposta.py && timeout 300 python3 -m unittest tests/test_risposta.py tests/test_ruoli_lettura.py tests/test_orchestratore_casi.py tests/test_agente_orchestratore.py tests/test_ruoli.py tests/test_orchestratore.py tests/test_agente.py`
