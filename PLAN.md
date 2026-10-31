---
stato: in-esecuzione
ramo: ai/agenti-base
modello: esecutore
collaudi: 1
aiuti: 1
---
# Piano: parte 1 — comando `agente`, profilo «programmatore» e KB di base

## Contesto
Progetto `agenti` (leggi `CLAUDE.md` e `docs/PROGETTO.md`). Questa parte costruisce, senza dipendere dal modello scelto:
- `kb/kb.py`: nucleo della knowledge base in Markdown (`docs/PROGETTO.md` §6): salvataggio in `inbox/` con rifiuto
  dei segreti, lettura sicura, indice SQLite FTS5 e ricerca (servizio, MCP e vettori arrivano nelle parti 2–3);
- `bin/agente`: avvia pi con il profilo `profili/<nome>/` (solo le sue skill: `--no-skills` più un `--skill` per
  ciascuna, solo i suoi strumenti con `--tools`, variabile `PI_CODING_AGENT_DIR`);
- il profilo `programmatore` con la skill `kb`.

Linguaggio: Python 3 della VM, solo libreria standard. Test con `unittest`; i file di test sono già scritti nei passi e
sono la specifica: si implementa finché passano. Comando dei test: `python3 -m unittest tests/NOME.py` (niente pytest).
Commenti e messaggi in italiano. Non usare git.

## Passi

- [x] 1. Test della KB
  File: `tests/test_kb.py` (nuovo)
  Cosa fare: crea `tests/test_kb.py` con **esattamente** questo contenuto, senza cambiare nulla:
```
"""Test di kb/kb.py: salvataggio in inbox, lettura sicura, indice FTS5 e ricerca."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

QUI = os.path.dirname(os.path.abspath(__file__))
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(QUI, '..', 'kb'))
import kb  # noqa: E402


class Base(unittest.TestCase):
    def setUp(self):
        self.kb = tempfile.mkdtemp()
        self.db = os.path.join(tempfile.mkdtemp(), 'indice.db')
        os.makedirs(os.path.join(self.kb, 'progetti'))
        with open(os.path.join(self.kb, 'progetti', 'neteye.md'), 'w') as f:
            f.write('# NetEye\n\nIl server NetEye 10.0.0.118 si usa solo in verifica.\n')
        with open(os.path.join(self.kb, 'ricetta.md'), 'w') as f:
            f.write('Pasta al pomodoro con basilico.\n')

    def tearDown(self):
        shutil.rmtree(self.kb, ignore_errors=True)
        shutil.rmtree(os.path.dirname(self.db), ignore_errors=True)


class SalvaTest(Base):
    def test_slug(self):
        self.assertEqual(kb.slug('Prova: Ollama e GPU!'), 'prova-ollama-e-gpu')
        self.assertEqual(kb.slug('   '), 'nota')

    def test_salva_in_inbox_con_intestazione(self):
        rel = kb.salva(self.kb, 'programmatore', 'Esito del banco', 'Testo.\n', progetto='agenti', oggi='2026-10-31')
        self.assertEqual(rel, 'inbox/2026-10-31-esito-del-banco.md')
        testo = open(os.path.join(self.kb, rel)).read()
        self.assertTrue(testo.startswith('---\n'))
        self.assertIn('agente: programmatore\n', testo)
        self.assertIn('progetto: agenti\n', testo)
        self.assertIn('data: 2026-10-31\n', testo)
        self.assertIn('# Esito del banco\n', testo)
        self.assertTrue(testo.endswith('Testo.\n'))

    def test_non_sovrascrive(self):
        a = kb.salva(self.kb, 'x', 'Doppia', 'uno', oggi='2026-10-31')
        b = kb.salva(self.kb, 'x', 'Doppia', 'due', oggi='2026-10-31')
        self.assertEqual(b, 'inbox/2026-10-31-doppia-2.md')
        self.assertIn('uno', open(os.path.join(self.kb, a)).read())

    def test_rifiuta_segreti(self):
        for t in ('password: abc123', 'TOKEN=ghp_' + 'a' * 36, '-----BEGIN OPENSSH PRIVATE KEY-----'):
            with self.assertRaises(ValueError):
                kb.salva(self.kb, 'x', 'Segreto', t, oggi='2026-10-31')
        self.assertFalse(os.path.exists(os.path.join(self.kb, 'inbox')))


class LeggiTest(Base):
    def test_leggi(self):
        self.assertIn('10.0.0.118', kb.leggi(self.kb, 'progetti/neteye.md'))

    def test_fuori_dalla_kb(self):
        with self.assertRaises(ValueError):
            kb.leggi(self.kb, '../../etc/passwd')
        with self.assertRaises(ValueError):
            kb.leggi(self.kb, '/etc/passwd')


class IndiceTest(Base):
    def test_indicizza_e_cerca(self):
        self.assertEqual(kb.indicizza(self.kb, self.db), 2)
        r = kb.cerca(self.db, 'verifica')
        self.assertEqual([x['path'] for x in r], ['progetti/neteye.md'])
        self.assertEqual(r[0]['titolo'], 'NetEye')
        self.assertIn('verifica', r[0]['estratto'])

    def test_titolo_dal_nome_del_file(self):
        kb.indicizza(self.kb, self.db)
        self.assertEqual(kb.cerca(self.db, 'basilico')[0]['titolo'], 'ricetta')

    def test_ricostruisce_da_zero(self):
        kb.indicizza(self.kb, self.db)
        os.remove(os.path.join(self.kb, 'ricetta.md'))
        self.assertEqual(kb.indicizza(self.kb, self.db), 1)
        self.assertEqual(kb.cerca(self.db, 'basilico'), [])

    def test_ignora_git(self):
        os.makedirs(os.path.join(self.kb, '.git'))
        with open(os.path.join(self.kb, '.git', 'x.md'), 'w') as f:
            f.write('segreto')
        self.assertEqual(kb.indicizza(self.kb, self.db), 2)


class RigaDiComandoTest(Base):
    def test_cli(self):
        env = dict(os.environ, KB_DIR=self.kb, KB_DB=self.db, PYTHONDONTWRITEBYTECODE='1')
        prog = os.path.join(QUI, '..', 'kb', 'kb.py')
        run = lambda *a, **k: subprocess.run([sys.executable, prog] + list(a), env=env, stdout=subprocess.PIPE,
                                             stderr=subprocess.STDOUT, universal_newlines=True, **k)
        self.assertEqual(run('indicizza').returncode, 0)
        r = run('cerca', 'verifica')
        self.assertEqual(r.returncode, 0)
        self.assertIn('progetti/neteye.md', r.stdout)
        r = run('salva', '--agente', 'prova', '--titolo', 'Da riga di comando', input='corpo\n')
        self.assertEqual(r.returncode, 0)
        self.assertTrue(r.stdout.strip().startswith('inbox/'))
        self.assertEqual(run('leggi', '../fuori.md').returncode, 1)


if __name__ == '__main__':
    unittest.main()
```
  Verifica: `python3 -c "import ast; ast.parse(open('tests/test_kb.py').read())"`

- [x] 2. KB: `slug` e `salva`
  File: `kb/kb.py` (nuovo)
  Cosa fare: crea `kb/kb.py` (docstring in italiano) con `slug(titolo)` e `salva(kb, agente, titolo, testo, progetto=None, oggi=None)` come richiesto dalla classe `SalvaTest` di `tests/test_kb.py` (leggila: è la specifica). `oggi` predefinito: data di oggi in formato AAAA-MM-GG. Il file si crea con `open(..., 'x')`; se il nome esiste prova `-2`, `-3`…
  Prima di creare qualsiasi cosa, `salva` chiama `controlla_segreti(testo)`: costante `SEGRETI` (lista di regex
  compilate, senza distinzione di maiuscole) per `password\s*[:=]`, `(token|secret|api_?key)\s*[:=]`, `ghp_[A-Za-z0-9]{30,}`,
  `-----BEGIN [A-Z ]*PRIVATE KEY-----`; se una corrisponde, `ValueError('il testo sembra contenere un segreto')`.
  Verifica: `python3 -m unittest tests/test_kb.py -k SalvaTest`

- [x] 3. KB: `leggi`
  File: `kb/kb.py`
  Cosa fare: aggiungi `leggi(kb, nota)` come richiesto da `LeggiTest`: percorsi assoluti o che escono dalla KB (dopo `os.path.realpath`) danno `ValueError`.
  Verifica: `python3 -m unittest tests/test_kb.py -k LeggiTest`

- [x] 4. KB: `indicizza` e `cerca`
  File: `kb/kb.py`
  Cosa fare: aggiungi `indicizza(kb, db)` e `cerca(db, query, n=5)` come richiesto da `IndiceTest`: tabella FTS5 `note(path UNINDEXED, titolo, testo)` ricreata da zero a ogni indicizzazione; solo file `.md`; salta le cartelle che iniziano con `.`; titolo = prima riga `# …`, altrimenti nome del file senza `.md`; `cerca` restituisce dict `path`, `titolo`, `estratto` (usa `snippet()` di FTS5) in ordine di `rank`. Crea la cartella di `db` se manca.
  Verifica: `python3 -m unittest tests/test_kb.py -k IndiceTest`

- [x] 5. KB: riga di comando
  File: `kb/kb.py`
  Cosa fare: aggiungi `main()` con argparse e i comandi `indicizza`, `cerca QUERY [-n N]`, `leggi NOTA`, `salva --agente --titolo [--progetto]` (testo da stdin, stampa il percorso creato). `KB_DIR` predefinita `/srv/kb`, `KB_DB` predefinita `~/.cache/kb/indice.db`. `ValueError` → messaggio su stderr e uscita 1. In fondo `if __name__ == '__main__': sys.exit(main())`.
  Verifica: `python3 -m unittest tests/test_kb.py`

- [x] 6. Test del comando `agente`
  File: `tests/test_agente.py` (nuovo)
  Cosa fare: crea `tests/test_agente.py` con **esattamente** questo contenuto, senza cambiare nulla:
```
"""Test di bin/agente: profilo, strumenti, cartella di lavoro e variabile PI_CODING_AGENT_DIR."""
import importlib.machinery
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

QUI = os.path.dirname(os.path.abspath(__file__))
sys.dont_write_bytecode = True
_l = importlib.machinery.SourceFileLoader('agente', os.path.join(QUI, '..', 'bin', 'agente'))
A = importlib.util.module_from_spec(importlib.util.spec_from_loader('agente', _l))
_l.exec_module(A)


class AgenteTest(unittest.TestCase):
    def setUp(self):
        self.radice = tempfile.mkdtemp()
        p = os.path.join(self.radice, 'profili', 'prova')
        os.makedirs(p)
        with open(os.path.join(p, 'strumenti'), 'w') as f:
            f.write('read,bash\n')
        for s in ('kb', 'test'):
            os.makedirs(os.path.join(p, 'skills', s))
            open(os.path.join(p, 'skills', s, 'SKILL.md'), 'w').close()
        os.makedirs(os.path.join(p, 'skills', 'vuota'))

    def tearDown(self):
        shutil.rmtree(self.radice, ignore_errors=True)

    def test_comando(self):
        argv, env, cwd = A.comando('prova', 'fai X', '/tmp', self.radice, pi='/bin/pi')
        sk = os.path.join(self.radice, 'profili', 'prova', 'skills')
        self.assertEqual(argv, ['/bin/pi', '-p', '--no-session', '--no-skills',
                                '--skill', os.path.join(sk, 'kb'), '--skill', os.path.join(sk, 'test'),
                                '--tools', 'read,bash', 'fai X'])
        self.assertEqual(env, {'PI_CODING_AGENT_DIR': os.path.join(self.radice, 'profili', 'prova')})
        self.assertEqual(cwd, '/tmp')

    def test_profilo_inesistente(self):
        with self.assertRaises(ValueError):
            A.comando('manca', 'x', '/tmp', self.radice, pi='/bin/pi')

    def test_nome_non_valido(self):
        with self.assertRaises(ValueError):
            A.comando('../prova', 'x', '/tmp', self.radice, pi='/bin/pi')

    def test_esegue_pi_finto(self):
        finto = os.path.join(self.radice, 'pi-finto')
        with open(finto, 'w') as f:
            f.write('#!/bin/sh\necho "$PI_CODING_AGENT_DIR|$*|$(pwd)"\n')
        os.chmod(finto, 0o755)
        env = dict(os.environ, AGENTE_PI=finto, AGENTE_RADICE=self.radice)
        r = subprocess.run([sys.executable, os.path.join(QUI, '..', 'bin', 'agente'), 'prova', '--cartella', '/tmp', 'compito'],
                           env=env, stdout=subprocess.PIPE, universal_newlines=True)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout.strip(),
                         os.path.join(self.radice, 'profili', 'prova') + '|-p --no-session --no-skills --skill {0}/kb --skill {0}/test --tools read,bash compito|/tmp'.format(
                             os.path.join(self.radice, 'profili', 'prova', 'skills')))


if __name__ == '__main__':
    unittest.main()
```
  Verifica: `python3 -c "import ast; ast.parse(open('tests/test_agente.py').read())"`

- [x] 7. Comando `agente`
  File: `bin/agente` (nuovo, eseguibile)
  Cosa fare: crea `bin/agente` (Python 3, prima riga `#!/usr/bin/env python3`, `chmod 755`) con `comando(nome, compito, cartella, radice, pi)` → `(argv, env, cwd)` e `main()`, come richiesto da `tests/test_agente.py` (leggilo: è la specifica). Nome valido: `^[a-z][a-z0-9-]{0,40}$`. Le skill sono le sottocartelle di `profili/<nome>/skills/` che contengono `SKILL.md`, in ordine alfabetico. Riga di comando: `agente NOME [--cartella DIR] COMPITO...`; `AGENTE_PI` (predefinito `~/.local/bin/pi`) e `AGENTE_RADICE` (predefinita: cartella sopra `bin/`).
  Verifica: `test -x bin/agente && python3 -m unittest tests/test_agente.py`

- [x] 8. Profilo «programmatore» e skill `kb`
  File: `profili/programmatore/` (nuovi)
  Cosa fare: **non scrivere i file a mano.** Esegui soltanto, dalla radice del progetto, questo comando:
```
python3 - <<'EOF'
import os
for p, t in [
    ('profili/programmatore/AGENTS.md',
     '# Agente «programmatore»\n\nEsegui UN compito alla volta nella cartella di lavoro e fermati quando la verifica indicata passa.\n\n- Se il compito dà un comando o un contenuto già pronto, usalo esattamente così: non riscrivere i file a mano.\n- Non leggere per intero file grandi (oltre 300 righe): cerca con `grep -n` e leggi solo le righe che servono.\n- Modifica solo i file indicati; non creare file non richiesti; non usare git.\n- Se qualcosa è ambiguo o impossibile, fermati e spiega perché.\n- Alla fine rispondi in breve: file modificati ed esito della verifica.\n- Se non sai come fare qualcosa, prima cerca nella knowledge base con la skill `kb`; se trovi su internet ciò che ti serve, salvalo nella KB con `kb salva` (fonte, URL, sintesi tua).\n'),
    ('profili/programmatore/models.json',
     '{\n  "providers": {\n    "llamaswap": {\n      "baseUrl": "http://10.0.0.100:9292/v1",\n      "api": "openai-completions",\n      "apiKey": "locale",\n      "compat": { "supportsDeveloperRole": false, "supportsReasoningEffort": false },\n      "models": [{ "id": "programmatore", "contextWindow": 65536, "maxTokens": 8192 }]\n    }\n  }\n}\n'),
    ('profili/programmatore/settings.json',
     '{\n  "defaultProvider": "llamaswap",\n  "defaultModel": "programmatore",\n  "defaultThinkingLevel": "off"\n}\n'),
    ('profili/programmatore/strumenti',
     'read,write,edit,bash\n'),
    ('profili/programmatore/skills/kb/SKILL.md',
     '---\nname: kb\ndescription: Cerca, legge e salva note nella knowledge base personale (second brain) dell\'utente. Usala per recuperare decisioni, convenzioni e contesto già scritti, e per salvare il risultato di un lavoro.\n---\n\n# Knowledge base\n\nLa KB è una cartella di Markdown. Comando: `kb` (variabili `KB_DIR` e `KB_DB` già impostate).\n\n- Cercare: `kb cerca "parole chiave"` → elenco `percorso: titolo` con un estratto. Usa poche parole precise.\n- Leggere: `kb leggi percorso/della/nota.md`.\n- Salvare il proprio lavoro: `echo "testo" | kb salva --agente <nome> --titolo "Titolo" [--progetto <nome>]`\n  → scrive in `inbox/`; non scrivere mai altrove nella KB.\n\nNon mettere mai credenziali o segreti nella KB.\n'),
]:
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, 'w').write(t)
EOF
```
  Verifica: `test -f profili/programmatore/skills/kb/SKILL.md && python3 -c "import json; json.load(open('profili/programmatore/models.json')); json.load(open('profili/programmatore/settings.json'))"`

- [x] 9. Controllo finale
  File: nessuno (correggi solo ciò che i comandi segnalano)
  Cosa fare: esegui tutti i test.
  Verifica: `python3 -m unittest tests/test_kb.py tests/test_agente.py`

## Correzioni del collaudo 1
Difetti trovati: `bin/agente` passa a pi **solo** `PI_CODING_AGENT_DIR` (perde HOME, `KB_DIR`, `KB_DB`… che la skill
`kb` dà per impostate), ignora il codice di uscita di pi e va in traceback con `--cartella` inesistente; `kb/kb.py`
non usa argparse, ha predefiniti sbagliati (`KB_DIR` «.» invece di `/srv/kb`, `KB_DB` non in `~/.cache/kb/indice.db`),
non supporta `cerca -n N`, con un segreto in `salva` va in traceback, inventa la variabile `KB_ODO`, `cerca` non usa
`snippet()` (estratto sbagliato con più parole) e nasconde gli errori, il titolo prende anche le righe `## …`.

- [x] 10. Test del collaudo 1
  File: `tests/test_collaudo1.py` (nuovo)
  Cosa fare: crea `tests/test_collaudo1.py` con **esattamente** questo contenuto, senza cambiare nulla:
```
"""Test del collaudo 1: ambiente e codice di uscita di bin/agente, riga di comando e ricerca di kb/kb.py."""
import importlib.machinery
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

QUI = os.path.dirname(os.path.abspath(__file__))
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(QUI, '..', 'kb'))
import kb  # noqa: E402

AGENTE = os.path.join(QUI, '..', 'bin', 'agente')
KBPY = os.path.join(QUI, '..', 'kb', 'kb.py')


class AgenteMainTest(unittest.TestCase):
    def setUp(self):
        self.radice = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.radice, 'profili', 'prova'))
        self.finto = os.path.join(self.radice, 'pi-finto')
        with open(self.finto, 'w') as f:
            f.write('#!/bin/sh\necho "$PI_CODING_AGENT_DIR|$HOME|$KB_DIR"\nexit 3\n')
        os.chmod(self.finto, 0o755)

    def tearDown(self):
        shutil.rmtree(self.radice, ignore_errors=True)

    def esegui(self, *argomenti):
        env = dict(os.environ, AGENTE_PI=self.finto, AGENTE_RADICE=self.radice, HOME='/casa/prova', KB_DIR='/kb/prova')
        return subprocess.run([sys.executable, AGENTE] + list(argomenti), env=env, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, universal_newlines=True)

    def test_conserva_ambiente_e_codice_di_uscita(self):
        r = self.esegui('prova', '--cartella', '/tmp', 'compito')
        self.assertEqual(r.stdout.strip(), os.path.join(self.radice, 'profili', 'prova') + '|/casa/prova|/kb/prova')
        self.assertEqual(r.returncode, 3)

    def test_cartella_inesistente(self):
        r = self.esegui('prova', '--cartella', os.path.join(self.radice, 'manca'), 'compito')
        self.assertEqual(r.returncode, 1)
        self.assertNotIn('Traceback', r.stderr)


class KbCollaudoTest(unittest.TestCase):
    def setUp(self):
        self.kb = tempfile.mkdtemp()
        self.casa = tempfile.mkdtemp()
        lungo = 'parola ' * 60
        for nome, testo in (('a.md', '# A\n\n' + lungo + 'verifica uno\n'), ('b.md', '# B\n\nverifica due\n'),
                            ('c.md', '## Sezione\n\nverifica tre\n'),
                            ('d.md', '# D\n\n' + lungo + 'alfa ' + lungo + 'omega\n')):
            with open(os.path.join(self.kb, nome), 'w') as f:
                f.write(testo)

    def tearDown(self):
        shutil.rmtree(self.kb, ignore_errors=True)
        shutil.rmtree(self.casa, ignore_errors=True)

    def esegui(self, *argomenti, **k):
        env = dict(os.environ, KB_DIR=self.kb, HOME=self.casa, PYTHONDONTWRITEBYTECODE='1')
        env.pop('KB_DB', None)
        return subprocess.run([sys.executable, KBPY] + list(argomenti), env=env, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, universal_newlines=True, **k)

    def test_db_predefinito_in_cache(self):
        self.assertEqual(self.esegui('indicizza').returncode, 0)
        self.assertTrue(os.path.isfile(os.path.join(self.casa, '.cache', 'kb', 'indice.db')))

    def test_kb_dir_predefinita(self):
        with open(KBPY) as f:
            self.assertIn("'/srv/kb'", f.read())

    def test_cerca_con_n(self):
        self.esegui('indicizza')
        for argomenti in (('cerca', 'verifica', '-n', '1'), ('cerca', '-n', '1', 'verifica')):
            r = self.esegui(*argomenti)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(len(re.findall(r'(?m)^\S+\.md: ', r.stdout)), 1, r.stdout)

    def test_salva_segreto_messaggio_e_uscita_1(self):
        r = self.esegui('salva', '--agente', 'x', '--titolo', 'T', input='password: abc\n')
        self.assertEqual(r.returncode, 1)
        self.assertIn('segreto', r.stderr)
        self.assertNotIn('Traceback', r.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.kb, 'inbox')))

    def test_salva_senza_titolo_errore(self):
        r = self.esegui('salva', '--agente', 'x', input='corpo\n')
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse(os.path.exists(os.path.join(self.kb, 'inbox')))

    def test_titolo_solo_da_riga_h1(self):
        db = os.path.join(self.casa, 'i.db')
        kb.indicizza(self.kb, db)
        self.assertEqual(kb.cerca(db, 'tre')[0]['titolo'], 'c')

    def test_estratto_con_snippet(self):
        db = os.path.join(self.casa, 'i.db')
        kb.indicizza(self.kb, db)
        r = kb.cerca(db, 'alfa omega')
        self.assertEqual([x['path'] for x in r], ['d.md'])
        self.assertIn('alfa', r[0]['estratto'])
        self.assertLess(len(r[0]['estratto']), 200)


if __name__ == '__main__':
    unittest.main()
```
  Verifica: `python3 -c "import ast; ast.parse(open('tests/test_collaudo1.py').read())"`

- [x] 11. KB: titolo solo dalla riga `# …`
  File: `kb/kb.py`
  Cosa fare: **non modificare il file a mano.** Esegui soltanto, dalla radice del progetto, questo comando, che
  sostituisce in `indicizza` il blocco del titolo (le altre righe del file restano come sono):
```
python3 - <<'EOF'
p = 'kb/kb.py'
s = open(p).read()
a = s.index("            # Estrai titolo dalla prima riga # ...\n")
b = s.index("            # Inserisci nella tabella FTS5\n")
s = s[:a] + '''            # Titolo: prima riga «# …», altrimenti il nome del file senza .md
            titolo = os.path.splitext(os.path.basename(rel_path))[0]
            for riga in testo.split('\\n'):
                if riga.startswith('# '):
                    titolo = riga[2:].strip()
                    break

''' + s[b:]
open(p, 'w').write(s)
EOF
```
  Verifica: `python3 -m unittest tests/test_collaudo1.py -k test_titolo_solo_da_riga_h1 && python3 -m unittest tests/test_kb.py -k IndiceTest`

- [ ] 12. KB: `cerca` con `snippet()` di FTS5
  File: `kb/kb.py`
  Cosa fare: **non modificare il file a mano.** Esegui soltanto, dalla radice del progetto, questo comando, che
  sostituisce la sola funzione `cerca` (da `def cerca` a `def main`; il resto del file resta com'è). Le righe
  tolte (circa 55) sono previste: è la vecchia `cerca` che va eliminata.
```
python3 - <<'EOF'
p = 'kb/kb.py'
s = open(p).read()
a = s.index('def cerca(db, query, n=5):')
b = s.index('def main(')
s = s[:a] + '''def cerca(db, query, n=5):
    """Cerca nell'indice FTS5: lista di dict path, titolo, estratto (snippet di FTS5) in ordine di rank."""
    conn = sqlite3.connect(db)
    try:
        righe = conn.execute(
            "SELECT path, titolo, snippet(note, 2, '', '', '…', 16) FROM note WHERE note MATCH ? ORDER BY rank LIMIT ?",
            (query, n)).fetchall()
    finally:
        conn.close()
    return [{'path': p, 'titolo': t, 'estratto': e} for p, t, e in righe]


''' + s[b:]
open(p, 'w').write(s)
EOF
```
  Verifica: `grep -q 'snippet(note' kb/kb.py && python3 -m unittest tests/test_collaudo1.py -k test_estratto_con_snippet && python3 -m unittest tests/test_kb.py -k IndiceTest`

- [ ] 13. KB: riga di comando con argparse
  File: `kb/kb.py`
  Cosa fare: **non modificare il file a mano.** Esegui soltanto, dalla radice del progetto, questo comando, che
  sostituisce la sola funzione `main` (da `def main` a `if __name__ == '__main__':`; il resto del file resta com'è).
  Le righe tolte (circa 80) sono previste: è la vecchia `main` senza argparse che va eliminata.
```
python3 - <<'EOF'
p = 'kb/kb.py'
s = open(p).read()
a = s.index('def main(')
b = s.index("if __name__ == '__main__':")
s = s[:a] + '''def main(argv=None):
    """Riga di comando: indicizza, cerca, leggi, salva (testo da stdin)."""
    import argparse
    ap = argparse.ArgumentParser(prog='kb', description='Knowledge base in Markdown')
    sub = ap.add_subparsers(dest='comando', required=True)
    sub.add_parser('indicizza', help="ricostruisce l'indice")
    c = sub.add_parser('cerca', help='cerca nelle note')
    c.add_argument('query')
    c.add_argument('-n', type=int, default=5)
    l = sub.add_parser('leggi', help='stampa una nota')
    l.add_argument('nota')
    s = sub.add_parser('salva', help='salva in inbox/ il testo letto da stdin')
    s.add_argument('--agente', required=True)
    s.add_argument('--titolo', required=True)
    s.add_argument('--progetto')
    a = ap.parse_args(argv)
    kb_dir = os.environ.get('KB_DIR', '/srv/kb')
    db = os.environ.get('KB_DB', os.path.expanduser('~/.cache/kb/indice.db'))
    try:
        if a.comando == 'indicizza':
            print('note indicizzate: %d' % indicizza(kb_dir, db))
        elif a.comando == 'cerca':
            for r in cerca(db, a.query, a.n):
                print('%s: %s' % (r['path'], r['titolo']))
                print('  ' + ' '.join(r['estratto'].split()))
        elif a.comando == 'leggi':
            sys.stdout.write(leggi(kb_dir, a.nota))
        else:
            print(salva(kb_dir, a.agente, a.titolo, sys.stdin.read(), progetto=a.progetto))
    except (ValueError, sqlite3.OperationalError) as e:
        print('kb: %s' % e, file=sys.stderr)
        return 1
    return 0


''' + s[b:]
open(p, 'w').write(s)
EOF
```
  Verifica: `grep -q 'import argparse' kb/kb.py && ! grep -q KB_ODO kb/kb.py && python3 -m unittest tests/test_kb.py && python3 -m unittest tests/test_collaudo1.py -k KbCollaudoTest`

- [ ] 14. `agente`: ambiente completo, codice di uscita, cartella inesistente
  File: `bin/agente`
  Cosa fare: **non modificare il file a mano.** Esegui soltanto, dalla radice del progetto, questo comando:
```
python3 - <<'EOF'
p = 'bin/agente'
s = open(p).read()
vecchio = '''    # Esegui il comando
    subprocess.run(argv, env=env, cwd=cwd)
'''
assert vecchio in s
s = s.replace(vecchio, '''    if not os.path.isdir(cwd):
        print(f'errore: cartella inesistente: {cwd}', file=sys.stderr)
        sys.exit(1)

    # Esegui pi con l'ambiente corrente più PI_CODING_AGENT_DIR e ne restituisce il codice di uscita
    sys.exit(subprocess.run(argv, env=dict(os.environ, **env), cwd=cwd).returncode)
''')
s = s.replace('import shutil\n', '', 1)
open(p, 'w').write(s)
EOF
```
  Verifica: `test -x bin/agente && python3 -m unittest tests/test_agente.py tests/test_collaudo1.py`

- [ ] 15. Controllo finale del collaudo 1
  File: nessuno (correggi solo ciò che i comandi segnalano)
  Cosa fare: esegui tutti i test.
  Verifica: `python3 -m unittest tests/test_kb.py tests/test_agente.py tests/test_collaudo1.py && ! grep -q KB_ODO kb/kb.py`
