"""Ciclo dell'agente: il metodo del runner per un compito solo (verifica, tentativi, perimetro, lezioni)."""
import os
import subprocess
import time

MAX_USCITA = 3000
MAX_PROMPT = 20000


def _git(cartella, *argomenti):
    """Esegue git nella cartella; restituisce (codice, uscita)."""
    try:
        r = subprocess.run(['git', '-C', cartella] + list(argomenti), stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, universal_newlines=True, timeout=60)
        return r.returncode, r.stdout
    except (FileNotFoundError, OSError) as e:
        return -1, str(e)


def _leggi(cartella, nome):
    """Contenuto del file in byte, None se non esiste."""
    percorso = os.path.join(cartella, nome)
    if not os.path.isfile(percorso):
        return None
    with open(percorso, 'rb') as f:
        return f.read()


def _scrivi(cartella, nome, contenuto):
    """Riporta il file al contenuto dato; None vuol dire cancellarlo."""
    # Prevenire path traversal: il nome non deve contenere .. o /
    if '..' in nome or '/' in nome or '\\' in nome:
        return
    percorso = os.path.join(cartella, nome)
    if contenuto is None:
        if os.path.isfile(percorso):
            os.remove(percorso)
        return
    cartella_file = os.path.dirname(percorso)
    if not os.path.isdir(cartella_file):
        os.makedirs(cartella_file)
    # Gestire stringa o bytes
    if isinstance(contenuto, str):
        contenuto = contenuto.encode('utf-8')
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
            # Per rename (R) o copy (C), il formato è "R old -> new" o "C old -> new"
            if voce[0] in 'RC':
                # Estrai il nuovo nome (dopo " -> ")
                freccia = ' -> '
                idx = voce.find(freccia)
                if idx != -1:
                    nuovo_nome = voce[idx + len(freccia):]
                    nomi.add(nuovo_nome)
                i += 2
            else:
                nomi.add(voce[3:])
                i += 1
        else:
            i += 1
    return nomi


def _ripristina_pulito(cartella, nome):
    """Riporta un file che era pulito allo stato di HEAD (lo cancella se HEAD non lo ha)."""
    # Controlla se il file esiste in HEAD
    codice, tracciato = _git(cartella, 'ls-files', '--', nome)
    if tracciato.strip():
        # Esiste in HEAD: ripristina con checkout
        _git(cartella, 'checkout', '-q', 'HEAD', '--', nome)
    else:
        # Non esiste in HEAD: cancella localmente se esiste
        _scrivi(cartella, nome, None)


def _diff(cartella, file):
    """Diff dei file del perimetro rispetto a HEAD, inclusi i file nuovi."""
    parti = []
    for nome in file:
        codice, tracciato = _git(cartella, 'ls-files', '--', nome)
        if tracciato.strip():
            codice, uscita = _git(cartella, 'diff', 'HEAD', '--', nome)
        elif os.path.isfile(os.path.join(cartella, nome)):
            # Usa /dev/null che funziona su tutti i sistemi (su Windows è un file speciale)
            codice, uscita = _git(cartella, 'diff', '--no-index', '--', '/dev/null', nome)
        else:
            uscita = ''
        if uscita:
            parti.append(uscita)
    return ''.join(parti)


def _prompt(compito, file, verifica, lezioni, errore, fuori, revisione_esito=None):
    """Prompt per l'agente: compito, perimetro, verifica, lezioni ed errore del tentativo prima."""
    parti = ['Compito: ' + compito,
             'File che puoi modificare (solo questi): ' + ', '.join(file),
             'Verifica che deve passare: ' + verifica,
             'Cambia solo quello che il compito chiede: non riscrivere codice che funziona, non aggiungere altro. Se il compito dice di eseguire un comando, eseguilo invece di modificare il file a mano.']
    if lezioni:
        parti.append('Lezioni dalla KB:\n' + '\n'.join('- ' + l for l in lezioni))
    if fuori:
        parti.append('Il tentativo precedente ha toccato file fuori dal perimetro (annullati): ' + ', '.join(fuori))
    if errore:
        parti.append('Errore della verifica nel tentativo precedente:\n' + errore)
    if revisione_esito and 'difetti' in revisione_esito and revisione_esito['difetti']:
        parti.append('Difetti rilevati dalla revisione:\n' + '\n'.join('- ' + d for d in revisione_esito['difetti']))
    return '\n\n'.join(parti)[:MAX_PROMPT]


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
        if nome is None:
            raise ValueError('elemento None nel perimetro')
        pulito = os.path.normpath(nome)
        if pulito == '' or pulito == '.' or os.path.isabs(pulito) or pulito == '..' or pulito.startswith('..' + os.sep):
            raise ValueError('file fuori dal progetto: ' + repr(nome))


def esegui(compito, cartella, verifica, file, tentativi=3, lancia=None, verifica_fn=None, lezioni=None,
           verifica_globale=None, revisione=None, tempo_max=1800, orologio=time.time):
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
    revisione_esito = None
    inizio_tentativi = orologio()
    for numero in range(1, tentativi + 1):
        if orologio() - inizio_tentativi >= tempo_max:
            risultato['motivo'] = 'tempo massimo del compito superato'
            for nome in file:
                _scrivi(cartella, nome, inizio[nome])
            return risultato
        prompt = _prompt(compito, file, verifica, testi, errore, fuori, revisione_esito)
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
            if verifica_globale:
                codice_globale, uscita_globale = verifica_fn(verifica_globale, cartella)
                uscita_globale = (uscita_globale or '')[-MAX_USCITA:]
                risultato['tentativi'][-1]['verifica_globale'] = codice_globale
                risultato['tentativi'][-1]['uscita_globale'] = uscita_globale
                if codice_globale != 0:
                    errore = 'verifica globale:\n' + uscita_globale
                    revisione_esito = None
                    continue
            if revisione:
                revisione_esito = revisione(compito, cartella)
                if isinstance(revisione_esito, dict) and 'ok' in revisione_esito:
                    if revisione_esito['ok']:
                        risultato['esito'] = 'fatto'
                        risultato['diff'] = _diff(cartella, file)
                        risultato['revisione'] = revisione_esito
                        return risultato
                    else:
                        errore = 'revisione:\n' + '\n'.join(revisione_esito.get('difetti', []))
                        revisione_esito = revisione_esito
                        continue
                else:
                    # Revisione senza esito ok: non ferma, ma si continua
                    risultato['revisione'] = revisione_esito
                    revisione_esito = revisione_esito
                    # Non si ritenta, si considera fatto
                    risultato['esito'] = 'fatto'
                    risultato['diff'] = _diff(cartella, file)
                    for nome in file:
                        _scrivi(cartella, nome, inizio[nome])
                    return risultato
            risultato['esito'] = 'fatto'
            risultato['diff'] = _diff(cartella, file)
            return risultato
        errore = uscita if codice != 0 else ''
    if risultato['esito'] == 'non-fatto':
        if errore:
            risultato['motivo'] = errore
        elif revisione_esito and isinstance(revisione_esito, dict) and 'difetti' in revisione_esito:
            risultato['motivo'] = '\n'.join(revisione_esito['difetti'])
    for nome in file:
        _scrivi(cartella, nome, inizio[nome])
    return risultato
