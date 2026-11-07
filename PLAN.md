---
stato: in-esecuzione
ramo: ai/agente-ciclo
modello: esecutore
verifica_globale: timeout 300 sh -c 'python3 -m unittest tests/test_agente.py tests/test_coda.py && python3 -m unittest tests/test_misura.py'
accettazione: timeout 200 python3 -m unittest tests/test_ciclo.py tests/test_esecuzione.py
spezzati: 1
aiuti: 2
---
# Piano: un agente unico che usa il modello locale nel modo migliore

## Contesto
Hermes e Claude devono poter affidare un compito al modello locale con lo stesso metodo che fa funzionare il runner dei piani: comando di verifica che deve passare, al massimo 3 tentativi con l'errore del tentativo prima, perimetro dei file con annullamento di ciò che esce, lezioni dalla KB, esito chiaro. Agente e verifica passano da `esegui-passo` (utente `esecutore`, rete solo locale, guardiano dei comandi appesi). I test sono già pronti e non si modificano: sono il contratto. Python 3.6, sola libreria standard, niente f-string nei file nuovi. Ogni comando con `timeout`. Non usare git per fare commit: il ciclo usa git solo per leggere e ripristinare.

## Passi
- [x] 1.1 Il ciclo, parte 1: funzioni di appoggio
  File: `ciclo/ciclo.py`
  Nota: il lavoro dei tentativi precedenti era giusto; falliva la verifica generale per un difetto dei test (corretta nel piano). Rifai il passo così com'è, senza toccare altri file.
  Cosa fare: file nuovo. Crealo con ESATTAMENTE questo comando (copialo così com'è, non cambiare il testo):
  ```sh
  mkdir -p ciclo && cat > ciclo/ciclo.py <<'FINE_CICLO'
"""Ciclo dell'agente: il metodo del runner per un compito solo (verifica, tentativi, perimetro, lezioni)."""
import os
import subprocess

MAX_USCITA = 3000
MAX_PROMPT = 20000


def _git(cartella, *argomenti):
    """Esegue git nella cartella; restituisce (codice, uscita)."""
    r = subprocess.run(['git', '-C', cartella] + list(argomenti), stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, universal_newlines=True, timeout=60)
    return r.returncode, r.stdout


def _leggi(cartella, nome):
    """Contenuto del file in byte, None se non esiste."""
    percorso = os.path.join(cartella, nome)
    if not os.path.isfile(percorso):
        return None
    with open(percorso, 'rb') as f:
        return f.read()


def _scrivi(cartella, nome, contenuto):
    """Riporta il file al contenuto dato; None vuol dire cancellarlo."""
    percorso = os.path.join(cartella, nome)
    if contenuto is None:
        if os.path.isfile(percorso):
            os.remove(percorso)
        return
    cartella_file = os.path.dirname(percorso)
    if not os.path.isdir(cartella_file):
        os.makedirs(cartella_file)
    with open(percorso, 'wb') as f:
        f.write(contenuto)


def _sporchi(cartella):
    """Insieme dei file modificati, cancellati o nuovi secondo git status."""
    codice, uscita = _git(cartella, 'status', '--porcelain', '-z', '--untracked-files=all')
    voci = uscita.split('\0')
    nomi = set()
    i = 0
    while i < len(voci):
        voce = voci[i]
        if voce:
            nomi.add(voce[3:])
            if voce[0] in 'RC':
                i += 1
        i += 1
    return nomi


def _ripristina_pulito(cartella, nome):
    """Riporta un file che era pulito allo stato di HEAD (lo cancella se HEAD non lo ha)."""
    codice, uscita = _git(cartella, 'checkout', '-q', 'HEAD', '--', nome)
    if codice != 0:
        _scrivi(cartella, nome, None)


def _diff(cartella, file):
    """Diff dei file del perimetro rispetto a HEAD, compresi i file nuovi."""
    parti = []
    for nome in file:
        codice, tracciato = _git(cartella, 'ls-files', '--', nome)
        if tracciato.strip():
            codice, uscita = _git(cartella, 'diff', 'HEAD', '--', nome)
        elif os.path.isfile(os.path.join(cartella, nome)):
            codice, uscita = _git(cartella, 'diff', '--no-index', '--', '/dev/null', nome)
        else:
            uscita = ''
        if uscita:
            parti.append(uscita)
    return ''.join(parti)


def _prompt(compito, file, verifica, lezioni, errore, fuori):
    """Prompt per l'agente: compito, perimetro, verifica, lezioni ed errore del tentativo prima."""
    parti = ['Compito: ' + compito,
             'File che puoi modificare (solo questi): ' + ', '.join(file),
             'Verifica che deve passare: ' + verifica]
    if lezioni:
        parti.append('Lezioni dalla KB:\n' + '\n'.join('- ' + l for l in lezioni))
    if fuori:
        parti.append('Il tentativo precedente ha toccato file fuori dal perimetro (annullati): ' + ', '.join(fuori))
    if errore:
        parti.append('Errore della verifica nel tentativo precedente:\n' + errore)
    return '\n\n'.join(parti)[:MAX_PROMPT]
FINE_CICLO
  ```
  Verifica: `timeout 60 python3 -c "import sys; sys.path.insert(0, 'ciclo'); import ciclo; assert ciclo.MAX_USCITA == 3000 and ciclo.MAX_PROMPT == 20000; [getattr(ciclo, n) for n in ('_git', '_leggi', '_scrivi', '_sporchi', '_ripristina_pulito', '_diff', '_prompt')]; assert 'Regola' in ciclo._prompt('c', ['a.py'], 'v', ['Regola'], '', [])"`

- [x] 1.2 Il ciclo, parte 2: controllo dell'ingresso ed `esegui`
  File: `ciclo/ciclo.py`
  Cosa fare: aggiungi in FONDO al file (con `>>`, non sovrascrivere) ESATTAMENTE questo testo, con questo comando:
  ```sh
  cat >> ciclo/ciclo.py <<'FINE_CICLO'


def _controlla(cartella, verifica, file):
    """Errori d'ingresso: ValueError se la cartella non e' la radice di un repository git, il perimetro e'
    vuoto o esce dalla cartella, la verifica e' vuota."""
    if not os.path.isdir(cartella):
        raise ValueError('cartella inesistente: ' + cartella)
    codice, radice = _git(cartella, 'rev-parse', '--show-toplevel')
    if codice != 0 or os.path.realpath(radice.strip()) != os.path.realpath(cartella):
        raise ValueError('non e\' la radice di un repository git: ' + cartella)
    if not verifica or not verifica.strip():
        raise ValueError('verifica vuota')
    if not file:
        raise ValueError('nessun file nel perimetro')
    for nome in file:
        pulito = os.path.normpath(nome) if nome else ''
        if not pulito or os.path.isabs(pulito) or pulito == '..' or pulito.startswith('..' + os.sep):
            raise ValueError('file fuori dal progetto: ' + repr(nome))


def esegui(compito, cartella, verifica, file, tentativi=3, lancia=None, verifica_fn=None, lezioni=None):
    """Affida il compito all'agente fino a `tentativi` volte.

    lancia(prompt, cartella) -> (codice, uscita); verifica_fn(comando, cartella) -> (codice, uscita);
    lezioni(compito) -> lista di testi. Ogni modifica fuori da `file` viene annullata; se nessun tentativo
    riesce i file del perimetro tornano come all'inizio. Restituisce
    {'esito': 'fatto'|'non-fatto', 'tentativi': [...], 'file': file, 'diff': testo}."""
    _controlla(cartella, verifica, file)
    file = [os.path.normpath(nome) for nome in file]
    perimetro = set(file)
    prima = {}
    for nome in _sporchi(cartella):
        if nome not in perimetro:
            prima[nome] = _leggi(cartella, nome)
    inizio = {}
    for nome in file:
        inizio[nome] = _leggi(cartella, nome)
    testi = list(lezioni(compito) or []) if lezioni else []
    risultato = {'esito': 'non-fatto', 'tentativi': [], 'file': file, 'diff': ''}
    errore = ''
    fuori = []
    for numero in range(1, tentativi + 1):
        prompt = _prompt(compito, file, verifica, testi, errore, fuori)
        codice_agente, uscita_agente = lancia(prompt, cartella)
        fuori = []
        for nome in sorted(_sporchi(cartella) | set(prima)):
            if nome in perimetro:
                continue
            if nome in prima:
                if _leggi(cartella, nome) != prima[nome]:
                    fuori.append(nome)
                    _scrivi(cartella, nome, prima[nome])
            else:
                fuori.append(nome)
                _ripristina_pulito(cartella, nome)
        codice, uscita = verifica_fn(verifica, cartella)
        uscita = (uscita or '')[-MAX_USCITA:]
        risultato['tentativi'].append({'numero': numero, 'agente': codice_agente, 'verifica': codice,
                                       'uscita': uscita, 'fuori_perimetro': fuori})
        if codice == 0 and not fuori:
            risultato['esito'] = 'fatto'
            risultato['diff'] = _diff(cartella, file)
            return risultato
        errore = uscita if codice != 0 else ''
    for nome in file:
        _scrivi(cartella, nome, inizio[nome])
    return risultato
FINE_CICLO
  ```
  Verifica: `timeout 120 python3 -m unittest tests.test_ciclo`

- [x] 2. L'esecuzione vera
  File: `ciclo/esecuzione.py`
  Cosa fare: classe `Esecuzione(radice='/srv/progetti', esegui=['sudo', '-n', '-u', 'esecutore', '/opt/ai-vm/libexec/esegui-passo'], modello='esecutore-pensiero', tempo=1900)`. `progetto(cartella)`: il nome se `realpath(cartella)` è esattamente `radice/<nome>`, altrimenti `ValueError`. `lancia(prompt, cartella)`: esegue `esegui + ['agente', nome, modello]` con il prompt su stdin; restituisce `(codice, uscita)`. `verifica(comando, cartella)`: `esegui + ['verifica', nome]` con il comando su stdin. `lezioni(compito)`: `kb cerca` con le prime parole del compito, al massimo 1500 caratteri, lista vuota se `kb` manca o fallisce. Ogni chiamata con `timeout=self.tempo`; un tempo scaduto diventa `(124, 'tempo massimo superato')`.
  Verifica: `timeout 120 python3 -m unittest tests/test_esecuzione.py`
- [x] 3. Il comando `agente` col ciclo
  File: `bin/agente`
  Cosa fare: nuove opzioni `--file a,b`, `--verifica "comando"`, `--tentativi N` (1-5, predefinito 3), `--json`. Con `--verifica` il comando usa `ciclo.esegui` con `Esecuzione` (import da `../ciclo`), stampa l'esito (in JSON con `--json`, altrimenti esito, tentativi e file) ed esce con 0 se `fatto`, 1 se `non-fatto`, 2 per errori d'ingresso; senza `--verifica` resta tutto com'è oggi. Aggiungi le opzioni all'aiuto.
  Verifica: `timeout 120 python3 -m unittest tests/test_agente.py && python3 bin/agente --aiuto 2>&1 | grep -q -- "--verifica" || python3 bin/agente 2>&1 | grep -q -- "--verifica"`
