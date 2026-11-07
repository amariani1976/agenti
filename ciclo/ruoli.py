"""Ruoli: programmatore usa il ciclo, revisore risponde in JSON e non scrive nulla."""
import os
import sys

from ciclo import esegui, _diff, _git, _leggi, _sporchi, _scrivi

# Importa primo_json da risposta.py
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import risposta
primo_json = risposta.primo_json


def _elenco(cartella):
    """Nomi relativi dei file tracciati e non tracciati (non ignorati), anche in sottocartelle."""
    nomi = set()
    for argomenti in (('ls-files', '-z'), ('ls-files', '-z', '--others', '--exclude-standard')):
        codice, uscita = _git(cartella, *argomenti)
        if codice == 0:
            nomi.update(n for n in uscita.split('\0') if n)
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


def programmatore(compito, cartella, esegui=esegui, **k):
    """Programmatore: affida il compito al ciclo.
    
    Chama esegui(compito['compito'], cartella, compito['verifica'], compito['file'], **k).
    Restituisce il risultato di esegui.
    """
    return esegui(
        compito['compito'],
        cartella,
        compito['verifica'],
        compito['file'],
        **k
    )


def _elenco_funzioni(cartella):
    """Elenco di funzioni e classi esistenti (max 200 righe) trovate con git grep."""
    import subprocess
    risultato = []
    try:
        stdout, _ = subprocess.Popen(
            ['git', '-C', cartella, 'grep', '-n',
             '^(def |class |export function|export const|export class)'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        ).communicate()
        for riga in stdout.decode('utf-8').split('\n'):
            if riga and len(risultato) < 200:
                risultato.append(riga)
    except Exception:
        pass
    return '\n'.join(risultato[:200])


def _aggiungi_difetti(difetti, nuovi):
    """Aggiunge nuovi difetti senza duplicati."""
    unione = list(difetti) if difetti else []
    if nuovi:
        for d in nuovi:
            if d not in unione:
                unione.append(d)
    return unione


def _aggiungi_richieste_non_fatte(difetti, richieste):
    """Aggiunge le richieste non fatte come difetti (senza duplicati)."""
    unione = list(difetti) if difetti else []
    if richieste:
        for r in richieste:
            if not r.get('fatta', True):
                testo = 'richiesta non fatta: ' + r.get('richiesta', '')
                if testo not in unione:
                    unione.append(testo)
    return unione


def revisore(compito, cartella, lancia):
    """Revisore: chiede un giudizio in JSON e annulla ogni scrittura fatta durante la chiamata.
    
    Chama lancia tre volte con prompt diversi (richieste, errori runtime, cambi oltre il richiesto),
    ripristinando la cartella dopo ciascuna.
    ok è vero solo se ogni lettura leggibile ha ok vero e nessuna richiesta con fatta falso.
    difetti è l'unione (senza duplicati) dei difetti e delle richieste non fatte.
    """
    prima = _istantanea(cartella)
    diff = _diff(cartella, sorted(_sporchi(cartella)))
    
    # Prompt comune: compito, diff, regole di scrittura, funzioni esistenti, forma del JSON
    prompt_base = 'Compito: ' + compito['compito']
    if diff:
        prompt_base += '\n\nDiff della cartella:\n' + diff
    prompt_base += '\n\nRegole di scrittura (segnala come difetti):'
    prompt_base += '\n- Funzioni e classi nelle librerie vanno richiamate dove servono, non copiate'
    prompt_base += '\n- Si riusa ciò che esiste invece di copiarlo'
    prompt_base += '\n- Nessun codice duplicato'
    prompt_base += '\n- Una funzione fa una cosa sola'
    prompt_base += '\n\nFunzioni e classi esistenti nel progetto:'
    prompt_base += '\n' + _elenco_funzioni(cartella)
    prompt_base += '\n\nElenca le richieste del compito una per una e rispondi SOLO con un JSON:'
    prompt_base += ' {"richieste": [{"richiesta": testo, "fatta": bool}], "ok": bool, "difetti": [stringhe]}'
    prompt_base += ' ok è vero solo se tutte le richieste sono fatte e non ci sono difetti.'
    
    # Tre letture con compiti diversi
    letture = []
    compiti = [
        'Controlla che il compito sia fatto tutto: elenca le richieste una per una e di\' per ciascuna se il diff la soddisfa.',
        'Cerca gli errori che si vedono solo quando il codice gira: metodi o attributi che non esistono sugli oggetti usati, file o flussi non chiusi, casi limite (vuoto, assente, errore), eccezioni non gestite.',
        'Cerca i cambi oltre quello che il compito chiede: righe riscritte, traduzioni, commenti o nomi cambiati senza che il compito lo chieda; se il compito diceva di eseguire un comando, controlla che il risultato sia quello del comando.'
    ]
    
    for compito_lettura in compiti:
        prompt = prompt_base + '\n\nCompito lettura: ' + compito_lettura
        try:
            codice, uscita = lancia(prompt, cartella)
        except Exception as e:
            _ripristina(cartella, prima)
            return {'esito': 'non-fatto', 'motivo': 'eccezione durante la chiamata: ' + str(e)}
        scritture_annullate = _ripristina(cartella, prima)
        dati = primo_json(uscita)
        if dati is None:
            letture.append(None)
        else:
            letture.append({'ok': dati.get('ok', False), 'difetti': dati.get('difetti', []),
                           'richieste': dati.get('richieste', []), 'scritture_annullate': scritture_annullate})
    
    # Filtra le letture leggibili
    letture_leggibili = [l for l in letture if l is not None]
    if not letture_leggibili:
        return {'esito': 'non-fatto', 'motivo': 'tutte le risposte illeggibili'}
    
    # ok è vero solo se ogni lettura leggibile ha ok vero e tutte le richieste hanno fatta vero
    ok = True
    tutte_richieste = []
    tutti_difetti = []
    for l in letture_leggibili:
        if not l['ok']:
            ok = False
        tutte_richieste.extend(l['richieste'])
        tutti_difetti = _aggiungi_difetti(tutti_difetti, l['difetti'])
    # Aggiungi richieste non fatte come difetti (evitando duplicati)
    for r in tutte_richieste:
        if not r.get('fatta', True):
            testo = 'richiesta non fatta: ' + r.get('richiesta', '')
            # Evita duplicati: non aggiungere se c'è già un difetto che la contiene
            if not any(r.get('richiesta', '') in d for d in tutti_difetti):
                tutti_difetti.append(testo)
            # Se c'è una richiesta non fatta, ok diventa false
            if not ok:
                pass  # ok è già false
            else:
                ok = False
    
    # Unione delle scritture annullate (dall'ultima lettura leggibile)
    scritture_annullate = letture_leggibili[-1]['scritture_annullate']
    
    return {
        'esito': 'fatto',
        'ok': ok,
        'difetti': tutti_difetti,
        'scritture_annullate': scritture_annullate
    }


def ricercatore(compito, cartella, lancia):
    """Ricercatore: una sola chiamata che cerca nella KB e sul web e salva la sintesi; non scrive file."""
    prima = _istantanea(cartella)
    prompt = ('Compito: ' + compito['compito'] +
              '\n\nCerca prima nella KB, poi usa la skill web, e salva la sintesi nella KB con kb_salva.')
    try:
        codice, uscita = lancia(prompt, cartella)
    except Exception as e:
        _ripristina(cartella, prima)
        return {'esito': 'non-fatto', 'motivo': 'eccezione durante la ricerca: ' + str(e)}
    scritture_annullate = _ripristina(cartella, prima)
    if codice != 0:
        return {'esito': 'non-fatto', 'motivo': 'codice di ritorno non zero: ' + str(codice)}
    return {'esito': 'fatto', 'testo': uscita, 'scritture_annullate': scritture_annullate}
