---
stato: completato
ramo: ai/agente-ciclo
modello: esecutore
verifica_globale: timeout 300 python3 -m unittest tests/test_agente.py tests/test_ciclo.py tests/test_esecuzione.py tests/test_ruoli.py tests/test_orchestratore.py tests/test_agente_catena.py
accettazione: cd piani && timeout 200 python3 -m unittest test_ciclo_qualita
correzioni_semafori: 1
aiuti: 1
collaudi: 1
collaudo: superato
---
# Piano: il ciclo consegna solo lavoro fatto bene

## Contesto
Il banco ha mostrato che l'agente si ferma appena passa la verifica del passo: in metà dei casi la verifica generale si rompe, il compito è fatto a metà o l'agente riscrive più del richiesto. Il ciclo deve controllare anche la verifica generale e passare dal revisore prima di consegnare. Il test `piani/test_ciclo_qualita.py` è già pronto e non si modifica. Python 3.6, sola libreria standard, niente f-string. Ogni comando con `timeout`.

## Passi
- [x] 1. Verifica generale, revisore e tempo massimo nel ciclo
  File: `ciclo/ciclo.py`
  Cosa fare: `esegui` riceve in più `verifica_globale=None`, `revisione=None`, `tempo_max=1800`, `orologio=time.time`. Dopo che la verifica del passo passa e nulla è fuori perimetro: se c'è `verifica_globale`, la esegue con `verifica_fn`; se fallisce, il tentativo fallisce e la sua uscita va nel prompt successivo. Poi, se c'è `revisione`, chiama `revisione(compito, cartella)`: con `ok` falso il tentativo fallisce e i `difetti` vanno nel prompt successivo; una revisione senza `ok` (risposta illeggibile) non ferma e il suo esito si mette in `risultato['revisione']`. Prima di ogni tentativo, se `orologio() - inizio >= tempo_max`, ci si ferma. A esito `non-fatto` il risultato ha `motivo` (ultimo errore, difetti o «tempo massimo del compito superato»). Nel prompt aggiungi: «Cambia solo quello che il compito chiede: non riscrivere codice che funziona, non aggiungere altro. Se il compito dice di eseguire un comando, eseguilo invece di modificare il file a mano.» Il resto della funzione non cambia.
  Verifica: `cd piani && timeout 200 python3 -m unittest test_ciclo_qualita && cd .. && timeout 200 python3 -m unittest tests/test_ciclo.py`
- [x] 2. Opzioni del comando
  File: `bin/agente`
  Cosa fare: nuove opzioni `--verifica-globale "comando"` e `--senza-revisione`. Col ciclo, passa `verifica_globale` e, se non c'è `--senza-revisione`, `revisione=lambda compito, cartella: ruoli.revisore({'agente': 'revisore', 'compito': compito}, cartella, e.lancia)` con lo stesso `Esecuzione` del programmatore. Nient'altro cambia.
  Verifica: `timeout 200 python3 -m unittest tests/test_agente_catena.py tests/test_agente.py && grep -q -- "--verifica-globale" bin/agente`
- [x] 3. Il test al suo posto
  File: `tests/test_ciclo_qualita.py`
  Esegui:
  ```bash
mv piani/test_ciclo_qualita.py tests/
  ```
  Verifica: `test -f tests/test_ciclo_qualita.py && timeout 200 python3 -m unittest tests/test_ciclo_qualita.py`

- [x] 4.1 Revisore e verifica generale nel percorso giusto di `bin/agente`
  File: `bin/agente`
  Cosa fare: il passo 2 ha messo `revisione_fn` dentro `_orchestratore`, dove `args` non esiste (NameError: rompe
  `tests/test_agente_orchestratore.py`), e non ha collegato nulla a `ciclo.esegui`. Esegui lo script qui sotto
  così com'è, dalla cartella del progetto: toglie il collegamento sbagliato da `_orchestratore` e passa
  `verifica_globale` e `revisione` a `ciclo.esegui` in `_esegui_con_verifica`. Non modificare il file a mano.
  Esegui:
  ```bash
python3 - <<'EOF'
import io
p = 'bin/agente'
s = io.open(p, encoding='utf-8').read()
vecchio = """    # Se non c'è --senza-revisione, aggiungi la funzione revisione con lo stesso Esecuzione del programmatore
    revisione_fn = None
    if not args.senza_revisione:
        revisione_fn = lambda compito, cartella: ruoli.revisore({'agente': 'revisore', 'compito': compito}, cartella, e.lancia)
    
"""
assert s.count(vecchio) == 1
s = s.replace(vecchio, '')
assert s.count("        revisione=revisione_fn,\n        max_compiti=6\n") == 1
s = s.replace("        revisione=revisione_fn,\n        max_compiti=6\n", "        max_compiti=6\n")
a = "def _esegui_con_verifica(file_arg, verifica_arg, tentativi_arg, nome, compito, cartella, radice, pi):"
assert s.count(a) == 1
s = s.replace(a, "def _esegui_con_verifica(file_arg, verifica_arg, tentativi_arg, nome, compito, cartella, radice, pi,\n                         verifica_globale=None, senza_revisione=False):")
b = """    # Esegui ciclo.esegui con tentativi da 1 a 5
"""
assert s.count(b) == 1
s = s.replace(b, """    # Revisore con lo stesso Esecuzione del programmatore, salvo --senza-revisione
    revisione_fn = None
    if not senza_revisione:
        sys.path.insert(0, moduli_path)
        import ruoli
        revisione_fn = lambda c, d: ruoli.revisore({'agente': 'revisore', 'compito': c}, d, esecuzione.lancia)

""" + b)
c = """        lezioni=esecuzione.lezioni
    )
"""
assert s.count(c) == 1
s = s.replace(c, """        lezioni=esecuzione.lezioni,
        verifica_globale=verifica_globale,
        revisione=revisione_fn
    )
""")
d = """            os.environ.get('AGENTE_PI', DEFAULT_PI)
        )
"""
assert s.count(d) == 1
s = s.replace(d, """            os.environ.get('AGENTE_PI', DEFAULT_PI),
            verifica_globale=args.verifica_globale,
            senza_revisione=args.senza_revisione
        )
""")
io.open(p, 'w', encoding='utf-8').write(s)
print('ok')
EOF
  ```
  Verifica: `timeout 200 python3 -m unittest tests/test_agente_orchestratore.py tests/test_agente_catena.py tests/test_agente.py tests/test_agente_collegamento.py && grep -q "verifica_globale=args.verifica_globale" bin/agente && ! grep -q "if not args.senza_revisione" bin/agente`
- [x] 4.2 Semafori di nuovo non rossi
  File: nessuno (solo controllo)
  Cosa fare: esegui la verifica; non modificare file. Se fallisce, fermati e riporta l'uscita.
  Verifica: `timeout 280 /opt/ai-vm/bin/semafori --base 1b7d0fc49af6; test $? -lt 2`
