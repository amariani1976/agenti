---
stato: completato
ramo: ai/agente-ciclo
modello: esecutore
verifica_globale: timeout 300 python3 -m unittest tests/test_agente.py tests/test_coda.py tests/test_misura.py tests/test_ciclo.py tests/test_esecuzione.py tests/test_ruoli.py tests/test_orchestratore.py
accettazione: cd piani && timeout 200 python3 -m unittest test_agente_catena
collaudi: 2
collaudo: superato
---
# Piano: il comando agente con la catena vera

## Contesto
La prova vera ha mostrato che `_esegui_con_verifica` in `bin/agente` non funziona: lancia `pi` direttamente come l'utente che chiama (fuori dalla rete chiusa), poi usa un nome non definito (`Esecuzione`); filtra il comando di verifica rifiutando virgolette e `>`; controlla i file rispetto alla radice degli agenti invece che alla cartella di lavoro; da un collegamento simbolico non trova i suoi moduli. Il test `piani/test_agente_catena.py` è già pronto, non si modifica, e prova la catena con un `esegui-passo` finto. Python 3.6, sola libreria standard. Ogni comando con `timeout`.

## Passi
- [x] 1. Collegamento vero tra comando, ciclo ed esecuzione
  File: `bin/agente`
  Cosa fare: riscrivi solo `_esegui_con_verifica` e il calcolo della cartella dei moduli. La cartella dei moduli si ricava da `os.path.realpath(__file__)`, in tutto il file. In `_esegui_con_verifica`: niente chiamata diretta a `pi` e niente filtro dei caratteri della verifica (la verifica gira come `esecutore` dentro `esegui-passo`); crea `Esecuzione` come fa `_orchestratore` (stesse variabili `AGENTE_ESEGUI` e `AGENTE_PROGETTI`, modello `esecutore-pensiero`); se `e.progetto(cartella)` solleva `ValueError`, errore con uscita 2; i file devono essere relativi, senza `..`, dentro la cartella di lavoro, altrimenti uscita 2; tentativi da 1 a 5, altrimenti uscita 2; poi `ciclo.esegui(compito, cartella, verifica, file, tentativi, lancia=e.lancia, verifica_fn=e.verifica, lezioni=e.lezioni)`. Lascia com'è il resto del file, compreso il percorso senza `--verifica` e l'orchestratore. Non scrivere test.
  Verifica: `cd piani && timeout 200 python3 -m unittest test_agente_catena && cd .. && timeout 200 python3 -m unittest tests/test_agente.py`
- [x] 2. Il test al suo posto
  File: `tests/test_agente_catena.py`
  Esegui:
  ```bash
mv piani/test_agente_catena.py tests/
  ```
  Verifica: `test -f tests/test_agente_catena.py && timeout 200 python3 -m unittest tests/test_agente_catena.py`

## Correzioni del collaudo
- [x] 3. realpath in tutto bin/agente
  File: `tests/test_agente_collegamento.py`, `bin/agente`
  Cosa fare: il passo 1 chiedeva `os.path.realpath(__file__)` in tutto il file, ma restano due `os.path.abspath(__file__)`: in `DEFAULT_RADICE` (riga 14) e in `_orchestratore` (calcolo di `ciclo_path`). Da un collegamento simbolico il percorso semplice non trova i profili («profilo non esistente») e l'orchestratore non trova i moduli (`ModuleNotFoundError: ruoli`). Prima crea il test qui sotto così com'è, poi in `bin/agente` sostituisci in quelle due righe `os.path.abspath(__file__)` con `os.path.realpath(__file__)`. Non cambiare altro.
  Esegui:
  ```bash
cat > tests/test_agente_collegamento.py <<'FINE'
"""bin/agente lanciato da un collegamento simbolico trova profili e moduli in ogni percorso (realpath in tutto il file)."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

AGENTE = os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'bin', 'agente'))


class Collegamento(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix='collegamento-')
        self.link = os.path.join(self.d, 'agente')
        os.symlink(AGENTE, self.link)
        self.pi = os.path.join(self.d, 'pi-finto')
        with open(self.pi, 'w') as f:
            f.write('#!/bin/sh\necho PI-FINTO "$@"\n')
        os.chmod(self.pi, 0o755)
        self.env = {k: v for k, v in os.environ.items() if k not in ('AGENTE_RADICE', 'AGENTE_ESEGUI', 'AGENTE_PROGETTI')}
        self.env['AGENTE_PI'] = self.pi

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def lancia(self, *argomenti):
        return subprocess.run([sys.executable, self.link] + list(argomenti), env=self.env, cwd=self.d,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=60)

    def test_percorso_semplice_trova_il_profilo(self):
        r = self.lancia('programmatore', '--cartella', self.d, 'ciao')
        self.assertEqual(r.returncode, 0, r.stderr[-500:])
        self.assertIn('PI-FINTO', r.stdout)

    def test_orchestratore_trova_i_moduli(self):
        self.env['AGENTE_PROGETTI'] = self.d
        r = self.lancia('orchestratore', '--cartella', '/', 'fai qualcosa')
        self.assertNotIn('ModuleNotFoundError', r.stderr)
        self.assertNotIn('Traceback', r.stderr)
        self.assertEqual(r.returncode, 2, r.stderr[-500:])


if __name__ == '__main__':
    unittest.main()
FINE
  ```
  Verifica: `! grep -n "abspath(__file__)" bin/agente && timeout 200 python3 -m unittest tests/test_agente_collegamento.py tests/test_agente_catena.py tests/test_agente.py tests/test_agente_orchestratore.py`
