---
stato: in-esecuzione
ramo: ai/agente-ciclo
modello: esecutore
verifica_globale: timeout 200 python3 -m unittest tests/test_agente.py tests/test_coda.py tests/test_misura.py tests/test_ciclo.py tests/test_esecuzione.py
accettazione: cd piani && timeout 200 python3 -m unittest test_ruoli test_orchestratore
collaudi: 1
spezzati: 3
aiuti: 3
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
- [x] 6.1 Funzioni di appoggio per la sola lettura (`_elenco`, `_istantanea`, `_ripristina`)
  File: `ciclo/ruoli.py`
  Cosa fare: eseguire dalla radice del progetto lo script qui sotto, così com'è, senza riscriverlo a mano. Toglie `_annulla_cambi` e `_prima_stato` e mette al loro posto `_elenco`, `_dentro`, `_istantanea`, `_ripristina` (`revisore` e `ricercatore` si sistemano nel passo 6.2: fino ad allora `tests/test_ruoli.py` fallisce, è previsto).
  Esegui:
  ```bash
python3 - <<'EOF'
p = 'ciclo/ruoli.py'
t = open(p, encoding='utf-8').read()
i = t.index('def _annulla_cambi(')
j = t.index('def programmatore(')
nuovo = '''def _elenco(cartella):
    """Nomi relativi dei file tracciati e non tracciati (non ignorati), anche in sottocartelle."""
    nomi = set()
    for argomenti in (('ls-files', '-z'), ('ls-files', '-z', '--others', '--exclude-standard')):
        codice, uscita = _git(cartella, *argomenti)
        if codice == 0:
            nomi.update(n for n in uscita.split('\\0') if n)
    return sorted(nomi)


def _dentro(cartella, nome):
    """Percorso assoluto del file se sta dentro la cartella, altrimenti None."""
    base = os.path.realpath(cartella)
    percorso = os.path.realpath(os.path.join(base, nome))
    if percorso == base or not percorso.startswith(base + os.sep):
        return None
    return percorso


def _istantanea(cartella):
    """Contenuto in byte di ogni file di _elenco: dict nome -> bytes."""
    prima = {}
    for nome in _elenco(cartella):
        contenuto = _leggi(cartella, nome)
        if contenuto is not None:
            prima[nome] = contenuto
    return prima


def _ripristina(cartella, prima):
    """Riporta la cartella all'istantanea; restituisce in ordine i nomi toccati."""
    toccati = []
    for nome in sorted(set(prima) | set(_elenco(cartella))):
        percorso = _dentro(cartella, nome)
        if percorso is None:
            continue
        ora = _leggi(cartella, nome)
        if nome in prima:
            if ora == prima[nome]:
                continue
            sopra = os.path.dirname(percorso)
            if not os.path.isdir(sopra):
                os.makedirs(sopra)
            with open(percorso, 'wb') as f:
                f.write(prima[nome])
            toccati.append(nome)
        elif ora is not None:
            os.remove(percorso)
            toccati.append(nome)
    return toccati


'''
open(p, 'w', encoding='utf-8').write(t[:i] + nuovo + t[j:])
EOF
  ```
  Verifica: `timeout 60 python3 -c "import sys; sys.path.insert(0, 'ciclo'); import ruoli; assert not hasattr(ruoli, '_annulla_cambi') and not hasattr(ruoli, '_prima_stato'); import os, tempfile, subprocess; d = tempfile.mkdtemp(); g = lambda *a: subprocess.check_call(['git', '-C', d] + list(a), stdout=subprocess.DEVNULL); g('init', '-q'); os.makedirs(os.path.join(d, 'sub')); open(os.path.join(d, 'sub/b.py'), 'w').write('y'); g('add', '.'); g('-c', 'user.email=p@e.invalid', '-c', 'user.name=p', 'commit', '-qm', 'i'); open(os.path.join(d, 'sub/n.py'), 'w').write('n'); assert ruoli._elenco(d) == ['sub/b.py', 'sub/n.py']; p = ruoli._istantanea(d); open(os.path.join(d, 'sub/b.py'), 'w').write('rotto'); open(os.path.join(d, 'sub/z.py'), 'w').write('z'); assert ruoli._ripristina(d, p) == ['sub/b.py', 'sub/z.py']; assert open(os.path.join(d, 'sub/b.py')).read() == 'y' and not os.path.exists(os.path.join(d, 'sub/z.py')); print('ok')"`
- [x] 6.2 Revisore e ricercatore usano `_istantanea` e `_ripristina`
  File: `ciclo/ruoli.py`
  Cosa fare: eseguire dalla radice del progetto lo script qui sotto, così com'è. Riscrive tutto da `def revisore(` alla fine del file: il revisore ignora `compito['file']` (niente «File che puoi modificare»), mostra il diff di `_sporchi`, ripristina sempre dopo `lancia` (anche con eccezione); il ricercatore fa UNA sola chiamata (KB, skill web, salva con kb_salva).
  Esegui:
  ```bash
python3 - <<'EOF'
p = 'ciclo/ruoli.py'
t = open(p, encoding='utf-8').read()
i = t.index('def revisore(')
nuovo = '''def revisore(compito, cartella, lancia):
    """Revisore: chiede un giudizio in JSON e annulla ogni scrittura fatta durante la chiamata."""
    prima = _istantanea(cartella)
    prompt = 'Compito: ' + compito['compito']
    diff = _diff(cartella, sorted(_sporchi(cartella)))
    if diff:
        prompt += '\\n\\nDiff della cartella:\\n' + diff
    prompt += '\\n\\nRispondi SOLO con un JSON: {"ok": bool, "difetti": [stringhe]}'
    try:
        codice, uscita = lancia(prompt, cartella)
    except Exception as e:
        _ripristina(cartella, prima)
        return {'esito': 'non-fatto', 'motivo': 'eccezione durante la chiamata: ' + str(e)}
    scritture_annullate = _ripristina(cartella, prima)
    dati = primo_json(uscita)
    if dati is None:
        return {'esito': 'non-fatto', 'motivo': 'risposta illeggibile: non è un JSON valido'}
    return {
        'esito': 'fatto',
        'ok': dati.get('ok', False),
        'difetti': dati.get('difetti', []),
        'scritture_annullate': scritture_annullate
    }


def ricercatore(compito, cartella, lancia):
    """Ricercatore: una sola chiamata che cerca nella KB e sul web e salva la sintesi; non scrive file."""
    prima = _istantanea(cartella)
    prompt = ('Compito: ' + compito['compito'] +
              '\\n\\nCerca prima nella KB, poi usa la skill web, e salva la sintesi nella KB con kb_salva.')
    try:
        codice, uscita = lancia(prompt, cartella)
    except Exception as e:
        _ripristina(cartella, prima)
        return {'esito': 'non-fatto', 'motivo': 'eccezione durante la ricerca: ' + str(e)}
    scritture_annullate = _ripristina(cartella, prima)
    if codice != 0:
        return {'esito': 'non-fatto', 'motivo': 'codice di ritorno non zero: ' + str(codice)}
    return {'esito': 'fatto', 'testo': uscita, 'scritture_annullate': scritture_annullate}
'''
open(p, 'w', encoding='utf-8').write(t[:i] + nuovo)
EOF
  ```
  Verifica: `cd piani && timeout 120 python3 -m unittest test_ruoli_lettura test_ruoli test_orchestratore && cd .. && ! grep -q "_annulla_cambi\|_prima_stato" ciclo/ruoli.py`

- [x] 7. Orchestratore: casi mancanti
  File: `ciclo/orchestratore.py`
  Cosa fare: (a) la seconda richiesta al modello e' il prompt completo della prima piu' una riga «piano non valido: <motivo>; rispondi di nuovo con il JSON.»; (b) `_convalida_piano` non va mai in errore: `compito` e `verifica` devono essere stringhe non vuote, `file` una lista non vuota di stringhe relative, senza `\\`, senza componenti `..` (controllare `f.split('/')`); con risposta non `dict` motivo «il piano non è un oggetto»; (c) i compiti si eseguono in ordine e la correzione avviene subito quando un revisore restituisce `ok` falso: se prima non c'e' stato un programmatore → `aiuto` con i difetti nel motivo; altrimenti il programmatore rifà l'ultimo compito del programmatore con i difetti aggiunti al testo del compito; se questo esito non e' `fatto` → `aiuto`; poi lo stesso compito del revisore (lo stesso dict del piano) ripassa; se l'esito non e' `fatto` o `ok` e' ancora falso → `aiuto` con i difetti; altrimenti si prosegue con i compiti successivi; un secondo revisore con `ok` falso dopo la correzione gia' fatta → `aiuto`. `avvisa` riceve sempre la richiesta, e in caso di `aiuto` il motivo con i difetti.
  Verifica: `cd piani && timeout 120 python3 -m unittest test_orchestratore_casi test_orchestratore`
- [x] 8. `agente orchestratore` funzionante
  File: `bin/agente`
  Cosa fare: togliere l'opzione `--orchestratore` e far riconoscere `orchestratore` come primo argomento (`nome`): `agente orchestratore --cartella DIR [--json] "richiesta"`. Senza richiesta o senza `--cartella`: messaggio su stderr e uscita 2, senza traceback. In `_orchestratore`: niente `import sys` locale; `sys.path.insert(0, <radice repo>/ciclo)` e poi `import ruoli, orchestratore, esecuzione` (togliere gli `spec_from_file_location`); `Esecuzione(radice=os.environ.get('AGENTE_PROGETTI', '/srv/progetti'), esegui=[os.environ['AGENTE_ESEGUI']] se la variabile c'e', altrimenti ['sudo', '-n', '-u', 'esecutore', '/opt/ai-vm/libexec/esegui-passo'], modello='esecutore-pensiero')`; se `esecuzione.progetto(cartella)` solleva `ValueError`: messaggio su stderr e uscita 2. Agenti collegati: `'programmatore': lambda c, d: ruoli.programmatore(c, d, lancia=e.lancia, verifica_fn=e.verifica, lezioni=e.lezioni)`, `'revisore': lambda c, d: ruoli.revisore(c, d, e.lancia)`, `'ricercatore': lambda c, d: ruoli.ricercatore(c, d, e.lancia)`. `chiedi` restituisce l'uscita di `e.lancia(prompt + '\n\nRispondi solo con il JSON.', cartella)` (stringa vuota se il codice non e' 0). `avvisa` come ora (FIFO `orchestratore` se `/opt/ai-vm/lib/avviso.py` c'e', e stampa su stderr). Con `--json` stampa il resoconto in JSON su stdout, e nient'altro su stdout; uscita 0 se `fatto`, 1 altrimenti.
  Verifica: `timeout 200 python3 -m unittest tests/test_agente.py piani/test_agente_orchestratore.py`
- [x] 9.1 Copia dei quattro test nuovi in `tests/`
  File: `tests/test_risposta.py`, `tests/test_ruoli_lettura.py`, `tests/test_orchestratore_casi.py`, `tests/test_agente_orchestratore.py`
  Cosa fare: eseguire dalla radice del progetto il comando qui sotto, così com'è, e nient'altro. È una copia, non uno spostamento: i file in `piani/` restano dove sono e non si toccano (come già `piani/test_ruoli.py` e `piani/test_orchestratore.py`); toglierli conterebbe come «test tolti». I quattro file nuovi in `tests/` devono essere identici agli originali.
  Esegui:
  ```bash
cp piani/test_risposta.py piani/test_ruoli_lettura.py piani/test_orchestratore_casi.py piani/test_agente_orchestratore.py tests/
  ```
  Verifica: `for f in test_risposta test_ruoli_lettura test_orchestratore_casi test_agente_orchestratore; do cmp piani/$f.py tests/$f.py || exit 1; done && timeout 300 python3 -m unittest tests/test_risposta.py tests/test_ruoli_lettura.py tests/test_orchestratore_casi.py tests/test_agente_orchestratore.py tests/test_ruoli.py tests/test_orchestratore.py tests/test_agente.py`
